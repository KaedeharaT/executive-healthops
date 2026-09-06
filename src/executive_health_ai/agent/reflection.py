"""Rule-first operational replanning; never changes medical facts or rules."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from executive_health_ai.agent.planner import HealthOpsPlanner
from executive_health_ai.models import AgentGoal, AgentPlan
from executive_health_ai.models.base import utc_now


class HealthOpsReflectionService:
    ALLOWED_REASONS = {"MEMBER_UNAVAILABLE", "TOOL_UNAVAILABLE", "DATA_INSUFFICIENT", "SERVICE_DELAYED"}

    def replan(self, session: Session, goal_id: UUID, *, reason: str, delay_days: int = 14) -> AgentPlan:
        if reason not in self.ALLOWED_REASONS:
            raise ValueError("Reflection may only adjust an operational execution path.")
        goal = session.get(AgentGoal, goal_id)
        if goal is None or goal.status in {"COMPLETED", "CANCELLED"}:
            raise ValueError("Active goal not found.")
        old = session.get(AgentPlan, goal.current_plan_id)
        if old:
            old.status = "SUPERSEDED"
        plan = HealthOpsPlanner().create_plan(session, goal, reason=f"Operational replan: {reason}", start_at=11)
        goal.status, goal.current_stage = "WAITING", "等待重新跟进"
        goal.next_check_at = utc_now() + timedelta(days=max(1, delay_days))
        goal.next_action = f"{goal.next_check_at.date().isoformat()} 重新检查成员可用状态"
        return plan
