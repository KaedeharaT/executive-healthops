"""Goal governance and daily aggregates linked to existing programs and facts."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import ForeignKey, JSON, Numeric, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from executive_health_ai.models.base import Base, UTCDateTime, utc_now


class ManagementGoal(Base):
    """The confirmed objective of an existing annual/stage program, not a new plan system."""
    __tablename__ = "management_goals"
    __table_args__ = (UniqueConstraint("program_id", name="uq_management_goal_program"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    program_id: Mapped[UUID] = mapped_column(ForeignKey("health_programs.id"), index=True)
    agent_goal_id: Mapped[UUID | None] = mapped_column(ForeignKey("agent_goals.id"))
    goal_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    metric_code: Mapped[str | None] = mapped_column(String(64))
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    target_unit: Mapped[str | None] = mapped_column(String(32))
    baseline_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    start_date: Mapped[date]
    target_date: Mapped[date]
    owner_id: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    source: Mapped[str] = mapped_column(String(64))
    confirmed_by: Mapped[str | None] = mapped_column(String(128))
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    requirements_version: Mapped[str] = mapped_column(String(40), default="goal-metrics-1")
    requirements_json: Mapped[list] = mapped_column(JSON, default=list)
    plan_draft: Mapped[dict] = mapped_column(JSON, default=dict)
    plan_confirmed_by: Mapped[str | None] = mapped_column(String(128))
    plan_confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class ReportCandidateRevision(Base):
    __tablename__ = "report_candidate_revisions"
    __table_args__ = (UniqueConstraint("candidate_id", "version", name="uq_report_candidate_revision"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("report_extraction_candidates.id"), index=True)
    version: Mapped[int]
    values_json: Mapped[dict] = mapped_column(JSON)
    author: Mapped[str] = mapped_column(String(128))
    method: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class DailyHealthSummary(Base):
    """One controlled current record per member/local date; prior versions retained."""
    __tablename__ = "daily_health_summaries"
    __table_args__ = (UniqueConstraint("patient_id", "summary_date", name="uq_daily_summary_member_day"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    summary_date: Mapped[date] = mapped_column(index=True)
    timezone: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(default=1)
    input_hash: Mapped[str] = mapped_column(String(64))
    metrics: Mapped[dict] = mapped_column(JSON)
    completeness: Mapped[dict] = mapped_column(JSON, default=dict)
    change_status: Mapped[str] = mapped_column(String(40), default="NO_MEANINGFUL_CHANGE")
    changes: Mapped[list] = mapped_column(JSON, default=list)
    calculated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class DailySummaryRevision(Base):
    __tablename__ = "daily_summary_revisions"
    __table_args__ = (UniqueConstraint("summary_id", "version", name="uq_daily_summary_revision"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    summary_id: Mapped[UUID] = mapped_column(ForeignKey("daily_health_summaries.id"), index=True)
    version: Mapped[int]
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class SummaryWorkItem(Base):
    """Coalesced member/date dirty marker; ingest never wakes the Agent or LLM."""
    __tablename__ = "summary_work_items"
    __table_args__ = (UniqueConstraint("patient_id", "summary_date", name="uq_summary_work_member_day"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    summary_date: Mapped[date]
    dirty: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class CommunicationRecord(Base):
    """Immutable original conversation, linked to the existing ManagementLog."""
    __tablename__ = "communication_records"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    program_id: Mapped[UUID] = mapped_column(ForeignKey("health_programs.id"))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime())
    participants: Mapped[list] = mapped_column(JSON, default=list)
    participant_roles: Mapped[dict] = mapped_column(JSON, default=dict)
    channel: Mapped[str] = mapped_column(String(40))
    raw_note: Mapped[str] = mapped_column(Text)
    structured_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(32))
    related_goal_id: Mapped[UUID | None] = mapped_column(ForeignKey("management_goals.id"))
    related_metrics: Mapped[list] = mapped_column(JSON, default=list)
    related_actions: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[str] = mapped_column(Text, default="")
    doctor_review_id: Mapped[UUID | None] = mapped_column(ForeignKey("doctor_reviews.id"))
    log_id: Mapped[UUID | None] = mapped_column(ForeignKey("management_logs.id"))
    confirmed_status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    confirmed_by: Mapped[str | None] = mapped_column(String(128))
    request_key: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
