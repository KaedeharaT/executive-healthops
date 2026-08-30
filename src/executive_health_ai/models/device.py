"""Device data model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from executive_health_ai.models.base import Base, UTCDateTime, utc_now

if TYPE_CHECKING:
    from executive_health_ai.models.observation import Observation
    from executive_health_ai.models.patient import Patient


class Device(Base):
    """A physical or software source of health data."""

    __tablename__ = "devices"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    device_type: Mapped[str] = mapped_column(String(64), nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_system: Mapped[str | None] = mapped_column(String(128), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)

    patient: Mapped["Patient"] = relationship(back_populates="devices")
    observations: Mapped[list["Observation"]] = relationship(back_populates="device")
