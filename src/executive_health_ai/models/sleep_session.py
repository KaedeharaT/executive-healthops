"""Sleep-session model used for descriptive sleep trends."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from executive_health_ai.models.base import Base, UTCDateTime, utc_now

if TYPE_CHECKING:
    from executive_health_ai.models.device import Device
    from executive_health_ai.models.patient import Patient
    from executive_health_ai.models.raw_data import RawData


class SleepSession(Base):
    """A normalized sleep session; it is not a sleep-disorder diagnosis."""

    __tablename__ = "sleep_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    device_id: Mapped[UUID | None] = mapped_column(ForeignKey("devices.id"), nullable=True)
    sleep_start: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    sleep_end: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    total_sleep_minutes: Mapped[int] = mapped_column(nullable=False)
    deep_sleep_minutes: Mapped[int | None] = mapped_column(nullable=True)
    rem_sleep_minutes: Mapped[int | None] = mapped_column(nullable=True)
    awake_minutes: Mapped[int | None] = mapped_column(nullable=True)
    # Exact phases are retained only when the source supplied them.  An empty
    # list means "not provided", never a fabricated sleep-stage timeline.
    stage_segments_json: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    sleep_efficiency: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    avg_heart_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    lowest_heart_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    avg_hrv: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_record_id: Mapped[UUID | None] = mapped_column(ForeignKey("raw_data.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)

    patient: Mapped["Patient"] = relationship()
    device: Mapped["Device | None"] = relationship()
    raw_data: Mapped["RawData | None"] = relationship()
