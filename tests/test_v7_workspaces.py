"""V7 navigation, one-action surfaces and real shared Agent presentation."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
from uuid import uuid4
import pytest
from streamlit.testing.v1 import AppTest
from test_management_action_loop import env,task,complete,loop

ROOT=Path(__file__).resolve().parents[1]


def panel_page(progress):
    from executive_health_ai.ui.agent_progress import AgentProgressPanel
    AgentProgressPanel.render(progress,flow_name='健康管理助手',next_action='核对实际资料')


@pytest.mark.parametrize('state',['PROCESSING','WAITING_MANAGER','WAITING_DOCTOR','COMPLETED','FAILED'])
def test_agent_panel_progress_and_waiting(state):
    from test_agent_progress import goal,steps,NOW,events
    from executive_health_ai.services.agent_progress import project
    p=project(goal(state,progress_events=events()),steps('RECEIVED','PARSING','MATCHING'),now=NOW)
    app=AppTest.from_function(panel_page,args=(p,)).run()
    assert not app.exception
    html=''.join(m.value for m in app.markdown)
    assert html.count('role="progressbar"')==1
    assert f'aria-valuenow="{p.progress_percent}"' in html
    assert ('aria-label="正在整理资料"' in html)==(state=='PROCESSING')
    assert '核对实际资料' in str([c.value for c in app.caption])


@pytest.mark.parametrize('label',['今日','成员','年度管理','服务运营','医疗协同','专项管理'])
def test_single_primary_cta_and_no_duplicate_buttons(label):
    app=AppTest.from_file(ROOT/'streamlit_app.py').run(timeout=45)
    next(r for r in app.radio if r.label=='工作区').set_value(label).run(timeout=45)
    assert not app.exception
    assert sum(b.proto.type=='primary' for b in app.button)<=1
    assert not any(b.label in {'查看会员','查看运行看板','进入该会员专项管理'} for b in app.button)


def test_annual_to_member360_management_preserves_period_and_clears_legacy_detail(monkeypatch):
    from executive_health_ai.ui.pages.manager import annual
    member=NS(id=uuid4());row=NS(id=uuid4(),member=member)
    state={f'workflow-mode-{member.id}':'年度方案与阶段',f'workflow-detail-{member.id}':True}
    monkeypatch.setattr(annual.st,'session_state',state);app=Mock()
    annual.open_member(app,row)
    app._open_member_management.assert_called_once_with(member.id)
    assert state[f'annual-program-{member.id}']==str(row.id)
    assert f'workflow-detail-{member.id}' not in state


def test_service_to_member_keeps_real_program_and_next_action(monkeypatch):
    from executive_health_ai.ui.pages.manager import services
    state={'ops-navigation':'服务运营'};monkeypatch.setattr(services.st,'session_state',state)
    request=NS(id=uuid4(),patient_id=uuid4(),program_id=uuid4());app=Mock()
    services.open_service_member(app,request)
    assert state[f'action-focus-{request.patient_id}']=='NEXT'
    assert state[f'annual-program-{request.patient_id}']==str(request.program_id)
    app._open_member_management.assert_called_once_with(request.patient_id)


def stage_page(member_id):
    from uuid import UUID
    from types import SimpleNamespace
    from executive_health_ai.ui.pages.manager import action_loop
    with action_loop.SessionLocal() as session:state=action_loop.service.project(session,UUID(member_id))
    action_loop.stage_detail(SimpleNamespace(id=UUID(member_id)),state)


def test_stage_review_next_phase_single_submit_is_atomic(env,monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from executive_health_ai.ui.pages.manager import action_loop,workflow
    s,p,phase=env;complete(env,task(env));s.commit()
    factory=sessionmaker(s.bind,expire_on_commit=False)
    for module in (action_loop,workflow):monkeypatch.setattr(module,'SessionLocal',factory)
    app=AppTest.from_function(stage_page,args=(str(p.patient_id),)).run()
    assert not app.exception
    assert [b.label for b in app.button if b.proto.type=='primary']==['确认并进入下一阶段']
    next(c for c in app.checkbox if c.label=='我已核对阶段结果，确认本次复盘').check()
    next(b for b in app.button if b.label=='确认并进入下一阶段').click().run()
    assert not app.exception
    s.expire_all();state=loop.project(s,p.patient_id)
    assert state['phase'].id!=phase.id and state['next'].title=='确认下一阶段执行安排'


def test_intake_exception_first_and_single_advanced_wizard():
    from tests.test_intake_workspace_v2 import archive_page,member
    app=AppTest.from_function(archive_page,args=(str(member()),)).run()
    assert not app.exception
    assert [e.label for e in app.expander].count('完整查看 / 手工修正')==1
    assert not any(r.label=='填写步骤' for r in app.selectbox)
    assert [b.label for b in app.button].count('查看完整健康档案')==1


def test_navigation_depth_and_member_row_entry():
    from tests.ui_selection import select_table_row
    app=AppTest.from_file(ROOT/'streamlit_app.py').run(timeout=45)
    next(r for r in app.radio if r.label=='工作区').set_value('成员').run(timeout=45)
    select_table_row(app,prefix='member-directory-').run(timeout=45)
    assert not app.exception
    assert next(r for r in app.radio if r.label=='成员页面').value=='概览'
    assert sum(b.label=='处理下一步' for b in app.button)==1
    assert not any(b.label=='查看运行看板' for b in app.button)


def test_management_current_action_and_no_legacy_button_forest(env,monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from executive_health_ai.ui.pages.manager import action_loop
    def workspace_page(member_id):
        from uuid import UUID
        from types import SimpleNamespace
        from executive_health_ai.ui.pages.manager import action_loop
        from executive_health_ai.models import Patient
        with action_loop.SessionLocal() as session:
            patient=session.get(Patient,UUID(member_id))
            state=action_loop.service.project(session,patient.id)
        action_loop.render(SimpleNamespace(),patient,state['view'])
    s,p,_=env;task(env)
    from tests.goal_loop_support import approved_program
    approved_program(s,p);s.commit()
    monkeypatch.setattr(action_loop,'SessionLocal',sessionmaker(s.bind,expire_on_commit=False))
    app=AppTest.from_function(workspace_page,args=(str(p.patient_id),)).run()
    assert not app.exception
    assert not any(b.label in {'新增管理记录','创建随访','安排复查','申请服务'} for b in app.button)
    assert {'新增管理记录','创建随访','安排复查','申请服务'}<=set(next(x for x in app.selectbox if x.label=='安排类型').options)


def test_doctor_has_single_submission_and_only_two_workspaces():
    app=AppTest.from_file(ROOT/'streamlit_app.py').run(timeout=45)
    next(r for r in app.radio if r.label=='当前视图').set_value('医生工作台').run(timeout=45)
    assert not app.exception
    assert next(r for r in app.radio if r.label=='医生工作').options==['待我判断','历史']
    assert not any(b.label in {'查看Agent','查看管理计划'} for b in app.button)
