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
    enabled: bool = True

    @property
    def responsibility(self):
        if self.mode == "read": return "READ_ONLY"
        return {AUTO:"AUTO_WRITE", MANAGER_APPROVAL:"MANAGER_CONFIRM", DOCTOR_APPROVAL:"DOCTOR_REQUIRED"}[self.permission]


from executive_health_ai.services.agent_business_tools import AgentBusinessTools


class AgentToolRegistry(AgentBusinessTools):
    """Explicit allow-list.  There is deliberately no diagnosis or risk-write tool."""

    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}
        self._register_defaults()
        from executive_health_ai.agent.post_checkup import register_tools
        register_tools(self)
        from executive_health_ai.agent.profile_intake import register_tools as register_profile_tools
        register_profile_tools(self)
        from executive_health_ai.services.care_tools import register
        register(self)

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
        from executive_health_ai.services.member_archive import require_active
        require_active(session,goal.member_id)
        tool = self.get(name)
        if not tool.enabled:
            raise ValueError("此能力尚未配置。")
        from executive_health_ai.agent.profile_intake import is_profile_goal
        profile_tools = {"parse_profile_document", "match_profile_document", "approve_profile_document", "request_profile_review"}
        if name in profile_tools and not is_profile_goal(goal):
            raise PermissionError("资料导入工具不能用于其他流程。")
        if is_profile_goal(goal):
            allowed = {"PARSING": "parse_profile_document", "MATCHING": "match_profile_document", "REVIEW": "approve_profile_document"}
            if tool.mode == "write" and (name not in profile_tools or allowed.get(goal.current_stage) != name and not (name == "request_profile_review" and goal.current_stage == "REVIEW" and goal.status == "WAITING_MANAGER")):
                raise PermissionError("此步骤不可执行该资料写入。")
            if name == "approve_profile_document" and goal.status != "WRITING":
                raise PermissionError("请先提交有权限的健管确认。")
        from executive_health_ai.agent.post_checkup import is_care_goal
        if is_care_goal(goal):
            from executive_health_ai.agent.care_routing import guard
            if tool.mode == 'write':
                # V1 can only write through its existing human-gated services.
                if name not in {'confirm_report_preparation','create_doctor_review','create_care_arrangements'}:
                    raise ValueError('此流程只能执行已确认的健康管理安排。')
                guard(session, goal, actions=name == 'create_care_arrangements')
        if tool.permission == MANAGER_APPROVAL and approved_role not in {"HEALTH_MANAGER", "ADMIN"}:
            raise PermissionError("Health manager approval is required.")
        if tool.permission == DOCTOR_APPROVAL:
            raise PermissionError("Clinical actions must be completed in DoctorReview.")
        from executive_health_ai.services.tool_execution import execute
        return execute(session, tool, goal, context or {})

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
