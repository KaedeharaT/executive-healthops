"""Phase 1A: durable identities, atomic receipts, bounded routing and human gates."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from executive_health_ai.models import (Base, Patient, MemberAgent, HealthEvent, AgentGoal,
    Observation, RawData, RiskEvent, Task)
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.member_agents import ensure_member_agent, synchronize
from executive_health_ai.services.health_events import ingest_health_event, process_pending
from executive_health_ai.services.health_event_measurements import evaluate_window
from executive_health_ai.services.profile_ingestion import ProfileIngestionService, candidates
from executive_health_ai.services.product_projection import ProductProjectionService
from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
from executive_health_ai.agent import profile_intake


@pytest.fixture
def db(tmp_path, monkeypatch):
    engine=create_engine('sqlite:///'+(tmp_path/'events.db').as_posix(),connect_args={'timeout':10})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(ProfileIngestionService,'storage_root',tmp_path/'uploads')
    with Session(engine,expire_on_commit=False) as s:
        member=Patient(display_name='Phase 1A 合成会员',timezone='Asia/Tokyo')
        s.add(member);s.commit()
        yield s,member,engine
    engine.dispose()


def receipt(s,member,**kw):
    values=dict(member_id=member.id,event_type='MEMBER_ANSWER_RECEIVED',event_category='NEW_INFORMATION',
        source_type='MANUAL',source_id=str(uuid4()))
    values.update(kw)
    return ingest_health_event(s,**values)


def measurement(s,member,i,source='DEVICE'):
    return receipt(s,member,event_type=source+'_RAW_MEASUREMENT',source_type=source,source_id='bp:'+str(i),
        payload_ref={'measurement':{'metric':'systolic_bp','value':145,'unit':'mmHg','observed_at':utc_now().isoformat()}})


def agent(s,member):
    return s.scalar(select(MemberAgent).where(MemberAgent.member_id==member.id))


def test_one_member_one_agent_and_restart(db):
    s,m,e=db
    a=ensure_member_agent(s,m.id);ident=a.id
    assert ensure_member_agent(s,m.id).id==ident
    s.commit()
    with Session(e) as fresh:
        assert ensure_member_agent(fresh,m.id).id==ident
        assert fresh.scalar(select(func.count(MemberAgent.id)))==1


def test_database_prevents_duplicate_identity(db):
    s,m,_=db
    ensure_member_agent(s,m.id);s.commit()
    with pytest.raises(IntegrityError),s.begin_nested():
        s.add(MemberAgent(member_id=m.id));s.flush()


def test_fresh_process_confirmation_synchronizes_without_ingestion_import():
    import subprocess
    import sys
    result=subprocess.run([sys.executable,'-c','''
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from executive_health_ai.models import Base,Patient,MemberAgent,AgentGoal
engine=create_engine('sqlite://');Base.metadata.create_all(engine)
with Session(engine) as s:
    member=Patient(display_name='Fresh process synthetic',timezone='UTC');s.add(member);s.flush()
    identity=MemberAgent(member_id=member.id);s.add(identity);s.flush()
    assert 'executive_health_ai.services.member_agents' not in sys.modules
    goal=AgentGoal(member_id=member.id,goal_type='PROFILE_INTAKE',title='Synthetic',source_type='health_document',source_id='fresh',status='WAITING_MANAGER')
    s.add(goal);s.flush()
    assert identity.status=='WAITING_MANAGER'
    goal.status='COMPLETED';s.flush()
    assert identity.status=='IDLE' and identity.current_goal_id is None
'''],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr


def test_concurrent_identity_and_event_are_single(db):
    s,m,e=db;member_id=m.id
    def ingest(_):
        with Session(e) as worker:
            a=ensure_member_agent(worker,member_id)
            event,_=ingest_health_event(worker,member_id=member_id,event_type='TIME_DUE',
                event_category='TIME_DUE',source_type='SYSTEM',source_id='followup:one')
            result=a.id,event.id
            worker.commit();return result
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(ingest,range(8)))
    assert len(set(results))==1
    assert agent(s,m).wake_count==1


@pytest.mark.parametrize('source',['MANUAL','MOBILE','DEVICE','SYSTEM'])
def test_all_source_types_use_one_ingestion(db,source):
    s,m,_=db
    event,created=receipt(s,m,source_type=source)
    assert created and event.source_type==source and event.status=='STORED'
    assert event.event_id and event.correlation_id and event.received_at


@pytest.mark.parametrize('source',['DEVICE','MOBILE'])
def test_raw_store_only_normalizes_without_wake(db,source):
    s,m,_=db;a=ensure_member_agent(s,m.id)
    event,_=measurement(s,m,0,source)
    assert event.route_action=='STORE_ONLY' and event.status=='STORED'
    assert a.wake_count==0 and a.status=='IDLE'
    assert s.scalar(select(func.count(Observation.id)))==1
    assert s.scalar(select(func.count(RawData.id)))==1
    assert not s.scalar(select(func.count(AgentGoal.id)))
    assert not ProductProjectionService().manager(s,utc_now()).items


def test_50_raw_then_one_rule_change(db):
    s,m,_=db;a=ensure_member_agent(s,m.id)
    start=utc_now()-timedelta(minutes=1)
    for i in range(50):measurement(s,m,i)
    assert s.scalar(select(func.count(HealthEvent.id)))==50
    assert s.scalar(select(func.count(Observation.id)))==50
    assert a.wake_count==0
    end=utc_now()+timedelta(minutes=1)
    params=dict(member_id=m.id,metric='systolic_bp',threshold=140,minimum_count=3,
        window_start=start,window_end=end,rule_id='synthetic-review-condition-v1')
    changed=evaluate_window(s,**params)
    assert changed.event_category=='MEANINGFUL_CHANGE'
    assert changed.route_action=='WAKE_MEMBER_AGENT'
    for _ in range(5):assert evaluate_window(s,**params).id==changed.id
    assert a.wake_count==1 and a.status=='IDLE'
    assert s.scalar(select(func.count(HealthEvent.id)))==51
    assert not s.scalar(select(func.count(AgentGoal.id)))
    assert not s.scalar(select(func.count(RiskEvent.id)))
    assert not s.scalar(select(func.count(Task.id)))


def test_bad_raw_payload_rolls_back_entire_receipt(db):
    s,m,_=db
    with pytest.raises(ValueError):receipt(s,m,event_type='DEVICE_RAW_MEASUREMENT',source_type='DEVICE')
    s.commit()
    assert s.scalar(select(func.count(HealthEvent.id)))==0
    assert s.scalar(select(func.count(Observation.id)))==0


def test_raw_cannot_claim_meaningful_change(db):
    s,m,_=db
    with pytest.raises(ValueError):receipt(s,m,event_type='DEVICE_RAW_MEASUREMENT',event_category='MEANINGFUL_CHANGE')
    with pytest.raises(ValueError):receipt(s,m,event_type='MEANINGFUL_CHANGE',event_category='MEANINGFUL_CHANGE',source_type='DEVICE')


def test_duplicate_origin_is_idempotent_even_with_new_key(db):
    s,m,_=db
    first,_=measurement(s,m,1)
    second,created=receipt(s,m,event_type='DEVICE_RAW_MEASUREMENT',source_type='DEVICE',source_id='bp:1',idempotency_key='new-retry-key')
    assert not created and first.id==second.id
    assert s.scalar(select(func.count(Observation.id)))==1


def test_event_does_not_commit_callers_transaction(db):
    s,m,e=db
    receipt(s,m,event_type='TIME_DUE',event_category='TIME_DUE',source_type='SYSTEM')
    s.rollback()
    with Session(e) as fresh:
        assert fresh.scalar(select(func.count(HealthEvent.id)))==0
        assert fresh.scalar(select(func.count(MemberAgent.id)))==0


def test_future_due_survives_restart_and_wakes_only_once(db):
    s,m,e=db;due=utc_now()+timedelta(hours=1)
    event,_=receipt(s,m,event_type='TIME_DUE',event_category='TIME_DUE',source_type='SYSTEM',occurred_at=due)
    ident=event.id
    assert event.status=='PENDING' and agent(s,m).wake_count==0
    assert agent(s,m).status=='WAITING_TIME' and agent(s,m).next_wake_at==due
    s.commit()
    with Session(e) as fresh:
        assert process_pending(fresh,HealthOpsAgentSupervisor(),now=due-timedelta(seconds=1))==0
        assert process_pending(fresh,HealthOpsAgentSupervisor(),now=due)==1
        assert process_pending(fresh,HealthOpsAgentSupervisor(),now=due)==0
        assert fresh.get(HealthEvent,ident).status=='PROCESSED'
        a=fresh.scalar(select(MemberAgent))
        assert a.status=='IDLE' and a.next_wake_at is None and a.wake_count==1
        fresh.commit()


def test_document_event_running_hidden_waiting_visible_completion_keeps_identity(db):
    s,m,_=db;a=ensure_member_agent(s,m.id);identity=a.id
    payload=json.dumps({'responses':{'生活方式':{'烟草':'无','睡眠':'七小时'}}},ensure_ascii=False).encode()
    goal,_=ProfileIngestionService().upload(s,m.id,'问卷.json',payload,'questionnaire',actor='王健管',role='HEALTH_MANAGER')
    assert a.status=='RUNNING' and a.current_goal_id==goal.id and a.wake_count==1
    event=s.scalar(select(HealthEvent).where(HealthEvent.event_category.is_not(None)))
    assert event.event_type=='HEALTH_DOCUMENT_UPLOADED' and event.goal_id==goal.id
    assert goal.context_json['trigger_reason']=='收到新的健康资料'
    assert not any(i.source_id==goal.id for i in ProductProjectionService().manager(s,utc_now()).items)
    same,_=ProfileIngestionService().upload(s,m.id,'问卷.json',payload,'questionnaire',actor='王健管',role='HEALTH_MANAGER')
    assert same.id==goal.id and a.wake_count==1
    supervisor=HealthOpsAgentSupervisor()
    while goal.status=='RUNNING':supervisor.execute_next_step(s,goal.id)
    assert a.status=='WAITING_MANAGER'
    assert any(i.source_id==goal.id for i in ProductProjectionService().manager(s,utc_now()).items)
    profile_intake.confirm(supervisor,s,goal,{str(c.id):'采用新资料' for c in candidates(s,goal)},actor='王健管',role='HEALTH_MANAGER')
    assert goal.status=='COMPLETED' and a.id==identity and a.status=='IDLE' and a.current_goal_id is None


def test_completing_one_goal_does_not_hide_another(db):
    s,m,_=db;a=ensure_member_agent(s,m.id)
    goals=[AgentGoal(member_id=m.id,goal_type='PROFILE_INTAKE',title='合成目标',source_type='health_document',
        source_id=str(uuid4()),status=status) for status in ('RUNNING','WAITING_DOCTOR')]
    s.add_all(goals);s.flush()
    assert a.current_goal_id==goals[0].id and a.status=='RUNNING'
    goals[0].status='COMPLETED';s.flush()
    assert a.current_goal_id==goals[1].id and a.status=='WAITING_DOCTOR'


def test_idempotency_key_cannot_cross_members(db):
    s,m,_=db;receipt(s,m,idempotency_key='fixed')
    other=Patient(display_name='other',timezone='Asia/Tokyo');s.add(other);s.flush()
    with pytest.raises(ValueError):receipt(s,other,idempotency_key='fixed')


def test_old_history_not_replayed(db):
    s,m,_=db
    old=HealthEvent(patient_id=m.id,start_at=utc_now(),event_type='surgery',description='既往记录',source='人工记录')
    s.add(old);s.flush()
    assert old.event_category is None
    assert process_pending(s,HealthOpsAgentSupervisor())==0
    assert agent(s,m) is None


def test_invalid_pending_event_does_not_starve_next_member(db):
    s,m,_=db
    invalid,_=receipt(s,m,event_type='HEALTH_DOCUMENT_UPLOADED',dispatch=False)
    due,_=receipt(s,m,event_type='TIME_DUE',event_category='TIME_DUE',source_type='SYSTEM',dispatch=False)
    assert process_pending(s,HealthOpsAgentSupervisor())==2
    assert invalid.status=='FAILED' and due.status=='PROCESSED'
    assert agent(s,m).wake_count==1 and not s.scalar(select(func.count(AgentGoal.id)))


def test_measurement_quality_and_unit_conversion_use_existing_data_layer(db):
    s,m,_=db
    receipt(s,m,event_type='DEVICE_RAW_MEASUREMENT',source_type='DEVICE',source_id='scale:one',
        payload_ref={'measurement':{'metric':'weight','value':200,'unit':'lb'}})
    obs=s.scalar(select(Observation))
    assert float(obs.value_numeric)==pytest.approx(90.718474,abs=.001) and obs.unit=='kg'
    receipt(s,m,event_type='DEVICE_RAW_MEASUREMENT',source_type='DEVICE',source_id='bp:bad',
        payload_ref={'measurement':{'metric':'systolic_bp','value':500,'unit':'mmHg'}})
    assert s.scalar(select(Observation).where(Observation.metric_code=='systolic_bp')).quality_flag=='invalid'
    assert evaluate_window(s,member_id=m.id,metric='systolic_bp',threshold=140,minimum_count=2,
        window_start=utc_now()-timedelta(hours=1),window_end=utc_now()+timedelta(hours=1),rule_id='quality-test') is None


def report_goal(db,tmp_path):
    from executive_health_ai.services.management_workflow import ManagementWorkflowService
    from executive_health_ai.services.report_parsing import ReportParsingService
    s,_,_=db
    program=ManagementWorkflowService().enroll(s,name='Phase 1A 体检会员',start=date.today(),
        end=date.today()+timedelta(days=364),owner='王健管',goal='年度健康管理')
    parser=ReportParsingService();parser.storage_root=tmp_path
    report,_,_=parser.upload_and_parse(s,program.patient_id,'合成体检.txt',
        ('体检日期：'+date.today().isoformat()+'\n低密度脂蛋白胆固醇  4.15 mmol/L\n谷丙转氨酶  56 U/L\n体重  85.8 kg').encode(),'王健管')
    return s.scalar(select(AgentGoal).where(AgentGoal.source_id==str(report.id)))


def test_checkup_wakes_same_member_and_doctor_resumes_goal(db,tmp_path):
    from executive_health_ai.agent import post_checkup
    from executive_health_ai.services.post_checkup import PostCheckupCareService
    s,_,_=db;g=report_goal(db,tmp_path);ident=g.id
    a=s.scalar(select(MemberAgent).where(MemberAgent.member_id==g.member_id));agent_id=a.id
    assert a.wake_count==1 and a.status=='WAITING_MANAGER'
    sup=HealthOpsAgentSupervisor()
    post_checkup.manager_review(sup,s,g,actor='王健管',role='HEALTH_MANAGER',doctor='演示医生',question='请核对资料')
    assert a.status=='WAITING_DOCTOR'
    review=PostCheckupCareService().submit_review(s,g,actor='演示医生',role='DOCTOR',
        judgement='资料不足以作医学结论，继续核对',recommendation='核对会员生活方式记录',recheck=False,
        recheck_title='',suggested_date=date.today()+timedelta(days=90),followup_date=date.today()+timedelta(days=30))
    assert a.id==agent_id and a.current_goal_id==ident and a.status=='WAITING_MANAGER'
    assert a.wake_count==2
    event=s.scalar(select(HealthEvent).where(HealthEvent.event_type=='DOCTOR_REVIEW_COMPLETED'))
    assert event.source_type=='SYSTEM' and event.goal_id==ident and event.route_action=='RESUME_CURRENT_GOAL'
    replay,_=ingest_health_event(s,member_id=g.member_id,event_type='DOCTOR_REVIEW_COMPLETED',
        event_category='NEW_INFORMATION',source_type='SYSTEM',source_id=str(review.id))
    assert replay.id==event.id and a.wake_count==2 and s.scalar(select(func.count(AgentGoal.id)))==1


def test_post_checkup_llm_runs_outside_write_transaction(db,tmp_path,monkeypatch):
    from executive_health_ai.agent import post_checkup_execution
    from executive_health_ai.llm.local_llm_client import LocalLLMClient
    monkeypatch.setenv('LOCAL_LLM_ENABLED','true')
    s,_,e=db;g=report_goal(db,tmp_path);calls=[]
    assert g.status=='RUNNING' and g.context_json['pending_ai']['kind']=='summary'
    def generate(self,**kw):
        assert not s.in_transaction(), 'LLM must not hold even an ORM transaction'
        # A second writer must be able to commit while inference is in flight.
        with Session(e) as other:
            other.add(Patient(display_name='并发写入合成会员',timezone='Asia/Tokyo'));other.commit()
        calls.append(kw['task'])
        return {'summary':'已整理体检资料，等待健管核对。'}
    monkeypatch.setattr(LocalLLMClient,'generate_structured',generate)
    post_checkup_execution.execute(HealthOpsAgentSupervisor(),s,g)
    assert calls==['post_checkup_manager_draft']
    assert g.status=='WAITING_MANAGER' and 'pending_ai' not in g.context_json
    assert s.scalar(select(MemberAgent).where(MemberAgent.member_id==g.member_id)).status=='WAITING_MANAGER'


def test_cancelled_during_llm_is_not_resurrected(db,tmp_path,monkeypatch):
    from executive_health_ai.agent import post_checkup_execution
    from executive_health_ai.llm.local_llm_client import LocalLLMClient
    monkeypatch.setenv('LOCAL_LLM_ENABLED','true')
    s,_,e=db;g=report_goal(db,tmp_path);ident=g.id
    def generate(self,**kw):
        with Session(e) as other:
            target=other.get(AgentGoal,ident);target.status='CANCELLED';target.automation_paused=True;other.commit()
        return {'summary':'此过期结果不能写入。'}
    monkeypatch.setattr(LocalLLMClient,'generate_structured',generate)
    post_checkup_execution.execute(HealthOpsAgentSupervisor(),s,g)
    assert g.status=='CANCELLED' and not g.context_json.get('ai_summary_draft')


def test_unconfirmed_doctor_result_does_not_wake_or_advance(db,tmp_path):
    from executive_health_ai.agent import post_checkup
    s,_,_=db;g=report_goal(db,tmp_path)
    post_checkup.manager_review(HealthOpsAgentSupervisor(),s,g,actor='王健管',role='HEALTH_MANAGER',doctor='演示医生',question='请核对')
    a=s.scalar(select(MemberAgent).where(MemberAgent.member_id==g.member_id))
    with pytest.raises(ValueError):
        ingest_health_event(s,member_id=g.member_id,event_type='DOCTOR_REVIEW_COMPLETED',
            event_category='NEW_INFORMATION',source_type='SYSTEM',source_id=g.context_json['review_id'])
    assert not s.scalar(select(HealthEvent).where(HealthEvent.event_type=='DOCTOR_REVIEW_COMPLETED'))
    assert a.wake_count==1 and g.status=='WAITING_DOCTOR'
