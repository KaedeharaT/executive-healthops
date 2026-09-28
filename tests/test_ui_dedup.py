"""User-purpose/context regressions for the deduplicated HealthOps paths."""
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock
import pytest
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[1]


def test_member_row_is_only_open_action_and_return_does_not_reopen():
    from tests.ui_selection import select_table_row
    app=AppTest.from_file(ROOT/'streamlit_app.py').run(timeout=45)
    next(r for r in app.radio if r.label=='工作区').set_value('成员').run(timeout=45)
    for _ in range(2):
        assert len([x for x in app.text_input if x.label=='搜索成员'])==1
        assert len([x for x in app.selectbox if x.label=='负责人'])==1
        assert not any(b.label=='查看会员 / 进入Member360' for b in app.button)
        app.run(timeout=45)
    select_table_row(app,prefix='member-directory-').run(timeout=45)
    assert next(r for r in app.radio if r.label=='成员页面').value=='概览'
    assert not any(b.label=='删除成员' for b in app.button)
    next(b for b in app.button if b.label=='← 返回会员').click().run(timeout=45)
    assert not app.exception
    assert any(x.label=='搜索成员' for x in app.text_input)
    app.run(timeout=45)
    assert any(x.label=='搜索成员' for x in app.text_input)


def test_member_and_annual_destinations_preserve_distinct_context(monkeypatch):
    from executive_health_ai.ui.pages.manager import workbench,annual
    state={};monkeypatch.setattr(workbench.st,'session_state',state)
    member=SimpleNamespace(id=uuid4());program=SimpleNamespace(id=uuid4(),member=member)
    app=Mock()
    workbench.open_directory_member(app,member)
    assert app.request_navigation.call_args.kwargs['member_section']=='概览'
    assert app.request_navigation.call_args.kwargs['member_id']==member.id
    assert state['member-return-origin']=='会员'
    annual.open_member(app,program)
    app._open_member_management.assert_called_once_with(member.id)
    assert state['member-return-origin']=='年度管理'
    assert state[f'annual-program-{member.id}']==str(program.id)


def test_same_intake_agent_instance_from_today_and_member_context(monkeypatch):
    from executive_health_ai.ui.pages.manager import assistant,profile_intake
    state={};monkeypatch.setattr(assistant.st,'session_state',state)
    goal=SimpleNamespace(id=uuid4(),member_id=uuid4(),goal_type='PROFILE_INTAKE');app=Mock()
    assistant.open_care(app,goal,'今日工作')
    assert state[f'intake-workspace-goal-{goal.member_id}']==str(goal.id)
    assert state['member-return-origin']=='今日工作'
    assert app.request_navigation.call_args.kwargs['member_section']=='健康'
    profile_intake.open_board(app,goal)
    assert state[f'intake-workspace-goal-{goal.member_id}']==str(goal.id)
    assert 'care-detail' not in state


def test_admin_profile_board_reuses_foreground_renderer(monkeypatch):
    from executive_health_ai.ui.pages.manager import operations_board,intake_workspace
    from executive_health_ai.services import intake_workspace as projection,agent_capabilities
    goal=SimpleNamespace(id=uuid4(),member_id=uuid4(),goal_type='PROFILE_INTAKE',context_json={'intake_id':str(uuid4())})
    from executive_health_ai.services import management_workflow
    assessment=SimpleNamespace(id=goal.context_json['intake_id'])
    monkeypatch.setattr(management_workflow,'owned',Mock(return_value=assessment))
    data={'same_goal':goal.id};project=Mock(return_value=data);draw=Mock()
    monkeypatch.setattr(projection,'project',project);monkeypatch.setattr(intake_workspace,'draw',draw)
    # V7 uses the shared design tokens; the removed local styles renderer is not
    # part of this reuse contract. Keep verifying the actual board and goal.
    monkeypatch.setattr(agent_capabilities,'load',Mock(return_value=([],[])))
    operations_board.render(None,goal,admin=True)
    assert project.call_args.args[1:]==(goal.member_id,assessment,str(goal.id))
    draw.assert_called_once_with(data)


def empty_trend():
    import streamlit as st
    from executive_health_ai.ui.pages.health_visualization import render_previews
    def opened():st.session_state['target']='健康数据'
    render_previews('synthetic',key='dedup-empty',series=[],shared_action=True,open_trend=opened)


def test_duplicate_action_regression_empty_trend_has_one_reachable_entry():
    app=AppTest.from_function(empty_trend).run()
    assert [b.label for b in app.button]==['查看健康变化']
    app.button[0].click().run()
    assert app.session_state['target']=='健康数据' and not app.exception


def completed_cards():
    from types import SimpleNamespace
    from executive_health_ai.ui.pages.manager.intake_workspace import cards
    row=SimpleNamespace(status='CONFIRMED',review_status='CONFIRMED',responses={},review={})
    cards(SimpleNamespace(id='synthetic'),SimpleNamespace(intake=row),
        {'stats':dict(percent=100,prefilled=1,pending=0,missing=0,conflicts=0),'sections':[]})


def test_completed_assessment_has_one_readonly_entry_and_keeps_amend():
    app=AppTest.from_function(completed_cards).run()
    assert not app.exception
    assert [b.label for b in app.button]==['查看评估','补充/修正']


def stage_and_following():
    import streamlit as st
    from types import SimpleNamespace
    from executive_health_ai.ui.pages.manager.action_loop import quick_actions,stage_prompt
    p=SimpleNamespace(id='synthetic')
    st.button('继续安排复查',type='primary')
    quick_actions(p,exclude={'安排复查'})
    stage_prompt(p,dict(review=True),primary=False)


def test_single_primary_cta_and_no_duplicate_following_action():
    app=AppTest.from_function(stage_and_following).run()
    assert not app.exception
    assert len([b for b in app.button if b.proto.type=='primary'])==1
    assert '安排复查' not in [b.label for b in app.button]
    assert {'创建随访','申请服务','提交医生判断'}<=set(app.selectbox[0].options)
    assert '安排复查' not in app.selectbox[0].options
    assert '进入下一阶段' in {b.label for b in app.button}


@pytest.mark.parametrize('old,new',[('系统','数据与集成'),('集成与数据','数据与集成'),('自动化运营','自动化运行'),('风险规则','规则与知识'),('专业资料','规则与知识'),('操作记录','系统状态')])
def test_legacy_navigation_has_no_dead_end_or_duplicate_menu(monkeypatch,old,new):
    from executive_health_ai.ui.pages import support_navigation
    state={'more-navigation':old};monkeypatch.setattr(support_navigation.st,'session_state',state)
    app=Mock();support_navigation.render_support_directory(app)
    assert state['ux-admin-navigation']==new and 'more-navigation' not in state
    if old in {'风险规则','专业资料'}:
        assert state['admin-knowledge-mode']==('专业知识' if old=='专业资料' else '规则')
    app.request_navigation.assert_called_once_with(surface='系统管理')
