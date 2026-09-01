"""Single transition contract for user-visible HealthOps tasks.

Presentation and API layers must call this service instead of mutating a
``Task`` directly.  Risk-linked tasks are dispatched back to the risk
workflow so that the task and its owning ``RiskEvent`` advance together.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from executive_health_ai.models import AuditLog, RiskEvent, Task
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.risk_operations import RiskOperationsService


class TaskTransitionService:
    """Apply audited task transitions without bypassing an owning workflow."""

    def complete(self, session: Session, task_id: UUID, *, actor: str, outcome: str) -> Task:
        if not actor.strip():
            raise ValueError("Task completion actor is required.")
        if not outcome.strip():
            raise ValueError("Task completion outcome is required.")

        task = session.get(Task, task_id)
        if task is None:
            raise ValueError("Task not found.")
        if task.status == "COMPLETED":
            return task
        if task.status == "CANCELLED":
            raise ValueError("A cancelled task cannot be completed.")

        if task.risk_event_id is not None:
            return self._complete_risk_task(session, task, actor=actor, outcome=outcome)

        task.status = "COMPLETED"
        task.completed_at = utc_now()
        session.add(AuditLog(
            patient_id=task.patient_id,
            actor=actor,
            actor_role=task.responsible_role or "health_manager",
            action="task_completed",
            entity_type="Task",
            entity_id=str(task.id),
            detail_json={"outcome": outcome, "source": task.source},
        ))
        session.flush()
        return task

    @staticmethod
    def _complete_risk_task(session: Session, task: Task, *, actor: str, outcome: str) -> Task:
        event = session.get(RiskEvent, task.risk_event_id)
        if event is None:
            raise ValueError("Risk-linked task has no owning RiskEvent.")

        operations = RiskOperationsService()
        if event.status == "MONITORING":
            return operations.complete_monitoring_task(session, event.id, actor, outcome, task.id)
        if event.status == "FOLLOW_UP":
            operations.record_follow_up(session, event.id, actor, outcome, task.id)
            return task
        if event.status == "IN_REVIEW":
            return operations.complete_management_task(session, event.id, actor, outcome, task.id)

        raise ValueError(
            f"Risk-linked task cannot be completed while RiskEvent is {event.status}; "
            "use the owning risk workflow action."
        )
