"""Human work routing contracts over the existing business facts."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from sqlalchemy import select
from streamlit.testing.v1 import AppTest
from tests.test_post_checkup_care_v1 import care, send_doctor, judge
from tests.ui_selection import open_member, select_table_row
from executive_health_ai.models import Task, DoctorReview
from executive_health_ai.services.product_projection import ProductProjectionService
from executive_health_ai.ui.pages.manager.medical import medical_rows
from executive_health_ai.agent import post_checkup as flow

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'streamlit_app.py'


def queue(session):
    return ProductProjectionService().manager(session,datetime.now(timezone.utc)).items


def test_report_confirmation_has_one_responsibility_not_report_and_agent(care):
    s,g,_=care
    s.add(Task(patient_id=g.member_id,title='报告核对',instruction='核对报告',status='PENDING',priority='MEDIUM',
        assignee=g.owner,responsible_role='health_manager',source='member_report_upload:'+g.source_id,due_at=datetime.now(timezone.utc)))
    s.flush()
    items=queue(s)
    assert len([i for i in items if i.source_type=='post_checkup'])==1
    assert not [i for i in items if i.source_type=='report_review']
    item=next(i for i in items if i.source_type=='post_checkup')
    assert item.next_action=='确认 3 项健康变化' and item.reason=='已完成报告整理'


def test_wait_moves_to_doctor_home_and_returned_opinion_reenters_today(care):
    s,g,sup=care
    send_doctor(s,g,sup)
    assert not [i for i in queue(s) if i.source_type in {'post_checkup','doctor_review'}]
    rows=medical_rows(s,doctor=True)
    assert len(rows)==1 and rows[0]['record'].id==s.scalar(select(DoctorReview.id))
    assert rows[0]['source']=='体检后健康管理'
    original=g.id
    judge(s,g)
    assert not medical_rows(s,doctor=True)
    returned=next(i for i in queue(s) if i.source_type=='post_checkup')
    assert returned.source_id==original and returned.title=='医生意见已返回'
    assert returned.reason=='已整理成 3 项行动' and returned.next_action=='确认后续行动'


def test_completion_replaces_confirmation_with_real_execution_work(care):
    s,g,sup=care;send_doctor(s,g,sup);judge(s,g)
    flow.approve_actions(sup,s,g,actions=g.context_json['actions'],actor=g.owner,role='HEALTH_MANAGER')
    items=queue(s)
    assert not [i for i in items if i.source_type=='post_checkup']
    tasks=list(s.scalars(select(Task)))
    assert len(tasks)==3 and all(t.assignee and t.due_at for t in tasks)
    assert any(i.source_id in {t.id for t in tasks} for i in items)


def test_running_goal_is_not_a_false_manager_confirmation(care):
    s,g,_=care;g.status='RUNNING';g.current_stage='ANALYZING';s.flush()
    assert not [i for i in queue(s) if i.source_type=='post_checkup']


def test_log_followup_is_findable_before_due_date_and_today_filter_stays_precise(care):
    from executive_health_ai.services.management_workflow import ManagementWorkflowService
    from executive_health_ai.models import HealthProgram
    from executive_health_ai.ui.presentation import work_filter
    s,g,_=care
    program=s.scalar(select(HealthProgram).where(HealthProgram.patient_id==g.member_id))
    now=datetime.now(timezone.utc)
    log=ManagementWorkflowService().record_log(s,g.member_id,program.id,actor=g.owner,
        request_key='v5-log-followup',create_followup=True,occurred_at=now,category='电话',channel='电话',
        member_issue='确认复查意向',manager_action='核对预约时间',result='会员同意',
        next_action='确认复查预约时间',follow_up_at=now+timedelta(days=5),owner=g.owner)
    items=queue(s)
    assert any(i.source_id==log.follow_up_task_id for i in items)
    assert not any(i.source_id==log.follow_up_task_id for i in work_filter(items,'今天',now))


def test_full_work_queue_remains_searchable_beyond_the_legacy_preview_limit(care):
    s,g,_=care
    tasks=[Task(patient_id=g.member_id,title=f'后续安排 {i}',instruction='按期联系会员',
        status='PENDING',assignee=g.owner,responsible_role='health_manager',source=f'v5-batch-{i}',
        due_at=datetime.now(timezone.utc)+timedelta(days=5)) for i in range(152)]
    s.add_all(tasks);s.flush()
    assert {t.id for t in tasks} <= {i.source_id for i in queue(s)}


def test_assistant_remains_visible_without_active_flows():
    app=AppTest.from_file(APP).run(timeout=45)
    assert not app.exception
    assert any(h.value=='健康管理助手' for h in app.subheader)
    assert any('当前没有需要您处理的自动流程' in c.value for c in app.caption)
    assert not any(x.label in {'键盘选择','使用下拉选择','完整标题','Agent模式'} for x in app.checkbox)


def test_annual_row_opens_the_single_member_management_surface():
    app=AppTest.from_file(APP).run(timeout=45)
    next(r for r in app.radio if r.label=='工作区').set_value('年度管理');app.run(timeout=45)
    select_table_row(app).run(timeout=45)
    assert not app.exception
    tabs=next(r for r in app.radio if r.label=='成员页面')
    assert len(tabs.options)==5 and tabs.value=='管理'
    assert any(b.label=='← 返回年度管理' for b in app.button)


def test_member_row_and_medical_record_share_member_context():
    app=AppTest.from_file(APP).run(timeout=45)
    next(r for r in app.radio if r.label=='工作区').set_value('成员');app.run(timeout=45)
    open_member(app).run(timeout=45)
    identity=app.session_state['focused_member_id']
    next(r for r in app.radio if r.label=='成员页面').set_value('医疗');app.run(timeout=45)
    assert not app.exception and app.session_state['focused_member_id']==identity
    assert not any(b.label=='提交判断' for b in app.button)
    assert len(next(r for r in app.radio if r.label=='成员页面').options)==5


def test_doctor_has_two_surfaces_and_no_business_module_navigation():
    app=AppTest.from_file(APP).run(timeout=45)
    next(r for r in app.radio if r.label=='当前视图').set_value('医生工作台');app.run(timeout=45)
    assert not app.exception
    nav=next(r for r in app.radio if r.label=='医生工作')
    assert nav.options==['待我判断','历史'] and nav.value=='待我判断'
    assert not any(r.label=='工作区' for r in app.radio)
