"""Local bookkeeping only: no per-measurement Agent or model invocation."""
from uuid import uuid4
from datetime import timezone
from zoneinfo import ZoneInfo
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session
from executive_health_ai.models.base import utc_now
from executive_health_ai.models.observation import Observation
from executive_health_ai.models.raw_data import RawData
from executive_health_ai.models.goal_data import SummaryWorkItem, ReportCandidateRevision, DailySummaryRevision, CommunicationRecord
from executive_health_ai.models.report_parsing import ReportExtractionCandidate

SUMMARY_TIMEZONE = 'Asia/Shanghai'


@event.listens_for(Session, 'before_flush')
def capture_changed_days(session, context, instances):
    days = session.info.setdefault('summary_changed_days', set())
    for row in session.new | session.dirty:
        if isinstance(row, Observation) and row.patient_id and row.observed_at:
            from executive_health_ai.models.patient import Patient
            member=session.get(Patient,row.patient_id)
            zone=ZoneInfo(member.timezone if member else SUMMARY_TIMEZONE)
            days.add((row.patient_id, row.observed_at.replace(tzinfo=timezone.utc).astimezone(
                zone).date() if row.observed_at.tzinfo is None else row.observed_at.astimezone(zone).date()))


@event.listens_for(Session, 'after_flush_postexec')
def mark_changed_days(session, context):
    days = session.info.pop('summary_changed_days', set())
    if not days: return
    connection = session.connection()
    if connection.dialect.name == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert
    elif connection.dialect.name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else: raise RuntimeError('Daily summary queue requires SQLite or PostgreSQL.')
    for member_id, day in days:
        statement = insert(SummaryWorkItem).values(id=uuid4(), patient_id=member_id,
            summary_date=day, dirty=True, updated_at=utc_now())
        connection.execute(statement.on_conflict_do_update(index_elements=['patient_id','summary_date'],
            set_={'dirty':True,'updated_at':utc_now()}))


@event.listens_for(Session, 'after_soft_rollback')
def forget_changed_days(session, transaction):
    session.info.pop('summary_changed_days', None)


def immutable(mapper, connection, row):
    raise ValueError('Historical evidence is append-only; retain it and add a correction.')


for model in (RawData, Observation, ReportCandidateRevision, DailySummaryRevision, CommunicationRecord):
    event.listen(model, 'before_delete', immutable)
for model in (ReportCandidateRevision, DailySummaryRevision):
    event.listen(model, 'before_update', immutable)


@event.listens_for(ReportExtractionCandidate, 'after_insert')
def initial_candidate(mapper, connection, row):
    values={key:getattr(row,key) for key in ('raw_name','raw_value','canonical_code','normalized_value','unit','evidence_text','status')}
    connection.execute(ReportCandidateRevision.__table__.insert().values(id=uuid4(),candidate_id=row.id,
        version=1,values_json=values,author='parser',method=row.extraction_method,reason='首次解析候选',created_at=utc_now()))


@event.listens_for(Observation, 'before_update')
def preserve_fact(mapper, connection, row):
    if any(inspect(row).attrs[key].history.has_changes() for key in
           ('value_numeric','unit','metric_code','observed_at','raw_record_id','patient_id')):
        immutable(mapper, connection, row)


@event.listens_for(CommunicationRecord, 'before_update')
def preserve_note(mapper, connection, row):
    if any(inspect(row).attrs[key].history.has_changes() for key in
           ('raw_note','source','participants','participant_roles','occurred_at')):
        immutable(mapper, connection, row)
