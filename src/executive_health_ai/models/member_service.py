"""Configurable member service catalogue and human-operated service requests."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from executive_health_ai.models.base import Base, UTCDateTime, utc_now


class ServiceCatalogItem(Base):
    __tablename__ = "service_catalog_items"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    is_major_timeline_service: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")


class ServicePlan(Base):
    __tablename__ = "service_plans"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    version: Mapped[str] = mapped_column(String(64), default="v1-demo")
    effective_from: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class ServicePlanItem(Base):
    __tablename__ = "service_plan_items"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    service_plan_id: Mapped[UUID] = mapped_column(ForeignKey("service_plans.id"), index=True)
    service_item_id: Mapped[UUID] = mapped_column(ForeignKey("service_catalog_items.id"), index=True)
    included: Mapped[bool] = mapped_column(Boolean, default=True)
    quota_type: Mapped[str] = mapped_column(String(32), default="UNLIMITED")
    included_quantity: Mapped[int | None] = mapped_column(nullable=True)
    discount: Mapped[str | None] = mapped_column(String(64), nullable=True)
    coverage: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class MemberEntitlement(Base):
    __tablename__ = "member_entitlements"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    service_plan_id: Mapped[UUID] = mapped_column(ForeignKey("service_plans.id"), index=True)
    service_item_id: Mapped[UUID] = mapped_column(ForeignKey("service_catalog_items.id"), index=True)
    total_quota: Mapped[int | None] = mapped_column(nullable=True)
    used_quota: Mapped[int] = mapped_column(default=0)
    valid_from: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    __table_args__ = (UniqueConstraint("patient_id", "service_item_id", name="uq_member_entitlement_item"),)


class ServiceRequest(Base):
    __tablename__ = "service_requests"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    service_item_id: Mapped[UUID] = mapped_column(ForeignKey("service_catalog_items.id"), index=True)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    requested_by: Mapped[str] = mapped_column(String(128))
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="REQUESTED", index=True)
    assigned_manager: Mapped[str | None] = mapped_column(String(128), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_problem_id: Mapped[UUID | None] = mapped_column(ForeignKey("health_problems.id"), nullable=True)
    related_risk_event_id: Mapped[UUID | None] = mapped_column(ForeignKey("risk_events.id"), nullable=True)
    related_doctor_review_id: Mapped[UUID | None] = mapped_column(ForeignKey("doctor_reviews.id"), nullable=True)


class MemberPlanChoice(Base):
    __tablename__ = "member_plan_choices"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    proposal: Mapped[str] = mapped_column(Text)
    recommended_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    member_choice: Mapped[str] = mapped_column(String(32))
    member_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    chosen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    manager_followup: Mapped[str | None] = mapped_column(Text, nullable=True)
