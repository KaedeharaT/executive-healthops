"""Encounters and clinician-confirmed recommendations."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from executive_health_ai.models.base import Base, UTCDateTime, utc_now

if TYPE_CHECKING:
    from executive_health_ai.models.patient import Patient


class Encounter(Base):
    """An individual consultation, follow-up, or multidisciplinary review."""

    __tablename__ = "encounters"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    encounter_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    encounter_type: Mapped[str] = mapped_column(String(64), nullable=False)
    department: Mapped[str] = mapped_column(String(128), nullable=False)
    clinician_name: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)

    patient: Mapped["Patient"] = relationship()
    recommendations: Mapped[list["ClinicalRecommendation"]] = relationship(
        back_populates="encounter"
    )


class ClinicalRecommendation(Base):
    """A clinician-confirmed record, deliberately separate from AI insight."""

    __tablename__ = "clinical_recommendations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    encounter_id: Mapped[UUID] = mapped_column(ForeignKey("encounters.id"), nullable=False)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    department: Mapped[str] = mapped_column(String(128), nullable=False)
    clinician_name: Mapped[str] = mapped_column(String(128), nullable=False)
    recommendation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="confirmed")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)

    patient: Mapped["Patient"] = relationship()
    encounter: Mapped[Encounter] = relationship(back_populates="recommendations")
