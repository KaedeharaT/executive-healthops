"""Regression coverage for HealthOps actions initiated by a named human."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.blood_pressure import TOKYO_TIMEZONE
from executive_health_ai.models import Alert, AuditLog, Base, Patient
from executive_health_ai.services.workflow import (
    close_alert_as_false_positive,
    confirm_alert_as_manager,
    create_operational_task,
)


def test_manager_can_link_alert_close_false_positive_and_create_audited_task() -> None:
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with session_factory() as session:
        member = Patient(external_id="synthetic-healthops", timezone="Asia/Tokyo")
        session.add(member)
        session.flush()
        alert = Alert(
            patient_id=member.id,
            alert_type="synthetic_screen",
            title="Synthetic alert awaiting verification",
            finding="Synthetic screening fact for workflow testing.",
            evidence_json={},
            status="AI_SCREENED",
            severity="HIGH",
            responsible_role="health_manager",
            source="synthetic_test",
        )
        false_alert = Alert(
            patient_id=member.id,
            alert_type="synthetic_screen",
            title="Synthetic false-positive candidate",
            finding="Synthetic screening fact for workflow testing.",
            evidence_json={},
            status="AI_SCREENED",
            severity="LOW",
            responsible_role="health_manager",
            source="synthetic_test",
        )
        session.add_all([alert, false_alert])
        session.flush()

        problem = confirm_alert_as_manager(session, alert, "synthetic manager", "Source and measurement method reviewed.")
        task = create_operational_task(
            session,
            member.id,
            "Synthetic follow-up task",
            "Contact the member and record a human-reviewed follow-up result.",
            "HIGH",
            "synthetic manager",
            "synthetic manager",
            datetime(2026, 8, 16, 17, 0, tzinfo=TOKYO_TIMEZONE),
            alert,
            problem,
        )
        close_alert_as_false_positive(session, false_alert, "synthetic manager", "Duplicate synthetic source record.")
        session.commit()

        assert alert.health_problem_id == problem.id
        assert alert.status == "WAITING_DOCTOR_REVIEW"
        assert task.health_problem_id == problem.id
        assert task.alert_id == alert.id
        assert false_alert.status == "CLOSED"
        assert "误报" in (false_alert.review_note or "")
        actions = set(session.scalars(select(AuditLog.action).where(AuditLog.patient_id == member.id)))
        assert {"confirmed_alert", "created_operational_task", "closed_alert_as_false_positive"} <= actions
