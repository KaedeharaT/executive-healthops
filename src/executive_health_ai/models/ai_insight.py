"""Rule- or AI-generated material, never a clinician conclusion."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from executive_health_ai.models.base import Base, UTCDateTime, utc_now

if TYPE_CHECKING:
    from executive_health_ai.models.patient import Patient


class AIInsight(Base):
    """A transparent derived insight awaiting optional clinician review."""

    __tablename__ = "ai_insights"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    insight_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_start: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    evidence_end: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="generated")
    needs_clinician_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False, default="rule-based-v0.1")
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    patient: Mapped["Patient"] = relationship()
