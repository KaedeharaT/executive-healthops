"""Standardized clinical observation data model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from executive_health_ai.models.base import Base, UTCDateTime, utc_now

if TYPE_CHECKING:
    from executive_health_ai.models.device import Device
    from executive_health_ai.models.patient import Patient
    from executive_health_ai.models.raw_data import RawData


class Observation(Base):
    """One standardized clinical or physiological measurement."""

    __tablename__ = "observations"
    __table_args__ = (
        CheckConstraint(
            "quality_flag IN ('valid', 'questionable', 'invalid', 'missing_context', 'suspect', 'duplicate', 'manually_corrected')",
            name="ck_observations_quality_flag",
        ),
        Index("ix_observations_patient_metric_observed_at", "patient_id", "metric_code", "observed_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    device_id: Mapped[UUID | None] = mapped_column(ForeignKey("devices.id"), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    metric_code: Mapped[str] = mapped_column(String(64), nullable=False)
    value_numeric: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    quality_flag: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_record_id: Mapped[UUID | None] = mapped_column(ForeignKey("raw_data.id"), nullable=True)
    ingestion_job_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingestion_jobs.id"), nullable=True, index=True)
    source_record_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    quality_notes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_deleted: Mapped[bool] = mapped_column(default=False, nullable=False)
    excluded_from_analysis: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)

    patient: Mapped["Patient"] = relationship(back_populates="observations")
    device: Mapped["Device | None"] = relationship(back_populates="observations")
    raw_data: Mapped["RawData | None"] = relationship(back_populates="observations")
