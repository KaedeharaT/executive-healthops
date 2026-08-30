"""Regression tests for the Portfolio Demo's user-facing workflow hand-offs."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from executive_health_ai.models import (
    Base, DoctorReview, HealthJourney, HealthProblem, HealthProgram, OutcomeEvaluation,
    Patient, RiskEvent, RiskRule, Task,
)
from executive_health_ai.services.chronic_care import apply_outcome_decision, complete_outcome_doctor_review
from executive_health_ai.services.member_services import MemberServiceOperations
from executive_health_ai.services.operational_worklist import OperationalWorklistService
from executive_health_ai.services.risk_operations import RiskOperationsService


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _member_and_program(session: Session) -> tuple[Patient, HealthProgram]:
    member = Patient(external_id="portfolio-usage-demo", timezone="Asia/Tokyo")
    session.add(member); session.flush()
    journey = HealthJourney(patient_id=member.id, current_stage="90_DAY_PROGRAM", status="ACTIVE", risk_level="MODERATE", assessment_summary="演示健康评估", main_focus="演示管理目标", supporting_goals_json=[], baseline_json={}, owner="健康管理师")
    session.add(journey); session.flush()
    program = HealthProgram(patient_id=member.id, journey_id=journey.id, program_type="NINETY_DAY", title="演示健康计划", main_goal="持续管理", supporting_goals_json=[], status="ACTIVE", start_date=date.today(), owner="健康管理师")
    session.add(program); session.flush()
    return member, program


def _yellow(session: Session, member: Patient) -> RiskEvent:
    rule = RiskRule(name="演示黄风险", code="PORTFOLIO_USAGE_YELLOW", applicable_device_class="ANY", canonical_code="steps", risk_level="YELLOW", condition_type="SYNTHETIC_TEST_THRESHOLD", threshold_config={}, window_config={}, requires_repeated_measurement=False, requires_symptom_confirmation=False, action_type="SYNTHETIC_TEST_ONLY", source_reference="SYNTHETIC TEST ONLY", scope="TEST", review_status="APPROVED", reviewed_by="演示审核人")
    session.add(rule); session.flush()
    event = RiskEvent(patient_id=member.id, risk_rule_id=rule.id, risk_level="YELLOW", status="NEW", device_class="WELLNESS", canonical_code="steps", recommended_route="HEALTH_MANAGER", evidence_json={"demo_flag": True}, summary="演示黄风险，需要人工核实。", requires_manager_review=True)
    session.add(event); session.flush(); return event


def test_taken_yellow_remains_a_single_active_work_item() -> None:
    with _session() as session:
        member, _ = _member_and_program(session); event = _yellow(session, member)
        RiskOperationsService().record_contact(session, event.id, "健康管理师", "电话", "待回访", "等待成员回复")
        items = OperationalWorklistService().list_items(session, datetime.now(timezone.utc))
        risk_items = [item for item in items if item.source_type == "risk_event" and item.source_id == event.id]
        assert len(risk_items) == 1
        assert risk_items[0].status == "等待成员"
        assert risk_items[0].owner == "健康管理师"
        assert risk_items[0].next_action.startswith("等待成员")


def test_doctor_escalated_yellow_is_one_waiting_doctor_item_not_three() -> None:
    with _session() as session:
        member, _ = _member_and_program(session); event = _yellow(session, member)
        review = RiskOperationsService().escalate_to_doctor(session, event.id, "健康管理师", "请医生人工确认下一步。")
        items = OperationalWorklistService().list_items(session, datetime.now(timezone.utc))
        related = [item for item in items if item.member_id == member.id and item.source_type in {"risk_event", "doctor_review"}]
        assert review.status == "PENDING"
        assert [(item.source_type, item.status) for item in related] == [("risk_event", "等待医生")]


def test_member_plan_choice_creates_a_human_next_action() -> None:
    with _session() as session:
        member, program = _member_and_program(session)
        choice = MemberServiceOperations().record_choice(session, member.id, "希望调整")
        task = session.scalar(select(Task).where(Task.patient_id == member.id, Task.source == "member_plan_choice"))
        assert choice.manager_followup == "等待健康管理师联系成员"
        assert task is not None and task.responsible_role == "health_manager"
        assert any(item.source_id == task.id for item in OperationalWorklistService().list_items(session, datetime.now(timezone.utc)))
        MemberServiceOperations().record_choice(session, member.id, "接受方案")
        assert program.status == "ACTIVE"


def test_service_requires_schedule_and_execution_before_completion() -> None:
    with _session() as session:
        member, _ = _member_and_program(session)
        operations = MemberServiceOperations(); operations.ensure_demo_plan(session, member.id)
        item, _ = operations.member_services(session, member.id)[0]
        request = operations.request(session, member.id, item.id, "演示申请")
        operations.approve(session, request.id, "健康管理师")
        operations.schedule(session, request.id, datetime.now(timezone.utc) + timedelta(days=1), "健康管理师")
        operations.start(session, request.id, "健康管理师")
        operations.complete(session, request.id, "已完成演示服务", "健康管理师")
        assert request.status == "COMPLETED" and request.result_summary == "已完成演示服务"


def test_outcome_decision_creates_next_step_or_doctor_review() -> None:
    with _session() as session:
        member, program = _member_and_program(session)
        outcome = OutcomeEvaluation(patient_id=member.id, program_id=program.id, metric="sleep_duration", baseline_value="360", current_value="390", unit="min", direction="UP", evaluator="健康管理师", evidence="演示前后观察", result="IMPROVED", evaluation_date=date.today())
        session.add(outcome); session.flush()
        task = apply_outcome_decision(session, outcome, "ADJUST", "健康管理师")
        assert isinstance(task, Task) and task.source == "outcome_adjustment"
        review = apply_outcome_decision(session, outcome, "DOCTOR_REVIEW", "健康管理师", "请医生人工判断下一步。")
        assert isinstance(review, DoctorReview) and review.status == "PENDING"
        follow_up = complete_outcome_doctor_review(session, review, "演示医生", "全科/健康管理", "人工意见", "健康管理师安排随访")
        assert follow_up.source == "outcome_doctor_followup" and review.status == "CONFIRMED"


def test_ui_keeps_baseline_target_knowledge_scope_and_freshness_copy() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert 'archive_view="基线"' in source
    assert 'key_scope="saved"' in source and 'key_scope="pending"' in source
    assert "_observation_freshness" in source
    assert "不会改变风险、诊断、处方或医疗规则" in source
