"""Product contracts: preserve access and compare the same facts across roles."""
import ast
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select
from streamlit.testing.v1 import AppTest
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import DoctorReview, HealthProblem, Observation, Patient, ServiceRequest, AgentGoal, AgentApprovalRequest
from executive_health_ai.services.product_projection import ProductProjectionService, current_program, pending_doctor_work
from executive_health_ai.services.longitudinal import HealthAssessmentService
from executive_health_ai.ui.display import get_status_display
from executive_health_ai.ui.localization.zh_cn import status
from executive_health_ai.ui.status_dictionary import status_label
from tests.test_baseline_visualization import _session, _baseline

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'streamlit_app.py'


def radio(app, label, value):
    next(r for r in app.radio if r.label == label).set_value(value)
    app.run(timeout=45)
    assert not app.exception


def click(app, label):
    next(b for b in app.button if b.label == label).click()
    app.run(timeout=45)
    assert not app.exception


def visible(app):
    return '\n'.join(str(e.value) for group in [app.markdown, app.caption, app.subheader, app.info] for e in group)


def test_all_frozen_elements_and_renderer_contracts_are_preserved():
    inventory = json.loads((ROOT/'docs/product_logic_elements.json').read_text(encoding='utf8'))
    assert len(inventory['elements']) == 102
    assert len({e['id'] for e in inventory['elements']}) == 102
    for e in inventory['elements']:
        assert e['new'] and e['logic'] in {'健康状态','健康运营','长期记录','支撑能力'}
        assert e['action'] in {'KEEP','MOVE','MERGE','GROUP','COLLAPSE','SECONDARY','ADVANCED','LEGACY ACCESS'}
    for path in {f['path'] for f in inventory['functions']}:
        current = {n.name for n in ast.walk(ast.parse((ROOT/path).read_text(encoding='utf8'))) if isinstance(n,ast.FunctionDef)}
        assert {f['function'] for f in inventory['functions'] if f['path']==path} <= current


def test_same_current_plan_even_when_newer_history_and_planned_records_exist():
    now=datetime.now(timezone.utc)
    plans=[SimpleNamespace(id=uuid4(),status=s,created_at=now+timedelta(days=i)) for i,s in enumerate(['ACTIVE','PAUSED','PLANNED','COMPLETED'])]
    assert current_program(plans) is plans[0]
    assert current_program(list(reversed(plans))) is plans[0]
    assert current_program(plans[1:]) is plans[1]
    assert current_program([plans[-1]]) is None


def test_baseline_and_current_are_shared_without_rewriting_frozen_snapshot():
    with _session() as session:
        patient, baseline, _ = _baseline(session)
        frozen=deepcopy(baseline.baseline_json)
        session.add(Observation(patient_id=patient.id,metric_code='weight',value_numeric=85.8,unit='kg',source='manual',quality_flag='valid',observed_at=datetime(2026,9,1,tzinfo=timezone.utc)))
        session.flush()
        views=[ProductProjectionService().member(session,patient.id,health=True) for _ in ['member','manager','doctor']]
        for view in views:
            change=next(c for c in view.health.baseline.comparisons if c.code=='weight')
            assert float(change.baseline)==90 and float(change.current)==85.8
            assert next(s for s in view.health.series if s.code=='weight').points[-1].value==change.delta+90
        assert baseline.baseline_json==frozen
        assert not session.new and not session.dirty and not session.deleted


def test_doctor_pending_count_matches_member_360_today_and_doctor_with_baseline():
    with _session() as session:
        patient, _, _ = _baseline(session)
        problem=HealthProblem(patient_id=patient.id,title='人工核实',description='依据',severity='MEDIUM',source='test')
        session.add(problem);session.flush()
        review=DoctorReview(patient_id=patient.id,health_problem_id=problem.id,doctor_name='待分配医生',department='全科',status='PENDING',opinion='',doctor_brief='已确认资料待医学核实',question_for_doctor='核实血压')
        session.add(review)
        draft=HealthAssessmentService().create_manual_draft(session,patient.id,created_by='健管',summary='年度医学确认',cycle_year=2027,medical_review_required=True)
        HealthAssessmentService().request_medical_review(session,draft.id,requested_by='健管')
        session.flush()
        service=ProductProjectionService()
        member=service.member(session,patient.id)
        today=service.manager(session,datetime.now(timezone.utc))
        assert len(member.pending_doctor)==len(today.pending_doctor)==len(pending_doctor_work(session,patient.id))==2
        assert {i.source_type for i in today.items} >= {'doctor_review','baseline_review'}
        review.status='CONFIRMED';session.flush()
        assert len(service.member(session,patient.id).pending_doctor)==len(service.manager(session,datetime.now(timezone.utc)).pending_doctor)==1


def test_service_status_and_owner_match_the_unified_work_item():
    with _session() as session:
        from executive_health_ai.models import ServiceCatalogItem
        patient, _, _ = _baseline(session)
        catalog=ServiceCatalogItem(code='consistency-test',category='复查',name='人工复查')
        session.add(catalog);session.flush()
        request=ServiceRequest(patient_id=patient.id,service_item_id=catalog.id,requested_by='一致性测试',status='IN_PROGRESS',assigned_manager='同一服务负责人')
        session.add(request);session.flush()
        view=ProductProjectionService().member(session,request.patient_id)
        work=ProductProjectionService().manager(session,datetime.now(timezone.utc))
        item=next(i for i in work.items if i.source_type=='service_request' and i.source_id==request.id)
        row=next(r for r in view.services if r.id==request.id)
        assert status_label(item.status,context='service_request')==get_status_display(row.status,context='service_request')
        assert item.owner==(row.assigned_manager or '待分配')


def test_pending_automation_approval_enters_existing_management_route_once():
    with _session() as session:
        patient,_,_=_baseline(session)
        goal=AgentGoal(member_id=patient.id,goal_type='POST_EXAM',title='现有人工确认',source_type='test',source_id=str(uuid4()),owner='负责人')
        session.add(goal);session.flush()
        approval=AgentApprovalRequest(goal_id=goal.id,plan_step_id=uuid4(),approval_type='HUMAN',required_role='HEALTH_MANAGER',status='PENDING')
        session.add(approval);session.flush()
        rows=ProductProjectionService().manager(session,datetime.now(timezone.utc)).items
        entries=[i for i in rows if i.source_type=='automation_approval' and i.source_id==approval.id]
        assert len(entries)==1 and entries[0].route_target=='member_management'
        approval.status='APPROVED';session.flush()
        assert not [i for i in ProductProjectionService().manager(session,datetime.now(timezone.utc)).items if i.source_id==approval.id]


@pytest.mark.parametrize('value',['OPEN','IN_PROGRESS','WAITING_MEMBER','WAITING_DOCTOR','WAITING_MANAGER_REVIEW','COMPLETED','CANCELLED','FAILED'])
def test_single_status_dictionary_for_legacy_and_current_ui(value):
    assert status(value)==get_status_display(value)==status_label(value)


def test_actual_member_and_manager_baseline_and_owner_read_the_same_context():
    member=AppTest.from_file(APP).run(timeout=45)
    radio(member,'当前视图','成员健康中心')
    with SessionLocal() as session:
        patient=session.scalar(select(Patient).order_by(Patient.created_at))
        view=ProductProjectionService().member(session,patient.id)
        owner=view.owner
    assert owner in visible(member)
    radio(member,'成员健康中心导航','计划')
    if view.program:
        assert view.program.title in visible(member) and owner in visible(member)
    radio(member,'成员健康中心导航','健康')
    manager=AppTest.from_file(APP).run(timeout=45)
    radio(manager,'工作区','成员');click(manager,'查看成员');radio(manager,'成员页面','健康')
    assert owner in visible(manager)
    for app in [member,manager]:
        assert '年度健康基线' in visible(app) and '当前健康状态' in visible(app)
        assert app.get('vega_lite_chart')


def test_support_directory_and_legacy_deep_link_still_reach_admin():
    app=AppTest.from_file(APP).run(timeout=45)
    radio(app,'工作区','更多')
    assert any(b.key=='more-open-风险规则' for b in app.button)
    next(b for b in app.button if b.key=='more-open-风险规则').click();app.run(timeout=45)
    assert not app.exception
    assert app.session_state['surface-mode']=='系统管理'
    assert app.session_state['ux-admin-navigation']=='规则与知识'
    radio(app,'当前视图','运营后台')
    radio(app,'工作区','更多')
    app.session_state['more-navigation']='操作记录';app.run(timeout=45)
    assert not app.exception and app.session_state['surface-mode']=='系统管理'
    assert app.session_state['ux-admin-navigation']=='系统状态'


def test_key_role_actions_reachable_in_at_most_three_activations():
    app=AppTest.from_file(APP).run(timeout=45)
    # Role selection is setup; count from the role's navigation.
    radio(app,'当前视图','成员健康中心')
    radio(app,'成员健康中心导航','首页')  # 1
    if any(b.label=='去完成' for b in app.button):
        click(app,'去完成')  # 2
        assert any(b.label=='确认完成' for b in app.button)  # 3 would submit
    radio(app,'当前视图','运营后台');radio(app,'工作区','今日')  # 1
    if any(b.label=='处理' for b in app.button):
        click(app,'处理')  # 2
        assert not app.exception
    radio(app,'当前视图','医生工作台')
    assert any(r.label=='复核工作' for r in app.radio)
    radio(app,'当前视图','系统管理');radio(app,'系统','集成与数据')  # 1
    next(b for b in app.button if b.key=='integration-open-ai').click();app.run(timeout=45)  # 2
    assert not app.exception and app.session_state['integration-center-mode']=='AI服务'


@pytest.mark.parametrize("channel", ["ui_command", "api"])
def test_report_confirmation_has_same_baseline_draft_and_frozen_followup(channel, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker
    from executive_health_ai.api import create_app
    from executive_health_ai.models import HealthAssessment, Document, ReportExtractionRun, ReportExtractionCandidate
    from executive_health_ai.services import care_commands
    from executive_health_ai.services.report_parsing import ReportParsingService
    events=[]
    monkeypatch.setattr(care_commands, 'publish_progress', lambda *a, **kw: events.append(kw['event_type']))
    with _session() as session:
        patient=Patient(external_id='shared-report-'+channel, timezone='Asia/Tokyo')
        session.add(patient); session.flush()
        parser=ReportParsingService(); parser.storage_root=tmp_path
        factory=sessionmaker(bind=session.bind, expire_on_commit=False)
        for number, weight in enumerate([90, 85.8]):
            report=Document(patient_id=patient.id,document_type='health_check_report',title='人工确认报告',storage_reference='synthetic://report',source='test')
            session.add(report);session.flush()
            run=ReportExtractionRun(document_id=report.id,patient_id=patient.id,status='COMPLETED',parser_version='test',canonical_registry_version='test',file_hash=str(report.id),file_type='TXT')
            session.add(run);session.flush()
            candidate=ReportExtractionCandidate(document_id=report.id,patient_id=patient.id,extraction_run_id=run.id,candidate_type='OBSERVATION',canonical_code='weight',normalized_value=str(weight),unit='kg',confidence='HIGH',extraction_method='RULE',evidence_text=f'Weight {weight} kg',status='PENDING_REVIEW')
            session.add(candidate);session.flush()
            session.commit()
            if channel=='api':
                response=TestClient(create_app(factory)).post(f'/report-candidates/{candidate.id}/confirm', json={'actor':'健管'})
                assert response.status_code==200, response.text
                session.expire_all()
            else:
                care_commands.confirm_report_candidate(session,candidate,'健管');session.commit()
            assert session.get(type(candidate),candidate.id).status=='CONFIRMED'
            rows=list(session.scalars(select(HealthAssessment).where(HealthAssessment.patient_id==patient.id)))
            assert len(rows)==1
            if number==0:
                assert rows[0].status=='DRAFT'
                HealthAssessmentService().confirm(session,rows[0].id,'健管');session.commit()
                frozen=deepcopy(rows[0].baseline_json)
            else:
                assert rows[0].status=='CONFIRMED' and rows[0].baseline_json==frozen
        assert events==['REPORT_CONFIRMED','REPORT_CONFIRMED']


def test_doctor_can_find_approval_even_without_pending_medical_reviews(monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from executive_health_ai.models import AgentPlan, AgentPlanStep
    from executive_health_ai.ui.pages.doctor import experience as doctor_page
    from executive_health_ai.ui.pages.manager import experience as manager_page
    with _session() as session:
        patient=Patient(external_id='approval-only',display_name='确认成员',timezone='Asia/Tokyo')
        session.add(patient);session.flush()
        goal=AgentGoal(member_id=patient.id,goal_type='POST_EXAM',title='后续安排',source_type='test',source_id=str(uuid4()))
        session.add(goal);session.flush()
        plan=AgentPlan(goal_id=goal.id);session.add(plan);session.flush()
        step=AgentPlanStep(plan_id=plan.id,step_order=1,step_type='APPROVAL',requires_approval=True,approval_role='DOCTOR')
        session.add(step);session.flush()
        approval=AgentApprovalRequest(goal_id=goal.id,plan_step_id=step.id,approval_type='HUMAN',required_role='DOCTOR')
        session.add(approval);session.commit()
        factory=sessionmaker(bind=session.bind,expire_on_commit=False)
        monkeypatch.setattr(doctor_page,'SessionLocal',factory)
        monkeypatch.setattr(manager_page,'SessionLocal',factory)
        def render():
            from sqlalchemy import select
            from executive_health_ai.models import Patient
            from executive_health_ai.ui.pages.doctor import experience as page
            with page.SessionLocal() as session:
                members=list(session.scalars(select(Patient)))
            page.workspace(None,members)
        app=AppTest.from_function(render).run(timeout=30)
        assert not app.exception
        assert any(b.key==f'approval-submit-{approval.id}' for b in app.button)
        assert any('当前没有待复核事项' in str(c.value) for c in app.caption)
