"""Human-authored intake and operational records. No new clinical fact store."""
from datetime import date, datetime
from uuid import UUID, uuid4
from sqlalchemy import ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from executive_health_ai.models.base import Base, UTCDateTime, utc_now


class IntakeAssessment(Base):
    __tablename__ = "intake_assessments"
    __table_args__ = (UniqueConstraint("patient_id", "cycle_year", name="uq_intake_member_year"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    cycle_year: Mapped[int]
    version: Mapped[str] = mapped_column(String(40), default="healthops-intake-v1")
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    responses: Mapped[dict] = mapped_column(JSON, default=dict)
    member_concern: Mapped[str] = mapped_column(Text, default="")
    professional_focus: Mapped[str] = mapped_column(Text, default="")
    review_status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    review: Mapped[dict] = mapped_column(JSON, default=dict)
    reviewed_by: Mapped[str | None] = mapped_column(String(128))
    doctor_review_id: Mapped[UUID | None] = mapped_column(ForeignKey("doctor_reviews.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)


class ManagementLog(Base):
    __tablename__ = "management_logs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    program_id: Mapped[UUID] = mapped_column(ForeignKey("health_programs.id"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime())
    category: Mapped[str] = mapped_column(String(40))
    channel: Mapped[str] = mapped_column(String(40), default="其他")
    member_issue: Mapped[str] = mapped_column(Text)
    manager_action: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(Text, default="")
    next_action: Mapped[str] = mapped_column(Text, default="")
    follow_up_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    owner: Mapped[str] = mapped_column(String(128))
    service_type: Mapped[str] = mapped_column(String(100), default="")
    provider: Mapped[str] = mapped_column(String(200), default="")
    department: Mapped[str] = mapped_column(String(128), default="")
    expert: Mapped[str] = mapped_column(String(128), default="")
    evidence: Mapped[str] = mapped_column(Text, default="")
    related_task_id: Mapped[UUID | None] = mapped_column(ForeignKey("tasks.id"))
    related_risk_id: Mapped[UUID | None] = mapped_column(ForeignKey("risk_events.id"))
    related_doctor_review_id: Mapped[UUID | None] = mapped_column(ForeignKey("doctor_reviews.id"))
    related_service_id: Mapped[UUID | None] = mapped_column(ForeignKey("service_requests.id"))
    related_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"))
    follow_up_task_id: Mapped[UUID | None] = mapped_column(ForeignKey("tasks.id"), unique=True)
    request_key: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class RecheckPlan(Base):
    __tablename__ = "recheck_plans"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    program_id: Mapped[UUID] = mapped_column(ForeignKey("health_programs.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text)
    planned_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    owner: Mapped[str] = mapped_column(String(128))
    provider: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(32), default="PENDING_CONFIRMATION")
    result: Mapped[str] = mapped_column(Text, default="")
    next_recheck_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"))
    doctor_review_id: Mapped[UUID | None] = mapped_column(ForeignKey("doctor_reviews.id"))
    evidence: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class ConsultationCase(Base):
    """Logistics and manager action drafts; opinions remain ClinicalRecommendation."""
    __tablename__ = "consultation_cases"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    program_id: Mapped[UUID | None] = mapped_column(ForeignKey("health_programs.id"))
    encounter_id: Mapped[UUID] = mapped_column(ForeignKey("encounters.id"), unique=True)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    scheduled_at: Mapped[datetime] = mapped_column(UTCDateTime())
    location: Mapped[str] = mapped_column(String(200))
    participants: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="PREPARING")
    owner: Mapped[str] = mapped_column(String(128))
    conclusion: Mapped[str] = mapped_column(Text, default="")
    concluded_by: Mapped[str | None] = mapped_column(String(128))
    action_drafts: Mapped[list] = mapped_column(JSON, default=list)
    confirmed_by: Mapped[str | None] = mapped_column(String(128))
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class FamilyRelation(Base):
    __tablename__ = "family_relations"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    related_patient_id: Mapped[UUID | None] = mapped_column(ForeignKey("patients.id"))
    relationship: Mapped[str] = mapped_column(String(64))
    contact_name: Mapped[str] = mapped_column(String(128))
    contact: Mapped[str] = mapped_column(String(200), default="")
    emergency: Mapped[bool] = mapped_column(default=False)
    shared_entitlement: Mapped[bool] = mapped_column(default=False)


class StageReview(Base):
    """Phase execution review; quantitative outcomes stay in OutcomeEvaluation."""
    __tablename__ = "stage_reviews"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    program_id: Mapped[UUID] = mapped_column(ForeignKey("health_programs.id"), index=True)
    phase_id: Mapped[UUID] = mapped_column(ForeignKey("program_phases.id"), unique=True)
    content: Mapped[dict] = mapped_column(JSON)
    decision: Mapped[str] = mapped_column(String(32))
    owner: Mapped[str] = mapped_column(String(128))
    reviewed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
