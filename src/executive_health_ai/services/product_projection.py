"""Read-only product context over existing facts; no persistence or commands.

Build once per page run/session, never cache detached ORM instances across runs.
"""
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select

from executive_health_ai.models import (
    Alert, AgentApprovalRequest, AgentGoal, DoctorReview, HealthAssessment,
    HealthProgram, Observation, ServiceRequest, Task, OutcomeEvaluation, HealthProblem, MedicationPlan, ProgramPhase,
)
from executive_health_ai.services.longitudinal import HealthAssessmentService
from executive_health_ai.services.health_visualization import HealthVisualizationService
from executive_health_ai.services.baseline_visualization import BaselineVisualizationService
from executive_health_ai.services.operational_worklist import OperationalWorkItem, OperationalWorklistService


def current_program(programs):
    priority = {"ACTIVE": 0, "PAUSED": 1, "PLANNED": 2}
    eligible = [p for p in programs if p.status in priority]
    enrolled = [p for p in eligible if getattr(p, 'cycle_year', None) == datetime.now().year]
    if enrolled:
        eligible = enrolled
    return min(eligible, key=lambda p: (priority[p.status], -p.created_at.timestamp(), str(p.id))) if eligible else None


def observations(session, patient_id, metric=None, since=None):
    query = select(Observation).where(Observation.patient_id == patient_id, Observation.source_deleted.is_(False), Observation.excluded_from_analysis.is_(False), Observation.quality_flag.in_(("valid", "manually_corrected")))
    if metric:
        query = query.where(Observation.metric_code == metric)
    if since:
        query = query.where(Observation.observed_at >= since)
    return list(session.scalars(query.order_by(Observation.observed_at, Observation.created_at)))


def pending_doctor_work(session, patient_id=None):
    reviews = select(DoctorReview).where(DoctorReview.status == "PENDING")
    baselines = select(HealthAssessment).where(HealthAssessment.status == "WAITING_MEDICAL_REVIEW")
    alerts = select(Alert).where(Alert.status == "WAITING_DOCTOR_REVIEW", Alert.health_problem_id.is_not(None))
    if patient_id:
        reviews = reviews.where(DoctorReview.patient_id == patient_id)
        baselines = baselines.where(HealthAssessment.patient_id == patient_id)
        alerts = alerts.where(Alert.patient_id == patient_id)
    rows = list(session.scalars(reviews))
    linked = {r.health_problem_id for r in rows if r.health_problem_id}
    return rows + list(session.scalars(baselines)) + [a for a in session.scalars(alerts) if a.health_problem_id not in linked]


@dataclass(frozen=True)
class HealthStatusView:
    baseline: object
    series: tuple


@dataclass(frozen=True)
class Member360View:
    patient_id: object
    program: object
    programs: tuple
    tasks: tuple
    services: tuple
    pending_doctor: tuple
    baseline: object
    observations: tuple
    health: HealthStatusView | None
    outcomes: tuple = ()
    phases: tuple = ()

    @property
    def phase_title(self):
        return next((p.title for p in self.phases if p.status == 'ACTIVE'), None)

    @property
    def owner(self):
        return self.program.owner if self.program and self.program.owner else "待确认"

    @property
    def active_tasks(self):
        return tuple(t for t in self.tasks if t.status not in {"COMPLETED", "CANCELLED"})

    @property
    def member_actions(self):
        return tuple(t for t in self.active_tasks if t.responsible_role == "member")

    @property
    def current_outcomes(self):
        return tuple(o for o in self.outcomes if self.program and o.program_id == self.program.id)

    @property
    def historical_outcomes(self):
        return tuple(o for o in self.outcomes if not self.program or o.program_id != self.program.id)

    @property
    def cycle(self):
        if self.program and getattr(self.program, 'cycle_year', None):
            return f"{self.program.cycle_year}年度健康管理"
        return f"{self.baseline.cycle_year or self.baseline.assessed_at.year}年度健康管理" if self.baseline else "年度周期待确认"


@dataclass(frozen=True)
class ManagerWorkView:
    items: tuple
    pending_doctor: tuple

    def counts(self, now):
        local = ZoneInfo("Asia/Tokyo")
        now = now.astimezone(local)
        def due(item):
            at = item.due_at
            return (at.replace(tzinfo=timezone.utc) if at and at.tzinfo is None else at).astimezone(local) if at else None
        waiting = {"等待成员", "等待医生", "WAITING_MEMBER", "WAITING_DOCTOR"}
        return (("今天待处理", sum(i.status not in waiting and due(i) is not None and due(i).date() == now.date() for i in self.items)),
                ("已逾期", sum(due(i) is not None and due(i) < now for i in self.items)),
                ("等待医生", len(self.pending_doctor)),
                ("等待成员", sum(i.status in {"等待成员", "WAITING_MEMBER"} for i in self.items)),
                ("高优先级", sum(i.priority <= 1 for i in self.items)))


@dataclass(frozen=True)
class DoctorReviewView:
    member: Member360View
    problem: object
    medications: tuple
    completed_actions: tuple


class ProductProjectionService:
    def health(self, session, patient_id, *, cycle_year=None):
        confirmed = HealthAssessmentService().latest_baseline(session, patient_id, include_draft=False, cycle_year=cycle_year)
        return HealthStatusView(BaselineVisualizationService().build(session, patient_id, cycle_year=cycle_year) if confirmed else None, HealthVisualizationService().build(session, patient_id))

    def member(self, session, patient_id, *, health=False):
        programs = tuple(session.scalars(select(HealthProgram).where(HealthProgram.patient_id == patient_id).order_by(HealthProgram.created_at.desc())))
        baseline = HealthAssessmentService().latest_baseline(session, patient_id)
        program = current_program(programs)
        return Member360View(patient_id, current_program(programs), programs,
            tuple(session.scalars(select(Task).where(Task.patient_id == patient_id).order_by(Task.due_at, Task.created_at))),
            tuple(session.scalars(select(ServiceRequest).where(ServiceRequest.patient_id == patient_id).order_by(ServiceRequest.requested_at.desc()))),
            tuple(pending_doctor_work(session, patient_id)), baseline,
            tuple(observations(session, patient_id)),
            self.health(session, patient_id, cycle_year=baseline.cycle_year if baseline else None) if health else None,
            tuple(session.scalars(select(OutcomeEvaluation).where(OutcomeEvaluation.patient_id == patient_id).order_by(OutcomeEvaluation.evaluation_date.desc()))),
            tuple(session.scalars(select(ProgramPhase).where(ProgramPhase.program_id == program.id).order_by(ProgramPhase.sequence))) if program else ())

    def doctor(self, session, review):
        member = self.member(session, review.patient_id)
        return DoctorReviewView(member, session.get(HealthProblem, review.health_problem_id) if review.health_problem_id else None,
            tuple(session.scalars(select(MedicationPlan).where(MedicationPlan.patient_id == review.patient_id))),
            tuple(sorted((t for t in member.tasks if t.status == "COMPLETED"), key=lambda t: t.created_at, reverse=True)))

    def manager(self, session, now):
        items = OperationalWorklistService().list_items(session, now)
        service_ids = {i.source_id for i in items if i.source_type == "service_request"}
        service_states = {r.id: r.status for r in session.scalars(select(ServiceRequest).where(ServiceRequest.id.in_(service_ids)))} if service_ids else {}
        # Preserve raw workflow state; UI applies the shared service vocabulary.
        items = [replace(i, status=service_states[i.source_id]) if i.source_type == "service_request" and i.source_id in service_states else i for i in items]
        pending = tuple(pending_doctor_work(session))
        represented_reviews = {i.source_id for i in items if i.source_type == "doctor_review"}
        represented_risks = {i.source_id for i in items if i.source_type == "risk_event"}
        for record in pending:
            if isinstance(record, DoctorReview) and (record.id in represented_reviews or record.risk_event_id in represented_risks):
                continue
            source = "baseline_review" if isinstance(record, HealthAssessment) else "doctor_review" if isinstance(record, DoctorReview) else "legacy_medical_review"
            items.append(OperationalWorkItem(record.patient_id, source, record.id, 4, "等待医生",
                "年度基线医学确认" if source == "baseline_review" else "医学资料复核",
                "已有人工提交的医学确认，需要医生判断。", "查看医学问题与依据", None,
                owner="内部医生", route_target="doctor_review", created_at=getattr(record, "created_at", None)))
        # Approval is a human responsibility, not a second editable goal/task.
        approvals = session.execute(select(AgentApprovalRequest, AgentGoal).join(AgentGoal, AgentApprovalRequest.goal_id == AgentGoal.id).where(AgentApprovalRequest.status == "PENDING"))
        for approval, goal in approvals:
            items.append(OperationalWorkItem(goal.member_id, "automation_approval", approval.id, 2,
                "等待医生" if approval.required_role == "DOCTOR" else "等待健管",
                "确认后续健康管理安排", goal.title, goal.next_action or "确认是否继续现有管理安排", None,
                owner="内部医生" if approval.required_role == "DOCTOR" else goal.owner or "健康管理师",
                route_target="doctor_review" if approval.required_role == "DOCTOR" else "member_management"))
        return ManagerWorkView(tuple(items), pending)
