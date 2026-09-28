from pathlib import Path
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from streamlit.testing.v1 import AppTest
from executive_health_ai.models import Patient, AuditLog, DoctorReview, AgentRunTrace, Base
from executive_health_ai.services.member_archive import MemberArchiveService, require_active, active_ids
from executive_health_ai.services.information_presentation import member_directory
from test_post_checkup_care_v1 import care, send_doctor
from test_profile_intake import env, upload


def archive(s, g, **kwargs):
    options = dict(expected_name='Synthetic V1 Member', confirmation_name='Synthetic V1 Member',
                   actor='王健管', role='HEALTH_MANAGER', confirmed=True)
    options.update(kwargs)
    return MemberArchiveService().archive(s, g.member_id, **options)


@pytest.mark.parametrize('options', [dict(confirmed=False), dict(confirmation_name='wrong'),
    dict(confirmation_name=''), dict(role='MEMBER'), dict(expected_name='Someone else')])
def test_requires_exact_identity_and_confirmation(care, options):
    s,g,_=care
    with pytest.raises((ValueError, PermissionError)):
        archive(s,g,**options)
    s.rollback()
    assert s.get(Patient,g.member_id).archived_at is None


def test_archive_retains_every_historical_row_and_stops_agent_truthfully(care):
    s,g,sup=care
    send_doctor(s,g,sup);s.commit()
    before={t.name:s.scalar(select(func.count()).select_from(t)) for t in Base.metadata.sorted_tables}
    doctor=s.scalar(select(DoctorReview));status=doctor.status
    archive(s,g);s.commit()
    assert g.status=='CANCELLED' and g.automation_paused and g.next_check_at is None
    assert g.completed_at is None and doctor.status==status
    for table in Base.metadata.sorted_tables:
        assert s.scalar(select(func.count()).select_from(table)) >= before[table.name]
    assert s.scalar(select(AuditLog).where(AuditLog.action=='member_archived'))
    assert s.scalar(select(AgentRunTrace).where(AgentRunTrace.action=='member_archived'))
    assert not member_directory(s,[s.get(Patient,g.member_id)])
    assert g.member_id not in list(s.scalars(active_ids()))
    with pytest.raises(ValueError):require_active(s,g.member_id)
    assert sup.execute_next_step(s,g.id).status=='CANCELLED'


def test_other_member_unaffected_and_stale_writes_rejected(care):
    s,g,_=care
    other=Patient(external_id='archive-other',display_name='Other',timezone='Asia/Shanghai');s.add(other);s.commit()
    with Session(s.bind) as stale:
        old=stale.get(Patient,g.member_id)
        archive(s,g);s.commit()
        old.display_name='late mutation'
        with pytest.raises(ValueError,match='归档'):stale.commit()
        stale.rollback()
    assert s.get(Patient,other.id).archived_at is None
    other.display_name='Still editable';s.commit()


def test_archive_requires_service_and_can_be_rolled_back(care):
    s,g,_=care
    member=archive(s,g);s.rollback()
    assert s.get(Patient,g.member_id).archived_at is None
    assert g.status=='WAITING_MANAGER'
    member=archive(s,g);s.commit()
    member.archived_at=None
    with pytest.raises(ValueError):s.flush()
    s.rollback()


def test_tasks_and_late_events_do_not_become_completed(care):
    from executive_health_ai.models import Task, AgentGoal, AgentEvent
    from executive_health_ai.services.event_service import EventService
    s,g,sup=care
    task=Task(patient_id=g.member_id,title='Pending',instruction='Synthetic',source='manual')
    s.add(task);s.commit()
    prior_events=list(s.scalars(select(AgentEvent)))
    history=[(e.status,e.processed_at,dict(e.metadata_json or {})) for e in prior_events]
    archive(s,g);s.commit()
    for old,expected in zip(prior_events,history):
        assert sup.receive_event(s,old) is None
        assert (old.status,old.processed_at,old.metadata_json)==expected
    assert task.status=='CANCELLED' and task.completed_at is None
    count=s.scalar(select(func.count()).select_from(AgentGoal))
    event,_=EventService().publish(s,event_type='REPORT_UPLOADED',member_id=g.member_id,
        source_type='report',source_id='late-archive-report')
    assert event.status=='IGNORED'
    assert sup.receive_event(s,event) is None
    s.commit()
    receipt_time=event.processed_at
    assert sup.receive_event(s,event) is None
    assert event.processed_at==receipt_time
    assert s.scalar(select(func.count()).select_from(AgentGoal))==count
    task.status='COMPLETED'
    with pytest.raises(ValueError):s.flush()
    s.rollback()


def test_running_profile_agent_cannot_continue_after_archive(env):
    s,member,sup=env
    goal=upload(env);s.commit()
    assert goal.status=='RUNNING'
    MemberArchiveService().archive(s,member.id,expected_name=member.display_name,
        confirmation_name=member.display_name,actor='QA',role='ADMIN',confirmed=True)
    s.commit()
    assert sup.execute_next_step(s,goal.id).status=='CANCELLED'
    assert goal.completed_at is None
    assert not goal.success_criteria.get('profile_confirmed')


def test_archived_excluded_from_annual_today_and_medical_work(care):
    from executive_health_ai.services.annual_portfolio import load
    from executive_health_ai.services.operational_worklist import OperationalWorklistService
    from executive_health_ai.services.product_projection import pending_doctor_work
    from executive_health_ai.models.base import utc_now
    s,g,sup=care
    send_doctor(s,g,sup);s.commit()
    archive(s,g);s.commit()
    assert all(row.member.id!=g.member_id for row in load(s))
    assert all(row.member_id!=g.member_id for row in OperationalWorklistService().list_items(s,utc_now()))
    assert not pending_doctor_work(s,g.member_id)


def test_member360_rejects_archived_member_before_detail_render(care, monkeypatch):
    import streamlit_app as app
    from unittest.mock import Mock
    s,g,_=care
    member=archive(s,g);s.commit()
    from contextlib import nullcontext
    detail=Mock();monkeypatch.setattr(app.manager_pages,'member_detail',detail)
    monkeypatch.setattr(app,'SessionLocal',lambda:nullcontext(s))
    monkeypatch.setattr(app.st,'session_state',{'focused_member_id':str(member.id)})
    monkeypatch.setattr(app.st,'info',Mock())
    monkeypatch.setattr(app,'_members',lambda:[])
    listing=Mock();monkeypatch.setattr(app,'render_members_workspace',listing)
    app.render_member_detail(member)
    detail.assert_not_called()
    listing.assert_called_once_with([])
    assert 'focused_member_id' not in app.st.session_state


def test_member_page_has_one_filter_and_explicit_secondary_delete():
    from tests.ui_selection import select_table_row
    app=AppTest.from_file(Path(__file__).resolve().parents[1]/'streamlit_app.py').run(timeout=45)
    next(r for r in app.radio if r.label=='工作区').set_value('成员').run(timeout=45)
    for _ in range(2):
        assert not app.exception
        assert len([x for x in app.text_input if x.label=='搜索成员'])==1
        assert len([x for x in app.selectbox if x.label=='状态'])==1
        assert len([x for x in app.selectbox if x.label=='负责人'])==1
        app.run(timeout=45)
    app.session_state['workflow-flash']='已保存，测试页面首次进入时带业务反馈。'
    app.run(timeout=45)
    assert len([x for x in app.text_input if x.label=='搜索成员'])==1
    app.run(timeout=45)
    assert len([x for x in app.text_input if x.label=='搜索成员'])==1
    next(s for s in app.selectbox if s.label=='管理会员档案').select_index(0).run(timeout=45)
    assert any(b.label=='删除成员' for b in app.button)
    assert not any(b.label=='查看会员 / 进入Member360' for b in app.button)
    next(b for b in app.button if b.label=='删除成员').click().run(timeout=45)
    assert next(b for b in app.button if b.label=='确认删除').disabled
    # Native dialog fragment reruns (wrong name, cancel, confirm) are exercised
    # by qa_member_delete.py in Chromium; AppTest only supports whole-app reruns.
    assert not app.exception
