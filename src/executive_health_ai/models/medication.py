"""Demo medication plans and patient-reported administration events."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from executive_health_ai.models.base import Base, UTCDateTime, utc_now

if TYPE_CHECKING:
    from executive_health_ai.models.patient import Patient


class MedicationPlan(Base):
    """A demo clinician-managed plan, not an electronic prescribing system."""

    __tablename__ = "medication_plans"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    drug_name: Mapped[str] = mapped_column(String(128), nullable=False)
    generic_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dose: Mapped[str] = mapped_column(String(64), nullable=False)
    dose_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    frequency: Mapped[str] = mapped_column(String(64), nullable=False)
    route: Mapped[str] = mapped_column(String(64), nullable=False)
    scheduled_time: Mapped[time | None] = mapped_column(nullable=True)
    start_date: Mapped[date] = mapped_column(nullable=False)
    end_date: Mapped[date | None] = mapped_column(nullable=True)
    prescriber_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    department: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now
    )

    patient: Mapped["Patient"] = relationship()
    events: Mapped[list["MedicationEvent"]] = relationship(back_populates="medication_plan")


class MedicationEvent(Base):
    """A scheduled or patient-recorded medication event."""

    __tablename__ = "medication_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    medication_plan_id: Mapped[UUID] = mapped_column(ForeignKey("medication_plans.id"), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    taken_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled")

    patient: Mapped["Patient"] = relationship()
    medication_plan: Mapped[MedicationPlan] = relationship(back_populates="events")
