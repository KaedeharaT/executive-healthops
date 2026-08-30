"""End-to-end regression tests for the V0.1 reviewed operational loop."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.api import create_app
from executive_health_ai.blood_pressure import TOKYO_TIMEZONE
from executive_health_ai.models import AgentRun, AuditLog, Base, Observation, Patient


def test_api_runs_reviewed_alert_to_closed_follow_up() -> None:
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with session_factory() as session:
        member = Patient(external_id="synthetic-zhang-wei", timezone="Asia/Tokyo")
        session.add(member)
        session.flush()
        member_id = member.id
        for day in range(5):
            observed_at = datetime(2026, 8, 1 + day, 7, 30, tzinfo=TOKYO_TIMEZONE)
            session.add_all([
                Observation(patient_id=member_id, observed_at=observed_at, metric_code="systolic_bp", value_numeric=Decimal("145"), unit="mmHg", source="synthetic_test", quality_flag="valid"),
                Observation(patient_id=member_id, observed_at=observed_at, metric_code="diastolic_bp", value_numeric=Decimal("92"), unit="mmHg", source="synthetic_test", quality_flag="valid"),
                Observation(patient_id=member_id, observed_at=observed_at, metric_code="heart_rate", value_numeric=Decimal("72"), unit="bpm", source="synthetic_test", quality_flag="valid"),
            ])
        session.commit()

    client = TestClient(create_app(session_factory))
    assert client.get("/health").json()["medical_safety"] == "human_review_required"
    document = client.post("/documents", json={
        "member_id": str(member_id), "document_type": "health_check_report",
        "title": "Synthetic report metadata", "storage_reference": "synthetic://report-001.pdf",
    })
    assert document.status_code == 201
    assert len(client.get(f"/documents?member_id={member_id}").json()) == 1
    screened = client.post(f"/members/{member_id}/screen")
    assert screened.status_code == 200
    alert = screened.json()
    assert alert["status"] == "AI_SCREENED"
    problem = client.post(
        f"/alerts/{alert['id']}/manager-confirm",
        json={"manager_name": "synthetic manager", "review_note": "Verified measurement provenance; request doctor review."},
    )
    assert problem.status_code == 200
    assert problem.json()["status"] == "OPEN"
    doctor_review = client.post(
        "/doctor-reviews",
        json={"problem_id": problem.json()["id"], "doctor_name": "synthetic doctor", "department": "cardiology", "opinion": "Review recorded; continue existing measurement and follow-up process."},
    )
    assert doctor_review.status_code == 201
    assert "不构成诊断" in doctor_review.json()["doctor_brief"]
    tasks = client.get(f"/tasks?member_id={member_id}").json()
    assert len(tasks) == 1 and tasks[0]["status"] == "PENDING"
    follow_up = client.post(
        "/followups",
        json={"problem_id": problem.json()["id"], "task_id": tasks[0]["id"], "reviewer": "synthetic manager", "outcome": "Synthetic follow-up completed."},
    )
    assert follow_up.status_code == 201
    assert follow_up.json()["status"] == "COMPLETED"
    assert client.get(f"/problems?member_id={member_id}").json()[0]["status"] == "CLOSED"
    with session_factory() as session:
        assert session.scalar(select(func.count(AuditLog.id)).where(AuditLog.patient_id == member_id)) >= 4
        assert session.scalar(select(func.count(AgentRun.id)).where(AgentRun.patient_id == member_id)) >= 2


def test_observation_api_requires_timezone_aware_timestamp() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session)
    with session_factory() as session:
        member = Patient(external_id="timezone-test", timezone="Asia/Tokyo")
        session.add(member)
        session.commit()
        member_id = member.id
    client = TestClient(create_app(session_factory))
    response = client.post("/observations", json={
        "member_id": str(member_id), "metric_code": "weight", "value": "70", "unit": "kg",
        "observed_at": "2026-08-09T08:00:00",
    })
    assert response.status_code == 422
