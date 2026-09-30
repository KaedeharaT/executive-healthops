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
    dict(confirmation_name=''), dict(confirmation_name=' Synthetic V1 Member'),
    dict(confirmation_name='Synthetic V1 Member '), dict(role='MEMBER'), dict(expected_name='Someone else')])
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
    options=dict(expected_name=member.display_name,confirmation_name=member.display_name,actor='QA',role='ADMIN',confirmed=True)
    with pytest.raises(ValueError,match='正在运行'):
        MemberArchiveService().archive(s,member.id,**options)
    assert member.archived_at is None
    MemberArchiveService().archive(s,member.id,**options,stop_running=True)
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


def test_member360_routes_archived_member_to_readonly_detail(care, monkeypatch):
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
    from executive_health_ai.ui.pages.manager import member_delete
    readonly=Mock();monkeypatch.setattr(member_delete,'archived_detail',readonly)
    app.render_member_detail(member)
    detail.assert_not_called()
    readonly.assert_called_once()
    assert readonly.call_args.args[1].id==member.id
    assert app.st.session_state['focused_member_id']==str(member.id)


def test_archive_only_in_member360_header_with_one_directory_filter():
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
    assert not any(b.label in {'归档会员','删除成员'} for b in app.button)
    assert next(x for x in app.selectbox if x.label=='状态').options==['在管','已归档']
    select_table_row(app,prefix='member-directory-').run(timeout=45)
    assert len([b for b in app.button if b.label=='归档会员'])==1
    next(b for b in app.button if b.label=='归档会员').click().run(timeout=45)
    confirmation=next(b for b in app.button if b.label in {'确认归档','停止当前流程并归档'})
    assert confirmation.disabled
    assert not app.exception


@pytest.mark.parametrize('waiting',['WAITING_MANAGER','WAITING_DOCTOR','WAITING_TIME'])
def test_archive_preserves_identity_and_trace_and_suppresses_due_work(care,waiting):
    from datetime import timedelta
    from executive_health_ai.models import MemberAgent, HealthEvent, AgentGoal
    from executive_health_ai.models.base import utc_now
    from executive_health_ai.services.health_events import ingest_health_event
    from executive_health_ai.services.operational_worklist import OperationalWorklistService
    s,g,_=care
    g.status=waiting;s.commit()
    identity=s.scalar(select(MemberAgent).where(MemberAgent.member_id==g.member_id))
    identity_id=identity.id;wakes=identity.wake_count
    trace_ids=set(s.scalars(select(AgentRunTrace.id).where(AgentRunTrace.goal_id==g.id)))
    event,_=ingest_health_event(s,member_id=g.member_id,event_type='TIME_DUE',event_category='TIME_DUE',
        source_type='SYSTEM',source_id='future-followup',occurred_at=utc_now()+timedelta(days=2))
    s.commit()
    archive(s,g);s.commit()
    s.refresh(identity)
    assert identity.id==identity_id and identity.status=='IDLE' and identity.next_wake_at is None
    assert event.status=='IGNORED'
    assert trace_ids<=set(s.scalars(select(AgentRunTrace.id).where(AgentRunTrace.goal_id==g.id)))
    count=s.scalar(select(func.count(AgentGoal.id)))
    late,_=ingest_health_event(s,member_id=g.member_id,event_type='TIME_DUE',event_category='TIME_DUE',
        source_type='SYSTEM',source_id='late-followup')
    s.commit();s.refresh(identity)
    assert late.status=='IGNORED' and identity.wake_count==wakes
    assert s.scalar(select(func.count(AgentGoal.id)))==count
    assert all(i.member_id!=g.member_id for i in OperationalWorklistService().list_items(s,utc_now()))
    member=s.get(Patient,g.member_id)
    assert member_directory(s,[member],include_archived=True)[0]['member'].id==member.id


def test_running_identity_blocks_archive_even_without_running_goal(care):
    from executive_health_ai.models import MemberAgent
    s,g,_=care
    identity=s.scalar(select(MemberAgent).where(MemberAgent.member_id==g.member_id))
    identity.status='RUNNING';s.commit()
    with pytest.raises(ValueError,match='正在运行'):archive(s,g)
    archive(s,g,stop_running=True);s.commit()
    assert identity.status=='IDLE'


def test_archived_member_all_five_tabs_are_readonly(care,tmp_path,monkeypatch):
    """Render actual historical rows, not a mocked detail renderer."""
    import sqlite3
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from executive_health_ai.ui.pages.manager import member_delete
    from executive_health_ai.ui.pages.member import experience
    s,g,sup=care
    send_doctor(s,g,sup);s.commit()
    archive(s,g);s.commit()
    snapshot=tmp_path/'archived-ui.db'
    with sqlite3.connect(snapshot) as destination:
        s.connection().connection.driver_connection.backup(destination)
    engine=create_engine('sqlite:///'+snapshot.as_posix())
    sessions=sessionmaker(engine,expire_on_commit=False)
    monkeypatch.setattr(member_delete,'SessionLocal',sessions)
    monkeypatch.setattr(experience,'SessionLocal',sessions)
    app=AppTest.from_string('''
from executive_health_ai.ui.pages.manager import member_delete
from executive_health_ai.models import Patient
from sqlalchemy import select
from streamlit_app import _ui_adapter
with member_delete.SessionLocal() as session:
    patient=session.scalar(select(Patient).where(Patient.archived_at.is_not(None)))
    member_delete.archived_detail(_ui_adapter(),patient)
''').run(timeout=45)
    for section in ('概览','健康','管理','医疗','历程'):
        next(r for r in app.radio if r.label=='成员页面').set_value(section).run(timeout=45)
        assert not app.exception
        assert [b.label for b in app.button]==['← 返回会员']
        assert any('已归档' in i.value for i in app.info)
        if section=='医疗':
            assert any('意见' in table.value.columns for table in app.dataframe)
    engine.dispose()
