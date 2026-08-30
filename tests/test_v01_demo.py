"""Focused regression tests for the V0.1 synthetic end-to-end demo."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pandas as pd
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from executive_health_ai.blood_pressure import TOKYO_TIMEZONE, build_blood_pressure_records
from executive_health_ai.models import (
    AIInsight, Base, CareTask, ClinicalRecommendation, MedicationEvent, Observation, Patient,
    RawData, SleepSession,
)
from executive_health_ai.services.analysis import (
    calculate_blood_pressure_summary, calculate_cgm_summary, calculate_medication_adherence,
    calculate_sleep_summary,
)
from executive_health_ai.services.ingestion import (
    get_or_create_raw_data, import_cgm_rows, import_sleep_rows, normalize_glucose,
    parse_cgm_csv, parse_sleep_csv,
)
from executive_health_ai.services.insights import generate_possible_associations
from executive_health_ai.services.timeline import build_patient_timeline
from scripts.seed_full_demo import seed_full_demo


@pytest.fixture()
def session_factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session)


def test_raw_payload_is_idempotent_and_immutable(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        patient = Patient(external_id="raw-test", timezone="Asia/Tokyo")
        session.add(patient)
        session.flush()
        at = datetime(2026, 8, 7, 8, tzinfo=TOKYO_TIMEZONE)
        first, created = get_or_create_raw_data(session, patient_id=patient.id, device_id=None, source="test", record_type="sample", payload_json={"a": 1}, recorded_at=at)
        second, repeated = get_or_create_raw_data(session, patient_id=patient.id, device_id=None, source="test", record_type="sample", payload_json={"a": 1}, recorded_at=at)
        assert created is True and repeated is False and first.id == second.id
        first.payload_json = {"a": 2}
        with pytest.raises(ValueError, match="immutable"):
            session.flush()


def test_cgm_and_sleep_csv_imports_are_explicit_and_idempotent(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        patient = Patient(external_id="import-test", timezone="Asia/Tokyo")
        session.add(patient)
        session.flush()
        cgm_rows, cgm_errors = parse_cgm_csv(pd.DataFrame([{"datetime": "2026-08-07 07:30", "glucose": 100}]))
        assert cgm_errors == [] and cgm_rows[0][0].tzinfo is not None
        assert normalize_glucose("5.5", "mmol/L") == Decimal("99.100")
        assert import_cgm_rows(session, patient.id, None, cgm_rows) == 1
        assert import_cgm_rows(session, patient.id, None, cgm_rows) == 0
        sleep_frame = pd.DataFrame([{
            "sleep_start": "2026-08-06 23:00", "sleep_end": "2026-08-07 07:00", "total_sleep_minutes": 420,
            "deep_sleep_minutes": 80, "rem_sleep_minutes": 90, "awake_minutes": 60, "sleep_efficiency": 87.5,
            "avg_heart_rate": 58, "lowest_heart_rate": 49, "avg_hrv": 40,
        }])
        sleep_rows, sleep_errors = parse_sleep_csv(sleep_frame)
        assert sleep_errors == []
        assert import_sleep_rows(session, patient.id, None, sleep_rows) == 1
        assert import_sleep_rows(session, patient.id, None, sleep_rows) == 0
        session.commit()
    with session_factory() as session:
        assert session.scalar(select(func.count(Observation.id))) == 1
        assert session.scalar(select(func.count(SleepSession.id))) == 1


def test_full_demo_seed_summaries_timeline_and_associations(session_factory: sessionmaker[Session]) -> None:
    first = seed_full_demo(session_factory)
    second = seed_full_demo(session_factory)
    assert first["observations"] == 1524
    assert first["sleep_sessions"] == 30
    assert first["medication_events"] == 60
    assert second == {"patients": 0, "devices": 0, "observations": 0, "sleep_sessions": 0, "medication_events": 0, "care_tasks": 0}
    with session_factory() as session:
        patient = session.scalar(select(Patient).where(Patient.external_id == "demo-executive-001"))
        assert patient is not None
        observations = list(session.scalars(select(Observation).where(Observation.patient_id == patient.id)))
        # 30 daily synthetic activity/energy/exercise records extend the
        # longitudinal demo without changing the BP/CGM source story.
        assert len(observations) == 1614
        assert all(item.observed_at.tzinfo is not None for item in observations)
        bp_records = build_blood_pressure_records(observations)
        assert len([item for item in bp_records if item.is_complete]) == 60
        bp_30 = calculate_blood_pressure_summary(bp_records, 30)
        cgm = calculate_cgm_summary(observations)
        sleep = calculate_sleep_summary(session.scalars(select(SleepSession).where(SleepSession.patient_id == patient.id)))
        adherence = calculate_medication_adherence(session.scalars(select(MedicationEvent).where(MedicationEvent.patient_id == patient.id)))
        timeline = build_patient_timeline(session, patient.id, 30)
        associations = generate_possible_associations(session, patient.id)
        assert cgm.count == 14 * 96 and cgm.completeness_percent == 100
        assert bp_30.valid_measurement_count == 60 and bp_30.completeness_percent == 100
        assert sleep.count == 30 and sleep.interpretation_status == "normal"
        assert adherence.scheduled_count == 60 and adherence.missed_count == 3
        assert {item.category for item in timeline} >= {"blood_pressure", "cgm", "sleep", "medication", "health_event", "encounter", "care_task"}
        assert associations[0].insight_type == "possible_association"


def test_abstention_ai_clinician_separation_and_care_task_completion(session_factory: sessionmaker[Session]) -> None:
    seed_full_demo(session_factory)
    with session_factory() as session:
        patient = session.scalar(select(Patient).where(Patient.external_id == "demo-executive-001"))
        assert patient is not None
        assert session.scalar(select(func.count(AIInsight.id)).where(AIInsight.patient_id == patient.id)) > 0
        assert session.scalar(select(func.count(ClinicalRecommendation.id)).where(ClinicalRecommendation.patient_id == patient.id)) > 0
        task = session.scalar(select(CareTask).where(CareTask.patient_id == patient.id, CareTask.status == "pending"))
        assert task is not None
        task.status = "completed"
        task.completed_at = datetime.now(TOKYO_TIMEZONE)
        session.commit()
    with session_factory() as session:
        completed = session.scalar(select(CareTask).where(CareTask.status == "completed"))
        assert completed is not None and completed.completed_at is not None
