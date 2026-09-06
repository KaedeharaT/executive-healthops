"""Durable supervisor for bounded post-checkup health operations."""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from executive_health_ai.agent.events import GOAL_START_EVENTS
from executive_health_ai.agent.planner import HealthOpsPlanner
from executive_health_ai.agent.tools import AgentToolRegistry
from executive_health_ai.models import (
    AgentApprovalRequest, AgentEvent, AgentGoal, AgentPlan, AgentPlanStep,
    AgentRunTrace, AuditLog, DoctorReview, RiskEvent,
)
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.event_service import EventService


GOAL_LABELS = {
    "ACTIVE": "进行中", "WAITING": "等待中", "BLOCKED": "需要处理",
    "COMPLETED": "已完成", "FAILED": "执行失败", "CANCELLED": "已取消",
}

WAIT_STEP_STATUSES = {
    "WAITING_EVENT", "WAITING_MEMBER", "WAITING_MANAGER",
    "WAITING_DOCTOR", "WAITING_SERVICE", "WAITING_TIME",
}


class HealthOpsAgentSupervisor:
    """Coordinate existing services without becoming a clinical fact source."""

    def __init__(self, *, registry: AgentToolRegistry | None = None) -> None:
        self.registry = registry or AgentToolRegistry()
        self.planner = HealthOpsPlanner()
        self.default_max_retries = max(0, int(os.getenv("AGENT_MAX_RETRIES", "3")))

    def receive_event(self, session: Session, event: AgentEvent) -> AgentGoal | None:
        if event.status == "PROCESSED":
            return self._goal_for_event(session, event)
        goal: AgentGoal | None
        if event.event_type in GOAL_START_EVENTS:
            goal = self.start_goal(
                session, member_id=event.member_id, goal_type=GOAL_START_EVENTS[event.event_type],
                source_type=event.source_type, source_id=event.source_id,
                title="完成本次体检后健康管理闭环", event_id=event.id,
            )
        else:
            goal = self._goal_for_event(session, event)
            if goal:
                self._resume_for_event(session, goal, event)
        event.status, event.processed_at = "PROCESSED", utc_now()
        if goal:
            goal.last_event_at = event.occurred_at
        session.flush()
        return goal

    def publish_and_receive(self, session: Session, **event_data: Any) -> tuple[AgentEvent, AgentGoal | None, bool]:
        event, created = EventService().publish(session, **event_data)
        return event, self.receive_event(session, event), created

    def start_goal(self, session: Session, *, member_id: UUID, goal_type: str, source_type: str, source_id: str | UUID, title: str, event_id: UUID | None = None, created_by: str = "agent_supervisor") -> AgentGoal:
        source = str(source_id)
        existing = session.scalar(select(AgentGoal).where(AgentGoal.goal_type == goal_type, AgentGoal.source_type == source_type, AgentGoal.source_id == source))
        if existing:
            return existing
        if goal_type != "POST_CHECKUP_MANAGEMENT":
            raise ValueError("V1 only supports post-checkup management goals.")
        goal = AgentGoal(
            member_id=member_id, goal_type=goal_type, title=title, source_type=source_type,
            source_id=source, status="ACTIVE", created_by=created_by,
            success_criteria={
                "report_confirmed": False, "baseline_ready": False, "risk_evaluated": False,
                "work_resolved_or_waiting": False, "doctor_review_complete": True,
                "followup_created": False, "plan_or_task_updated": False,
                "outcome_recorded": False, "timeline_ready": False,
            }, next_action="等待健康管理师确认体检报告",
        )
        session.add(goal); session.flush()
        plan = self.planner.create_plan(session, goal, reason="体检报告上传后启动安全模板计划")
        self._trace(session, goal, plan=plan, event_id=event_id, action="goal_started", status="COMPLETED", summary="体检后管理目标已建立")
        self.execute_next_step(session, goal.id, event_id=event_id)
        return goal

    def execute_next_step(self, session: Session, goal_id: UUID, *, event_id: UUID | None = None) -> AgentGoal:
        goal = self._goal(session, goal_id)
        if goal.status in {"COMPLETED", "FAILED", "CANCELLED"} or goal.automation_paused:
            return goal
        plan = session.get(AgentPlan, goal.current_plan_id)
        if plan is None:
            raise ValueError("Active agent plan not found.")
        while True:
            step = session.scalar(select(AgentPlanStep).where(
                AgentPlanStep.plan_id == plan.id,
                AgentPlanStep.status.in_(("PENDING", "RETRY_WAIT")),
            ).order_by(AgentPlanStep.step_order).limit(1))
            if step is None:
                if all((goal.success_criteria or {}).values()):
                    self.complete_goal(session, goal.id)
                return goal
            now = utc_now()
            if step.status == "RETRY_WAIT" and step.next_retry_at and step.next_retry_at > now:
                goal.status, goal.current_stage, goal.next_check_at = "WAITING", "等待系统重试", step.next_retry_at
                return goal
            claimed = session.execute(update(AgentPlanStep).where(
                AgentPlanStep.id == step.id, AgentPlanStep.status == step.status,
            ).values(status="RUNNING", started_at=now)).rowcount
            if claimed != 1:
                session.expire_all()
                return self._goal(session, goal_id)
            session.flush(); session.refresh(step)

            if step.step_type == "WAIT_REPORT_CONFIRMATION":
                self._wait_for_event(session, goal, plan, step, "WAITING_MANAGER", "等待健康管理师确认报告", "健康管理师确认报告事实", event_id=event_id, approval_role="HEALTH_MANAGER")
                return goal
            if step.step_type == "WAIT_MANAGER_ACTION":
                step.status, step.completed_at, step.result_summary = "COMPLETED", now, "健康管理师已接手当前流程"
                continue
            if step.step_type == "WAIT_DOCTOR":
                if not self._doctor_needed(session, goal):
                    step.status, step.completed_at, step.result_summary = "SKIPPED", now, "当前流程不需要医生复核"
                    self._criterion(goal, "doctor_review_complete", True)
                    continue
                self._wait_for_event(session, goal, plan, step, "WAITING_DOCTOR", "等待医生完成医学复核", "医生复核完成后自动继续", event_id=event_id)
                return goal
            if step.step_type == "WAIT_FOLLOWUP":
                scheduled = step.scheduled_for or now + timedelta(days=7)
                step.scheduled_for = scheduled
                goal.next_check_at = scheduled
                self._wait_for_event(session, goal, plan, step, "WAITING_TIME", "等待下一次复核", f"{scheduled.date().isoformat()} 检查随访结果", event_id=event_id)
                return goal
            if step.step_type == "CHECK_OUTCOME":
                result = self.registry.execute(session, "get_latest_outcome", goal)
                if not result.get("recorded") and not (goal.success_criteria or {}).get("outcome_recorded"):
                    self._wait_for_event(session, goal, plan, step, "WAITING_EVENT", "等待结果回写", "记录本阶段结果后继续", event_id=event_id)
                    return goal
                self._finish_step(session, goal, plan, step, result, event_id)
                self._criterion(goal, "outcome_recorded", True)
                continue
            if step.step_type == "ASSIGN_MANAGER":
                approval = session.scalar(select(AgentApprovalRequest).where(AgentApprovalRequest.plan_step_id == step.id, AgentApprovalRequest.approval_type == "MANAGER_ACTION"))
                if approval is None or approval.status == "PENDING":
                    if approval is None:
                        approval = self._approval(session, goal, step, "MANAGER_ACTION", "HEALTH_MANAGER")
                    step.status = "WAITING_APPROVAL"
                    goal.status, goal.current_stage, goal.next_action = "WAITING", "等待健康管理师接手", "健康管理师确认接手并安排后续"
                    self._trace(session, goal, plan=plan, step=step, event_id=event_id, approval_id=approval.id, action="approval_requested", status="WAITING", summary="等待健康管理师接手")
                    return goal
                if approval.status != "APPROVED":
                    goal.status, goal.current_stage = "BLOCKED", "需要人工处理"
                    return goal
                self._run_tool(session, goal, plan, step, event_id=event_id, approved_role="HEALTH_MANAGER", context={"actor": approval.decided_by})
                self._criterion(goal, "work_resolved_or_waiting", True)
                continue
            if step.step_type == "REQUEST_DOCTOR_REVIEW" and not self._doctor_needed(session, goal):
                step.status, step.completed_at, step.result_summary = "SKIPPED", now, "没有需要医生判断的事项"
                self._criterion(goal, "doctor_review_complete", True)
                continue
            if step.tool_name:
                approved_role = "HEALTH_MANAGER" if step.tool_name == "request_doctor_review" else None
                if not self._run_tool(session, goal, plan, step, event_id=event_id, approved_role=approved_role):
                    return goal
                if step.step_type == "CHECK_BASELINE":
                    baseline_ready = bool((step.result_summary or "").find('"ready": true') >= 0)
                    self._criterion(goal, "baseline_ready", baseline_ready)
                    if not baseline_ready:
                        self._wait_for_event(
                            session, goal, plan, step, "WAITING_MANAGER",
                            "等待健康基线确认", "健康管理师确认年度健康基线后继续",
                            event_id=event_id,
                        )
                        return goal
                elif step.step_type == "EVALUATE_RISK":
                    self._criterion(goal, "risk_evaluated", True)
                elif step.step_type == "CREATE_FOLLOWUP":
                    self._criterion(goal, "followup_created", True)
                    self._criterion(goal, "plan_or_task_updated", True)
                elif step.step_type == "CHECK_TIMELINE":
                    self._criterion(goal, "timeline_ready", bool((step.result_summary or "").find('"writeback_ready": true') >= 0))
                elif step.step_type == "VERIFY_SUCCESS":
                    if all((goal.success_criteria or {}).values()):
                        self.complete_goal(session, goal.id)
                    else:
                        goal.status, goal.current_stage = "BLOCKED", "需要补齐闭环条件"
                        goal.next_action = "请由健康管理师核对基线、结果回写与长期档案"
                    return goal

    def decide_approval(self, session: Session, approval_id: UUID, *, decision: str, actor: str, actor_role: str, comment: str = "") -> AgentApprovalRequest:
        approval = session.get(AgentApprovalRequest, approval_id)
        if approval is None:
            raise ValueError("Approval request not found.")
        if approval.status != "PENDING":
            return approval
        if actor_role not in {approval.required_role, "ADMIN"}:
            raise PermissionError("This role cannot decide the approval.")
        if decision not in {"APPROVED", "REJECTED", "CANCELLED"}:
            raise ValueError("Unsupported approval decision.")
        approval.status = decision
        approval.decision = decision
        approval.decided_at = utc_now()
        approval.decided_by = actor
        approval.comment = comment[:1000] or None
        step = session.get(AgentPlanStep, approval.plan_step_id)
        goal = self._goal(session, approval.goal_id)
        if decision == "APPROVED":
            step.status = "PENDING"
            goal.status = "ACTIVE"
            self.execute_next_step(session, goal.id)
        else:
            step.status = "BLOCKED"
            goal.status, goal.current_stage, goal.next_action = "BLOCKED", "需要人工处理", comment or "审批未通过，请人工接手"
        self._trace(session, goal, plan_id=step.plan_id, step=step, approval_id=approval.id, action="approval_decided", status=decision, summary=comment or decision)
        return approval

    def pause_goal(self, session: Session, goal_id: UUID, *, actor: str, reason: str) -> AgentGoal:
        goal = self._goal(session, goal_id)
        goal.automation_paused, goal.takeover_by, goal.takeover_reason = True, actor, reason
        goal.status, goal.current_stage, goal.next_action = "BLOCKED", "人工接手", reason or "由健康管理师人工处理"
        self._control_audit(session, goal, actor, "agent_goal_paused", reason)
        return goal

    def resume_goal(self, session: Session, goal_id: UUID, *, actor: str = "admin", reason: str = "人工确认恢复") -> AgentGoal:
        goal = self._goal(session, goal_id)
        if goal.status in {"COMPLETED", "CANCELLED"}:
            return goal
        goal.automation_paused, goal.takeover_by, goal.takeover_reason = False, None, None
        goal.status, goal.current_stage = "ACTIVE", "恢复自动跟进"
        self._control_audit(session, goal, actor, "agent_goal_resumed", reason)
        return self.execute_next_step(session, goal.id)

    def cancel_goal(self, session: Session, goal_id: UUID, *, actor: str, reason: str) -> AgentGoal:
        goal = self._goal(session, goal_id)
        goal.status, goal.completed_at, goal.next_action = "CANCELLED", utc_now(), reason
        self._control_audit(session, goal, actor, "agent_goal_cancelled", reason)
        return goal

    def complete_goal(self, session: Session, goal_id: UUID) -> AgentGoal:
        goal = self._goal(session, goal_id)
        goal.status, goal.current_stage, goal.next_action = "COMPLETED", "本次体检后管理已完成", "进入下一次周期复盘"
        goal.completed_at, goal.next_check_at = utc_now(), None
        plan = session.get(AgentPlan, goal.current_plan_id)
        if plan:
            plan.status = "COMPLETED"
        self._trace(session, goal, plan=plan, action="goal_completed", status="COMPLETED", summary="成功条件已检查，进入下一周期")
        return goal

    def fail_goal(self, session: Session, goal_id: UUID, *, reason: str) -> AgentGoal:
        goal = self._goal(session, goal_id)
        goal.status, goal.current_stage, goal.next_action = "FAILED", "自动跟进暂时停止，需要人工处理", reason
        return goal

    def _resume_for_event(self, session: Session, goal: AgentGoal, event: AgentEvent) -> None:
        plan = session.get(AgentPlan, goal.current_plan_id)
        if plan is None:
            return
        step = session.scalar(select(AgentPlanStep).where(
            AgentPlanStep.plan_id == plan.id,
            AgentPlanStep.status.in_(WAIT_STEP_STATUSES),
            AgentPlanStep.wait_event_type == event.event_type,
        ).order_by(AgentPlanStep.step_order))
        if step is None:
            return
        step.status, step.completed_at, step.result_summary = "COMPLETED", utc_now(), f"收到 {event.event_type} 事件"
        if event.event_type == "REPORT_CONFIRMED":
            self._criterion(goal, "report_confirmed", True)
            approval = session.scalar(select(AgentApprovalRequest).where(AgentApprovalRequest.plan_step_id == step.id, AgentApprovalRequest.status == "PENDING"))
            if approval:
                approval.status, approval.decision, approval.decided_at = "APPROVED", "APPROVED", utc_now()
                approval.decided_by = str((event.metadata_json or {}).get("actor") or "健康管理师")
        elif event.event_type == "BASELINE_CONFIRMED":
            self._criterion(goal, "baseline_ready", True)
        elif event.event_type == "DOCTOR_REVIEW_COMPLETED":
            self._criterion(goal, "doctor_review_complete", True)
        elif event.event_type == "OUTCOME_RECORDED":
            self._criterion(goal, "outcome_recorded", True)
        goal.status, goal.next_check_at = "ACTIVE", None
        self._trace(session, goal, plan=plan, step=step, event_id=event.id, action="goal_resumed", status="COMPLETED", summary=f"事件 {event.event_type} 唤醒流程")
        self.execute_next_step(session, goal.id, event_id=event.id)

    def _run_tool(self, session: Session, goal: AgentGoal, plan: AgentPlan, step: AgentPlanStep, *, event_id: UUID | None, approved_role: str | None = None, context: dict[str, Any] | None = None) -> bool:
        try:
            result = self.registry.execute(session, step.tool_name or "", goal, context, approved_role=approved_role)
        except Exception as exc:
            step.retry_count += 1
            step.error_summary = f"{type(exc).__name__}: {str(exc)[:300]}"
            if step.retry_count > min(step.max_retries, self.default_max_retries):
                step.status = "BLOCKED"
                goal.status, goal.current_stage, goal.next_action = (
                    "BLOCKED",
                    "自动跟进暂时停止，需要人工处理",
                    "请由健康管理师接手处理",
                )
            else:
                step.status = "RETRY_WAIT"
                step.next_retry_at = utc_now() + timedelta(seconds=2 ** step.retry_count)
                goal.status, goal.current_stage, goal.next_check_at = "WAITING", "等待系统重试", step.next_retry_at
            self._trace(session, goal, plan=plan, step=step, event_id=event_id, action="tool_failed", status=step.status, error=step.error_summary)
            return False
        self._finish_step(session, goal, plan, step, result, event_id)
        return True

    def _finish_step(self, session: Session, goal: AgentGoal, plan: AgentPlan, step: AgentPlanStep, result: dict[str, Any], event_id: UUID | None) -> None:
        import json
        step.status, step.completed_at = "COMPLETED", utc_now()
        step.result_summary = json.dumps(result, ensure_ascii=False, default=str)[:2000]
        self._trace(session, goal, plan=plan, step=step, event_id=event_id, tool_name=step.tool_name, action="tool_completed", status="COMPLETED", summary=step.result_summary)

    def _wait_for_event(self, session: Session, goal: AgentGoal, plan: AgentPlan, step: AgentPlanStep, goal_stage: str, stage_text: str, next_action: str, *, event_id: UUID | None, approval_role: str | None = None) -> None:
        step.status = goal_stage
        goal.status, goal.current_stage, goal.next_action = "WAITING", stage_text, next_action
        approval_id = None
        if approval_role:
            approval = self._approval(session, goal, step, "REPORT_CONFIRMATION", approval_role)
            approval_id = approval.id
        self._trace(session, goal, plan=plan, step=step, event_id=event_id, approval_id=approval_id, action="waiting", status=goal_stage, summary=next_action)

    def _approval(self, session: Session, goal: AgentGoal, step: AgentPlanStep, approval_type: str, role: str) -> AgentApprovalRequest:
        existing = session.scalar(select(AgentApprovalRequest).where(AgentApprovalRequest.plan_step_id == step.id, AgentApprovalRequest.approval_type == approval_type))
        if existing:
            return existing
        row = AgentApprovalRequest(goal_id=goal.id, plan_step_id=step.id, approval_type=approval_type, required_role=role)
        session.add(row); session.flush(); return row

    def _doctor_needed(self, session: Session, goal: AgentGoal) -> bool:
        pending = session.scalar(select(DoctorReview.id).where(DoctorReview.patient_id == goal.member_id, DoctorReview.status == "PENDING").limit(1))
        risk = session.scalar(select(RiskEvent).where(RiskEvent.patient_id == goal.member_id, RiskEvent.status.not_in(("CLOSED", "DISMISSED_DATA_ISSUE"))).order_by(RiskEvent.created_at.desc()))
        needed = bool(pending or (risk and (risk.requires_doctor_review or risk.risk_level in {"YELLOW", "RED"})))
        criteria = dict(goal.success_criteria or {})
        criteria["doctor_review_complete"] = not needed
        goal.success_criteria = criteria
        return needed

    def _goal_for_event(self, session: Session, event: AgentEvent) -> AgentGoal | None:
        direct = session.scalar(select(AgentGoal).where(AgentGoal.source_type == event.source_type, AgentGoal.source_id == event.source_id).order_by(AgentGoal.started_at.desc()))
        if direct:
            return direct
        return session.scalar(select(AgentGoal).where(AgentGoal.member_id == event.member_id, AgentGoal.status.in_(("ACTIVE", "WAITING", "BLOCKED"))).order_by(AgentGoal.started_at.desc()))

    @staticmethod
    def _goal(session: Session, goal_id: UUID) -> AgentGoal:
        goal = session.get(AgentGoal, goal_id)
        if goal is None:
            raise ValueError("Agent goal not found.")
        return goal

    @staticmethod
    def _criterion(goal: AgentGoal, key: str, value: bool) -> None:
        criteria = dict(goal.success_criteria or {})
        criteria[key] = value
        goal.success_criteria = criteria

    def _trace(self, session: Session, goal: AgentGoal, *, action: str, status: str, plan: AgentPlan | None = None, plan_id: UUID | None = None, step: AgentPlanStep | None = None, event_id: UUID | None = None, tool_name: str | None = None, summary: str | None = None, error: str | None = None, approval_id: UUID | None = None) -> AgentRunTrace:
        row = AgentRunTrace(goal_id=goal.id, plan_id=plan.id if plan else plan_id, plan_step_id=step.id if step else None, event_id=event_id, tool_name=tool_name, action=action, status=status, completed_at=utc_now(), result_summary=(summary or "")[:2000] or None, error_summary=(error or "")[:1000] or None, approval_id=approval_id, metadata_json={})
        session.add(row); session.flush(); return row

    @staticmethod
    def _control_audit(session: Session, goal: AgentGoal, actor: str, action: str, reason: str) -> None:
        session.add(AuditLog(patient_id=goal.member_id, actor=actor, actor_role="health_manager", action=action, entity_type="AgentGoal", entity_id=str(goal.id), detail_json={"reason": reason[:500]}))
