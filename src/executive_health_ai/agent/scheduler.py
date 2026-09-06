"""Small DB-backed wake-up scheduler; replaceable by a production worker."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
from executive_health_ai.models import AgentGoal, AgentPlanStep
from executive_health_ai.services.event_service import EventService


class AgentSchedulerService:
    def __init__(self, supervisor: HealthOpsAgentSupervisor | None = None) -> None:
        self.supervisor = supervisor or HealthOpsAgentSupervisor()

    def run_due(self, session: Session, *, now: datetime) -> int:
        supervisor = self.supervisor
        processed = 0
        due_goals = list(session.scalars(select(AgentGoal).where(AgentGoal.status == "WAITING", AgentGoal.next_check_at.is_not(None), AgentGoal.next_check_at <= now, AgentGoal.automation_paused.is_(False))))
        for goal in due_goals:
            plan_id = goal.current_plan_id
            retry = session.scalar(select(AgentPlanStep).where(AgentPlanStep.plan_id == plan_id, AgentPlanStep.status == "RETRY_WAIT", AgentPlanStep.next_retry_at <= now).order_by(AgentPlanStep.step_order))
            if retry:
                retry.status = "PENDING"
                goal.status = "ACTIVE"
                supervisor.execute_next_step(session, goal.id)
                processed += 1
                continue
            event, _ = EventService().publish(session, event_type="REVIEW_DUE", member_id=goal.member_id, source_type="agent_goal", source_id=goal.id, payload_summary="Scheduled follow-up review is due", dedup_key=f"REVIEW_DUE:{goal.id}:{goal.next_check_at.isoformat()}")
            supervisor.receive_event(session, event)
            processed += 1
        return processed
