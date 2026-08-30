"""Deterministic, governed risk-triage records; not clinical diagnoses."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4
from sqlalchemy import Boolean, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from executive_health_ai.models.base import Base, UTCDateTime, utc_now

class RiskRule(Base):
    __tablename__ = "risk_rules"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    applicable_device_class: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    condition_type: Mapped[str] = mapped_column(String(64), nullable=False)
    threshold_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    window_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    requires_repeated_measurement: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_symptom_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    recommended_route: Mapped[str] = mapped_column(String(64), nullable=False, default="HEALTH_MANAGER")
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1.0")
    # Legacy/demo rules are deliberately TEST until a clinician-governed
    # CLINICAL scope is explicitly assigned.  This prevents synthetic rules
    # from grading a non-demo UAT member after migration.
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="TEST", index=True)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)

class RiskEvent(Base):
    __tablename__ = "risk_events"
    __table_args__ = (
        Index("ix_risk_events_patient_rule_status", "patient_id", "risk_rule_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    risk_rule_id: Mapped[UUID] = mapped_column(ForeignKey("risk_rules.id"), nullable=False, index=True)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW", index=True)
    device_class: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recommended_route: Mapped[str] = mapped_column(String(64), nullable=False, default="HEALTH_MANAGER")
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    requires_manager_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_doctor_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_emergency_action: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    acknowledged_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)

class EmergencyContact(Base):
    __tablename__ = "emergency_contacts"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    relationship: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[str] = mapped_column(String(64), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    consent_status: Mapped[str] = mapped_column(String(32), nullable=False, default="DEMO_ONLY")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
