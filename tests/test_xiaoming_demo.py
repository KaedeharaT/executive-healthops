"""A full business story, not UI-only rows or handwritten change events."""
from datetime import timedelta
from decimal import Decimal
from uuid import UUID
import sqlite3
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from executive_health_ai.database import create_database_engine
from executive_health_ai.models import (Base, Patient, MemberAgent, Observation, RawData, HealthAssessment,
    AgentGoal, AgentRunTrace, RiskEvent, RiskRule, DoctorReview, HealthEvent, Task, ProgramPhase, AuditLog)
from executive_health_ai.models.goal_data import ManagementGoal, DailyHealthSummary, ReportCandidateRevision, CommunicationRecord
from executive_health_ai.models.management_workflow import StageReview, RecheckPlan, ManagementLog
from executive_health_ai.services.longitudinal_timeline import LongitudinalTimelineProjection
from executive_health_ai.services.goal_metrics import requirements
from executive_health_ai.services.data_provenance import detail
from scripts.seed_xiaoming_demo import seed_xiaoming, inventory, assert_preserved, EXTERNAL_ID, MANIFEST, at


@pytest.fixture(scope='module')
def story(tmp_path_factory):
    path=tmp_path_factory.mktemp('xiaoming')/'story.db'
    engine=create_database_engine('sqlite:///'+path.as_posix());Base.metadata.create_all(engine)
    with Session(engine) as db:
        other=Patient(display_name='Unrelated member',external_id='unrelated',timezone='UTC');db.add(other);db.flush()
        db.add(Observation(patient_id=other.id,metric_code='weight',value_numeric=77,unit='kg',source='MANUAL',observed_at=at(1,1),quality_flag='valid'))
        db.commit();before=inventory(db)
        from executive_health_ai.llm.local_llm_client import LocalLLMClient
        from unittest.mock import patch
        with patch.object(LocalLLMClient,'generate_structured',side_effect=AssertionError('Synthetic raw/summary must not call an LLM')):
            p=seed_xiaoming(db);db.commit()
        assert_preserved(before,inventory(db))
        receipt=db.scalar(select(AuditLog).where(AuditLog.patient_id==p.id,AuditLog.action==MANIFEST))
        yield db,p,receipt.detail_json,path
    engine.dispose()


def test_xiaoming_seed_idempotent(story):
    db,p,_,_=story;before=inventory(db)
    assert seed_xiaoming(db).id==p.id
    assert inventory(db)==before
    assert db.scalar(select(func.count()).select_from(Patient).where(Patient.external_id==EXTERNAL_ID))==1


def test_xiaoming_marked_synthetic(story):
    _,p,receipt,_=story
    assert p.display_name=='小明' and 'synthetic-demo' in p.external_id and receipt['synthetic']
    assert p.birth_date.year==1984 and p.archived_at is None


def test_xiaoming_member_agent_exists(story):
    db,p,_,_=story
    assert db.scalar(select(func.count()).select_from(MemberAgent).where(MemberAgent.member_id==p.id))==1


def test_xiaoming_annual_baseline(story):
    db,p,_,_=story
    row=db.scalar(select(HealthAssessment).where(HealthAssessment.patient_id==p.id,HealthAssessment.cycle_year==2026))
    assert row.status=='CONFIRMED' and row.baseline_json['weight']==86
    assert row.baseline_json['bmi']==28.1 and row.source_references_json
    assert row.confirmed_at==at(1,5)


def test_xiaoming_goal(story):
    db,p,_,_=story;goal=db.scalar(select(ManagementGoal).where(ManagementGoal.patient_id==p.id))
    assert goal.confirmed_by and goal.plan_confirmed_by and goal.target_value==82 and goal.baseline_value==86
    assert db.get(AgentGoal,goal.agent_goal_id).status=='COMPLETED'


def test_xiaoming_metric_mapping(story):
    db,p,_,_=story;goal=db.scalar(select(ManagementGoal).where(ManagementGoal.patient_id==p.id))
    assert {r.metric_code for r in requirements(goal.goal_type)}>={'weight','bmi','sleep_duration','steps'}
    assert goal.requirements_json and goal.requirements_version


def test_xiaoming_observations(story):
    db,p,_,_=story;rows=list(db.scalars(select(Observation).where(Observation.patient_id==p.id)))
    assert 1000<len(rows)<5000 and all(r.raw_record_id for r in rows)
    assert {r.source_type for r in rows}>={'DEVICE','MOBILE','REPORT'}


def test_xiaoming_daily_summary(story):
    db,p,_,_=story;rows=list(db.scalars(select(DailyHealthSummary).where(DailyHealthSummary.patient_id==p.id)))
    assert len(rows)>200 and len({r.summary_date for r in rows})==len(rows)
    assert all(r.input_hash for r in rows)
    latest=max(rows,key=lambda r:r.summary_date)
    assert Decimal(latest.metrics['sleep_duration']['value'])==372


def test_xiaoming_meaningful_change(story):
    db,_,r,_=story;e=db.get(HealthEvent,UUID(r['sleep_change']));summary=db.get(DailyHealthSummary,UUID(e.payload_ref['summary_id']))
    change=e.payload_ref['change'];assert summary.change_status=='MEANINGFUL_CHANGE'
    assert change['rule_id'] and change['rule_version'] and Decimal(change['today'])==324
    assert Decimal(change['mean_7d'])==390 and change['window_days']==7
    assert e.payload_ref['risk_evaluation']['engine']=='deterministic'
    assert all(set(h['metrics'])<=set(e.payload_ref['lookback']['metric_scope']) for h in e.payload_ref['lookback']['history_30d'])
    assert e.payload_ref['lookback']['phase']=='阶段3 · 睡眠问题处理'
    assert all(h['date']<='2026-08-10' for h in e.payload_ref['lookback']['history_30d'])


def test_xiaoming_yellow_event(story):
    db,p,_,_=story;risks=list(db.scalars(select(RiskEvent).where(RiskEvent.patient_id==p.id,RiskEvent.risk_level=='YELLOW')))
    assert len(risks)==2 and all(r.status=='CLOSED' for r in risks)
    for r in risks:assert db.get(RiskRule,r.risk_rule_id).scope=='DEMO'


def test_xiaoming_manager_followup(story):
    db,p,_,_=story;row=db.scalar(select(CommunicationRecord).where(CommunicationRecord.patient_id==p.id,CommunicationRecord.source=='MANAGER'))
    assert '夜班' in row.raw_note and '咖啡' in row.raw_note and row.confirmed_status=='CONFIRMED'
    assert {f['field'] for f in row.structured_summary['lifestyle_candidates']}>={'睡眠','饮食','工作压力'}
    assert row.structured_summary['doctor_opinion'] is None
    assert db.get(ManagementLog,row.log_id).related_risk_id


def test_xiaoming_doctor_review(story):
    db,p,r,_=story;review=db.scalar(select(DoctorReview).where(DoctorReview.patient_id==p.id))
    assert review.status=='CONFIRMED' and review.doctor_name=='演示王医生' and review.opinion
    goal=db.get(AgentGoal,UUID(r['doctor_goal']))
    assert goal.context_json['responsibility']['route_type']=='DOCTOR'
    note=db.scalar(select(CommunicationRecord).where(CommunicationRecord.patient_id==p.id,CommunicationRecord.source=='DOCTOR'))
    assert note.doctor_review_id==review.id and note.structured_summary['doctor_opinion']==review.opinion


def test_xiaoming_same_goal_resume(story):
    db,_,r,_=story;goal=db.get(AgentGoal,UUID(r['doctor_goal']))
    traces=list(db.scalars(select(AgentRunTrace).where(AgentRunTrace.goal_id==goal.id)))
    assert goal.status=='COMPLETED'
    assert any(t.action=='wait' and t.metadata_json.get('state')=='WAITING_DOCTOR' for t in traces)
    assert any(t.action=='resume' and t.metadata_json.get('event_type')=='DOCTOR_REVIEW_COMPLETED' for t in traces)


def test_xiaoming_recheck(story):
    db,p,r,_=story;row=db.scalar(select(RecheckPlan).where(RecheckPlan.patient_id==p.id))
    assert row.status=='CLOSED' and row.document_id and row.doctor_review_id and row.result
    goal=db.get(AgentGoal,UUID(r['recheck_goal']));assert goal.status=='COMPLETED'
    traces=list(db.scalars(select(AgentRunTrace).where(AgentRunTrace.goal_id==goal.id)))
    assert any(t.action=='wait' and t.metadata_json.get('state')=='WAITING_TIME' for t in traces)
    assert any(t.action=='resume' and t.metadata_json.get('event_type')=='TIME_DUE' for t in traces)


def test_xiaoming_stage_review(story):
    db,p,_,_=story;reviews=list(db.scalars(select(StageReview).where(StageReview.patient_id==p.id)))
    assert len(reviews)==3 and all(r.owner and r.content.get('下一阶段建议') for r in reviews)
    assert {r.reviewed_at.date().isoformat() for r in reviews}=={'2026-02-28','2026-07-31','2026-09-30'}
    goals=list(db.scalars(select(AgentGoal).where(AgentGoal.member_id==p.id,AgentGoal.goal_type=='STAGE_REVIEW')))
    assert len(goals)==3 and all(g.status=='COMPLETED' and g.context_json.get('next_phase_id') for g in goals)


@pytest.mark.parametrize('case',['projection','health_track','care_track','care_episode','outcome','current_state','twelve_months'])
def test_xiaoming_timeline(story,case):
    db,p,r,_=story;view=LongitudinalTimelineProjection().build(db,p.id,now=at(10,4)+timedelta(hours=12))
    assert not view.empty and 15<=len(view.entries)<=60
    if case=='projection':
        for e in view.entries:LongitudinalTimelineProjection().details(db,view,e.entry_id)
    elif case=='health_track':assert {e.entry_type for e in view.entries if e.track=='HEALTH_STATE'}>={'ANNUAL_BASELINE','MEANINGFUL_CHANGE','OUTCOME','CURRENT_STATE'}
    elif case=='care_track':assert {e.entry_type for e in view.entries if e.track=='CARE_ACTION'}>={'GOAL_CONFIRMED','PLAN_CONFIRMED','DOCTOR_DECISION','RECHECK','PHASE_REVIEW','PHASE_STARTED'}
    elif case in {'care_episode','outcome'}:
        for key in ('sleep_change','doctor_change'):
            ep=view.episodes['change:'+r[key]]
            assert ep.outcome_ids and len(ep.entry_ids)>=4 and ep.outcome_status!='结果待观察'
    elif case=='current_state':
        e=view.entries[-1];assert e.entry_type=='CURRENT_STATE' and e.risk_level=='GREEN'
        assert e.goal_id and e.details['progress']['percent']==90
        assert Decimal(e.snapshot.metric_summary['weight']['value'])==Decimal('82.4')
        assert '阶段4' in e.snapshot.phase_summary and '10-15' in e.details['next']
    else:assert (view.entries[-1].occurred_at-view.entries[0].occurred_at).days>=364


def test_xiaoming_provenance_and_correction_history(story):
    db,p,r,_=story;fact=db.get(Observation,UUID(r['confirmed_observation']));data=detail(db,fact)
    assert fact.value_numeric==Decimal('83.6') and fact.confirmation_status=='CONFIRMED'
    assert '83.6 kg' in db.get(RawData,fact.raw_record_id).payload_json['original_text']
    versions=list(db.scalars(select(ReportCandidateRevision).where(ReportCandidateRevision.candidate_id==UUID(r['candidate'])).order_by(ReportCandidateRevision.version)))
    assert versions[0].values_json['normalized_value']=='86.3' and versions[-1].values_json['normalized_value']=='83.6'
    assert data['corrected']


def test_xiaoming_one_open_item_green_no_human(story):
    db,p,r,_=story
    assert db.scalar(select(func.count()).select_from(Task).where(Task.patient_id==p.id,Task.status.not_in(('COMPLETED','CANCELLED'))))==1
    green=db.get(HealthEvent,UUID(r['green_change']));assert db.get(AgentGoal,green.goal_id).status=='COMPLETED'
    assert not list(db.scalars(select(AgentGoal).where(AgentGoal.member_id==p.id,AgentGoal.status.in_(('WAITING_MANAGER','WAITING_DOCTOR')))))
    assert not list(db.scalars(select(RiskRule).where(RiskRule.code.like(EXTERNAL_ID+'%'),RiskRule.is_active.is_(True))))


def test_xiaoming_foreign_keys(story):
    db,_,_,_=story
    assert not db.connection().exec_driver_sql('pragma foreign_key_check').fetchall()


def test_xiaoming_historical_correction_reachable_in_health_record(story,monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from streamlit.testing.v1 import AppTest
    from executive_health_ai.ui.pages.manager import goal_loop
    db,p,_,_=story
    monkeypatch.setattr(goal_loop,'SessionLocal',sessionmaker(db.bind))
    app=AppTest.from_string(f'from uuid import UUID\nfrom executive_health_ai.ui.pages.manager.goal_loop import provenance\nprovenance(UUID("{p.id}"))').run(timeout=30)
    label=next(s for s in app.selectbox[0].options if '83.600' in s and '2026-05-10' in s)
    app.selectbox[0].select(label).run()
    app.checkbox[0].check().run()
    assert not app.exception and any('已修正' in c.value for c in app.caption)
    assert any('86.3' in c.value for c in app.caption)


def test_xiaoming_reset_is_scoped(story,tmp_path):
    _,_,_,path=story;copy=tmp_path/'reset.db'
    with sqlite3.connect(path) as source,sqlite3.connect(copy) as target:source.backup(target)
    engine=create_database_engine('sqlite:///'+copy.as_posix())
    with Session(engine) as db:
        other=db.scalar(select(Patient).where(Patient.external_id=='unrelated'));oid=other.id
        before=db.scalar(select(Observation).where(Observation.patient_id==oid)).value_numeric
        p=seed_xiaoming(db,reset=True);db.commit()
        assert db.get(Patient,oid).display_name=='Unrelated member'
        assert db.scalar(select(Observation).where(Observation.patient_id==oid)).value_numeric==before
        assert db.scalar(select(func.count()).select_from(Patient).where(Patient.external_id==EXTERNAL_ID))==1
        assert not db.connection().exec_driver_sql('pragma foreign_key_check').fetchall()
    engine.dispose()
