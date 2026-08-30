"""Persistence tests for a Yuwell blood pressure reading."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from executive_health_ai.models import Base, Device, Observation, Patient


def assert_utc_datetime(value: datetime) -> None:
    assert value.tzinfo is not None
    assert value.utcoffset() == timedelta(0)


def test_yuwell_blood_pressure_reading_is_persisted_as_three_observations() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session)

    patient_id = uuid4()
    device_id = uuid4()
    raw_record_id = uuid4()
    observed_at = datetime(2026, 8, 7, 12, 30, tzinfo=timezone(timedelta(hours=9)))

    with session_factory() as write_session:
        patient = Patient(id=patient_id, external_id="synthetic-patient-001", timezone="Asia/Tokyo")
        device = Device(
            id=device_id,
            patient_id=patient_id,
            manufacturer="Yuwell",
            model="YE670A",
            device_type="bp_monitor",
            source_system="yuwell_local_import",
            active=True,
        )
        observations = [
            Observation(patient_id=patient_id, device_id=device_id, observed_at=observed_at,
                        metric_code="systolic_bp", value_numeric=Decimal("145"), unit="mmHg",
                        source="yuwell_local_import", quality_flag="valid", raw_record_id=raw_record_id),
            Observation(patient_id=patient_id, device_id=device_id, observed_at=observed_at,
                        metric_code="diastolic_bp", value_numeric=Decimal("92"), unit="mmHg",
                        source="yuwell_local_import", quality_flag="valid", raw_record_id=raw_record_id),
            Observation(patient_id=patient_id, device_id=device_id, observed_at=observed_at,
                        metric_code="heart_rate", value_numeric=Decimal("78"), unit="bpm",
                        source="yuwell_local_import", quality_flag="valid", raw_record_id=raw_record_id),
        ]
        write_session.add_all([patient, device, *observations])
        write_session.commit()

    with session_factory() as read_session:
        stored_patient = read_session.get(Patient, patient_id)
        stored_device = read_session.get(Device, device_id)
        stored_observations = list(read_session.scalars(
            select(Observation).where(Observation.patient_id == patient_id)
        ))

        assert stored_patient is not None
        assert stored_patient.timezone == "Asia/Tokyo"
        assert_utc_datetime(stored_patient.created_at)
        assert_utc_datetime(stored_patient.updated_at)

        assert stored_device is not None
        assert stored_device.manufacturer == "Yuwell"
        assert stored_device.device_type == "bp_monitor"
        assert_utc_datetime(stored_device.created_at)

        assert len(stored_observations) == 3
        expected_metrics = {
            "systolic_bp": (Decimal("145"), "mmHg"),
            "diastolic_bp": (Decimal("92"), "mmHg"),
            "heart_rate": (Decimal("78"), "bpm"),
        }
        expected_observed_at = observed_at.astimezone(timezone.utc)

        for observation in stored_observations:
            expected_value, expected_unit = expected_metrics[observation.metric_code]
            assert observation.value_numeric == expected_value
            assert observation.unit == expected_unit
            assert observation.patient_id == patient_id
            assert observation.device_id == device_id
            assert observation.source == "yuwell_local_import"
            assert observation.raw_record_id == raw_record_id
            assert observation.observed_at == expected_observed_at
            assert_utc_datetime(observation.observed_at)
            assert_utc_datetime(observation.created_at)
