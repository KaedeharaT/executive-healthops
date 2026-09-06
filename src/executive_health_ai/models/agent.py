"""Durable orchestration state for bounded, human-owned HealthOps automation.

These rows coordinate existing business entities.  They are never a second
source of truth for health facts, clinical risk, diagnosis, or treatment.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from executive_health_ai.models.base import Base, UTCDateTime, utc_now


class AgentEvent(Base):
    __tablename__ = "agent_events"
    __table_args__ = (UniqueConstraint("dedup_key", name="uq_agent_events_dedup_key"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    member_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING", index=True)
    processed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    payload_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedup_key: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class AgentGoal(Base):
    __tablename__ = "agent_goals"
    __table_args__ = (
        UniqueConstraint("goal_type", "source_type", "source_id", name="uq_agent_goal_source"),
        Index("ix_agent_goals_member_status", "member_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    member_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    goal_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE", index=True)
    success_criteria: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    current_stage: Mapped[str] = mapped_column(String(128), nullable=False, default="检查体检报告")
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_plan_id: Mapped[UUID | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, default="agent_supervisor")
    last_event_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    next_check_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    automation_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    takeover_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    takeover_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)


class AgentPlan(Base):
    __tablename__ = "agent_plans"
    __table_args__ = (UniqueConstraint("goal_id", "version", name="uq_agent_plan_version"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    goal_id: Mapped[UUID] = mapped_column(ForeignKey("agent_goals.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="Initial safe workflow plan")


class AgentPlanStep(Base):
    __tablename__ = "agent_plan_steps"
    __table_args__ = (
        UniqueConstraint("plan_id", "step_order", name="uq_agent_plan_step_order"),
        Index("ix_agent_plan_steps_status_schedule", "status", "scheduled_for"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("agent_plans.id"), nullable=False, index=True)
    step_order: Mapped[int] = mapped_column(nullable=False)
    step_type: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(96), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", index=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    wait_event_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retry_count: Mapped[int] = mapped_column(nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(nullable=False, default=3)
    scheduled_for: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class AgentApprovalRequest(Base):
    __tablename__ = "agent_approval_requests"
    __table_args__ = (UniqueConstraint("plan_step_id", "approval_type", name="uq_agent_approval_step_type"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    goal_id: Mapped[UUID] = mapped_column(ForeignKey("agent_goals.id"), nullable=False, index=True)
    plan_step_id: Mapped[UUID] = mapped_column(ForeignKey("agent_plan_steps.id"), nullable=False, index=True)
    approval_type: Mapped[str] = mapped_column(String(64), nullable=False)
    required_role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING", index=True)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(24), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class AgentRunTrace(Base):
    __tablename__ = "agent_run_traces"
    __table_args__ = (Index("ix_agent_run_traces_goal_created", "goal_id", "started_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    goal_id: Mapped[UUID] = mapped_column(ForeignKey("agent_goals.id"), nullable=False, index=True)
    plan_id: Mapped[UUID | None] = mapped_column(ForeignKey("agent_plans.id"), nullable=True)
    plan_step_id: Mapped[UUID | None] = mapped_column(ForeignKey("agent_plan_steps.id"), nullable=True)
    event_id: Mapped[UUID | None] = mapped_column(ForeignKey("agent_events.id"), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(96), nullable=True)
    action: Mapped[str] = mapped_column(String(96), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_id: Mapped[UUID | None] = mapped_column(ForeignKey("agent_approval_requests.id"), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
