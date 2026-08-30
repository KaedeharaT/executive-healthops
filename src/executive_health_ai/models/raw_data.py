"""Immutable raw device records and their provenance."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, JSON, String, UniqueConstraint, event, inspect
from sqlalchemy.orm import Mapped, mapped_column, relationship

from executive_health_ai.models.base import Base, UTCDateTime, utc_now

if TYPE_CHECKING:
    from executive_health_ai.models.device import Device
    from executive_health_ai.models.observation import Observation
    from executive_health_ai.models.patient import Patient


class RawData(Base):
    """Original device payload, retained separately from normalized observations."""

    __tablename__ = "raw_data"
    __table_args__ = (
        UniqueConstraint("patient_id", "checksum", name="uq_raw_data_patient_checksum"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    device_id: Mapped[UUID | None] = mapped_column(ForeignKey("devices.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    record_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)

    patient: Mapped["Patient"] = relationship()
    device: Mapped["Device | None"] = relationship()
    observations: Mapped[list["Observation"]] = relationship(back_populates="raw_data")


@event.listens_for(RawData, "before_update")
def _prevent_raw_payload_changes(mapper: object, connection: object, target: RawData) -> None:
    """Raw payloads are append-only; corrections belong in standardized layers."""

    state = inspect(target)
    if state.attrs.payload_json.history.has_changes():
        raise ValueError("RawData.payload_json is immutable; add a new raw record instead.")
