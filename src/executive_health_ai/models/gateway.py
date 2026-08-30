"""Operational provenance for the unified health-data gateway."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from executive_health_ai.models.base import Base, UTCDateTime, utc_now


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_system: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    patient_id: Mapped[UUID | None] = mapped_column(ForeignKey("patients.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", index=True)
    records_received: Mapped[int] = mapped_column(nullable=False, default=0)
    records_valid: Mapped[int] = mapped_column(nullable=False, default=0)
    records_invalid: Mapped[int] = mapped_column(nullable=False, default=0)
    records_duplicate: Mapped[int] = mapped_column(nullable=False, default=0)
    records_created: Mapped[int] = mapped_column(nullable=False, default=0)
    records_updated: Mapped[int] = mapped_column(nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(nullable=False, default=0)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, default="system")
    installation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    external_sync_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)


class ExternalIdentity(Base):
    __tablename__ = "external_identities"
    __table_args__ = (UniqueConstraint("provider", "external_id", name="uq_external_identity_provider_value"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    external_id: Mapped[str] = mapped_column(String(256), nullable=False)
    identity_type: Mapped[str] = mapped_column(String(64), nullable=False, default="provider_member_id")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)


class RawIngestionRecord(Base):
    """Append-only per-record gateway result; raw payload remains in ``RawData``."""

    __tablename__ = "raw_ingestion_records"
    __table_args__ = (UniqueConstraint("job_id", "source_record_id", name="uq_ingestion_job_source_record"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("ingestion_jobs.id"), nullable=False, index=True)
    patient_id: Mapped[UUID | None] = mapped_column(ForeignKey("patients.id"), nullable=True, index=True)
    raw_data_id: Mapped[UUID | None] = mapped_column(ForeignKey("raw_data.id"), nullable=True)
    source_system: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(256), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    adapter_name: Mapped[str] = mapped_column(String(128), nullable=False)
    adapter_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalization_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, default="UPSERT")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
