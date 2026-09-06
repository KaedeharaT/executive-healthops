"""Behavioral coverage for bounded, durable post-checkup orchestration."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from executive_health_ai.agent.reflection import HealthOpsReflectionService
from executive_health_ai.agent.scheduler import AgentSchedulerService
from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
from executive_health_ai.agent.tools import AUTO, DOCTOR_APPROVAL, AgentTool, AgentToolRegistry
from executive_health_ai.api import create_app
from executive_health_ai.models import (
    AgentApprovalRequest, AgentEvent, AgentGoal, AgentPlan, AgentPlanStep,
    AgentRunTrace, Base, Document, HealthAssessment, Patient, RiskEvent, RiskRule,
)
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.event_service import EventService


def _factory(tmp_path: Path) -> sessionmaker[Session]:
    engine = create_engine(f"sqlite:///{(tmp_path / 'agent.db').as_posix()}")
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False)


def _member_report(session: Session) -> tuple[Patient, Document]:
    member = Patient(external_id="synthetic-agent-member", display_name="演示成员", timezone="Asia/Tokyo")
    session.add(member); session.flush()
    report = Document(patient_id=member.id, document_type="health_check_report", title="2026年度体检报告（演示）", storage_reference="synthetic://report", source="test")
    session.add(report); session.flush()
    session.add(HealthAssessment(patient_id=member.id, assessment_type="BASELINE", version=1, title="健康基线", summary="人工确认的演示基线", baseline_json={}, created_by="manager", status="CONFIRMED", reviewed_by="manager", confirmed_at=utc_now(), source_references_json={"document_id": str(report.id)}))
    session.flush()
    return member, report


def _event(session: Session, supervisor: HealthOpsAgentSupervisor, event_type: str, member: Patient, source_type: str, source_id: object, suffix: str = "") -> AgentGoal:
    event, _ = EventService().publish(session, event_type=event_type, member_id=member.id, source_type=source_type, source_id=str(source_id), metadata={"actor": "演示健康管理师"}, dedup_key=f"{event_type}:{source_type}:{source_id}:{suffix}")
    goal = supervisor.receive_event(session, event)
    assert goal is not None
    return goal


def test_post_checkup_goal_crosses_wait_approval_time_resume_and_completes(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    with factory() as session:
        member, report = _member_report(session)
        supervisor = HealthOpsAgentSupervisor()
        goal = _event(session, supervisor, "REPORT_UPLOADED", member, "document", report.id)
        assert goal.status == "WAITING" and "确认" in goal.current_stage
        assert session.scalar(select(AgentGoal).where(AgentGoal.source_id == str(report.id))) == goal

        duplicate = _event(session, supervisor, "REPORT_UPLOADED", member, "document", report.id)
        assert duplicate.id == goal.id
        assert session.query(AgentGoal).count() == 1
        assert session.query(AgentEvent).count() == 1

        goal = _event(session, supervisor, "REPORT_CONFIRMED", member, "document", report.id)
        approval = session.scalar(select(AgentApprovalRequest).where(AgentApprovalRequest.goal_id == goal.id, AgentApprovalRequest.status == "PENDING"))
        assert approval is not None and approval.required_role == "HEALTH_MANAGER"
        supervisor.decide_approval(session, approval.id, decision="APPROVED", actor="王健管", actor_role="HEALTH_MANAGER", comment="已核对并接手")
        assert goal.status == "WAITING" and goal.current_stage == "等待下一次复核"
        assert goal.next_check_at is not None

        goal.next_check_at = utc_now() - timedelta(seconds=1)
        waiting_step = session.scalar(select(AgentPlanStep).where(AgentPlanStep.plan_id == goal.current_plan_id, AgentPlanStep.step_type == "WAIT_FOLLOWUP"))
        waiting_step.scheduled_for = goal.next_check_at
        assert AgentSchedulerService().run_due(session, now=utc_now()) == 1
        assert goal.status == "WAITING" and goal.current_stage == "等待结果回写"

        goal = _event(session, supervisor, "OUTCOME_RECORDED", member, "outcome", "synthetic-outcome")
        assert goal.status == "COMPLETED"
        assert goal.completed_at is not None
        assert session.query(AgentRunTrace).filter_by(goal_id=goal.id, action="goal_completed").count() == 1


def test_doctor_review_is_human_gate_and_risk_rule_is_unchanged(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    with factory() as session:
        member, report = _member_report(session)
        rule = RiskRule(name="演示规则", code="SYNTHETIC_AGENT_YELLOW", applicable_device_class="ANY", canonical_code="ldl", risk_level="YELLOW", condition_type="SYNTHETIC_TEST", threshold_config={}, window_config={}, action_type="HUMAN_REVIEW", recommended_route="HEALTH_MANAGER", source_reference="SYNTHETIC TEST ONLY", scope="TEST", review_status="APPROVED", reviewed_by="demo", is_active=True)
        session.add(rule); session.flush()
        risk = RiskEvent(patient_id=member.id, risk_rule_id=rule.id, risk_level="YELLOW", status="NEW", device_class="REPORT", canonical_code="ldl", summary="演示体检风险，等待人工复核", requires_manager_review=True, requires_doctor_review=True)
        session.add(risk); session.flush()
        original_config = dict(rule.threshold_config)

        supervisor = HealthOpsAgentSupervisor()
        goal = _event(session, supervisor, "REPORT_UPLOADED", member, "document", report.id)
        _event(session, supervisor, "REPORT_CONFIRMED", member, "document", report.id)
        approval = session.scalar(select(AgentApprovalRequest).where(AgentApprovalRequest.goal_id == goal.id, AgentApprovalRequest.status == "PENDING"))
        supervisor.decide_approval(session, approval.id, decision="APPROVED", actor="王健管", actor_role="HEALTH_MANAGER")
        assert goal.status == "WAITING" and goal.current_stage == "等待医生完成医学复核"
        assert rule.threshold_config == original_config
        assert all(tool.name not in {"create_risk", "update_risk_rule", "change_medication", "diagnose"} for tool in supervisor.registry.tools)

        from executive_health_ai.models import DoctorReview
        review = session.scalar(select(DoctorReview).where(DoctorReview.patient_id == member.id, DoctorReview.status == "PENDING"))
        assert review is not None
        review.status, review.opinion, review.reviewed_at = "CONFIRMED", "医生人工确认后继续随访", utc_now()
        _event(session, supervisor, "DOCTOR_REVIEW_COMPLETED", member, "doctor_review", review.id)
        assert goal.status == "WAITING" and goal.current_stage == "等待下一次复核"
        assert rule.threshold_config == original_config


def test_tool_permissions_retry_limit_replan_and_manual_takeover(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    calls = {"count": 0}

    def flaky(session: Session, goal: AgentGoal, context: dict[str, object]) -> dict[str, object]:
        calls["count"] += 1
        if calls["count"] == 1: raise RuntimeError("temporary")
        return {"ok": True}

    with factory() as session:
        member, report = _member_report(session)
        supervisor = HealthOpsAgentSupervisor()
        goal = _event(session, supervisor, "REPORT_UPLOADED", member, "document", report.id)
        assert supervisor.registry.get("create_followup_task").permission == AUTO
        try:
            supervisor.registry.execute(session, "request_doctor_review", goal)
            assert False, "manager approval must be enforced"
        except PermissionError:
            pass
        supervisor.registry.register(AgentTool("clinical_decision", "blocked", DOCTOR_APPROVAL, "write", False, 5, flaky))
        try:
            supervisor.registry.execute(session, "clinical_decision", goal, approved_role="DOCTOR")
            assert False, "doctor decisions must remain in DoctorReview"
        except PermissionError:
            pass

        plan = session.get(AgentPlan, goal.current_plan_id)
        step = session.scalar(select(AgentPlanStep).where(AgentPlanStep.plan_id == plan.id, AgentPlanStep.step_order == 1))
        step.status, step.tool_name, step.retry_count, step.max_retries = "PENDING", "flaky", 0, 1
        supervisor.registry.register(AgentTool("flaky", "temporary dependency", AUTO, "read", True, 5, flaky))
        supervisor.execute_next_step(session, goal.id)
        assert step.status == "RETRY_WAIT" and step.retry_count == 1
        step.next_retry_at = utc_now() - timedelta(seconds=1); goal.next_check_at = step.next_retry_at
        AgentSchedulerService(supervisor).run_due(session, now=utc_now())
        assert calls["count"] == 2 and step.status == "COMPLETED"

        supervisor.pause_goal(session, goal.id, actor="王健管", reason="成员暂时无法联系")
        assert goal.automation_paused and goal.status == "BLOCKED"
        supervisor.resume_goal(session, goal.id, actor="管理员")
        assert not goal.automation_paused
        old_version = session.get(AgentPlan, goal.current_plan_id).version
        new_plan = HealthOpsReflectionService().replan(session, goal.id, reason="MEMBER_UNAVAILABLE")
        assert new_plan.version == old_version + 1 and new_plan.reason.endswith("MEMBER_UNAVAILABLE")
        assert rule_count(session) == 0


def rule_count(session: Session) -> int:
    return session.query(RiskRule).count()


def test_tool_stops_after_retry_limit_and_requires_human_takeover(tmp_path: Path) -> None:
    factory = _factory(tmp_path)

    def unavailable(session: Session, goal: AgentGoal, context: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("dependency unavailable")

    with factory() as session:
        member, report = _member_report(session)
        supervisor = HealthOpsAgentSupervisor()
        goal = _event(session, supervisor, "REPORT_UPLOADED", member, "document", report.id)
        plan = session.get(AgentPlan, goal.current_plan_id)
        step = session.scalar(
            select(AgentPlanStep).where(
                AgentPlanStep.plan_id == plan.id,
                AgentPlanStep.step_order == 1,
            )
        )
        step.status, step.tool_name, step.retry_count, step.max_retries = "PENDING", "unavailable", 0, 0
        supervisor.registry.register(
            AgentTool("unavailable", "unavailable dependency", AUTO, "read", True, 5, unavailable)
        )

        supervisor.execute_next_step(session, goal.id)

        assert step.status == "BLOCKED"
        assert step.retry_count == 1
        assert goal.status == "BLOCKED"
        assert goal.current_stage == "自动跟进暂时停止，需要人工处理"


def test_agent_api_exposes_goal_plan_trace_resume_and_approval(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    with factory() as session:
        member, report = _member_report(session); session.commit()
    client = TestClient(create_app(factory))
    created = client.post("/agent/events", json={"event_type": "REPORT_UPLOADED", "member_id": str(member.id), "source_type": "document", "source_id": str(report.id), "actor": "manager"})
    assert created.status_code == 201
    goal_id = created.json()["goal_id"]
    assert client.get(f"/agent/goals/{goal_id}").status_code == 200
    plan = client.get(f"/agent/goals/{goal_id}/plan")
    assert plan.status_code == 200 and len(plan.json()["plans"][0]["steps"]) == 15
    assert client.get(f"/agent/goals/{goal_id}/trace").status_code == 200
    assert client.get("/agent/approvals?required_role=HEALTH_MANAGER").json()
    assert client.post(f"/agent/goals/{goal_id}/resume", json={"action": "PAUSE", "actor": "member", "actor_role": "MEMBER", "reason": "x"}).status_code == 403
    assert client.post(f"/agent/goals/{goal_id}/resume", json={"action": "PAUSE", "actor": "admin", "actor_role": "ADMIN", "reason": "人工接手"}).status_code == 200
