from datetime import timedelta
from decimal import Decimal
import importlib.util
from pathlib import Path
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, select, func, event
from sqlalchemy.orm import Session
from executive_health_ai.models import Base, HealthEvent, Observation, RawData, DoctorReview
from executive_health_ai.services.longitudinal_timeline import LongitudinalTimelineProjection as Projection
from executive_health_ai.services.care_episodes import link_care_episode

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('timeline_qa',ROOT/'scripts/seed_longitudinal_timeline_qa.py')
seed=importlib.util.module_from_spec(spec);spec.loader.exec_module(seed)


@pytest.fixture
def data():
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        records=seed.seed_story(session);session.commit()
        yield session,records
    engine.dispose()


def view(data,**kwargs):
    db,r=data
    return Projection().build(db,r['member'].id,now=r['now'],**kwargs)


def one(v,kind):return next(e for e in v.entries if e.entry_type==kind)


def test_timeline_projection_chronological(data):
    v=view(data)
    assert [e.occurred_at for e in v.entries]==sorted(e.occurred_at for e in v.entries)
    assert len(v.entries)>=10


@pytest.mark.parametrize('kind,track',[
    ('ANNUAL_BASELINE','HEALTH_STATE'),('CURRENT_STATE','HEALTH_STATE'),('MEANINGFUL_CHANGE','HEALTH_STATE'),
    ('GOAL_CONFIRMED','CARE_ACTION'),('CARE_CONTACT','CARE_ACTION'),('DOCTOR_DECISION','CARE_ACTION'),
    ('PHASE_REVIEW','CARE_ACTION'),('OUTCOME','HEALTH_STATE')])
def test_node_track(data,kind,track):assert one(view(data),kind).track==track


def test_routine_raw_observation_not_visible_as_main_node(data):
    v=view(data)
    assert not any(e.entry_type in {'OBSERVATION','DAILY_SUMMARY','RAW'} for e in v.entries)
    assert data[0].scalar(select(func.count()).select_from(RawData))>len(v.entries)


def test_goal_and_risk_association(data):
    e=one(view(data),'MEANINGFUL_CHANGE')
    assert e.goal_id==str(data[1]['goal'].id) and e.risk_level=='YELLOW'
    assert e.details['change']['today']=='324'


@pytest.mark.parametrize('kind',['CARE_CONTACT','DOCTOR_DECISION','RECHECK','PHASE_REVIEW','PLAN_ADJUSTMENT'])
def test_care_actions_linked_to_trigger(data,kind):
    v=view(data)
    assert one(v,kind).care_episode_id==one(v,'MEANINGFUL_CHANGE').care_episode_id


def test_outcome_linked_without_invented_causality(data):
    v=view(data);change=one(v,'MEANINGFUL_CHANGE');episode=v.episodes[change.care_episode_id]
    assert len(episode.outcome_ids)==1 and episode.outcome_status=='改善'
    detail=Projection().details(data[0],v,change.entry_id)
    assert any(e.entry_type=='DOCTOR_DECISION' for e in detail['related'])
    weight=next(e for e in v.entries if e.entry_type=='OUTCOME' and '体重' in e.summary)
    assert weight.care_episode_id is None


def test_pending_outcome_visible(data):
    db,r=data
    second=HealthEvent(member_id=r['member'].id,event_type='MEANINGFUL_CHANGE',event_category='MEANINGFUL_CHANGE',
        occurred_at=r['now']-timedelta(hours=1),source='test',source_type='SYSTEM',source_id=str(uuid4()),description='另一个未处理变化',
        payload_ref={'change':{'metric':'weight','today':'81.2'}})
    db.add(second);db.flush();v=view(data)
    assert v.episodes['change:'+str(second.id)].outcome_status=='结果待观察'


def test_result_before_doctor_decision_is_not_its_later_outcome(data):
    v=view(data);detail=Projection().details(data[0],v,one(v,'DOCTOR_DECISION').entry_id)
    assert detail['outcome']=='结果待观察' and not detail['outcomes']
    assert Projection().details(data[0],v,one(v,'CARE_CONTACT').entry_id)['outcome']=='改善'


def test_raw_provenance_accessible(data):
    v=view(data);e=one(v,'MEANINGFUL_CHANGE');details=Projection().details(data[0],v,e.entry_id)
    assert any('324 min' in s['original'] for s in details['sources'])


def test_current_state_progress_and_week_summary(data):
    e=one(view(data),'CURRENT_STATE')
    assert e.snapshot.metric_summary['weight']['delta']=='-4.8'
    assert e.details['progress']['percent']==96
    assert '6.2' in e.details['sleep_week'] and '10-15' in e.details['next']


def test_projection_readonly_no_llm_or_raw_scan(data):
    db,r=data;statements=[]
    def capture(conn,cursor,statement,parameters,context,executemany):statements.append(statement)
    event.listen(db.bind,'before_cursor_execute',capture)
    try:v=view(data)
    finally:event.remove(db.bind,'before_cursor_execute',capture)
    assert v.entries
    assert not any(s.lstrip().upper().startswith(('INSERT','UPDATE','DELETE')) for s in statements)
    assert not any('FROM raw_data' in s for s in statements)
    source=(ROOT/'src/executive_health_ai/services/longitudinal_timeline.py').read_text(encoding='utf8')
    assert 'import httpx' not in source and 'from executive_health_ai.llm' not in source


def test_daily_summary_snapshot_reuses_version_without_main_node(data):
    db,r=data;s=Projection().daily_snapshot(db,r['member'].id,r['now'].date())
    assert s.snapshot_type=='DAILY_SUMMARY' and s.version==2
    assert s.metric_summary['sleep_duration']['value']=='372.000'


def test_timeline_empty_state(data):
    db,r=data;v=Projection().build(db,r['empty'].id,now=r['now'])
    assert v.empty and not v.entries


def test_draft_doctor_opinion_is_not_public(data):
    db,r=data
    db.add(DoctorReview(patient_id=r['member'].id,health_problem_id=r['doctor'].health_problem_id,doctor_name='未确认',
        department='全科',doctor_brief='draft',question_for_doctor='draft',opinion='不可展示的草稿',status='DRAFT'))
    db.flush();assert not any('不可展示' in e.summary for e in view(data).entries)


def test_episode_references_reject_cross_member_and_unauthorized_actor(data):
    db,r=data
    for role in ('MEMBER','AUTO'):
        with pytest.raises(PermissionError):link_care_episode(db,r['member'].id,r['change'].id,links=[],actor='test',role=role)
    with pytest.raises(ValueError):link_care_episode(db,r['empty'].id,r['change'].id,links=[],actor='test',role='HEALTH_MANAGER')


def test_episode_receipts_idempotent_and_versioned(data):
    db,r=data;before=db.scalar(select(func.count()).select_from(HealthEvent).where(HealthEvent.event_type=='CARE_EPISODE_LINK'))
    a=link_care_episode(db,r['member'].id,r['change'].id,links=[{'type':'DoctorReview','id':str(r['doctor'].id)}],actor='林健管',role='HEALTH_MANAGER')
    b=link_care_episode(db,r['member'].id,r['change'].id,links=[{'type':'Observation','id':str(r['observation'].id)}],actor='林健管',role='HEALTH_MANAGER')
    assert b.payload_ref['version']==a.payload_ref['version']+1 and b.payload_ref['supersedes']==str(a.id)
    assert db.scalar(select(func.count()).select_from(HealthEvent).where(HealthEvent.event_type=='CARE_EPISODE_LINK'))==before+1
    assert b.event_category is None and b.status=='STORED'


def test_default_window_and_earlier_records(data):
    v=view(data);assert v.has_earlier
    assert all(e.occurred_at>=data[1]['now']-timedelta(days=365) for e in v.entries)
    older=view(data,time_range=(data[1]['now']-timedelta(days=730),data[1]['now']))
    assert sum(e.entry_type=='ANNUAL_BASELINE' for e in older.entries)==2


def test_filters_and_member_scoped_details(data):
    v=view(data,filters='医疗');assert all(e.entry_type in {'DOCTOR_DECISION','RECHECK','MEDICATION_CHANGE','MEDICATION_END'} for e in v.entries)
    with pytest.raises(ValueError):Projection().details(data[0],v,'current:'+str(data[1]['empty'].id))


def test_single_member360_entry_and_trace_hidden():
    source=(ROOT/'src/executive_health_ai/ui/pages/manager/longitudinal_timeline.py').read_text(encoding='utf8')
    assert 'st.json(' not in source and 'detail_target' not in source and "source['id']" not in source
    callers=[]
    for p in (ROOT/'src/executive_health_ai/ui').rglob('*.py'):
        if 'from executive_health_ai.ui.pages.manager.longitudinal_timeline import render' in p.read_text(encoding='utf8'):callers.append(p.name)
    assert callers==['experience.py']
