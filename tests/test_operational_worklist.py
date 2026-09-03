"""Synthetic coverage for the UI-only daily operational worklist."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.blood_pressure import TOKYO_TIMEZONE
from executive_health_ai.models import Base, ManagementRule, ManagementSignal, Observation, Patient, RiskEvent, RiskRule, Task
from executive_health_ai.services.operational_worklist import OperationalWorklistService


def _factory():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def test_worklist_is_sorted_by_operational_priority_without_creating_new_records() -> None:
    now = datetime.now(TOKYO_TIMEZONE)
    with _factory()() as session:
        member = Patient(external_id="worklist-synthetic", display_name="合成工作项成员", timezone="Asia/Tokyo")
        rule = RiskRule(
            name="synthetic worklist", code="SYNTHETIC_WORKLIST", applicable_device_class="ANY", canonical_code="glucose",
            risk_level="YELLOW", condition_type="SYNTHETIC_TEST_THRESHOLD", threshold_config={}, window_config={},
            requires_repeated_measurement=False, requires_symptom_confirmation=False, action_type="SYNTHETIC_TEST_ONLY",
            source_reference="SYNTHETIC TEST ONLY", review_status="APPROVED", is_active=True,
        )
        management_rule = ManagementRule(
            name="synthetic lifestyle worklist", code="SYNTHETIC_LIFESTYLE_WORKLIST", canonical_code="steps",
            condition_type="THRESHOLD", threshold_config={}, window_config={}, recommended_route="HEALTH_MANAGER",
            review_status="APPROVED", is_active=True, source_reference="SYNTHETIC TEST ONLY",
        )
        session.add_all((member, rule, management_rule)); session.flush()
        observation = Observation(patient_id=member.id, observed_at=now, metric_code="steps", value_numeric=Decimal("1"), unit="count", source="synthetic_demo", quality_flag="valid")
        glucose_observation = Observation(patient_id=member.id, observed_at=now, metric_code="glucose", value_numeric=Decimal("1"), unit="mmol/L", source="synthetic_demo", quality_flag="valid")
        session.add_all((observation, glucose_observation)); session.flush()
        session.add_all((
            RiskEvent(patient_id=member.id, risk_rule_id=rule.id, risk_level="RED", status="NEW", device_class="MEDICAL_MONITOR", canonical_code="glucose", summary="合成紧急工作项", requires_manager_review=True, requires_doctor_review=False, requires_emergency_action=True),
            RiskEvent(patient_id=member.id, risk_rule_id=rule.id, risk_level="YELLOW", status="ESCALATED_TO_DOCTOR", device_class="MEDICAL_MONITOR", canonical_code="glucose", summary="合成医生等待项", requires_manager_review=True, requires_doctor_review=True, requires_emergency_action=False),
            Task(patient_id=member.id, title="合成逾期跟进", instruction="完成合成人工跟进", status="PENDING", priority="MEDIUM", due_at=now - timedelta(days=1), source="synthetic"),
            ManagementSignal(patient_id=member.id, management_rule_id=management_rule.id, observation_id=observation.id, metric_code="steps", severity="ACTION_NEEDED", status="OPEN", recommended_route="HEALTH_MANAGER", summary="合成活动下降", evidence_json={}),
            ManagementSignal(patient_id=member.id, management_rule_id=management_rule.id, observation_id=glucose_observation.id, metric_code="glucose", severity="ACTION_NEEDED", status="OPEN", recommended_route="HEALTH_MANAGER", summary="不应重复显示的同指标管理信号", evidence_json={}),
        ))
        session.flush()
        before = session.query(RiskEvent).count() + session.query(Task).count() + session.query(ManagementSignal).count()
        items = OperationalWorklistService().list_items(session, now)
        after = session.query(RiskEvent).count() + session.query(Task).count() + session.query(ManagementSignal).count()

    assert [item.status for item in items] == ["高风险", "逾期", "等待医生", "建议健康管理"]
    assert after == before
    assert all(item.member_id == member.id for item in items)
    assert all("不应重复显示" not in item.title for item in items)
    assert all(item.source_label and item.owner and item.next_action for item in items)
