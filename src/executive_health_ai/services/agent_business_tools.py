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


class AgentBusinessTools:
    """Service boundary for legacy business commands; caller owns transaction."""

    def _evaluate_risk(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        observations = list(session.scalars(select(Observation).where(Observation.patient_id == goal.member_id).order_by(Observation.observed_at.desc()).limit(25)))
        created = 0
        for observation in observations:
            created += RiskEvaluationService().evaluate_observation_safely(session, observation.id).created_event_count
        return {"evaluated": len(observations), "created_events": created, "engine": "deterministic"}

    def _create_followup(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        source = f"agent_goal:{goal.id}:followup"
        task = session.scalar(select(Task).where(Task.patient_id == goal.member_id, Task.source == source))
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
        from executive_health_ai.models import ServiceCatalogItem
        from executive_health_ai.services.member_services import MemberServiceOperations
        item = session.get(ServiceCatalogItem, UUID(str(context['service_item_id'])))
        if item is None or not str(context.get('reason', '')).strip():
            raise ValueError('请选择服务并说明申请原因。')
        row = MemberServiceOperations().request(session, goal.member_id, item.id,
            context['reason'], requested_by=context.get('actor') or goal.owner or '健康管理师')
        return {'service_request_id': str(row.id), 'status': row.status}

    def _progress(self, session: Session, goal: AgentGoal, context: dict[str, Any]) -> dict[str, Any]:
        session.add(AuditLog(patient_id=goal.member_id, actor=str(context.get("actor") or "agent_supervisor"), actor_role="system", action="agent_goal_progress", entity_type="AgentGoal", entity_id=str(goal.id), detail_json={"summary": str(context.get("summary") or "Progress recorded")[:500]}))
        return {"recorded": True}
