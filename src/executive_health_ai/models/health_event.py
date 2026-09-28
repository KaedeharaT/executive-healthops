"""Unified business receipts and the preserved clinical/life event history."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text, JSON, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from executive_health_ai.models.base import Base, UTCDateTime, utc_now

if TYPE_CHECKING:
    from executive_health_ai.models.patient import Patient


class HealthEvent(Base):
    """A recorded fact/receipt, never a clinical inference or risk decision."""

    __tablename__ = "health_events"
    __table_args__ = (
        UniqueConstraint('idempotency_key', name='uq_health_event_idempotency'),
        UniqueConstraint('patient_id','event_type','source_id',name='uq_health_event_origin'),
        Index('ix_health_event_pending','status','received_at'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    start_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    end_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(128), nullable=False)

    # NULL category identifies existing clinical/life history, never replayed as
    # an automation event. Aliases preserve every existing history consumer.
    event_id = synonym('id')
    member_id = synonym('patient_id')
    occurred_at = synonym('start_at')
    event_category: Mapped[str | None] = mapped_column(String(32))
    source_type: Mapped[str | None] = mapped_column(String(16))
    source_id: Mapped[str | None] = mapped_column(String(256))
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    payload_ref: Mapped[dict | None] = mapped_column(JSON)
    correlation_id: Mapped[str | None] = mapped_column(String(128))
    idempotency_key: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(24),default='STORED')
    route_action: Mapped[str | None] = mapped_column(String(32))
    goal_id: Mapped[UUID | None] = mapped_column(ForeignKey('agent_goals.id'))

    patient: Mapped["Patient"] = relationship()
