"""Behavioral contracts for the current HealthOps workflow sources."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.api import create_app
from executive_health_ai.models import Alert, AuditLog, Base, Document, Observation, Patient, ReportExtractionRun, RiskEvent, RiskRule, Task
from executive_health_ai.services.operational_worklist import OperationalWorklistService
from executive_health_ai.services.risk_operations import RiskOperationsService
from executive_health_ai.services.risk_triage import RiskEvaluationService


def _factory():
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def _current_risk(session: Session) -> tuple[Patient, RiskEvent]:
    member = Patient(external_id="workflow-unification-synthetic", timezone="Asia/Tokyo")
    session.add(member)
    session.flush()
    rule = RiskRule(
        name="合成工作流规则", code="SYNTHETIC_WORKFLOW_UNIFICATION",
        applicable_device_class="ANY", canonical_code="steps", risk_level="YELLOW",
        condition_type="SYNTHETIC_TEST_THRESHOLD",
        threshold_config={"metric": "steps", "operator": ">=", "value": "8000", "unit": "count"},
        window_config={}, requires_repeated_measurement=False,
        requires_symptom_confirmation=False, action_type="SYNTHETIC_TEST_ONLY",
        source_reference="SYNTHETIC TEST ONLY", review_status="APPROVED",
        reviewed_by="synthetic", is_active=True,
    )
    session.add(rule)
    observation = Observation(
        patient_id=member.id, observed_at=datetime.now(timezone.utc), metric_code="steps",
        value_numeric=Decimal("9000"), unit="count", source="synthetic_test", quality_flag="valid",
    )
    session.add(observation)
    session.flush()
    RiskEvaluationService().evaluate_observation(session, observation.id)
    return member, session.scalar(select(RiskEvent).where(RiskEvent.patient_id == member.id))


def test_generic_task_completion_advances_owning_risk_event() -> None:
    factory = _factory()
    with factory() as session:
        _, event = _current_risk(session)
        task = RiskOperationsService().continue_monitoring(
            session, event.id, "测试健康管理师", "次日复核合成数据",
            datetime.now(timezone.utc) + timedelta(days=1),
        )
        task_id, event_id = task.id, event.id
        session.commit()

    response = TestClient(create_app(factory)).post(
        f"/tasks/{task_id}/complete",
        json={"actor": "测试健康管理师", "outcome": "已复核合成数据"},
    )
    assert response.status_code == 200
    with factory() as session:
        task, event = session.get(Task, task_id), session.get(RiskEvent, event_id)
        assert task.status == "COMPLETED" and task.completed_at is not None
        assert event.status == "IN_REVIEW"
        assert not (task.status == "COMPLETED" and event.status == "MONITORING")
        assert session.scalar(select(AuditLog).where(AuditLog.action == "yellow_monitoring_followup_completed")) is not None


def test_api_dashboard_is_a_compatibility_view_of_operational_worklist() -> None:
    factory = _factory()
    with factory() as session:
        member, event = _current_risk(session)
        RiskOperationsService().continue_monitoring(
            session, event.id, "测试健康管理师", "保持合成风险在工作台",
            datetime.now(timezone.utc) + timedelta(days=1),
        )
        session.commit()
        service = OperationalWorklistService()
        expected = service.dashboard_counts(service.list_items(session, datetime.now(timezone.utc)))
        # A legacy row must not affect the current operational dashboard.
        session.add(Alert(
            patient_id=member.id, alert_type="legacy_dashboard_fixture", title="Legacy high alert",
            finding="Must not become current dashboard work", evidence_json={}, status="NEW",
            severity="HIGH", responsible_role="health_manager", source="legacy_test_fixture",
        ))
        session.commit()

    payload = TestClient(create_app(factory)).get("/dashboard/manager").json()
    for field, value in expected.items():
        assert payload[field] == value


def test_current_risk_evaluation_creates_risk_event_not_legacy_alert() -> None:
    factory = _factory()
    with factory() as session:
        member, event = _current_risk(session)
        assert event.patient_id == member.id
        assert session.scalar(select(func.count(RiskEvent.id))) == 1
        assert session.scalar(select(func.count(Alert.id))) == 0


def test_legacy_alert_read_compatibility_remains_available() -> None:
    factory = _factory()
    with factory() as session:
        member = Patient(external_id="legacy-alert-read-synthetic", timezone="Asia/Tokyo")
        session.add(member)
        session.flush()
        alert = Alert(
            patient_id=member.id, alert_type="legacy_test", title="Legacy synthetic alert",
            finding="Synthetic compatibility fixture", evidence_json={}, status="CLOSED",
            severity="LOW", responsible_role="health_manager", source="legacy_test_fixture",
        )
        session.add(alert)
        session.commit()
        member_id = member.id

    response = TestClient(create_app(factory)).get(f"/alerts?member_id={member_id}")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["source"] == "legacy_test_fixture"


def test_current_timeline_api_returns_source_derived_projection() -> None:
    factory = _factory()
    with factory() as session:
        member = Patient(external_id="current-timeline-api-synthetic", timezone="Asia/Tokyo")
        session.add(member)
        session.flush()
        document = Document(
            patient_id=member.id, document_type="health_check_report", title="Synthetic annual report",
            storage_reference="synthetic://timeline-report", source="synthetic_test",
        )
        session.add(document)
        session.flush()
        session.add(ReportExtractionRun(
            document_id=document.id, patient_id=member.id, status="COMPLETED",
            parser_version="test", canonical_registry_version="test", file_hash="b" * 64,
            file_type="TXT", created_at=datetime.now(timezone.utc),
        ))
        session.commit()
        member_id = member.id

    client = TestClient(create_app(factory))
    response = client.get(f"/members/{member_id}/timeline/v2")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["event_type"] == "report"
    assert payload[0]["event_type_label"] == "体检"
    assert payload[0]["group_key"].startswith("REPORT:")
    paths = client.get("/openapi.json").json()["paths"]
    assert paths["/members/{member_id}/timeline"]["get"]["deprecated"] is True
    assert not paths["/members/{member_id}/timeline/v2"]["get"].get("deprecated", False)
