from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from executive_health_ai.models import Base, Patient, HealthJourney, HealthProgram, Observation, HealthAssessment, AgentGoal, HealthEvent, Task, ManagementRule
from executive_health_ai.models.management_workflow import IntakeAssessment
from executive_health_ai.models.goal_data import ManagementGoal, DailyHealthSummary, DailySummaryRevision, SummaryWorkItem, ReportCandidateRevision
from executive_health_ai.models.base import utc_now
from executive_health_ai.services import goal_metrics, management_goals as goals, daily_summary, communications


@pytest.fixture
def db():
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def member(db,ready=True):
    p=Patient(display_name='目标闭环合成会员',external_id='synthetic-goal-'+str(uuid4()),timezone='Asia/Shanghai');db.add(p);db.flush()
    journey=HealthJourney(patient_id=p.id,assessment_summary='资料已整理',main_focus='体重',owner='健管甲')
    db.add(journey);db.flush()
    today=date.today()
    program=HealthProgram(patient_id=p.id,journey_id=journey.id,program_type='ANNUAL',title='年度健康管理',
        main_goal='想3个月减5kg',owner='健管甲',cycle_year=today.year,start_date=today,end_date=today+timedelta(days=365))
    db.add(program);db.flush()
    intake=IntakeAssessment(patient_id=p.id,cycle_year=today.year,member_concern='想3个月减5kg',
        status='CONFIRMED' if ready else 'DRAFT',review_status='CONFIRMED' if ready else 'DRAFT')
    db.add(intake);db.flush()
    return p,program


def obs(db,p,code,value,day=None):
    at=datetime.combine(day or date.today(),datetime.min.time(),tzinfo=timezone.utc)+timedelta(hours=4)
    row=Observation(patient_id=p.id,metric_code=code,value_numeric=Decimal(str(value)),
        unit=goal_metrics.REGISTRY[code].default_unit,observed_at=at,source='DEVICE',source_type='DEVICE',quality_flag='valid')
    db.add(row);db.flush();return row


def baseline(db,p):
    row=HealthAssessment(patient_id=p.id,cycle_year=date.today().year,version=1,title='年度基线',summary='已核对',
        created_by='健管甲',reviewed_by='健管甲',status='CONFIRMED',confirmed_at=utc_now(),baseline_json={'weight':86,'sleep_duration':480})
    db.add(row);db.flush();return row


@pytest.mark.parametrize('kind',list(goal_metrics.GOAL_LABELS))
def test_goal_metric_mapping(kind):
    assert all(r.metric_code in goal_metrics.REGISTRY and r.source_capability for r in goal_metrics.requirements(kind))


def test_goal_metric_completeness_and_supporting_not_blocking(db):
    p,program=member(db);obs(db,p,'weight',86);obs(db,p,'bmi',28)
    data=goal_metrics.completeness(db,p.id,'WEIGHT_MANAGEMENT',now=utc_now()+timedelta(days=1))
    assert data['CORE']['available']==2
    assert 'waist_circumference' in data['SUPPORTING']['missing']
    assert all(not x['blocking'] for x in data['suggestions'])
    optional=goal_metrics.completeness(db,p.id,'SLEEP_MANAGEMENT')
    assert not any(x['metric']=='exercise_minutes' for x in optional['suggestions'])


def test_goal_progress_deterministic():
    goal=SimpleNamespace(target_value=81,baseline_value=86)
    assert goal_metrics.progress(goal,82.4)['percent']==72
    assert goal_metrics.progress(goal,82.4)['remaining']=='1.4'
    assert goal_metrics.progress(SimpleNamespace(target_value=None,baseline_value=86),82)['percent'] is None


def test_goal_and_plan_human_gates_same_goal_resumes(db):
    p,program=member(db);obs(db,p,'weight',86,date.today()-timedelta(days=1));baseline(db,p)
    goal=goals.prepare(db,program)
    agent=db.get(AgentGoal,goal.agent_goal_id)
    assert goal.target_value==81 and agent.status=='WAITING_MANAGER'
    with pytest.raises(PermissionError):goals.confirm_goal(db,goal,actor='AI',role='AGENT')
    goals.confirm_goal(db,goal,actor='健管甲',role='HEALTH_MANAGER')
    assert agent.status=='WAITING_MANAGER' and goal.plan_draft
    with pytest.raises(PermissionError):goals.confirm_plan(db,goal,actor='AI',role='AGENT')
    goals.confirm_plan(db,goal,actor='健管甲',role='HEALTH_MANAGER')
    assert agent.status=='COMPLETED' and goals.prerequisites(db,program)['formal']
    assert db.scalar(select(func.count()).select_from(AgentGoal).where(AgentGoal.goal_type=='MANAGEMENT_SETUP'))==1
    assert db.scalar(select(func.count()).select_from(Task))==1
    goals.confirm_plan(db,goal,actor='健管甲',role='HEALTH_MANAGER')
    assert db.scalar(select(func.count()).select_from(Task))==1


def test_management_prerequisite_empty_state(db):
    p,program=member(db,False)
    assert not goals.prerequisites(db,program)['formal']
    with pytest.raises(ValueError):goals.prepare(db,program)


def test_plan_requires_baseline(db):
    p,program=member(db);goal=goals.prepare(db,program)
    goals.confirm_goal(db,goal,actor='健管甲',role='HEALTH_MANAGER')
    with pytest.raises(ValueError,match='基线'):goals.confirm_plan(db,goal,actor='健管甲',role='HEALTH_MANAGER')


def test_daily_summary_deterministic_idempotent_and_versioned(db):
    p,_=member(db);day=date.today()-timedelta(days=1)
    obs(db,p,'steps',5000,day);obs(db,p,'steps',7400,day)
    obs(db,p,'systolic_bp',120,day);obs(db,p,'systolic_bp',124,day)
    summary=daily_summary.calculate(db,p.id,day)
    assert Decimal(summary.metrics['steps']['value'])==7400
    assert Decimal(summary.metrics['systolic_bp']['value'])==122
    assert daily_summary.calculate(db,p.id,day).version==1
    obs(db,p,'steps',8000,day)
    assert daily_summary.calculate(db,p.id,day).version==2
    assert db.scalar(select(func.count()).select_from(DailyHealthSummary))==1
    assert db.scalar(select(func.count()).select_from(DailySummaryRevision))==2


def test_stable_seven_days_never_wake(db):
    p,_=member(db)
    for i in range(7):
        day=date.today()-timedelta(days=7-i);obs(db,p,'sleep_duration',480,day)
        daily_summary.calculate(db,p.id,day)
    assert db.scalar(select(func.count()).select_from(HealthEvent))==0
    assert db.scalar(select(func.count()).select_from(AgentGoal))==0
    assert db.scalar(select(func.count()).select_from(Task))==0


def test_meaningful_change_relevant_lookback_and_dedup(db):
    p,program=member(db);baseline(db,p)
    from executive_health_ai.models import MedicationPlan
    for name in ('合成用药甲','无关用药乙'):
        db.add(MedicationPlan(patient_id=p.id,drug_name=name,dose='1',dose_unit='合成单位',frequency='测试',route='测试',
            start_date=date.today()-timedelta(days=30),prescriber_name='测试医生'))
    note=communications.record(db,member_id=p.id,program_id=program.id,raw_note='睡眠随访：会员提到合成用药甲。',
        actor='健管甲',role='HEALTH_MANAGER',request_key='lookback-note',occurred_at=utc_now()-timedelta(days=2))
    communications.confirm(db,note,actor='健管甲',role='HEALTH_MANAGER')
    db.add(ManagementRule(name='合成睡眠下降规则',code='test-sleep',canonical_code='sleep_duration',
        condition_type='PERCENTAGE_DECLINE',threshold_config={'value':-25,'operator':'<=','unit':'minutes'},
        window_config={'summary_minimum_days':3},review_status='APPROVED',source_reference='合成测试规则'))
    for i in range(8):
        day=date.today()-timedelta(days=8-i)
        obs(db,p,'sleep_duration',480 if i<7 else 300,day);obs(db,p,'ldl_c',3,day)
        summary=daily_summary.calculate(db,p.id,day)
    assert summary.change_status=='MEANINGFUL_CHANGE'
    assert db.scalar(select(func.count()).select_from(HealthEvent))==1
    event=db.scalar(select(HealthEvent));context=event.payload_ref['lookback']
    assert all('ldl_c' not in h['metrics'] for h in context['history_30d'])
    assert context['annual_baseline']=={'sleep_duration':480}
    assert [r['drug'] for r in context['confirmed_medication_plans']]==['合成用药甲']
    obs(db,p,'sleep_duration',310,day);daily_summary.calculate(db,p.id,day)
    assert db.scalar(select(func.count()).select_from(HealthEvent))==1


def test_no_summary_without_new_data(db):
    p,_=member(db)
    assert daily_summary.calculate(db,p.id,date.today()) is None
    assert daily_summary.run_daily_batch(db)==0


def test_lookback_reads_existing_report_baseline_contract(db):
    p,_=member(db)
    annual=baseline(db,p)
    annual.baseline_json={'key_metrics':[
        {'metric':'sleep_duration','value':480,'unit':'minutes','source_candidate_id':'sleep-evidence'},
        {'metric':'ldl_c','value':3,'unit':'mmol/L','source_candidate_id':'unrelated-evidence'}]}
    db.flush()
    context=daily_summary.lookback(db,p.id,'sleep_duration',date.today())
    assert set(context['annual_baseline'])=={'sleep_duration'}
    assert context['annual_baseline']['sleep_duration']['source_candidate_id']=='sleep-evidence'


def test_raw_device_no_llm_and_normalized_provenance(db,monkeypatch):
    from executive_health_ai.llm.local_llm_client import LocalLLMClient
    def forbidden(*args,**kwargs):raise AssertionError('Raw device ingestion must not call an LLM')
    monkeypatch.setattr(LocalLLMClient,'generate_structured',forbidden)
    from executive_health_ai.services.health_events import ingest_health_event
    from executive_health_ai.models import RawData,MemberAgent
    p,_=member(db)
    event,_=ingest_health_event(db,member_id=p.id,event_type='DEVICE_RAW_MEASUREMENT',event_category='NEW_INFORMATION',
        source_type='DEVICE',source_id='device-1',payload_ref={'measurement':{'metric':'weight','value':83600,'unit':'g','observed_at':utc_now().isoformat()}})
    row=db.scalar(select(Observation));raw=db.get(RawData,row.raw_record_id)
    assert row.value_numeric==Decimal('83.600') and raw.payload_json['value']==83600
    assert row.provenance_json['ai_parsed'] is False and event.route_action=='STORE_ONLY'
    assert db.scalar(select(func.count()).select_from(AgentGoal))==0
    assert db.scalar(select(func.count()).select_from(SummaryWorkItem))==1


def test_correction_preserves_previous_fact(db):
    from executive_health_ai.services.data_provenance import correct_observation
    p,_=member(db);row=obs(db,p,'weight',86.3)
    new=correct_observation(db,row,value='83.6',unit='kg',actor='健管甲',reason='与原文核对')
    assert row.value_numeric==Decimal('86.3') and row.excluded_from_analysis
    assert new.value_numeric==Decimal('83.6') and new.supersedes_id==row.id and new.version==2


def test_communication_raw_and_manager_not_doctor(db):
    p,program=member(db);text='今天和王医生讨论，暂不调整用药，继续家庭血压监测两周，下次复查时再判断。'
    row=communications.record(db,member_id=p.id,program_id=program.id,raw_note=text,actor='健管甲',role='HEALTH_MANAGER',request_key='note-1')
    assert row.raw_note==text and row.structured_summary['doctor_opinion'] is None
    communications.confirm(db,row,actor='健管甲',role='HEALTH_MANAGER')
    assert row.raw_note==text and len(row.related_actions)==2
    with pytest.raises(PermissionError):communications.record(db,member_id=p.id,program_id=program.id,raw_note=text,
        actor='健管甲',role='HEALTH_MANAGER',source='DOCTOR',request_key='fake-doctor')


def test_doctor_attribution_preserved(db):
    p,program=member(db)
    row=communications.record(db,member_id=p.id,program_id=program.id,raw_note='暂不调整用药',actor='王医生',
        role='DOCTOR',source='DOCTOR',request_key='doctor-note')
    assert row.structured_summary['doctor_name']=='王医生'
    assert row.structured_summary['doctor_opinion']=='暂不调整用药'


def test_ai_error_raw_candidate_and_confirmation_all_preserved(db):
    from executive_health_ai.models import Document,ReportExtractionRun,ReportExtractionCandidate,RawData
    from executive_health_ai.services.report_parsing import ReportParsingService
    p,_=member(db)
    doc=Document(patient_id=p.id,document_type='health_check_report',title='合成报告',storage_reference='synthetic://83.6',source='test')
    db.add(doc);db.flush()
    run=ReportExtractionRun(document_id=doc.id,patient_id=p.id,parser_version='synthetic',canonical_registry_version='1',file_hash='synthetic',file_type='txt')
    db.add(run);db.flush()
    candidate=ReportExtractionCandidate(extraction_run_id=run.id,document_id=doc.id,patient_id=p.id,
        candidate_type='OBSERVATION',canonical_code='weight',raw_name='体重',raw_value='83.6',
        normalized_value='86.3',unit='kg',extraction_method='LLM',evidence_text='83.6kg')
    db.add(candidate);db.flush()
    service=ReportParsingService()
    service.correct_candidate(db,candidate,'健管甲',canonical='weight',value='83.6',unit='kg',reason='核对原文')
    fact=service.confirm_candidate(db,candidate,'健管甲')
    revisions=list(db.scalars(select(ReportCandidateRevision).order_by(ReportCandidateRevision.version)))
    assert revisions[0].values_json['normalized_value']=='86.3'
    assert revisions[-1].values_json['normalized_value']=='83.6'
    assert db.get(RawData,fact.raw_record_id).payload_json['original_text']=='83.6kg'
    assert fact.value_numeric==Decimal('83.6') and fact.confirmed_by=='健管甲'
    assert fact.confirmation_status=='CONFIRMED' and fact.evidence_ref==str(doc.id)


@pytest.mark.parametrize('level,expected',[('GREEN','COMPLETED'),('YELLOW','WAITING_MANAGER'),('RED','WAITING_DOCTOR')])
def test_summary_change_runs_existing_risk_engine(db,level,expected):
    from executive_health_ai.models import RiskRule,AgentRunTrace
    from executive_health_ai.services.health_events import process_pending
    from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
    p,_=member(db)
    db.add(ManagementRule(name='合成下降',code='summary-trend',canonical_code='sleep_duration',condition_type='TREND',
        threshold_config={'value':-25,'operator':'<='},window_config={'summary_minimum_days':3},
        review_status='APPROVED',source_reference='synthetic test only'))
    db.add(RiskRule(name='合成测试规则',code='summary-risk',applicable_device_class='ANY',canonical_code='sleep_duration',
        risk_level=level,condition_type='SYNTHETIC_TEST_THRESHOLD',threshold_config={'metric':'sleep_duration','value':350,'operator':'<=','unit':'minutes'},
        window_config={},action_type='SYNTHETIC_TEST_ONLY',source_reference='synthetic test only',review_status='APPROVED',
        reviewed_by='测试审核',recommended_route='DOCTOR' if level=='RED' else 'HEALTH_MANAGER',version='test-1'))
    for i in range(4):
        day=date.today()-timedelta(days=4-i);obs(db,p,'sleep_duration',480 if i<3 else 300,day)
        daily_summary.calculate(db,p.id,day)
    process_pending(db,HealthOpsAgentSupervisor())
    event=db.scalar(select(HealthEvent))
    assert event.payload_ref['risk_evaluation']['engine']=='deterministic'
    goal=db.get(AgentGoal,event.goal_id)
    assert goal.status==expected,goal.context_json
    assert goal.context_json['event_payload']['lookback']['bounded']


def test_doctor_record_generates_monitoring_recheck_and_log(db):
    from executive_health_ai.models import DoctorReview,HealthProblem
    from executive_health_ai.models.management_workflow import RecheckPlan
    p,program=member(db)
    problem=HealthProblem(patient_id=p.id,title='合成协同',description='test',source='test');db.add(problem);db.flush()
    review=DoctorReview(patient_id=p.id,program_id=program.id,health_problem_id=problem.id,doctor_name='王医生',
        department='全科',doctor_brief='合成讨论记录',question_for_doctor='血压随访',opinion='暂不调整用药，继续家庭血压监测两周，下次复查时再判断。',status='CONFIRMED')
    db.add(review);db.flush()
    row=communications.record(db,member_id=p.id,program_id=program.id,raw_note='今天和王医生讨论，'+review.opinion,
        actor='健管甲',role='HEALTH_MANAGER',source='DOCTOR',doctor_review_id=review.id,request_key='doctor-discussion')
    communications.confirm(db,row,actor='健管甲',role='HEALTH_MANAGER')
    assert {r['kind'] for r in row.related_actions}=={'log','followup','recheck'}
    assert row.structured_summary['doctor_name']=='王医生'
    assert db.scalar(select(RecheckPlan)).doctor_review_id==review.id


def test_batch_reuses_dirty_day_and_skips_current_day(db):
    p,_=member(db);yesterday=date.today()-timedelta(days=1)
    obs(db,p,'steps',5000,yesterday);obs(db,p,'steps',5500,yesterday)
    obs(db,p,'steps',6000,date.today())
    daily_summary.run_daily_batch(db,now=datetime.combine(date.today(),datetime.min.time(),tzinfo=timezone.utc))
    assert db.scalar(select(func.count()).select_from(DailyHealthSummary))==1
    assert db.scalar(select(DailyHealthSummary)).summary_date==yesterday
    assert daily_summary.run_daily_batch(db,now=datetime.combine(date.today(),datetime.min.time(),tzinfo=timezone.utc))==0


def test_quality_and_raw_are_not_risk(db):
    p,_=member(db);day=date.today()-timedelta(days=1)
    row=obs(db,p,'sleep_duration',40,day);row.quality_flag='suspect';db.flush()
    assert daily_summary.calculate(db,p.id,day) is None
    assert db.scalar(select(func.count()).select_from(HealthEvent))==0


def test_formal_risk_rule_can_trigger_without_lifestyle_rule(db):
    from executive_health_ai.models import RiskRule
    p,_=member(db)
    db.add(RiskRule(name='合成正式风险测试',code='SYNTHETIC_SUMMARY_BP_TEST',applicable_device_class='ANY',canonical_code='systolic_bp',
        risk_level='RED',condition_type='SYNTHETIC_TEST_THRESHOLD',threshold_config={'metric':'systolic_bp','operator':'>=','value':180,'unit':'mmHg'},
        window_config={},action_type='SYNTHETIC_TEST_ONLY',source_reference='synthetic test only',review_status='APPROVED',reviewed_by='测试',recommended_route='DOCTOR'))
    day=date.today()-timedelta(days=2);obs(db,p,'systolic_bp',190,day)
    summary=daily_summary.calculate(db,p.id,day)
    assert len(summary.changes)==1 and summary.changes[0]['risk_rule']
    obs(db,p,'systolic_bp',191,day+timedelta(days=1))
    assert not daily_summary.calculate(db,p.id,day+timedelta(days=1)).changes


def test_removed_source_invalidates_current_summary_without_erasing_history(db):
    p,_=member(db);day=date.today()-timedelta(days=1);row=obs(db,p,'weight',83.6,day)
    summary=daily_summary.calculate(db,p.id,day);row.source_deleted=True;db.flush()
    assert daily_summary.calculate(db,p.id,day) is None
    assert summary.metrics=={} and summary.change_status=='INSUFFICIENT_DATA'
    assert db.scalar(select(func.count()).select_from(DailySummaryRevision))==2


def test_confirmed_fact_cannot_be_overwritten(db):
    p,_=member(db);row=obs(db,p,'weight',86.3);db.commit()
    with pytest.raises(ValueError,match='append-only'):
        with db.begin_nested():
            row.value_numeric=Decimal('83.6');db.flush()


def test_cancelled_recheck_does_not_break_today_work(db):
    from executive_health_ai.models.management_workflow import RecheckPlan
    from executive_health_ai.services.member_management_projection import management_work_items
    p,program=member(db)
    row=RecheckPlan(patient_id=p.id,program_id=program.id,title='已取消复查',reason='合成验证',owner='健管甲',planned_at=utc_now(),status='CANCELLED')
    db.add(row);db.flush()
    assert not any(item.source_id==row.id for item in management_work_items(db,utc_now()))


@pytest.mark.parametrize('note',['两周后联系，暂不复查','两周后联系，无需复查'])
def test_doctor_negation_is_not_a_recheck_order(db,note):
    p,program=member(db)
    row=communications.record(db,member_id=p.id,program_id=program.id,raw_note=note,actor='王医生',
        role='DOCTOR',source='DOCTOR',request_key='negative-opinion')
    assert row.structured_summary['clinical_recheck_at'] is None


def empty_management_page(member_id):
    from uuid import UUID
    from types import SimpleNamespace
    from executive_health_ai.models import Patient
    from executive_health_ai.ui.pages.manager import workflow
    with workflow.SessionLocal() as session:patient=session.get(Patient,UUID(member_id))
    workflow.management(SimpleNamespace(request_navigation=lambda **kwargs:None),patient)


def test_new_schedule_hidden_before_plan(monkeypatch):
    from sqlalchemy.pool import StaticPool
    from sqlalchemy.orm import sessionmaker
    from streamlit.testing.v1 import AppTest
    from executive_health_ai.ui.pages.manager import workflow,goal_loop
    engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine);factory=sessionmaker(engine,expire_on_commit=False)
    with factory() as session:
        patient,program=member(session,False);session.commit();identity=str(patient.id)
    monkeypatch.setattr(workflow,'SessionLocal',factory);monkeypatch.setattr(goal_loop,'SessionLocal',factory)
    app=AppTest.from_function(empty_management_page,args=(identity,)).run()
    assert not app.exception
    assert any(h.value=='尚未进入正式年度健康管理' for h in app.subheader)
    assert any(b.label=='继续处理初评' for b in app.button)
    assert not any(s.label in {'安排类型','查看或修正'} for s in app.selectbox)
    assert not any('开放事项' in h.value for h in app.subheader)
    engine.dispose()
