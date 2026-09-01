"""Deprecated V0.1 Alert compatibility workflow.

Current risk detection and operations use RiskEvent.  These functions remain
only for historical fixtures and explicitly deprecated API compatibility.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.ai.doctor_brief_agent import build_doctor_brief
from executive_health_ai.ai.signal_agent import screen_persistent_bp_signal
from executive_health_ai.models import (
    AgentRun, Alert, AuditLog, DoctorReview, FollowUp, HealthProblem,
    ManagementPlan, ServiceEvent, Task,
)
from executive_health_ai.models.base import utc_now


def _audit(session: Session, patient_id: UUID, actor: str, actor_role: str, action: str, entity: object, detail: dict[str, object] | None = None) -> None:
    session.add(AuditLog(patient_id=patient_id, actor=actor, actor_role=actor_role, action=action, entity_type=entity.__class__.__name__, entity_id=str(getattr(entity, "id")), detail_json=detail or {}))


def screen_member(session: Session, patient_id: UUID) -> Alert | None:
    """Deprecated: create a legacy V0.1 Alert for compatibility tests only."""
    alert = screen_persistent_bp_signal(session, patient_id)
    if alert is not None:
        _audit(session, patient_id, "signal_agent", "system", "screened_alert", alert)
    return alert


def confirm_alert_as_manager(
    session: Session,
    alert: Alert,
    manager_name: str,
    review_note: str,
    problem_id: UUID | None = None,
) -> HealthProblem:
    """Record a manager confirmation and create/link a non-diagnostic problem."""
    if alert.status not in {"NEW", "AI_SCREENED", "WAITING_MANAGER_REVIEW"}:
        raise ValueError(f"Alert in {alert.status} cannot be manager-confirmed.")
    problem = session.get(HealthProblem, problem_id) if problem_id else None
    if problem is not None and (problem.patient_id != alert.patient_id or problem.status == "CLOSED"):
        raise ValueError("Selected HealthProblem cannot be linked to this Alert.")
    if problem is None:
        problem = session.scalar(select(HealthProblem).where(HealthProblem.patient_id == alert.patient_id, HealthProblem.title == "血压记录模式待医生复核", HealthProblem.status != "CLOSED"))
    if problem is None:
        problem = HealthProblem(patient_id=alert.patient_id, program_id=alert.program_id, title="血压记录模式待医生复核", description="由健康管理师确认需进入医生复核的血压数据模式；不是诊断。", severity=alert.severity, responsible_role="doctor", owner=None, source="manager_review")
        session.add(problem)
        session.flush()
    alert.health_problem_id = problem.id
    alert.status = "WAITING_DOCTOR_REVIEW"
    alert.reviewed_by = manager_name
    alert.reviewed_at = utc_now()
    alert.review_note = review_note
    _audit(session, alert.patient_id, manager_name, "health_manager", "confirmed_alert", alert, {"problem_id": str(problem.id)})
    session.add(ServiceEvent(patient_id=alert.patient_id, event_type="manager_review", status="completed", owner=manager_name, detail=review_note, source="workflow"))
    session.flush()
    return problem


def close_alert_as_false_positive(
    session: Session, alert: Alert, manager_name: str, review_note: str
) -> None:
    """Close a screening item only after a named manager records the rationale."""
    if alert.status not in {"NEW", "AI_SCREENED", "WAITING_MANAGER_REVIEW"}:
        raise ValueError(f"Alert in {alert.status} cannot be closed as a false positive.")
    alert.status = "CLOSED"
    alert.reviewed_by = manager_name
    alert.reviewed_at = utc_now()
    alert.review_note = f"[数据核实：误报/不升级] {review_note}"
    _audit(session, alert.patient_id, manager_name, "health_manager", "closed_alert_as_false_positive", alert)
    session.add(ServiceEvent(patient_id=alert.patient_id, event_type="manager_review", status="closed_false_positive", owner=manager_name, detail=review_note, source="workflow"))
    session.flush()


def create_operational_task(
    session: Session,
    patient_id: UUID,
    title: str,
    instruction: str,
    priority: str,
    assignee: str,
    actor: str,
    due_at: datetime | None = None,
    alert: Alert | None = None,
    problem: HealthProblem | None = None,
    program_id: UUID | None = None,
) -> Task:
    """Create a human-requested HealthOps task with an immutable audit record."""
    if alert is not None and alert.patient_id != patient_id:
        raise ValueError("Alert does not belong to this member.")
    if problem is not None and problem.patient_id != patient_id:
        raise ValueError("HealthProblem does not belong to this member.")
    task = Task(
        patient_id=patient_id, program_id=program_id or (problem.program_id if problem else alert.program_id if alert else None),
        health_problem_id=problem.id if problem else (alert.health_problem_id if alert else None),
        alert_id=alert.id if alert else None,
        title=title,
        instruction=instruction,
        priority=priority,
        assignee=assignee,
        responsible_role="health_manager",
        due_at=due_at,
        source="health_manager_manual_task",
    )
    session.add(task)
    session.flush()
    _audit(session, patient_id, actor, "health_manager", "created_operational_task", task)
    return task


def record_doctor_review(
    session: Session, problem: HealthProblem, doctor_name: str, department: str, opinion: str, alert: Alert | None = None
) -> tuple[DoctorReview, ManagementPlan, Task]:
    """Persist a clinician opinion and create a follow-up task, never a prescription."""
    linked_alert = alert or session.scalar(select(Alert).where(Alert.health_problem_id == problem.id).order_by(Alert.created_at.desc()))
    brief = build_doctor_brief(session, problem.patient_id, problem, linked_alert)
    review = DoctorReview(patient_id=problem.patient_id, program_id=problem.program_id, health_problem_id=problem.id, alert_id=linked_alert.id if linked_alert else None, doctor_name=doctor_name, department=department, doctor_brief=brief, question_for_doctor="请确认数据模式、后续复查与管理安排。", opinion=opinion, status="CONFIRMED")
    session.add(review)
    session.flush()
    plan = ManagementPlan(patient_id=problem.patient_id, program_id=problem.program_id, health_problem_id=problem.id, doctor_review_id=review.id, title="医生复核后的随访管理计划", content="按医生确认意见执行记录与随访；系统不自动生成或变更药物治疗。", status="ACTIVE", owner=doctor_name, source="doctor_review", start_date=date.today())
    session.add(plan)
    session.flush()
    task = Task(patient_id=problem.patient_id, program_id=problem.program_id, health_problem_id=problem.id, management_plan_id=plan.id, alert_id=linked_alert.id if linked_alert else None, title="完成既定血压复查记录", instruction="按既定测量流程完成连续记录，并在随访中由医疗团队复核。", priority="HIGH", assignee="member", responsible_role="member", source="task_agent_draft_confirmed_by_workflow")
    session.add(task)
    if linked_alert is not None:
        linked_alert.status = "IN_FOLLOW_UP"
    problem.responsible_role = "health_manager"
    _audit(session, problem.patient_id, doctor_name, "doctor", "recorded_doctor_review", review, {"management_plan_id": str(plan.id), "task_id": str(task.id)})
    session.add(AgentRun(patient_id=problem.patient_id, agent_name="doctor_brief_agent", status="completed", input_reference_json={"problem_id": str(problem.id)}, output_json={"doctor_review_id": str(review.id)}, needs_human_review=True))
    session.add(ServiceEvent(patient_id=problem.patient_id, event_type="doctor_review", status="completed", owner=doctor_name, detail="Doctor review recorded.", source="workflow"))
    session.flush()
    return review, plan, task


def complete_follow_up(session: Session, problem: HealthProblem, reviewer: str, outcome: str, task: Task | None = None) -> FollowUp:
    """Close the demo workflow only after a named human records an outcome."""
    related_task = task or session.scalar(select(Task).where(
        Task.health_problem_id == problem.id,
        Task.status.not_in(("COMPLETED", "CANCELLED")),
    ).order_by(Task.created_at.desc()))
    if related_task is not None:
        from executive_health_ai.services.task_transitions import TaskTransitionService

        TaskTransitionService().complete(
            session, related_task.id, actor=reviewer, outcome=outcome,
        )
    follow_up = FollowUp(patient_id=problem.patient_id, health_problem_id=problem.id, task_id=related_task.id if related_task else None, status="COMPLETED", completed_at=utc_now(), outcome=outcome, reviewed_by=reviewer, source="health_manager_follow_up")
    session.add(follow_up)
    problem.status = "CLOSED"
    problem.closed_at = utc_now()
    for alert in session.scalars(select(Alert).where(Alert.health_problem_id == problem.id)):
        alert.status = "CLOSED"
        alert.reviewed_by = reviewer
        alert.reviewed_at = utc_now()
    for plan in session.scalars(select(ManagementPlan).where(ManagementPlan.health_problem_id == problem.id)):
        plan.status = "CLOSED"
    _audit(session, problem.patient_id, reviewer, "health_manager", "closed_follow_up", problem, {"outcome": outcome})
    session.add(ServiceEvent(patient_id=problem.patient_id, event_type="follow_up", status="closed", owner=reviewer, detail=outcome, source="workflow"))
    session.flush()
    return follow_up
