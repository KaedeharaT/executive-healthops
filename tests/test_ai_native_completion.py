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
