"""Render contracts plus identity/navigation checks, using actual care records."""
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import sessionmaker
from streamlit.testing.v1 import AppTest

from test_post_checkup_care_v1 import send_doctor, judge
from executive_health_ai.agent import post_checkup as flow
from executive_health_ai.models import AgentGoal


@pytest.fixture
def care(tmp_path, monkeypatch):
    from datetime import date, timedelta
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from executive_health_ai.models import Base
    from executive_health_ai.services.management_workflow import ManagementWorkflowService
    from executive_health_ai.services.report_parsing import ReportParsingService
    from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
    monkeypatch.setenv('LOCAL_LLM_ENABLED', 'false')
    engine=create_engine('sqlite:///'+(tmp_path/'render.db').as_posix())
    Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as session:
        program=ManagementWorkflowService().enroll(session,name='Synthetic visibility member',
            start=date.today(),end=date.today()+timedelta(days=364),owner='王健管',goal='年度管理')
        parser=ReportParsingService();parser.storage_root=tmp_path
        report,_,_=parser.upload_and_parse(session,program.patient_id,'visibility.txt',
            ('体检日期：'+date.today().isoformat()+'\n谷丙转氨酶  56 U/L\n体重  85.8 kg').encode(),'王健管')
        goal=session.scalar(select(AgentGoal).where(AgentGoal.source_id==str(report.id)))
        session.commit()
        yield session,goal,HealthOpsAgentSupervisor()
    engine.dispose()


def page(member_id, surface):
    import streamlit as st
    from sqlalchemy import select
    from uuid import UUID
    from types import SimpleNamespace
    from executive_health_ai.ui.pages.manager import assistant, post_checkup
    from executive_health_ai.models import Patient, AgentGoal
    def navigate(**kwargs):
        st.session_state['destination'] = kwargs
    app = SimpleNamespace(request_navigation=navigate, _member_display=lambda p:p.display_name if p else '会员')
    with assistant.SessionLocal() as session:
        member = session.get(Patient, UUID(member_id))
        goal = session.scalar(select(AgentGoal))
    if surface == 'today':
        assistant.assistant(app, {member.id:member})
    elif surface == 'member':
        post_checkup.compact_member_status(member.id)
    elif surface == 'support':
        from executive_health_ai.services.agent_capabilities import load
        from executive_health_ai.ui.pages.manager.ai_support import panel
        with assistant.SessionLocal() as session:
            activities, _ = load(session, goal)
        panel(goal, activities)


@pytest.fixture
def rendered(care, monkeypatch):
    from executive_health_ai.ui.pages.manager import assistant, post_checkup, care_activity, profile_intake
    session, goal, sup = care
    factory = sessionmaker(session.bind, expire_on_commit=False)
    for module in (assistant, post_checkup, care_activity, profile_intake):
        monkeypatch.setattr(module, 'SessionLocal', factory)
    def render(surface='today'):
        session.commit()
        app = AppTest.from_function(page, args=(str(goal.member_id),surface)).run()
        assert not app.exception
        return app
    return session, goal, sup, render


def text(app):
    return '\n'.join(str(e.value) for kind in ('subheader','markdown','caption','info') for e in getattr(app,kind))


@pytest.mark.parametrize('state', ['WAITING_MANAGER','WAITING_DOCTOR','COMPLETED','NONE'])
def test_today_assistant_always_renders(rendered, state):
    session, goal, sup, render = rendered
    if state in {'WAITING_DOCTOR','COMPLETED'}:
        send_doctor(session,goal,sup)
    if state == 'COMPLETED':
        judge(session,goal)
        flow.approve_actions(sup,session,goal,actions=goal.context_json['actions'],actor='王健管',role='HEALTH_MANAGER')
    if state == 'NONE':
        session.delete(goal)
    app=render()
    assert '健康管理助手' in text(app)
    assert all(label in text(app) for label in ('正在运行','等待我确认','等待医生','最近完成'))
    if state in {'COMPLETED','NONE'}:
        assert '当前没有需要您处理的自动流程。' in text(app)
        assert bool(app.selectbox) == (state!='NONE')
    else:
        assert any(b.label=='查看完整运行' and not b.disabled for b in app.button)
        assert ('等待医生' if state=='WAITING_DOCTOR' else '等待我确认') in text(app)


def test_completed_member_keeps_automatic_followup_and_same_instance(rendered):
    session,goal,sup,render=rendered
    send_doctor(session,goal,sup);judge(session,goal)
    flow.approve_actions(sup,session,goal,actions=goal.context_json['actions'],actor='王健管',role='HEALTH_MANAGER')
    app=render('member')
    assert '自动跟进' in text(app) and '已完成' in text(app)
    assert '最近结果' in text(app)
    assert not app.button
    app=render('today')
    next(b for b in app.button if b.label=='查看完整运行').click().run()
    assert app.session_state['care-detail']==str(goal.id)
    assert app.session_state['care-origin']=='今日工作'
    assert session.scalar(select(func.count(AgentGoal.id)))==1


def test_today_and_member_links_open_same_goal_without_creating_one(rendered):
    session,goal,sup,render=rendered
    for surface in ('today','today'):
        app=render(surface)
        next(b for b in app.button if b.label=='查看完整运行').click().run()
        assert app.session_state['care-detail']==str(goal.id)
    assert session.scalar(select(func.count(AgentGoal.id)))==1


def test_member_without_goals_keeps_honest_empty_followup(rendered):
    session,goal,sup,render=rendered
    session.delete(goal)
    app=render('member')
    assert '自动跟进' in text(app) and '暂无自动流程' in text(app)
    assert not app.button


def test_support_panel_reflects_real_calls_and_unused_model(rendered):
    session,goal,sup,render=rendered
    app=render('support')
    assert 'AI与知识支持' in text(app) and '知识依据检索' in text(app)
    assert '暂无匹配' in text(app) and '暂不可用' in text(app)
    assert '未使用：本步骤没有已发起的调用记录。' in text(app)
    assert '尚未执行' in text(app)


def test_sidebar_callback_clears_nested_selections_without_touching_management(monkeypatch):
    from executive_health_ai.ui.pages.manager import experience
    state={'care-detail':'goal','care-origin':'会员360','today-detail':('task','old'),
           'action-focus-member':'TASK:keep','workflow-mode-member':'管理事项'}
    monkeypatch.setattr(experience.st,'session_state',state)
    experience.reset_today_selection()
    assert not {'care-detail','care-origin','today-detail'} & state.keys()
    assert state['action-focus-member']=='TASK:keep' and state['workflow-mode-member']=='管理事项'
    assert state['today-work-grid-epoch']==1


def test_today_previews_at_most_three_real_active_workflows(rendered, tmp_path):
    from datetime import date
    from executive_health_ai.services.report_parsing import ReportParsingService
    session,goal,sup,render=rendered
    parser=ReportParsingService();parser.storage_root=tmp_path
    for index in range(3):
        parser.upload_and_parse(session,goal.member_id,f'additional-{index}.txt',
            ('体检日期：'+date.today().isoformat()+f'\n体重  {70+index} kg').encode(),'王健管')
    app=render()
    assert session.scalar(select(func.count(AgentGoal.id)))==4
    assert len([b for b in app.button if b.label=='查看完整运行'])==1
    assert len(app.selectbox[0].options)==4


def test_profile_followup_progress_reads_same_existing_plan(rendered, tmp_path):
    import json
    from executive_health_ai.services.profile_ingestion import ProfileIngestionService
    from executive_health_ai.ui.pages.manager.profile_intake import progress_steps
    session,goal,sup,render=rendered
    ingestion=ProfileIngestionService();ingestion.storage_root=tmp_path
    profile,_=ingestion.upload(session,goal.member_id,'问卷.json',json.dumps({
        'responses':{'生活方式':{'睡眠':'每天七小时'}}},ensure_ascii=False).encode(),
        'questionnaire',actor='王健管',role='HEALTH_MANAGER')
    for _ in range(5):
        if profile.status!='RUNNING':break
        sup.execute_next_step(session,profile.id)
    session.commit()
    done=[label for label,completed,_ in progress_steps(profile) if completed]
    assert done and profile.status=='WAITING_MANAGER'
    app=render('member')
    assert '资料整理' in text(app)
    assert not app.button
    app=render('today')
    app.selectbox[0].select_index(0).run()
    next(b for b in app.button if b.label=='查看完整运行').click().run()
    assert app.session_state[f'intake-workspace-goal-{goal.member_id}']==str(profile.id)
