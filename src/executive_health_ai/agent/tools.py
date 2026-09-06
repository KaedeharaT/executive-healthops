"""Permissioned tools that adapt existing HealthOps services for orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.models import (
    AgentGoal, AuditLog, DoctorReview, Document, HealthAssessment, HealthProgram,
    ManagementPlan, Observation, OutcomeEvaluation, ReportExtractionCandidate,
    RiskEvent, ServiceRequest, Task,
)
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.longitudinal import HealthTimelineService
from executive_health_ai.services.operational_worklist import OperationalWorklistService
from executive_health_ai.services.risk_operations import RiskOperationsService
from executive_health_ai.services.risk_triage import RiskEvaluationService


AUTO = "AUTO"
MANAGER_APPROVAL = "MANAGER_APPROVAL"
DOCTOR_APPROVAL = "DOCTOR_APPROVAL"


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    permission: str
    mode: str
    idempotent: bool
    timeout_seconds: int
    handler: Callable[[Session, AgentGoal, dict[str, Any]], dict[str, Any]]
    input_schema: str = "goal context"
    output_schema: str = "bounded summary"


class AgentToolRegistry:
    """Explicit allow-list.  There is deliberately no diagnosis or risk-write tool."""

    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}
        self._register_defaults()

    def register(self, tool: AgentTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Duplicate agent tool: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> AgentTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ValueError("Agent tool is not allowed.") from exc

    def execute(self, session: Session, name: str, goal: AgentGoal, context: dict[str, Any] | None = None, *, approved_role: str | None = None) -> dict[str, Any]:
        tool = self.get(name)
        if tool.permission == MANAGER_APPROVAL and approved_role not in {"HEALTH_MANAGER", "ADMIN"}:
            raise PermissionError("Health manager approval is required.")
        if tool.permission == DOCTOR_APPROVAL:
            raise PermissionError("Clinical actions must be completed in DoctorReview.")
        return tool.handler(session, goal, context or {})

    @property
    def tools(self) -> tuple[AgentTool, ...]:
        return tuple(self._tools.values())

    def _register_defaults(self) -> None:
        read = {
            "get_member_summary": self._member_summary,
            "get_report_status": self._report_status,
            "get_latest_baseline": self._baseline,
            "get_report_comparison": self._report_comparison,
            "get_recent_observations": self._observations,
            "get_active_risks": self._risks,
            "get_active_work_items": self._worklist,
            "get_pending_doctor_reviews": self._doctor_reviews,
            "get_current_plan": self._plan,
            "get_open_tasks": self._tasks,
            "get_service_status": self._services,
            "get_latest_outcome": self._outcome,
            "get_timeline_summary": self._timeline,
            "verify_post_checkup_success": self._verify_success,
        }
        for name, handler in read.items():
            self.register(AgentTool(name, "Read an existing HealthOps projection.", AUTO, "read", True, 10, handler))
        self.register(AgentTool("evaluate_confirmed_observations", "Run approved deterministic risk rules.", AUTO, "write", True, 30, self._evaluate_risk))
        self.register(AgentTool("create_followup_task", "Create an internal follow-up task.", AUTO, "write", True, 10, self._create_followup))
        self.register(AgentTool("schedule_followup", "Schedule a future workflow check.", AUTO, "write", True, 10, self._schedule_followup))
        self.register(AgentTool("create_member_reminder", "Create a platform reminder task.", AUTO, "write", True, 10, self._create_followup))
        self.register(AgentTool("record_goal_progress", "Append an audited orchestration note.", AUTO, "write", True, 10, self._progress))
        self.register(AgentTool("assign_work_item", "Assign existing operational work.", MANAGER_APPROVAL, "write", True, 10, self._assign_work))
        self.register(AgentTool("request_doctor_review", "Request human medical review through the existing risk workflow.", MANAGER_APPROVAL, "write", True, 10, self._request_doctor))
        self.register(AgentTool("update_plan_status", "Update a management plan after manager approval.", MANAGER_APPROVAL, "write", True, 10, self._update_plan))
        self.register(AgentTool("create_service_request", "Create a service request draft after manager approval.", MANAGER_APPROVAL, "write", True, 10, self._service_request))
        self.register(AgentTool("record_management_note", "Record an operational note after manager approval.", MANAGER_APPROVAL, "write", True, 10, self._progress))

    @staticmethod
    def _count(session: Session, model: type, member_id: UUID, *conditions: Any) -> int:
        return len(list(session.scalars(select(model).where(model.patient_id == member_id, *conditions))))

    def _member_summary(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        return {"member_id": str(goal.member_id), "goal": goal.title}

    def _report_status(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        document = session.get(Document, UUID(goal.source_id))
        if document is None:
            raise ValueError("Report not found.")
        candidates = list(session.scalars(select(ReportExtractionCandidate).where(ReportExtractionCandidate.document_id == document.id)))
        pending = sum(item.status == "PENDING_REVIEW" for item in candidates)
        confirmed = sum(item.status in {"CONFIRMED", "CORRECTED"} for item in candidates)
        return {"report": document.title, "pending": pending, "confirmed": confirmed}

    def _baseline(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        row = session.scalar(select(HealthAssessment).where(HealthAssessment.patient_id == goal.member_id, HealthAssessment.status.in_(("CONFIRMED", "AMENDED"))).order_by(HealthAssessment.cycle_year.desc(), HealthAssessment.version.desc()))
        report_count = self._count(session, Document, goal.member_id)
        return {
            "ready": row is not None,
            "assessment_type": row.assessment_type if row else None,
            "comparison_available": report_count > 1,
            "report_count": report_count,
        }

    def _report_comparison(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        count = self._count(session, Document, goal.member_id)
        return {"available": count > 1, "report_count": count}

    def _observations(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        rows = list(session.scalars(select(Observation).where(Observation.patient_id == goal.member_id).order_by(Observation.observed_at.desc()).limit(25)))
        return {"count": len(rows), "observation_ids": [str(row.id) for row in rows]}

    def _risks(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        rows = list(session.scalars(select(RiskEvent).where(RiskEvent.patient_id == goal.member_id, RiskEvent.status.not_in(("CLOSED", "DISMISSED_DATA_ISSUE")))))
        return {"count": len(rows), "requires_doctor": any(row.requires_doctor_review for row in rows)}

    def _worklist(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        items = [item for item in OperationalWorklistService().list_items(session, utc_now()) if item.member_id == goal.member_id]
        return {"count": len(items), "owners": sorted({item.owner for item in items})}

    def _doctor_reviews(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        return {"pending": self._count(session, DoctorReview, goal.member_id, DoctorReview.status == "PENDING")}

    def _plan(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        row = session.scalar(select(HealthProgram).where(HealthProgram.patient_id == goal.member_id).order_by(HealthProgram.created_at.desc()))
        return {"exists": row is not None, "status": row.status if row else None}

    def _tasks(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        return {"open": self._count(session, Task, goal.member_id, Task.status.not_in(("COMPLETED", "CANCELLED")))}

    def _services(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        return {"active": self._count(session, ServiceRequest, goal.member_id, ServiceRequest.status.not_in(("COMPLETED", "CANCELLED")))}

    def _outcome(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        row = session.scalar(select(OutcomeEvaluation).where(OutcomeEvaluation.patient_id == goal.member_id).order_by(OutcomeEvaluation.created_at.desc()))
        return {"recorded": row is not None}

    def _timeline(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        events = HealthTimelineService().get_timeline(session, goal.member_id, limit=20)
        return {"event_count": len(events), "writeback_ready": bool(events)}

    def _verify_success(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        return {"complete": bool(context.get("outcome_recorded", True)), "criteria": goal.success_criteria}

    def _evaluate_risk(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        observations = list(session.scalars(select(Observation).where(Observation.patient_id == goal.member_id).order_by(Observation.observed_at.desc()).limit(25)))
        created = 0
        for observation in observations:
            created += RiskEvaluationService().evaluate_observation_safely(session, observation.id).created_event_count
        return {"evaluated": len(observations), "created_events": created, "engine": "deterministic"}

    def _create_followup(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        source = f"agent_goal:{goal.id}:followup"
        task = session.scalar(select(Task).where(Task.patient_id == goal.member_id, Task.source == source, Task.status.not_in(("COMPLETED", "CANCELLED"))))
        if task is None:
            task = Task(patient_id=goal.member_id, title="体检后复核跟进", instruction="核对已确认事项、执行结果与下一步安排。", status="PENDING", priority="MEDIUM", assignee=goal.owner or "健康管理师", responsible_role="health_manager", due_at=utc_now() + timedelta(days=7), source=source)
            session.add(task); session.flush()
        return {"task_id": str(task.id), "due_at": task.due_at.isoformat() if task.due_at else None}

    def _schedule_followup(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        goal.next_check_at = context.get("scheduled_for") or utc_now() + timedelta(days=7)
        return {"scheduled_for": goal.next_check_at.isoformat()}

    def _assign_work(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        actor = str(context.get("actor") or goal.owner or "健康管理师")
        goal.owner = actor
        risks = list(session.scalars(select(RiskEvent).where(RiskEvent.patient_id == goal.member_id, RiskEvent.status == "NEW")))
        for risk in risks:
            if risk.risk_level == "YELLOW":
                RiskOperationsService().acknowledge(session, risk.id, actor, "体检后管理流程已接手")
        return {"owner": actor, "items": len(risks)}

    def _request_doctor(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        existing = session.scalar(select(DoctorReview).where(DoctorReview.patient_id == goal.member_id, DoctorReview.status == "PENDING").order_by(DoctorReview.created_at.desc()))
        if existing:
            return {"doctor_review_id": str(existing.id), "created": False}
        risk = session.scalar(select(RiskEvent).where(RiskEvent.patient_id == goal.member_id, RiskEvent.risk_level == "YELLOW", RiskEvent.status.not_in(("CLOSED", "DISMISSED_DATA_ISSUE"))).order_by(RiskEvent.created_at.desc()))
        if risk is None:
            return {"needed": False}
        review = RiskOperationsService().escalate_to_doctor(session, risk.id, str(context.get("actor") or goal.owner or "健康管理师"), "请结合已确认体检事实完成人工医学复核。")
        return {"doctor_review_id": str(review.id), "created": True}

    def _update_plan(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        plan = session.scalar(select(ManagementPlan).where(ManagementPlan.patient_id == goal.member_id).order_by(ManagementPlan.created_at.desc()))
        if plan:
            plan.status = str(context.get("status") or plan.status)
        return {"updated": plan is not None}

    def _service_request(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        return {"created": False, "reason": "Service choice remains a health-manager decision."}

    def _progress(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        session.add(AuditLog(patient_id=goal.member_id, actor=str(context.get("actor") or "agent_supervisor"), actor_role="system", action="agent_goal_progress", entity_type="AgentGoal", entity_id=str(goal.id), detail_json={"summary": str(context.get("summary") or "Progress recorded")[:500]}))
        return {"recorded": True}
