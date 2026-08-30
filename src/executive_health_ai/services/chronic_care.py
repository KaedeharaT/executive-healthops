"""Human-operated chronic-care journey services.

The service layer only records operational decisions made by named humans.  It
does not diagnose, prescribe, alter medication, or make clinical decisions.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.models import (
    AnnualHealthAccount, AuditLog, ExecutionBarrier, HealthJourney, HealthProblem,
    HealthProgram, ManagementPlan, OutcomeEvaluation, ProgramPhase, ServiceEvent,
    Task, WeeklyReview,
)
from executive_health_ai.models.base import utc_now

RISK_LEVELS = {"LOW", "MODERATE", "HIGH", "NEEDS_MEDICAL_EVALUATION"}
PROGRAM_TYPES = {"NINETY_DAY", "STABILIZATION", "ANNUAL"}
BARRIER_REASONS = {
    "TRAVEL", "WORK_PRESSURE", "SOCIAL_DINING", "POOR_SLEEP", "TOO_DIFFICULT",
    "FORGOT", "LOW_MOTIVATION", "SIDE_EFFECT_CONCERN", "FAMILY_REASON",
    "SCHEDULE_CONFLICT", "OTHER",
}
OUTCOME_RESULTS = {"IMPROVED", "STABLE", "WORSENED", "INSUFFICIENT_DATA", "NEEDS_MEDICAL_REVIEW"}


def _audit(session: Session, patient_id: UUID, actor: str, role: str, action: str, entity: object, detail: dict[str, object] | None = None) -> None:
    session.add(AuditLog(patient_id=patient_id, actor=actor, actor_role=role, action=action, entity_type=entity.__class__.__name__, entity_id=str(entity.id), detail_json=detail or {}))


def create_assessment(
    session: Session, patient_id: UUID, assessment_summary: str, main_focus: str,
    risk_level: str, supporting_goals: list[str], baseline: dict[str, object],
    owner: str, doctor: str | None = None,
) -> HealthJourney:
    """Create an assessment record; risk tier remains a named human assessment."""
    if risk_level not in RISK_LEVELS:
        raise ValueError("Unsupported risk level.")
    if not assessment_summary.strip() or not main_focus.strip():
        raise ValueError("Assessment summary and 90-day focus are required.")
    journey = HealthJourney(patient_id=patient_id, current_stage="ASSESSMENT", status="ACTIVE", risk_level=risk_level, assessment_summary=assessment_summary.strip(), main_focus=main_focus.strip(), supporting_goals_json=[goal.strip() for goal in supporting_goals if goal.strip()], baseline_json=baseline, owner=owner, doctor=doctor)
    session.add(journey)
    session.flush()
    _audit(session, patient_id, owner, "health_manager", "created_assessment", journey, {"risk_level": risk_level})
    return journey


def create_program(
    session: Session, journey: HealthJourney, program_type: str, title: str, main_goal: str,
    supporting_goals: list[str], start_date: date, owner: str, doctor: str | None = None,
    priority_problems: list[HealthProblem] | None = None, end_date: date | None = None,
) -> HealthProgram:
    if program_type not in PROGRAM_TYPES:
        raise ValueError("Unsupported program type.")
    if not main_goal.strip():
        raise ValueError("A HealthProgram must have one explicit main goal.")
    if not title.strip():
        raise ValueError("Program title is required.")
    if end_date is None:
        end_date = start_date + timedelta(days=89 if program_type == "NINETY_DAY" else 181 if program_type == "STABILIZATION" else 364)
    program = HealthProgram(patient_id=journey.patient_id, journey_id=journey.id, program_type=program_type, title=title.strip(), main_goal=main_goal.strip(), supporting_goals_json=[goal.strip() for goal in supporting_goals if goal.strip()], status="ACTIVE", current_phase="STARTUP" if program_type == "NINETY_DAY" else "ONGOING", owner=owner, doctor=doctor or journey.doctor, start_date=start_date, end_date=end_date)
    session.add(program)
    session.flush()
    stage = {"NINETY_DAY": "90_DAY_PROGRAM", "STABILIZATION": "STABILIZATION", "ANNUAL": "ANNUAL_MANAGEMENT"}[program_type]
    journey.current_stage = stage
    for rank, problem in enumerate(priority_problems or [], start=1):
        if problem.patient_id != journey.patient_id:
            raise ValueError("Priority problem must belong to the journey member.")
        problem.program_id, problem.priority_rank = program.id, rank
    if program_type == "NINETY_DAY":
        _create_ninety_day_phases(session, program)
    _audit(session, journey.patient_id, owner, "health_manager", "created_health_program", program, {"program_type": program_type, "main_goal": program.main_goal})
    return program


def _create_ninety_day_phases(session: Session, program: HealthProgram) -> None:
    phases = [
        ("STARTUP", "启动", 1, 0, 13, "完成基线、确认优先问题与最少必要行动。"),
        ("EXECUTION", "执行", 2, 14, 41, "观察实际执行、数据趋势与中断原因。"),
        ("STABILIZATION", "稳定", 3, 42, 69, "在出差、应酬和工作高峰中测试可持续性。"),
        ("REASSESSMENT", "复评", 4, 70, 89, "比较基线与当前状态，确认下一阶段。"),
    ]
    for code, title, sequence, start_offset, end_offset, goal in phases:
        session.add(ProgramPhase(program_id=program.id, phase_code=code, title=title, sequence=sequence, start_date=program.start_date + timedelta(days=start_offset), end_date=program.start_date + timedelta(days=end_offset), status="ACTIVE" if sequence == 1 else "PLANNED", goal=goal))


def progress_program_phase(session: Session, program: HealthProgram, phase_code: str, actor: str) -> ProgramPhase:
    phase = session.scalar(select(ProgramPhase).where(ProgramPhase.program_id == program.id, ProgramPhase.phase_code == phase_code))
    if phase is None:
        raise ValueError("Program phase not found.")
    active = session.scalar(select(ProgramPhase).where(ProgramPhase.program_id == program.id, ProgramPhase.status == "ACTIVE"))
    if active and active.id != phase.id:
        active.status = "COMPLETED"
    phase.status = "ACTIVE"
    program.current_phase = phase_code
    _audit(session, program.patient_id, actor, "health_manager", "progressed_program_phase", phase, {"phase": phase_code})
    return phase


def create_program_task(session: Session, program: HealthProgram, title: str, instruction: str, due_at, assignee: str, actor: str, priority: str = "MEDIUM", problem: HealthProblem | None = None) -> Task:
    if problem and problem.patient_id != program.patient_id:
        raise ValueError("Problem does not belong to this program member.")
    task = Task(patient_id=program.patient_id, program_id=program.id, health_problem_id=problem.id if problem else None, title=title, instruction=instruction, status="PENDING", priority=priority, assignee=assignee, responsible_role="member", due_at=due_at, source="health_program_human_task")
    session.add(task)
    session.flush()
    _audit(session, program.patient_id, actor, "health_manager", "created_program_task", task, {"program_id": str(program.id)})
    return task


def record_execution_barrier(session: Session, program: HealthProgram, reason: str, description: str, confirmed_by: str, task: Task | None = None, resolution: str | None = None) -> ExecutionBarrier:
    if reason not in BARRIER_REASONS:
        raise ValueError("Unsupported execution barrier reason.")
    if task and (task.patient_id != program.patient_id or task.program_id not in {None, program.id}):
        raise ValueError("Task cannot be linked to this program barrier.")
    barrier = ExecutionBarrier(patient_id=program.patient_id, program_id=program.id, task_id=task.id if task else None, reason=reason, description=description, confirmed_by=confirmed_by, resolution=resolution, status="RESOLVED" if resolution else "OPEN", resolved_at=utc_now() if resolution else None)
    session.add(barrier)
    session.flush()
    session.add(ServiceEvent(patient_id=program.patient_id, event_type="execution_risk", status="confirmed", owner=confirmed_by, detail=f"{reason}: {description}", source="health_program"))
    _audit(session, program.patient_id, confirmed_by, "health_manager", "recorded_execution_barrier", barrier, {"reason": reason, "task_id": str(task.id) if task else None})
    return barrier


def adjust_management_plan(session: Session, plan: ManagementPlan, actor: str, reason: str, revised_content: str, requires_doctor_review: bool = False) -> ManagementPlan:
    """Record a human operational adjustment, never a medication instruction."""
    if not reason.strip() or not revised_content.strip():
        raise ValueError("Adjustment reason and revised plan content are required.")
    plan.status = "ADJUSTED"
    plan.adjustment_reason, plan.adjusted_by, plan.adjusted_at = reason.strip(), actor, utc_now()
    plan.content = revised_content.strip()
    _audit(session, plan.patient_id, actor, "health_manager", "adjusted_management_plan", plan, {"requires_doctor_review": requires_doctor_review})
    if requires_doctor_review:
        session.add(ServiceEvent(patient_id=plan.patient_id, event_type="medical_referral", status="PENDING_DOCTOR_REVIEW", owner=actor, detail=reason.strip(), source="health_program"))
    return plan


def record_weekly_review(session: Session, program: HealthProgram, week_number: int, task_completion: str, data_completeness: str, key_changes: str, next_week_focus: str, reviewed_by: str, execution_barriers: str | None = None, manager_notes: str | None = None, adjustment: str | None = None) -> WeeklyReview:
    if week_number < 1:
        raise ValueError("Week number must be positive.")
    review = WeeklyReview(program_id=program.id, week_number=week_number, task_completion=task_completion, data_completeness=data_completeness, key_changes=key_changes, execution_barriers=execution_barriers, manager_notes=manager_notes, adjustment=adjustment, next_week_focus=next_week_focus, reviewed_by=reviewed_by)
    session.add(review)
    session.flush()
    _audit(session, program.patient_id, reviewed_by, "health_manager", "recorded_weekly_review", review, {"week_number": week_number})
    return review


def record_outcome_evaluation(session: Session, program: HealthProgram, metric: str, baseline_value: str, current_value: str, unit: str, direction: str, evaluator: str, evidence: str, result: str, target_value: str | None = None, notes: str | None = None, evaluation_date: date | None = None) -> OutcomeEvaluation:
    if result not in OUTCOME_RESULTS:
        raise ValueError("Unsupported outcome result.")
    outcome = OutcomeEvaluation(patient_id=program.patient_id, program_id=program.id, metric=metric, baseline_value=baseline_value, current_value=current_value, target_value=target_value, unit=unit, direction=direction, evaluation_date=evaluation_date or date.today(), evaluator=evaluator, evidence=evidence, result=result, notes=notes)
    session.add(outcome)
    session.flush()
    _audit(session, program.patient_id, evaluator, "health_manager", "recorded_outcome_evaluation", outcome, {"result": result, "metric": metric})
    return outcome


def escalate_to_medical_care(session: Session, program: HealthProgram, actor: str, reason: str) -> None:
    program.status = "ESCALATED_TO_MEDICAL_CARE"
    program.next_decision = "MEDICAL_REFERRAL"
    session.add(ServiceEvent(patient_id=program.patient_id, event_type="medical_referral", status="PENDING_DOCTOR_REVIEW", owner=actor, detail=reason, source="health_program"))
    _audit(session, program.patient_id, actor, "health_manager", "escalated_to_medical_care", program, {"reason": reason})


def transition_to_stabilization(session: Session, program: HealthProgram, actor: str) -> HealthProgram:
    if program.program_type != "NINETY_DAY":
        raise ValueError("Only a 90-day program can transition to stabilization.")
    program.status, program.next_decision = "COMPLETED", "STABILIZATION"
    journey = session.get(HealthJourney, program.journey_id)
    assert journey is not None
    follow_on = create_program(session, journey, "STABILIZATION", "半年稳定管理", program.main_goal, list(program.supporting_goals_json), program.end_date or date.today(), actor, program.doctor, end_date=(program.end_date or date.today()) + timedelta(days=181))
    _audit(session, program.patient_id, actor, "health_manager", "transitioned_to_stabilization", follow_on, {"from_program_id": str(program.id)})
    return follow_on


def create_annual_account(session: Session, journey: HealthJourney, year: int, annual_goal: str, owner: str, next_review_date: date | None = None) -> AnnualHealthAccount:
    account = AnnualHealthAccount(patient_id=journey.patient_id, journey_id=journey.id, year=year, annual_goal=annual_goal, owner=owner, next_review_date=next_review_date)
    session.add(account)
    session.flush()
    _audit(session, journey.patient_id, owner, "care_coordinator", "created_annual_health_account", account, {"year": year})
    return account
