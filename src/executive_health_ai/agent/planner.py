"""Deterministic, template-guided planning for the first bounded workflow."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from executive_health_ai.models import AgentGoal, AgentPlan, AgentPlanStep


@dataclass(frozen=True)
class StepTemplate:
    step_type: str
    tool_name: str | None = None
    approval_role: str | None = None
    wait_event_type: str | None = None


POST_CHECKUP_TEMPLATE = (
    StepTemplate("CHECK_REPORT", "get_report_status"),
    StepTemplate("WAIT_REPORT_CONFIRMATION", approval_role="HEALTH_MANAGER", wait_event_type="REPORT_CONFIRMED"),
    StepTemplate("CHECK_BASELINE", "get_latest_baseline"),
    StepTemplate("EVALUATE_RISK", "evaluate_confirmed_observations"),
    StepTemplate("CHECK_WORKLIST", "get_active_work_items"),
    StepTemplate("ASSIGN_MANAGER", "assign_work_item", approval_role="HEALTH_MANAGER"),
    StepTemplate("WAIT_MANAGER_ACTION"),
    StepTemplate("REQUEST_DOCTOR_REVIEW", "request_doctor_review", approval_role="HEALTH_MANAGER"),
    StepTemplate("WAIT_DOCTOR", wait_event_type="DOCTOR_REVIEW_COMPLETED"),
    StepTemplate("CHECK_ACTIONS", "get_open_tasks"),
    StepTemplate("CREATE_FOLLOWUP", "create_followup_task"),
    StepTemplate("WAIT_FOLLOWUP", wait_event_type="REVIEW_DUE"),
    StepTemplate("CHECK_OUTCOME", "get_latest_outcome", wait_event_type="OUTCOME_RECORDED"),
    StepTemplate("CHECK_TIMELINE", "get_timeline_summary"),
    StepTemplate("VERIFY_SUCCESS", "verify_post_checkup_success"),
)


class HealthOpsPlanner:
    """Create immutable versions of a medically bounded plan skeleton."""

    def create_plan(self, session: Session, goal: AgentGoal, *, reason: str, start_at: int = 1) -> AgentPlan:
        if goal.goal_type != "POST_CHECKUP_MANAGEMENT":
            raise ValueError("Unsupported goal type.")
        version = int(session.scalar(select(func.max(AgentPlan.version)).where(AgentPlan.goal_id == goal.id)) or 0) + 1
        plan = AgentPlan(goal_id=goal.id, version=version, status="ACTIVE", reason=reason)
        session.add(plan)
        session.flush()
        for order, template in enumerate(POST_CHECKUP_TEMPLATE, 1):
            status = "SKIPPED" if order < start_at else "PENDING"
            session.add(AgentPlanStep(
                plan_id=plan.id, step_order=order, step_type=template.step_type,
                tool_name=template.tool_name, status=status,
                requires_approval=bool(template.approval_role), approval_role=template.approval_role,
                wait_event_type=template.wait_event_type,
            ))
        session.flush()
        goal.current_plan_id = plan.id
        return plan

    @staticmethod
    def steps(session: Session, plan_id: UUID) -> list[AgentPlanStep]:
        return list(session.scalars(select(AgentPlanStep).where(AgentPlanStep.plan_id == plan_id).order_by(AgentPlanStep.step_order)))
