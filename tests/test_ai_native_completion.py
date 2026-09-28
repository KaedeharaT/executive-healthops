"""Bounded tools, durable operational work and real outcome contracts."""
from datetime import date, timedelta
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from executive_health_ai.models import Base, AgentGoal, AgentRunTrace, Task, MemberAgent
from executive_health_ai.services.management_workflow import ManagementWorkflowService
from executive_health_ai.agent.tools import AgentToolRegistry
from executive_health_ai.models.base import utc_now


@pytest.fixture
def care_db(tmp_path):
    engine = create_engine('sqlite:///' + (tmp_path/'native.db').as_posix())
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as s:
        p = ManagementWorkflowService().enroll(s, name='AI Native 合成会员', start=date.today(),
            end=date.today()+timedelta(days=364), owner='责任健管', goal='有来源的持续管理')
        g = AgentGoal(member_id=p.patient_id, goal_type='DAILY_CARE', title='核对到期工作',
            source_type='health_event', source_id=str(uuid4()), status='RUNNING', owner=p.owner)
        s.add(g); s.commit()
        yield s, p, g, engine
    engine.dispose()


def followup(p):
    return {'program_id':str(p.id), 'title':'电话随访', 'instruction':'核对会员反馈',
        'due_at':utc_now().isoformat(), 'source_reference':'已确认阶段计划', 'idempotency_key':'followup-one'}


def test_registry_contains_core_tools_and_boundaries():
    registry=AgentToolRegistry()
    for name in ['get_member_profile','get_health_record','get_observations','get_annual_baseline',
        'get_current_phase','get_open_management_items','get_recent_management_logs','get_service_status',
        'get_doctor_review','create_management_item','create_followup','create_recheck','create_service_request',
        'write_management_log','complete_management_item','request_doctor_review','prepare_stage_review','start_next_phase']:
        assert registry.get(name)
    assert registry.get('start_next_phase').responsibility=='MANAGER_CONFIRM'
    assert registry.get('get_health_record').responsibility=='READ_ONLY'
    assert not registry.get('knowledge_search').enabled


def test_tool_duplicate_is_one_result_with_persistent_audit(care_db):
    s,p,g,engine=care_db; registry=AgentToolRegistry(); context=followup(p)
    result=registry.execute(s,'create_followup',g,context);s.commit()
    with Session(engine) as restarted:
        same=registry.execute(restarted,'create_followup',restarted.get(AgentGoal,g.id),context)
        assert result==same
        assert restarted.scalar(select(func.count(Task.id)))==1
        trace=restarted.scalar(select(AgentRunTrace).where(AgentRunTrace.action=='tool_execution'))
        assert trace.status=='COMPLETED' and trace.completed_at
        assert trace.metadata_json['member_agent_id']
        assert trace.metadata_json['result_reference']==result


def test_changed_duplicate_input_rejected(care_db):
    s,p,g,_=care_db; registry=AgentToolRegistry(); c=followup(p)
    registry.execute(s,'create_followup',g,c)
    with pytest.raises(ValueError,match='不能更换'):
        registry.execute(s,'create_followup',g,{**c,'title':'不同事项'})


@pytest.mark.parametrize('name',['start_next_phase','create_recheck','complete_management_item','create_service_request'])
def test_confirmation_cannot_be_bypassed(care_db,name):
    s,p,g,_=care_db
    with pytest.raises(PermissionError):AgentToolRegistry().execute(s,name,g,{})


def test_auto_write_requires_source(care_db):
    s,p,g,_=care_db
    with pytest.raises(ValueError,match='来源'):AgentToolRegistry().execute(s,'create_followup',g,{'program_id':str(p.id)})
    assert s.scalar(select(func.count(Task.id)))==0
    trace=s.scalar(select(AgentRunTrace).where(AgentRunTrace.action=='tool_execution'))
    assert trace.status=='FAILED'


def test_tools_cannot_cross_member(care_db):
    s,p,g,_=care_db
    other=ManagementWorkflowService().enroll(s,name='另一会员',start=date.today(),end=date.today()+timedelta(days=364),owner='另一健管',goal='管理')
    with pytest.raises(ValueError,match='不属于'):
        AgentToolRegistry().execute(s,'create_followup',g,followup(other))


def test_knowledge_unavailable_and_no_clinical_auto_tools(care_db):
    s,p,g,_=care_db;registry=AgentToolRegistry()
    with pytest.raises(ValueError,match='尚未配置'):registry.execute(s,'knowledge_search',g)
    for name in ['diagnose','prescribe','update_risk','execute_sql']:
        with pytest.raises(ValueError):registry.get(name)


@pytest.mark.parametrize('name',['get_member_profile','get_health_record','get_observations',
    'get_annual_baseline','get_current_phase','get_open_management_items','get_recent_management_logs',
    'get_service_status','get_doctor_review'])
def test_read_tools_use_existing_sources(care_db,name):
    s,p,g,_=care_db
    assert isinstance(AgentToolRegistry().execute(s,name,g),dict)


@pytest.mark.parametrize('kind',['DAILY_CARE','FOLLOWUP_RESULT','STAGE_REVIEW'])
def test_bounded_planner_preserves_required_gates(care_db,kind):
    from executive_health_ai.agent.planner import HealthOpsPlanner, CARE_TEMPLATES, StepTemplate
    s,p,g,_=care_db;g.goal_type=kind
    planner=HealthOpsPlanner();plan=planner.create_plan(s,g,reason='业务事件')
    assert len(planner.steps(s,plan.id))<=12
    assert any(step.requires_approval for step in planner.steps(s,plan.id))
    with pytest.raises(ValueError):planner.validate(kind,(StepTemplate('绕过确认','start_next_phase'),))
    with pytest.raises(ValueError):planner.validate(kind,CARE_TEMPLATES[kind][:-1])


def test_completion_needs_actual_business_result(care_db):
    from executive_health_ai.services.care_runtime import finish
    s,p,g,_=care_db
    with pytest.raises(ValueError,match='业务结果'):finish(s,g)
    g.context_json={'no_action_reason':'核对后暂无到期或开放事项'}
    finish(s,g);s.commit()
    assert g.status=='COMPLETED'
    agent=s.scalar(select(MemberAgent).where(MemberAgent.member_id==p.patient_id))
    assert agent is not None and agent.status=='IDLE'


@pytest.mark.parametrize('state',['WAITING_MANAGER','WAITING_DOCTOR','WAITING_MEMBER','WAITING_TIME','WAITING_INPUT'])
def test_durable_wait_and_same_goal_resume(care_db,state):
    from executive_health_ai.services.care_runtime import wait,resume
    s,p,g,engine=care_db
    wait(s,g,state,next_action='等待原事项结果',due=utc_now()-timedelta(seconds=1) if state=='WAITING_TIME' else None,
        expected_event='TIME_DUE' if state=='WAITING_TIME' else 'RESULT_RECEIVED',expected_source='original')
    s.commit();identity=g.id
    with Session(engine) as fresh:
        original=fresh.get(AgentGoal,identity)
        assert original.status==state
        with pytest.raises(ValueError):resume(fresh,original,event_type='OTHER',source_id='original')
        assert resume(fresh,original,event_type='TIME_DUE' if state=='WAITING_TIME' else 'RESULT_RECEIVED',source_id='original')
        assert not resume(fresh,original,event_type='RESULT_RECEIVED',source_id='original')
        assert original.id==identity and original.status=='RUNNING'


def test_due_scheduler_original_task_is_only_human_work(care_db):
    from executive_health_ai.agent.scheduler import AgentSchedulerService
    from executive_health_ai.models import HealthEvent
    s,p,g,_=care_db;g.status='COMPLETED';s.flush()
    row=AgentToolRegistry().execute(s,'create_followup',g,followup(p))
    scheduler=AgentSchedulerService();scheduler.run_due(s,now=utc_now());s.commit()
    goal=s.scalar(select(AgentGoal).where(AgentGoal.status=='WAITING_MANAGER'))
    assert goal and goal.goal_type=='DAILY_CARE'
    assert goal.context_json['work_refs']==[row['task_id']]
    scheduler.run_due(s,now=utc_now());s.commit()
    assert s.scalar(select(func.count(Task.id)))==1
    assert s.scalar(select(func.count(HealthEvent.id)))==1
    from executive_health_ai.services.management_action_loop import ManagementActionLoop
    from uuid import UUID
    ManagementActionLoop().process_task(s,p.patient_id,p.id,UUID(row['task_id']),actor=p.owner,result='已核对会员反馈',
        outcome='已完成',next_action='无需后续',follow_at=None,request_key='complete-task')
    s.commit()
    assert goal.status=='COMPLETED'

    recheck=ManagementWorkflowService().create_recheck(s,p.patient_id,p.id,title='血脂复查',reason='沿用合成医生安排',
        planned_at=utc_now(),owner=p.owner,evidence='合成医生书面复查建议')
    scheduler.run_due(s,now=utc_now());s.commit()
    waiting=s.scalar(select(AgentGoal).where(AgentGoal.goal_type=='DAILY_CARE',AgentGoal.status=='WAITING_MANAGER'))
    assert waiting.context_json['related_work']=={'kind':'recheck','id':str(recheck.id)}
    total=s.scalar(select(func.count(AgentGoal.id)))
    scheduler.run_due(s,now=utc_now());s.commit()
    assert s.scalar(select(func.count(AgentGoal.id)))==total
    assert s.scalar(select(func.count(Task.id)))==1  # No duplicate human task.


def test_result_extraction_requires_verbatim_evidence():
    from executive_health_ai.services.care_result_extraction import validate
    text='会员最近不喝酒，睡眠每天6个小时，准备10月15日复查血脂。'
    checked=validate({'facts':[{'field':'睡眠','value':'8小时','evidence':'睡眠每天6个小时'},
        {'field':'诊断','value':'高血压','evidence':text},{'field':'饮酒','value':'不喝酒','evidence':'会员最近不喝酒'}],
        'actions':[{'kind':'RECHECK','title':'血脂','date_text':'10月15日','evidence':'准备10月15日复查血脂'}]},text,date(2026,9,29))
    assert len(checked['facts'])==1 and checked['facts'][0]['value']=='不喝酒'
    assert checked['actions'][0]['date']=='2026-10-15'


def test_cancelled_recheck_and_missing_dates_not_invented():
    from executive_health_ai.services.care_result_extraction import rules
    assert not rules('会员不需要10月15日复查血脂',date.today())['actions']
    assert not rules('会员考虑复查血脂',date.today())['actions']


def test_recheck_intention_cannot_be_duplicated_as_a_followup():
    from executive_health_ai.services.care_result_extraction import extract
    from types import SimpleNamespace
    text='准备10月15日去复查血脂'
    class Client:
        settings=SimpleNamespace(enabled=True)
        def generate_structured(self,**kwargs):
            return {'facts':[],'actions':[
                {'kind':'FOLLOWUP','title':'复查血脂','date_text':'10月15日','evidence':text},
                {'kind':'RECHECK','title':'复查血脂','date_text':'10月15日','evidence':text},
                {'kind':'RECHECK','title':'血脂','date_text':'10月15日','evidence':text}]}
    parsed=extract(text,today=date(2026,9,29),source_id='synthetic-result',client=Client())
    assert len(parsed['actions'])==1
    assert parsed['actions'][0]['kind']=='RECHECK' and parsed['actions'][0]['title']=='血脂'


def test_nlp_worker_releases_transaction_and_confirmation_is_idempotent(care_db,monkeypatch):
    from executive_health_ai.services import care_results
    from executive_health_ai.agent.care_result_execution import execute
    from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
    from executive_health_ai.services import care_result_extraction
    from executive_health_ai.models.management_workflow import ManagementLog
    from executive_health_ai.models import HealthEvent
    s,p,g,engine=care_db;g.status='COMPLETED'
    item=AgentToolRegistry().execute(s,'create_followup',g,followup(p))
    from uuid import UUID
    text='会员最近不喝酒，睡眠每天6个小时，准备10月15日复查血脂。'
    result=care_results.submit(s,member_id=p.patient_id,program_id=p.id,task_id=UUID(item['task_id']),
        text=text,actor=p.owner,outcome='已完成',request_key='result-once');s.commit()
    from zoneinfo import ZoneInfo
    assert result.context_json['recorded_date']==utc_now().astimezone(ZoneInfo('Asia/Tokyo')).date().isoformat()
    def extract(note,**kwargs):
        assert not s.in_transaction()
        with Session(engine) as concurrent:
            concurrent.add(Task(patient_id=p.patient_id,title='并发写入',instruction='验证事务边界',source='concurrent'))
            concurrent.commit()
        return {**care_result_extraction.rules(note,date(2026,9,29)),'ai_used':False,'warning':''}
    monkeypatch.setattr(care_result_extraction,'extract',extract)
    supervisor=HealthOpsAgentSupervisor();execute(supervisor,s,result)
    assert result.status=='WAITING_MANAGER'
    assert len(care_results.proposals(s,result))==1
    care_results.confirm(s,result,supervisor,actor=p.owner,role='HEALTH_MANAGER');s.commit()
    care_results.confirm(s,result,supervisor,actor=p.owner,role='HEALTH_MANAGER');s.commit()
    assert s.scalar(select(func.count(ManagementLog.id)))==1
    assert result.status=='COMPLETED' and result.context_json['outputs']
    assert s.scalar(select(func.count(AgentRunTrace.id)).where(AgentRunTrace.goal_id==result.id,AgentRunTrace.action=='resume'))==1
    assert s.scalar(select(func.count(HealthEvent.id)).where(HealthEvent.event_type=='TIME_DUE'))==1
    due_event=s.scalar(select(HealthEvent).where(HealthEvent.event_type=='TIME_DUE'))
    assert due_event.occurred_at.astimezone(ZoneInfo('Asia/Tokyo')).hour==9
    assert s.get(Task,UUID(item['task_id'])).status=='COMPLETED'


def test_one_hundred_raw_samples_wake_zero_then_one_change(care_db):
    from executive_health_ai.services.health_events import ingest_health_event
    from executive_health_ai.services.health_event_measurements import evaluate_window
    from executive_health_ai.models import Observation,HealthEvent
    s,p,g,_=care_db;g.status='COMPLETED';s.commit()
    agent=s.scalar(select(MemberAgent).where(MemberAgent.member_id==p.patient_id));before=agent.wake_count
    start=utc_now()-timedelta(minutes=1)
    for i in range(100):
        ingest_health_event(s,member_id=p.patient_id,event_type='DEVICE_RAW_MEASUREMENT',event_category='NEW_INFORMATION',
            source_type='DEVICE',source_id='native-bp-'+str(i),payload_ref={'measurement':{
                'metric':'systolic_bp','value':145,'unit':'mmHg','observed_at':utc_now().isoformat()}})
    s.commit();s.refresh(agent)
    assert agent.wake_count==before and s.scalar(select(func.count(Observation.id)))==100
    end=utc_now()+timedelta(seconds=1)
    for _ in range(3):
        evaluate_window(s,member_id=p.patient_id,metric='systolic_bp',threshold=140,minimum_count=3,
            window_start=start,window_end=end,rule_id='synthetic-repeat-bp')
    s.commit();s.refresh(agent)
    assert agent.wake_count==before+1
    assert s.scalar(select(func.count(HealthEvent.id)).where(HealthEvent.event_category=='MEANINGFUL_CHANGE'))==1
    assert s.scalar(select(func.count(Task.id)))==1


def test_stage_summary_wait_and_next_phase_same_goal(care_db):
    from executive_health_ai.services.management_action_loop import ManagementActionLoop
    from executive_health_ai.models import ProgramPhase
    s,p,g,_=care_db;g.status='COMPLETED';p.status='ACTIVE'
    workflow=ManagementWorkflowService()
    phase=workflow.add_phase(s,p.patient_id,p.id,title='本阶段',goal='沟通与跟进',content='电话随访',
        start=date.today(),end=date.today()+timedelta(days=30),owner=p.owner)
    phase.status='ACTIVE';p.current_phase=phase.phase_code
    context=followup(p)
    from datetime import datetime,time,timezone
    context['due_at']=datetime.combine(phase.start_date,time(9),timezone.utc).isoformat()
    item=AgentToolRegistry().execute(s,'create_followup',g,context);s.commit()
    from uuid import UUID
    loop=ManagementActionLoop()
    loop.process_task(s,p.patient_id,p.id,UUID(item['task_id']),actor=p.owner,result='已记录会员反馈',outcome='已完成',
        next_action='无需后续',follow_at=None,request_key='stage-core-complete');s.commit()
    goal=s.scalar(select(AgentGoal).where(AgentGoal.goal_type=='STAGE_REVIEW'))
    assert goal and goal.status=='WAITING_MANAGER' and goal.context_json['stage_summary']
    content=loop.stage_summary(loop.project(s,p.patient_id,p.id))
    loop.review_stage(s,p.patient_id,p.id,phase_id=phase.id,content=content,actor=p.owner)
    next_row=loop.enter_next_phase(s,p.patient_id,p.id,phase.id,actor=p.owner,title='下一阶段',goal='继续跟进',
        content='沿用确认计划',start=phase.end_date+timedelta(days=1),end=phase.end_date+timedelta(days=30),action='下阶段随访')
    s.commit();assert goal.status=='COMPLETED' and goal.context_json['next_phase_id']==str(next_row.id)
    assert s.scalar(select(func.count(AgentRunTrace.id)).where(AgentRunTrace.goal_id==goal.id,AgentRunTrace.action=='resume'))==1


def test_crashed_semantic_claim_recovers_and_stale_result_cannot_write(care_db,monkeypatch):
    from executive_health_ai.services import care_results,care_result_extraction
    from executive_health_ai.agent.care_result_execution import execute
    from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
    from uuid import UUID
    s,p,g,engine=care_db
    task=AgentToolRegistry().execute(s,'create_followup',g,followup(p))
    goal=care_results.submit(s,member_id=p.patient_id,program_id=p.id,task_id=UUID(task['task_id']),
        text='会员反馈夜班工作',actor=p.owner,outcome='已完成',request_key='crash-result')
    goal.status='PROCESSING';goal.next_check_at=utc_now()-timedelta(seconds=1)
    goal.context_json={**goal.context_json,'execution':{'token':'dead-process'}};s.commit()
    def external(*args,**kwargs):
        assert not s.in_transaction()
        with Session(engine) as other:
            other.get(AgentGoal,goal.id).status='CANCELLED';other.commit()
        return {'facts':[],'actions':[],'ai_used':False,'warning':''}
    monkeypatch.setattr(care_result_extraction,'extract',external)
    execute(HealthOpsAgentSupervisor(),s,goal);s.refresh(goal)
    assert goal.status=='CANCELLED' and 'parsed' not in goal.context_json


def test_longitudinal_context_has_time_and_original_log(care_db):
    from executive_health_ai.services.care_memory import remember_result,longitudinal
    s,p,g,_=care_db
    row=ManagementWorkflowService().record_log(s,p.patient_id,p.id,actor=p.owner,request_key='memory-log',
        category='电话',member_issue='本周执行安排',manager_action='核对可行时间',result='会员反馈夜班安排影响作息',owner=p.owner,occurred_at=utc_now())
    g.context_json={'log_id':str(row.id)};remember_result(s,g);remember_result(s,g);s.commit()
    memory=longitudinal(s,p.patient_id)
    assert len(memory)==1 and memory[0]['source']['source_id']==str(row.id) and memory[0]['recorded_at']


@pytest.mark.parametrize('source',['MOBILE','DEVICE'])
def test_adapter_contract_preserves_raw_store_only(care_db,source):
    from executive_health_ai.services.measurement_ingestion import MeasurementEnvelope,ingest_measurement
    s,p,g,_=care_db
    event,_=ingest_measurement(s,MeasurementEnvelope(member_id=p.patient_id,source_type=source,source_id='vendor:1',
        metric='weight',value=80,unit='kg',observed_at=utc_now()))
    assert event.route_action=='STORE_ONLY'


def test_same_item_duplicate_submission_returns_same_goal(care_db):
    from executive_health_ai.services.care_results import submit
    from uuid import UUID
    s,p,g,_=care_db;result=AgentToolRegistry().execute(s,'create_followup',g,followup(p))
    args=dict(member_id=p.patient_id,program_id=p.id,task_id=UUID(result['task_id']),text='会员说睡眠六小时',actor=p.owner,outcome='已完成')
    first=submit(s,**args,request_key='first')
    second=submit(s,**args,request_key='second')
    assert first.id==second.id


def test_intake_report_handoff_retains_confirmation_and_same_goal(care_db):
    from executive_health_ai.models import Document,ReportExtractionRun,ReportExtractionCandidate,HealthEvent,Observation
    from executive_health_ai.services.intake_handoff import report_ready
    s,p,g,_=care_db
    doc=Document(patient_id=p.patient_id,document_type='auto',title='合成体检报告.txt',storage_reference='synthetic.txt',source='MANUAL')
    s.add(doc);s.flush()
    run=ReportExtractionRun(patient_id=p.patient_id,document_id=doc.id,status='COMPLETED',parser_version='test',
        canonical_registry_version='test',file_hash='a'*64,file_type='txt')
    s.add(run);s.flush()
    candidate=ReportExtractionCandidate(patient_id=p.patient_id,document_id=doc.id,extraction_run_id=run.id,
        candidate_type='OBSERVATION',canonical_code='weight',normalized_value='78',unit='kg',
        extraction_method='RULE',evidence_text='体重 78kg',status='PENDING_REVIEW')
    s.add(candidate);g.source_id=str(doc.id);g.goal_type='PROFILE_INTAKE';g.status='COMPLETED';s.flush()
    first,_=report_ready(s,g);second,created=report_ready(s,g);s.commit()
    assert first.id==second.id and not created
    assert s.scalar(select(func.count(AgentGoal.id)).where(AgentGoal.goal_type=='POST_CHECKUP_MANAGEMENT'))==1
    assert candidate.status=='PENDING_REVIEW' and s.scalar(select(func.count(Observation.id)))==0
