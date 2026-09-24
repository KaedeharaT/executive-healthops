from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from executive_health_ai.models import (Base, AgentGoal, AgentEvent, AgentApprovalRequest, DoctorReview,
    Task, FollowUp, RiskEvent, HealthAssessment, Patient)
from executive_health_ai.models.management_workflow import RecheckPlan, ManagementLog
from executive_health_ai.services.management_workflow import ManagementWorkflowService
from executive_health_ai.services.report_parsing import ReportParsingService
from executive_health_ai.services.post_checkup import PostCheckupCareService
from executive_health_ai.services.event_service import EventService
from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
from executive_health_ai.agent import post_checkup as flow


@pytest.fixture
def care(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCAL_LLM_ENABLED', 'false')
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as s:
        program = ManagementWorkflowService().enroll(s, name='Synthetic V1 Member', start=date.today(),
            end=date.today()+timedelta(days=364), owner='王健管', goal='年度连续健康管理')
        parser = ReportParsingService(); parser.storage_root = tmp_path
        report, _, _ = parser.upload_and_parse(s, program.patient_id, 'synthetic-checkup.txt',
            ('体检日期：'+date.today().isoformat()+'\n低密度脂蛋白胆固醇  4.15 mmol/L\n谷丙转氨酶  56 U/L\n体重  85.8 kg').encode(), '王健管')
        goal = s.scalar(select(AgentGoal).where(AgentGoal.source_id == str(report.id)))
        s.commit()
        yield s, goal, HealthOpsAgentSupervisor()
    engine.dispose()


def send_doctor(s, g, sup):
    flow.manager_review(sup, s, g, actor='王健管', role='HEALTH_MANAGER', doctor='演示医生', question='肝功能变化是否需要进一步医学处理？')


def judge(s, g):
    return PostCheckupCareService().submit_review(s, g, actor='演示医生', role='DOCTOR',
        judgement='结合资料继续观察，建议按期复核。', recommendation='了解饮酒情况并随访执行情况',
        recheck=True, recheck_title='肝功能复查', suggested_date=date.today()+timedelta(days=90),
        followup_date=date.today()+timedelta(days=30))


def test_ingestion_creates_one_goal_with_member_context(care):
    s, g, sup = care
    assert g.status == 'WAITING_MANAGER' and g.current_stage == 'WAITING_MANAGER_REVIEW'
    assert g.title == '完成本次体检报告的后续健康管理准备'
    assert len(g.context_json['findings']) == 3
    assert {'member', 'report', 'baseline', 'history_reports', 'management'} <= g.context_json.keys()
    event = s.scalar(select(AgentEvent).where(AgentEvent.event_type == 'REPORT_UPLOADED'))
    assert {'member_id', 'report_id', 'annual_cycle_id', 'triggered_at'} <= event.metadata_json.keys()
    for _ in range(3):
        assert sup.receive_event(s, event).id == g.id
    assert s.query(AgentGoal).count() == 1


def test_doctor_wait_resumes_same_goal_and_creates_nothing_before_confirmation(care):
    s, g, sup = care
    send_doctor(s, g, sup)
    assert g.status == 'WAITING_DOCTOR'
    assert s.query(DoctorReview).count() == 1
    assert not s.query(Task).count()
    identity = g.id
    judge(s, g)
    assert g.id == identity and g.status == 'WAITING_MANAGER'
    assert g.current_stage == 'WAITING_ACTION_APPROVAL'
    assert len(g.context_json['actions']) == 3 and s.query(AgentGoal).count() == 1
    assert not s.query(RecheckPlan).count() and not s.query(Task).count()


def test_confirm_creates_business_records_and_completes_without_waiting_months(care):
    s, g, sup = care
    send_doctor(s, g, sup); judge(s, g)
    flow.approve_actions(sup, s, g, actions=g.context_json['actions'], actor='王健管', role='HEALTH_MANAGER')
    assert g.status == 'COMPLETED' and g.next_check_at is None
    assert s.query(Task).count() == 3
    assert s.query(RecheckPlan).count() == 1 and s.query(FollowUp).count() == 1
    assert s.query(ManagementLog).count() == 1
    assert all(t.assignee and t.due_at for t in s.scalars(select(Task)))
    assert all(g.success_criteria.values())
    assert not s.query(AgentApprovalRequest).filter_by(status='PENDING').count()
    assert not s.query(RiskEvent).count()
    assert not s.query(HealthAssessment).count()


def test_duplicate_resume_confirmation_and_doctor_submit_do_not_duplicate(care):
    s, g, sup = care
    send_doctor(s, g, sup); review = judge(s, g)
    actions = g.context_json['actions']
    flow.approve_actions(sup, s, g, actions=actions, actor='王健管', role='HEALTH_MANAGER')
    event, _ = EventService().publish(s, event_type='DOCTOR_REVIEW_COMPLETED', member_id=g.member_id,
                                     source_type='doctor_review', source_id=str(review.id))
    for _ in range(3):
        sup.receive_event(s, event); judge(s, g)
        flow.approve_actions(sup, s, g, actions=actions, actor='王健管', role='HEALTH_MANAGER')
    assert s.query(Task).count() == 3 and s.query(RecheckPlan).count() == 1
    assert s.query(ManagementLog).count() == 1 and s.query(DoctorReview).count() == 1


def test_normal_path_skips_doctor_and_has_two_human_gates(care):
    s, g, sup = care
    flow.manager_review(sup, s, g, actor='王健管', role='HEALTH_MANAGER')
    assert g.current_stage == 'WAITING_ACTION_APPROVAL' and not s.query(DoctorReview).count()
    assert s.query(AgentApprovalRequest).filter_by(status='PENDING').count() == 1
    flow.approve_actions(sup, s, g, actions=g.context_json['actions'], actor='王健管', role='HEALTH_MANAGER')
    assert g.status == 'COMPLETED'


@pytest.mark.parametrize('role', ['MEMBER', 'DOCTOR', 'ADMIN'])
def test_manager_gate_permission_boundary(care, role):
    s, g, sup = care
    with pytest.raises(PermissionError):
        flow.manager_review(sup, s, g, actor='other', role=role)
    assert g.current_stage == 'WAITING_MANAGER_REVIEW'


def test_doctor_permission_and_assignment(care):
    s, g, sup = care
    send_doctor(s, g, sup)
    for role, actor in [('HEALTH_MANAGER', '王健管'), ('DOCTOR', '其他医生')]:
        with pytest.raises(PermissionError):
            PostCheckupCareService().submit_review(s, g, actor=actor, role=role, judgement='判断', recommendation='建议',
                                                   recheck=False, suggested_date=date.today())
    assert g.status == 'WAITING_DOCTOR'


def test_complete_and_generic_approval_cannot_bypass_gates(care):
    s, g, sup = care
    with pytest.raises(ValueError):
        sup.complete_goal(s, g.id)
    approval = s.scalar(select(AgentApprovalRequest).where(AgentApprovalRequest.goal_id == g.id))
    with pytest.raises(ValueError):
        sup.decide_approval(s, approval.id, decision='APPROVED', actor='admin', actor_role='ADMIN')
    assert g.status == 'WAITING_MANAGER'


def test_invalid_action_rolls_back_all_records_and_state(care):
    s, g, sup = care
    flow.manager_review(sup, s, g, actor='王健管', role='HEALTH_MANAGER')
    actions = [dict(a) for a in g.context_json['actions']]
    actions[-1]['owner'] = ''
    with pytest.raises(ValueError):
        flow.approve_actions(sup, s, g, actions=actions, actor='王健管', role='HEALTH_MANAGER')
    assert g.current_stage == 'WAITING_ACTION_APPROVAL' and not s.query(Task).count()


def test_llm_and_knowledge_unavailable_keep_manual_path(care):
    s, g, sup = care
    assert g.context_json['llm_status'] == 'UNAVAILABLE'
    assert g.context_json['knowledge'] == []
    flow.manager_review(sup, s, g, actor='王健管', role='HEALTH_MANAGER', summary='人工核对报告与资料')
    assert g.current_stage == 'WAITING_ACTION_APPROVAL'


def test_unparseable_report_escalates_without_guesses(care, tmp_path):
    s, g, sup = care
    parser = ReportParsingService(); parser.storage_root = tmp_path
    document, _, _ = parser.upload_and_parse(s, g.member_id, 'unreadable.txt', b'no extractable health evidence', 'manager')
    failed = s.scalar(select(AgentGoal).where(AgentGoal.source_id == str(document.id)))
    assert failed.status == 'ESCALATED' and '人工查看' in failed.next_action


def test_wrong_member_entry_and_unrelated_doctor_event_cannot_resume(care):
    s, g, sup = care
    p = Patient(display_name='Other synthetic', timezone='UTC'); s.add(p); s.flush()
    event, _ = EventService().publish(s, event_type='REPORT_UPLOADED', member_id=p.id, source_type='document', source_id=g.source_id,
        metadata={'workflow': flow.VERSION}, dedup_key=str(uuid4()))
    with pytest.raises(ValueError):
        sup.receive_event(s, event)
    send_doctor(s, g, sup)
    unrelated, _ = EventService().publish(s, event_type='DOCTOR_REVIEW_COMPLETED', member_id=g.member_id,
                                        source_type='doctor_review', source_id=str(uuid4()))
    sup.receive_event(s, unrelated)
    assert g.current_stage == 'WAITING_DOCTOR_REVIEW'


def test_llm_draft_is_display_only_and_cannot_decide_risk(care, monkeypatch):
    s, g, sup = care
    monkeypatch.setattr(flow.LocalLLMClient, 'generate_structured', lambda *a, **kw: {'summary': '报告列出血脂与体重变化，请健管核对。', 'risk': 'RED', 'diagnosis': 'discarded'})
    flow.analyze(sup, s, g)
    assert g.context_json['llm_status'] == 'AVAILABLE'
    assert 'risk' not in g.context_json and not s.query(RiskEvent).count()


def test_missing_doctor_stays_at_manager_gate(care):
    s, g, sup = care
    with pytest.raises(ValueError, match='责任医生'):
        flow.manager_review(sup, s, g, actor='王健管', role='HEALTH_MANAGER', doctor='', question='待判断')
    assert g.status == 'WAITING_MANAGER' and not s.query(DoctorReview).count()


def test_knowledge_tool_failure_is_audited_and_does_not_fabricate(care, monkeypatch):
    s, g, sup = care
    monkeypatch.setattr(PostCheckupCareService, 'knowledge', lambda *a: (_ for _ in ()).throw(RuntimeError('offline')))
    flow.analyze(sup, s, g)
    assert g.status == 'WAITING_MANAGER' and g.context_json['knowledge'] == []
    from executive_health_ai.models import AgentRunTrace
    assert s.query(AgentRunTrace).filter_by(goal_id=g.id, action='knowledge_unavailable').count() == 1


def test_confirmed_annual_baseline_comparison_uses_units_and_real_history(care):
    from executive_health_ai.models import Observation
    from executive_health_ai.models.base import utc_now
    s, g, sup = care
    s.add(HealthAssessment(patient_id=g.member_id, assessment_type='BASELINE', version=1, cycle_year=date.today().year,
        title='Synthetic confirmed baseline', summary='Confirmed by manager', created_by='王健管', status='CONFIRMED',
        baseline_json={'key_metrics': [{'metric': 'ldl_c', 'value': '3.42', 'unit': 'mmol/L', 'observed_at': (utc_now()-timedelta(days=100)).isoformat()}]}))
    s.add(Observation(patient_id=g.member_id, metric_code='ldl_c', value_numeric='3.70', unit='mmol/L',
                      observed_at=utc_now()-timedelta(days=30), source='synthetic', quality_flag='valid'))
    s.flush(); flow.analyze(sup, s, g)
    finding = next(f for f in g.context_json['findings'] if f['code'] == 'ldl_c')
    assert finding['baseline'] == 3.42 and finding['delta'] == .73
    assert [p['value'] for p in finding['points']] == [3.7, 4.15]
    assert next(f for f in g.context_json['findings'] if f['code'] == 'weight')['baseline'] is None


def test_manager_confirmation_writes_report_facts_only_after_gate(care):
    from executive_health_ai.models import Observation, ReportExtractionCandidate
    s, g, sup = care
    assert not s.query(Observation).count()
    flow.manager_review(sup, s, g, actor='王健管', role='HEALTH_MANAGER')
    assert s.query(Observation).count() == 3
    assert s.query(ReportExtractionCandidate).filter_by(status='CONFIRMED').count() == 3


def test_completion_verifies_actual_owners_not_just_flags(care):
    s, g, sup = care
    flow.manager_review(sup, s, g, actor='王健管', role='HEALTH_MANAGER')
    flow.approve_actions(sup, s, g, actions=g.context_json['actions'], actor='王健管', role='HEALTH_MANAGER')
    action = s.scalar(select(Task)); action.assignee = None; s.flush()
    with pytest.raises(ValueError, match='负责人'):
        sup.complete_goal(s, g.id)


def test_optional_service_uses_existing_catalogue_and_links_management_task(care):
    from executive_health_ai.models import ServiceCatalogItem, ServiceRequest
    s, g, sup = care
    catalog = ServiceCatalogItem(code='synthetic-service', name='合成预约支持', category='就医协助', status='ACTIVE')
    s.add(catalog); s.flush()
    flow.manager_review(sup, s, g, actor='王健管', role='HEALTH_MANAGER')
    actions = g.context_json['actions'] + [{'title': '安排预约支持', 'kind': 'SERVICE', 'due': date.today().isoformat(),
        'owner': '王健管', 'evidence': '健管确认服务需求', 'service_code': catalog.code}]
    flow.approve_actions(sup, s, g, actions=actions, actor='王健管', role='HEALTH_MANAGER')
    request = s.scalar(select(ServiceRequest))
    assert request.assigned_manager == '王健管' and request.management_task_id and request.program_id
    assert g.status == 'COMPLETED'
    assert next(step for step in sup.planner.steps(s, g.current_plan_id) if step.step_type == 'WAITING_DOCTOR_REVIEW').status == 'SKIPPED'


def test_same_dedup_key_cannot_be_reused_for_another_member(care):
    s, g, sup = care
    event = s.scalar(select(AgentEvent).where(AgentEvent.source_id == g.source_id))
    with pytest.raises(ValueError):
        EventService().publish(s, event_type='REPORT_UPLOADED', member_id=uuid4(), source_type='document', source_id=g.source_id, dedup_key=event.dedup_key)


def test_admin_pause_resume_preserves_the_original_human_gate(care):
    s, g, sup = care
    send_doctor(s, g, sup)
    sup.pause_goal(s, g.id, actor='admin', reason='等待核实资料')
    assert g.status == 'ESCALATED' and g.automation_paused
    sup.resume_goal(s, g.id)
    assert g.status == 'WAITING_DOCTOR' and g.current_stage == 'WAITING_DOCTOR_REVIEW'
    assert not g.automation_paused and s.query(DoctorReview).count() == 1


def test_context_includes_current_history_allergies_and_procedures_without_baseline(care):
    from executive_health_ai.models import HealthProblem, HealthEvent, MedicationPlan
    from executive_health_ai.models.management_workflow import IntakeAssessment
    from executive_health_ai.models.base import utc_now
    s, g, sup = care
    s.add(HealthProblem(patient_id=g.member_id, title='既往健康问题', description='合成既往记录', source='manual', status='OPEN'))
    s.add(HealthEvent(patient_id=g.member_id, start_at=utc_now()-timedelta(days=300), event_type='surgery', description='合成手术史', source='manual'))
    intake=s.scalar(select(IntakeAssessment).where(IntakeAssessment.patient_id==g.member_id))
    intake.responses={'过敏史':[{'名称':'合成过敏资料','过敏反应':'会员自述待医生核实'}]}
    s.add(MedicationPlan(patient_id=g.member_id, drug_name='合成既有药物', dose='1', dose_unit='片', frequency='每日', route='口服', start_date=date.today(), status='ACTIVE'))
    s.flush(); flow.analyze(sup,s,g)
    member=g.context_json['member']
    assert member['history'][0]['title']=='既往健康问题'
    assert member['allergies'][0]['名称']=='合成过敏资料'
    assert member['procedures'][0]['description']=='合成手术史'
    assert member['medications'][0]['name']=='合成既有药物'
