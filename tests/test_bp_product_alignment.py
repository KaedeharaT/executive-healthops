from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from executive_health_ai.integrations.adapters import MockYuwellAdapter
from executive_health_ai.models import AuditLog, Base, Patient
from executive_health_ai.models.program import HealthProgram
from executive_health_ai.services.bp_product import (
    CONSENT_SCOPES,
    SEVEN_STEP_RESPONSIBILITY_LOOP,
    ConsentService,
    care_cycle_for,
)
from executive_health_ai.services.member_services import MemberServiceOperations, bp_service_category


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _program(start: date, end: date) -> HealthProgram:
    return HealthProgram(
        patient_id=uuid4(), journey_id=uuid4(), program_type="ANNUAL",
        title="synthetic annual plan", main_goal="synthetic goal", status="ACTIVE",
        start_date=start, end_date=end,
    )


def test_bp_cadence_and_seven_step_loop_are_explicit() -> None:
    today = date(2026, 9, 3)
    assert SEVEN_STEP_RESPONSIBILITY_LOOP == ("采集", "判断", "分级", "确认", "行动", "回写", "复盘", "下一轮")
    assert care_cycle_for(None, baseline_confirmed=False, today=today).code == "FIRST_MONTH"
    assert care_cycle_for(_program(date(2026, 8, 20), date(2027, 8, 19)), baseline_confirmed=True, today=today).code == "FIRST_MONTH"
    assert care_cycle_for(_program(date(2026, 7, 1), date(2027, 6, 30)), baseline_confirmed=True, today=today).code == "MONTHLY"
    assert care_cycle_for(_program(date(2026, 6, 15), date(2027, 6, 14)), baseline_confirmed=True, today=today).code == "QUARTERLY"
    assert care_cycle_for(_program(date(2025, 9, 15), date(2026, 9, 14)), baseline_confirmed=True, today=today).code == "ANNUAL"


def test_three_member_consent_scopes_are_revocable_and_audited() -> None:
    with _session() as session:
        member = Patient(external_id="synthetic-consent", timezone="Asia/Tokyo")
        session.add(member); session.flush()
        service = ConsentService()
        for scope in CONSENT_SCOPES:
            consent = service.grant(session, member.id, scope, actor="synthetic member", source="member settings")
            assert consent.scope == scope and consent.status == "GRANTED" and consent.granted_at
        revoked = service.revoke(session, member.id, "ALGORITHM_MODEL_USE", actor="synthetic member", source="member settings")
        assert revoked.status == "REVOKED" and revoked.revoked_at
        assert len(list(session.scalars(select(AuditLog).where(AuditLog.patient_id == member.id)))) == 4


def test_service_catalog_is_presented_in_four_bp_delivery_families() -> None:
    with _session() as session:
        member = Patient(external_id="synthetic-service-groups", timezone="Asia/Tokyo")
        session.add(member); session.flush()
        operations = MemberServiceOperations(); operations.ensure_demo_plan(session, member.id)
        groups = {bp_service_category(item) for item, _ in operations.member_services(session, member.id)}
        assert groups == {"评估与建档", "连续管理", "专业协作", "就医协调"}


def test_device_adapter_translates_data_without_medical_decision_methods() -> None:
    adapter = MockYuwellAdapter()
    records = adapter.parse({
        "user_id": "synthetic", "device_id": "synthetic-device",
        "measure_time": "2026-09-03T08:00:00+09:00", "sys": 120, "dia": 80, "pulse": 70,
    })
    assert {record.metric for record in records} == {"systolic_bp", "diastolic_bp", "heart_rate"}
    assert not hasattr(adapter, "decide_risk") and not hasattr(adapter, "diagnose")


def test_product_navigation_hides_quality_governance_and_uses_blue_tokens() -> None:
    app = Path("streamlit_app.py").read_text(encoding="utf-8")
    shell = Path("src/executive_health_ai/ui/pages/shell.py").read_text(encoding="utf-8")
    assert '"运营后台", "成员健康中心"' in app
    assert '["首页", "健康", "历程", "计划", "服务"]' in app
    assert '["今日", "成员", "医疗协同", "服务运营", "更多"]' in app
    assert 'options = ["风险规则", "操作记录", "系统"]' in shell
    assert 'with st.expander("AI 质量治理（高级）")' in shell
    assert "--blue:#2563eb" in app and "linear-gradient" not in app
    assert "健管培训助手" not in shell
