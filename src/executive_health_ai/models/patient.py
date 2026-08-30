"""Patient data model."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from executive_health_ai.models.base import Base, UTCDateTime, utc_now

if TYPE_CHECKING:
    from executive_health_ai.models.device import Device
    from executive_health_ai.models.observation import Observation


class Patient(Base):
    """A user of the health management platform."""

    __tablename__ = "patients"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    # ``Patient`` is the legacy persistence name.  The product/API calls this a
    # Member; retaining the table avoids a destructive V0.1 migration.
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(nullable=True)
    sex: Mapped[str | None] = mapped_column(String(32), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now
    )

    devices: Mapped[list["Device"]] = relationship(back_populates="patient")
    observations: Mapped[list["Observation"]] = relationship(back_populates="patient")


# Product terminology uses Member.  This alias preserves the existing table and
# all V0.1 foreign keys while offering the correct domain-language import.
Member = Patient
