"""Governed human-feedback and offline AI-improvement records.

These records are operational governance metadata. They never become clinical
measurements, clinician decisions, or executable risk rules.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, event, inspect
from sqlalchemy.orm import Mapped, mapped_column

from executive_health_ai.models.base import Base, UTCDateTime, utc_now


class FeedbackRecord(Base):
    __tablename__ = "feedback_records"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    feedback_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    feature: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_entity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    member_id: Mapped[UUID | None] = mapped_column(ForeignKey("patients.id"), nullable=True, index=True)
    model_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    prediction_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_correction: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_label: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    feedback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="CAPTURED", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    eligible_for_training: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    deidentified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class FeedbackDatasetVersion(Base):
    __tablename__ = "feedback_dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "dataset_version", name="uq_feedback_dataset_version"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dataset_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    dataset_version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    feature: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_feedback_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    records_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)


@event.listens_for(FeedbackDatasetVersion, "before_update")
@event.listens_for(FeedbackDatasetVersion, "before_delete")
def _prevent_dataset_snapshot_mutation(mapper: object, connection: object, target: FeedbackDatasetVersion) -> None:
    if inspect(target).persistent:
        raise ValueError("Feedback dataset snapshots are immutable.")


class ModelVersionRegistry(Base):
    __tablename__ = "model_version_registry"
    __table_args__ = (UniqueConstraint("provider", "model_version", name="uq_model_provider_version"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    base_model: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    training_dataset_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="CANDIDATE", index=True)
    evaluation_report: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    approved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class RiskRuleReviewCandidate(Base):
    __tablename__ = "risk_rule_review_candidates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    risk_rule_id: Mapped[UUID] = mapped_column(ForeignKey("risk_rules.id"), nullable=False, index=True)
    risk_event_id: Mapped[UUID | None] = mapped_column(ForeignKey("risk_events.id"), nullable=True, index=True)
    feedback_record_id: Mapped[UUID] = mapped_column(ForeignKey("feedback_records.id"), nullable=False, unique=True)
    feedback_type: Mapped[str] = mapped_column(String(48), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING_REVIEW", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
