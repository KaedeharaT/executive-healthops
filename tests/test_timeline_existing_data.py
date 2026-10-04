"""Existing database/member compatibility; never reads a developer database."""
from datetime import timedelta
from types import SimpleNamespace
from pathlib import Path
from uuid import uuid4
import sqlite3
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from streamlit.testing.v1 import AppTest
from executive_health_ai.models import Base, Patient, Observation, HealthEvent, HealthJourney, HealthProgram, HealthAssessment
from executive_health_ai.models.management_workflow import ManagementLog
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.longitudinal_timeline import LongitudinalTimelineProjection as Projection
from executive_health_ai.services.schema_readiness import require_longitudinal_schema

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def existing(tmp_path):
    url='sqlite:///'+(tmp_path/'existing.db').as_posix()
    engine=create_engine(url);Base.metadata.create_all(engine)
    factory=sessionmaker(engine,expire_on_commit=False)
    with factory() as db:
        member=Patient(display_name='Existing synthetic member',external_id=str(uuid4()),timezone='Asia/Shanghai')
        db.add(member);db.commit()
        yield db,member,factory,url
    engine.dispose()


def old_observation(db,p):
    row=Observation(patient_id=p.id,metric_code='weight',value_numeric=83.6,unit='kg',
        observed_at=utc_now()-timedelta(days=1),source='MANUAL',source_type=None,raw_record_id=None,
        evidence_ref=None,quality_flag='valid')
    db.add(row);db.flush();return row


def old_log(db,p):
    journey=HealthJourney(patient_id=p.id,assessment_summary='旧资料',main_focus='生活方式');db.add(journey);db.flush()
    program=HealthProgram(patient_id=p.id,journey_id=journey.id,program_type='ANNUAL',title='旧年度管理',main_goal='旧安排',start_date=utc_now().date())
    db.add(program);db.flush()
    log=ManagementLog(patient_id=p.id,program_id=program.id,occurred_at=utc_now()-timedelta(hours=1),category='日常跟进',
        member_issue='旧电话记录',manager_action='核实睡眠反馈',result='会员确认已收到安排',owner='健管甲',created_by='健管甲',request_key=str(uuid4()))
    db.add(log);db.flush();return log


@pytest.mark.parametrize('kind',['empty','old_observation','old_log','no_snapshot','no_care_episode','no_outcome','missing_goal_phase'])
def test_timeline_existing_member_states(existing,kind):
    db,p,_,_=existing
    if kind in {'old_log','no_snapshot','no_care_episode','no_outcome'}:old_log(db,p)
    elif kind!='empty':old_observation(db,p)
    db.commit();projection=Projection();view=projection.build(db,p.id)
    assert view.empty==(kind=='empty')
    assert not view.episodes
    assert all(e.goal_id is None and e.phase_id is None for e in view.entries)
    for e in view.entries:projection.details(db,view,e.entry_id)
    if kind=='old_log':assert any(e.entry_type=='CARE_CONTACT' for e in view.entries)
    if kind=='old_observation':assert view.entries[-1].snapshot.metric_summary['weight']['value']=='83.600'


@pytest.mark.parametrize('refs',[None,[],[None,{}, {'type':'Observation','id':None}]])
def test_timeline_nullable_source_refs(existing,refs):
    db,p,_,_=existing;old_observation(db,p);db.commit()
    projection=Projection();view=projection.build(db,p.id);entry=view.entries[-1];entry.source_refs=refs
    assert projection.details(db,view,entry.entry_id)['sources']==[]


def test_nullable_legacy_payload_does_not_invent_episode(existing):
    db,p,_,_=existing
    baseline=HealthAssessment(patient_id=p.id,assessment_type='BASELINE',cycle_year=2026,version=1,title='旧基线',summary='旧已确认记录',
        created_by='健管甲',status='CONFIRMED',confirmed_at=utc_now(),baseline_json={'key_metrics':None},source_references_json=None)
    db.add(baseline)
    for kind,payload in [('MEANINGFUL_CHANGE',{'change':None,'lookback':None,'observation_ids':None,'summary_version':None}),
                         ('CARE_EPISODE_LINK',{'trigger_id':None,'links':None})]:
        db.add(HealthEvent(member_id=p.id,event_type=kind,occurred_at=utc_now(),description='旧记录',source='MANUAL',payload_ref=payload))
    db.commit();v=Projection().build(db,p.id)
    assert any(e.entry_type=='MEANINGFUL_CHANGE' for e in v.entries)
    assert len(v.episodes)==1 and all(e.outcome_status=='结果待观察' for e in v.episodes.values())


@pytest.mark.parametrize('kind',['empty','old_observation','old_log'])
def test_timeline_renderer_no_crash(existing,monkeypatch,kind):
    from executive_health_ai.ui.pages.manager import longitudinal_timeline as ui
    db,p,factory,_=existing
    if kind=='old_observation':old_observation(db,p)
    if kind=='old_log':old_log(db,p)
    db.commit()
    monkeypatch.setattr(ui,'SessionLocal',factory)
    monkeypatch.setattr(ui,'_track',lambda **kw:kw['entries'][0]['key'] if kw['entries'] else None)
    app=AppTest.from_string(f'''
from types import SimpleNamespace
from uuid import UUID
from executive_health_ai.ui.pages.manager.longitudinal_timeline import render
render(None,SimpleNamespace(id=UUID('{p.id}')))
''').run(timeout=30)
    assert not app.exception and not app.error
    content=' '.join(str(item.value) for item in [*app.markdown, *app.caption])
    assert '当前还没有足够的纵向健康记录' in content if kind=='empty' else '当时的健康状态' in content


def test_timeline_formal_db_schema_upgrade_preserves_old_records(tmp_path,monkeypatch):
    path=tmp_path/'legacy.db';url='sqlite:///'+path.as_posix();monkeypatch.setenv('DATABASE_URL',url)
    cfg=Config(str(ROOT/'alembic.ini'));command.upgrade(cfg,'0031_member_wait_input')
    mid=uuid4().hex;oid=uuid4().hex;raw=uuid4().hex
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO patients (id,display_name,timezone,created_at,updated_at) VALUES (?,'Legacy member','UTC',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",(mid,))
        db.execute("INSERT INTO raw_data (id,patient_id,source,record_type,payload_json,recorded_at,received_at,checksum) VALUES (?,?,'MANUAL','measurement','{}',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'legacy')",(raw,mid))
        db.execute("INSERT INTO observations (id,patient_id,metric_code,value_numeric,unit,observed_at,source,quality_flag,raw_record_id,created_at,source_deleted,excluded_from_analysis) VALUES (?,?,'weight',83.6,'kg',CURRENT_TIMESTAMP,'MANUAL','valid',?,CURRENT_TIMESTAMP,0,0)",(oid,mid,raw))
        db.commit()
        before={t:db.execute('select * from '+t).fetchall() for t in ('patients','raw_data','observations')}
        columns=[r[1] for r in db.execute('pragma table_info(observations)')]
        with sqlite3.connect(tmp_path/'backup.db') as backup:db.backup(backup)
    with pytest.raises(RuntimeError,match='observations.source_type'):require_longitudinal_schema(url)
    engine=create_engine(url)
    with Session(engine) as db,pytest.raises(OperationalError,match='observations.source_type'):db.scalars(select(Observation)).all()
    command.upgrade(cfg,'head');require_longitudinal_schema(url)
    with sqlite3.connect(path) as db:
        for table,rows in before.items():
            selected=','.join(columns) if table=='observations' else '*'
            assert db.execute(f'select {selected} from {table}').fetchall()==rows
        assert db.execute('pragma integrity_check').fetchone()==('ok',)
    with Session(engine) as db:
        p=db.scalar(select(Patient));v=Projection().build(db,p.id)
        assert not v.empty and v.entries[-1].snapshot.metric_summary['weight']['value']=='83.600'
    engine.dispose()


def test_schema_guard_does_not_create_database(tmp_path):
    path=tmp_path/'missing.db'
    with pytest.raises(RuntimeError,match='No database was created'):require_longitudinal_schema('sqlite:///'+path.as_posix())
    assert not path.exists()


def test_launcher_checks_schema_before_starting_services(monkeypatch):
    from tests.test_service_processes import manager
    from executive_health_ai.services import schema_readiness
    def outdated():raise RuntimeError('database schema is out of date')
    monkeypatch.setattr(schema_readiness,'require_longitudinal_schema',outdated)
    with pytest.raises(RuntimeError,match='database schema is out of date'):
        manager.preflight(SimpleNamespace(profile='platform'),[])
