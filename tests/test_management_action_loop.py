"""Concrete human work, successor resolution and existing medical boundaries."""
from datetime import date,datetime,time,timedelta,timezone
from uuid import uuid4
import pytest
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from executive_health_ai.models import Patient,Task,HealthProgram,DoctorReview,RiskEvent,HealthProblem,ServiceCatalogItem,ServiceRequest
from executive_health_ai.models.base import Base
from executive_health_ai.models.management_workflow import ManagementLog
from executive_health_ai.services.management_workflow import ManagementWorkflowService
from executive_health_ai.services.management_action_loop import ManagementActionLoop
from executive_health_ai.services import care_commands

loop=ManagementActionLoop();workflow=ManagementWorkflowService()

@pytest.fixture
def env():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as s:
        program=workflow.enroll(s,name='Synthetic action member',start=date.today()-timedelta(days=2),end=date.today()+timedelta(days=90),owner='QA',goal='管理执行')
        phase=workflow.add_phase(s,program.patient_id,program.id,title='当前阶段',goal='核对执行',content='完成三个事项',start=program.start_date,end=date.today()+timedelta(days=3),owner='QA')
        phase.status='ACTIVE';program.status='ACTIVE';s.flush()
        yield s,program,phase

def task(env,title='普通管理事项'):
    s,p,phase=env
    return care_commands.schedule_followup(s,p,title=title,instruction='核对实际执行并记录',due_at=datetime.now(timezone.utc),owner='QA')

def complete(env,row,**values):
    s,p,phase=env
    return loop.process_task(s,p.patient_id,p.id,row.id,actor='QA',result='本人已反馈，已核对',outcome='已完成',next_action=values.get('next_action','无需后续'),follow_at=values.get('follow_at'),request_key=values.get('request_key',str(uuid4())))

def test_overview_next_resolves_concrete_priority_and_completion_next(env):
    s,p,phase=env;first=task(env);second=task(env,'电话随访');first.priority='HIGH'
    state=loop.project(s,p.patient_id)
    assert state['next'].record.id==first.id and state['next'].kind=='MANAGEMENT'
    complete(env,first)
    assert loop.project(s,p.patient_id)['next'].record.id==second.id
    assert s.scalar(select(func.count(ManagementLog.id)))==1

def test_followup_records_result_and_schedules_next(env):
    s,p,_=env;row=task(env,'电话随访')
    assert loop.project(s,p.patient_id)['next'].kind=='FOLLOWUP'
    log=complete(env,row,next_action='继续随访',follow_at=datetime.now(timezone.utc)+timedelta(days=1))
    assert log.follow_up_task_id and loop.project(s,p.patient_id)['next'].record.id==log.follow_up_task_id

def test_partial_work_stays_open_and_requires_next_date(env):
    s,p,_=env;row=task(env)
    kwargs=dict(actor='QA',result='尚待补充',outcome='部分完成',next_action='继续随访',request_key=str(uuid4()))
    with pytest.raises(ValueError):loop.process_task(s,p.patient_id,p.id,row.id,follow_at=None,**kwargs)
    loop.process_task(s,p.patient_id,p.id,row.id,follow_at=datetime.now(timezone.utc)+timedelta(days=1),**kwargs)
    assert row.status=='PENDING' and row.completed_at is None

def test_request_is_idempotent_and_member_bound(env):
    s,p,_=env;row=task(env);key=str(uuid4())
    first=complete(env,row,request_key=key);second=complete(env,row,request_key=key)
    assert first.id==second.id and s.scalar(select(func.count(ManagementLog.id)))==1
    with pytest.raises(ValueError):loop.process_task(s,uuid4(),p.id,row.id,actor='QA',result='x',outcome='已完成',next_action='无需后续',follow_at=None,request_key=str(uuid4()))

def test_no_open_work_has_creation_actions_not_fake_completed_phase(env):
    s,p,_=env;state=loop.project(s,p.patient_id)
    assert state['state']=='CREATE' and state['next'] is None and not state['review_ready']

def test_completed_phase_review_next_phase_and_new_action(env):
    s,p,phase=env;row=task(env);complete(env,row)
    state=loop.project(s,p.patient_id);assert state['state']=='STAGE_REVIEW'
    content=loop.stage_summary(state)
    review=loop.review_stage(s,p.patient_id,p.id,phase_id=phase.id,content=content,actor='QA')
    state=loop.project(s,p.patient_id);assert state['state']=='NEXT_PHASE'
    draft=loop.next_phase_draft(state)
    following=loop.enter_next_phase(s,p.patient_id,p.id,phase.id,actor='QA',title=draft['title'],goal=draft['goal'],content=draft['content'],start=draft['start'],end=draft['end'],action='落实新阶段随访')
    assert phase.status=='COMPLETED' and following.status=='ACTIVE'
    assert loop.project(s,p.patient_id)['next'].title=='落实新阶段随访'

def test_recheck_dispatch_keeps_medical_evidence_gate(env):
    s,p,_=env
    with pytest.raises(ValueError):workflow.create_recheck(s,p.patient_id,p.id,title='复查',reason='跟进',planned_at=datetime.now(timezone.utc),owner='QA')
    row=workflow.create_recheck(s,p.patient_id,p.id,title='复查',reason='跟进',planned_at=datetime.now(timezone.utc),owner='QA',evidence='合成医生建议')
    assert loop.project(s,p.patient_id)['next'].kind=='RECHECK'
    workflow.advance_recheck(s,p.patient_id,row.id,status='TO_BOOK',actor='QA')
    assert row.status=='TO_BOOK'

def test_pending_doctor_blocks_phase_advance(env):
    s,p,phase=env;complete(env,task(env))
    state=loop.project(s,p.patient_id)
    loop.review_stage(s,p.patient_id,p.id,phase_id=phase.id,content=loop.stage_summary(state),actor='QA',medical=True)
    assert s.scalar(select(DoctorReview)).status=='PENDING'
    state=loop.project(s,p.patient_id);draft=loop.next_phase_draft(state)
    with pytest.raises(ValueError,match='医学判断'):
        loop.enter_next_phase(s,p.patient_id,p.id,phase.id,actor='QA',title=draft['title'],goal=draft['goal'],content=draft['content'],start=draft['start'],end=draft['end'],action='下一件')
    assert phase.status=='ACTIVE' and s.scalar(select(func.count(RiskEvent.id)))==0

def test_existing_log_creates_next_task(env):
    s,p,_=env
    row=workflow.record_log(s,p.patient_id,p.id,actor='QA',request_key=str(uuid4()),create_followup=True,occurred_at=datetime.now(timezone.utc),category='电话',member_issue='联系成员',manager_action='核对记录',result='已沟通',next_action='继续核对',follow_up_at=datetime.now(timezone.utc),owner='QA')
    assert loop.project(s,p.patient_id)['next'].record.id==row.follow_up_task_id

def test_service_result_remains_actionable_before_stage_review(env):
    from executive_health_ai.services.member_services import MemberServiceOperations
    s,p,phase=env;ops=MemberServiceOperations()
    catalog=ServiceCatalogItem(code='test-service',category='健康管理',name='合成沟通服务');s.add(catalog);s.flush()
    row=ops.request(s,p.patient_id,catalog.id,'合成服务','QA')
    workflow.link_service(s,p.patient_id,row.id,p.id,phase.id)
    assert loop.project(s,p.patient_id)['next'].kind=='SERVICE'
    ops.approve(s,row.id,'QA');ops.schedule(s,row.id,datetime.now(timezone.utc),'QA');ops.start(s,row.id,'QA')
    ops.complete(s,row.id,'已执行','QA',completion_evidence='合成服务确认',next_action='核对服务结果')
    state=loop.project(s,p.patient_id)
    assert not state['review_ready'] and state['next'].kind=='FOLLOWUP'
    complete(env,state['next'].record)
    assert loop.project(s,p.patient_id)['review_ready']

def workspace_page(member_id):
    from uuid import UUID
    from types import SimpleNamespace
    import streamlit as st
    from executive_health_ai.ui.pages.manager import action_loop
    from executive_health_ai.models import Patient
    with action_loop.SessionLocal() as session:
        patient=session.get(Patient,UUID(member_id))
        state=action_loop.service.project(session,patient.id)
    def navigate(**kwargs):st.session_state['test-screen']='management'
    app=SimpleNamespace(request_navigation=navigate)
    st.button('处理下一步',on_click=action_loop.open_next,args=(app,patient))
    if st.session_state.get('test-screen')=='management':action_loop.render(app,patient,state['view'])

def test_overview_button_opens_executable_detail(env,monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from streamlit.testing.v1 import AppTest
    from executive_health_ai.ui.pages.manager import action_loop
    s,p,phase=env;row=task(env);s.commit()
    monkeypatch.setattr(action_loop,'SessionLocal',sessionmaker(s.bind,expire_on_commit=False))
    app=AppTest.from_function(workspace_page,args=(str(p.patient_id),)).run()
    next(b for b in app.button if b.label=='处理下一步').click();app.run()
    assert not app.exception
    assert len([b for b in app.button if b.label=='完成本次处理'])==1
    assert any(t.label=='处理结果' for t in app.text_area)

def test_no_open_item_ui_keeps_every_quick_action(env,monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from streamlit.testing.v1 import AppTest
    from executive_health_ai.ui.pages.manager import action_loop
    s,p,phase=env;s.commit()
    monkeypatch.setattr(action_loop,'SessionLocal',sessionmaker(s.bind,expire_on_commit=False))
    app=AppTest.from_function(workspace_page,args=(str(p.patient_id),)).run()
    next(b for b in app.button if b.label=='处理下一步').click();app.run()
    assert not app.exception
    assert {'新增管理记录','创建随访','安排复查','申请服务','提交医生判断'} <= set(next(x for x in app.selectbox if x.label=='安排类型').options)

def test_cancelled_or_empty_phase_not_claimed_completed(env):
    s,p,phase=env;row=task(env);row.status='CANCELLED';s.flush()
    state=loop.project(s,p.patient_id)
    assert state['review_ready'] and not state['all_done']

def test_undated_open_task_blocks_phase_completion(env):
    s,p,phase=env;row=task(env);row.due_at=None;s.flush()
    assert not loop.project(s,p.patient_id)['review_ready']


def test_future_phase_work_does_not_bypass_stage_review(env):
    s,p,phase=env;complete(env,task(env))
    future=task(env,'下一阶段随访')
    future.due_at=datetime.combine(phase.end_date+timedelta(days=3),time(9),timezone.utc)
    s.flush();state=loop.project(s,p.patient_id)
    assert state['review_ready'] and state['next'] is None
    assert any(i.record.id==future.id for i in state['items'])
    loop.review_stage(s,p.patient_id,p.id,phase_id=phase.id,content=loop.stage_summary(state),actor='QA')
    state=loop.project(s,p.patient_id)
    assert state['state']=='NEXT_PHASE' and state['next'] is None
