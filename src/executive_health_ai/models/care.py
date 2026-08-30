"""Care plans and user-facing care tasks."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from executive_health_ai.models.base import Base, UTCDateTime, utc_now

if TYPE_CHECKING:
    from executive_health_ai.models.patient import Patient


class CarePlan(Base):
    """A clinician-confirmed management plan for the demo patient."""

    __tablename__ = "care_plans"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    condition: Mapped[str] = mapped_column(String(160), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date] = mapped_column(nullable=False)
    end_date: Mapped[date | None] = mapped_column(nullable=True)
    primary_clinician: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now
    )

    patient: Mapped["Patient"] = relationship()
    tasks: Mapped[list["CareTask"]] = relationship(back_populates="care_plan")


class CareTask(Base):
    """A specific daily action derived from a clinician-confirmed plan."""

    __tablename__ = "care_tasks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    care_plan_id: Mapped[UUID] = mapped_column(ForeignKey("care_plans.id"), nullable=False)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)

    patient: Mapped["Patient"] = relationship()
    care_plan: Mapped[CarePlan] = relationship(back_populates="tasks")
