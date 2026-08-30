"""Tests for idempotent synthetic local demo data seeding."""

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from executive_health_ai.models import Base, Device, Observation, Patient
from scripts.seed_demo_data import (
    DEMO_RAW_RECORD_ID,
    DEMO_SOURCE,
    DEMO_WEEKLY_MEASUREMENTS,
    seed_demo_data,
)


def test_demo_seed_is_idempotent() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session)

    first_result = seed_demo_data(session_factory)
    second_result = seed_demo_data(session_factory)

    assert first_result == {"patients": 1, "devices": 1, "observations": 42}
    assert second_result == {"patients": 0, "devices": 0, "observations": 0}

    with session_factory() as session:
        assert session.scalar(select(func.count(Patient.id))) == 1
        assert session.scalar(select(func.count(Device.id))) == 1

        observations = list(session.scalars(select(Observation)))
        assert len(observations) == 42
        assert {observation.metric_code for observation in observations} == {
            "systolic_bp",
            "diastolic_bp",
            "heart_rate",
        }
        assert {observation.source for observation in observations} == {DEMO_SOURCE}
        raw_record_ids = {observation.raw_record_id for observation in observations}
        assert DEMO_RAW_RECORD_ID in raw_record_ids
        assert len({observation.patient_id for observation in observations}) == 1
        assert len({observation.device_id for observation in observations}) == 1
        assert len({observation.observed_at for observation in observations}) == len(
            DEMO_WEEKLY_MEASUREMENTS
        )
        assert len(raw_record_ids) == len(DEMO_WEEKLY_MEASUREMENTS)
