"""Validated API commands for bounded agent orchestration."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentEventCreate(BaseModel):
    event_type: str
    member_id: UUID
    source_type: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=64)
    payload_summary: str | None = Field(default=None, max_length=1000)
    actor: str = Field(default="system", max_length=128)


class AgentGoalCreate(BaseModel):
    member_id: UUID
    goal_type: str = "POST_CHECKUP_MANAGEMENT"
    source_type: str = Field(default="document", max_length=64)
    source_id: str = Field(min_length=1, max_length=64)
    title: str = Field(default="完成本次体检后健康管理闭环", max_length=240)
    actor: str = Field(default="health_manager", max_length=128)
    actor_role: str = "HEALTH_MANAGER"


class AgentApprovalDecision(BaseModel):
    decision: str
    actor: str = Field(min_length=1, max_length=128)
    actor_role: str
    comment: str = Field(default="", max_length=1000)


class AgentControlRequest(BaseModel):
    action: str = "RESUME"
    actor: str = Field(default="admin", max_length=128)
    actor_role: str = "ADMIN"
    reason: str = Field(default="人工确认恢复", max_length=1000)


class AgentGoalView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    member_id: UUID
    goal_type: str
    title: str
    status: str
    current_stage: str
    next_action: str | None
    owner: str | None
    started_at: datetime
    due_at: datetime | None
    next_check_at: datetime | None
    completed_at: datetime | None
