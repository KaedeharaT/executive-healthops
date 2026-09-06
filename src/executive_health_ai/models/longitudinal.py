"""Longitudinal HealthOps records.

These records connect already-confirmed health facts with human-managed
longitudinal work.  They are deliberately not diagnoses, prescriptions, or
automated clinical decisions.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from executive_health_ai.models.base import Base, UTCDateTime, utc_now


class HealthAssessment(Base):
    __tablename__ = "health_assessments"
    __table_args__ = (
        UniqueConstraint(
            "patient_id", "assessment_type", "cycle_year", "version",
            name="uq_health_assessment_cycle_version",
        ),
        Index("ix_health_assessment_cycle_status", "patient_id", "cycle_year", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    assessment_type: Mapped[str] = mapped_column(String(32), nullable=False, default="INITIAL", index=True)
    version: Mapped[int] = mapped_column(nullable=False)
    management_cycle_id: Mapped[UUID | None] = mapped_column(ForeignKey("annual_health_accounts.id"), nullable=True, index=True)
    cycle_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    cycle_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    cycle_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    baseline_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    collection_started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    collection_due_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    collection_closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    medical_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    medical_reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    medical_reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    parent_assessment_id: Mapped[UUID | None] = mapped_column(ForeignKey("health_assessments.id"), nullable=True, index=True)
    amendment_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    amendment_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    amended_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    superseded_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("health_assessments.id"), nullable=True)
    snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_references_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    assessed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)


class ManagementRule(Base):
    """Governed lifestyle/management signal rule; distinct from medical RiskRule."""

    __tablename__ = "management_rules"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    canonical_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    condition_type: Mapped[str] = mapped_column(String(64), nullable=False, default="THRESHOLD")
    threshold_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    window_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    recommended_route: Mapped[str] = mapped_column(String(64), nullable=False, default="HEALTH_MANAGER")
    version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1.0")
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)


class ManagementSignal(Base):
    """A human-management item, never a medical diagnosis or RiskEvent."""

    __tablename__ = "management_signals"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    management_rule_id: Mapped[UUID] = mapped_column(ForeignKey("management_rules.id"), nullable=False, index=True)
    observation_id: Mapped[UUID] = mapped_column(ForeignKey("observations.id"), nullable=False, index=True)
    # These fields make the signal independently auditable without turning it
    # into a medical RiskEvent.  The originating Observation remains the
    # canonical measurement and evidence_json retains the evaluated window.
    signal_category: Mapped[str] = mapped_column(String(64), nullable=False, default="LIFESTYLE_MANAGEMENT")
    metric_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="WATCH")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN", index=True)
    recommended_route: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    first_detected_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    last_detected_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)


class MemberDeviceAssignment(Base):
    __tablename__ = "member_device_assignments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    device_category: Mapped[str] = mapped_column(String(32), nullable=False)
    assignment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="ASSIGNED")
    connection_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    assigned_by: Mapped[str] = mapped_column(String(128), nullable=False, default="health_manager")
    assigned_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    disabled_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExternalReferral(Base):
    __tablename__ = "external_referrals"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    doctor_review_id: Mapped[UUID | None] = mapped_column(ForeignKey("doctor_reviews.id"), nullable=True, index=True)
    specialty: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    organization: Mapped[str | None] = mapped_column(String(200), nullable=True)
    doctor_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    appointment_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", index=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_reference: Mapped[str | None] = mapped_column(String(512), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
