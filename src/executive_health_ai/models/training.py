"""Portfolio training-session persistence; never a clinical assessment record."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from executive_health_ai.models.base import Base, UTCDateTime, utc_now


class TrainingSession(Base):
    """A synthetic HealthOps learning session, not an employee performance record."""

    __tablename__ = "training_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    case_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    step: Mapped[int] = mapped_column(nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="IN_PROGRESS", index=True)
    trainee_messages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    coach_answers: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    score_result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
