"""Tests for Streamlit demo data-processing helpers."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from executive_health_ai.blood_pressure import (
    BloodPressureRecord,
    TOKYO_TIMEZONE,
    calculate_health_feedback,
    calculate_seven_day_summary,
    measurement_from_values,
    parse_csv_measurements,
    persist_measurement,
)
from executive_health_ai.models import Base, Device, Observation, Patient


def test_persist_measurement_creates_three_observations_only_once() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session)

    with session_factory() as session:
        patient = Patient(external_id="test-demo", timezone="Asia/Tokyo")
        session.add(patient)
        session.flush()
        device = Device(patient_id=patient.id, manufacturer="Yuwell", device_type="bp_monitor")
        session.add(device)
        session.commit()
        patient_id, device_id = patient.id, device.id

    measurement = measurement_from_values("2026-08-07 07:30", 145, 92, 78)
    with session_factory() as session:
        first_created, first_raw_record_id = persist_measurement(
            session, patient_id, device_id, measurement, "test_source"
        )
        session.commit()

    with session_factory() as session:
        second_created, second_raw_record_id = persist_measurement(
            session, patient_id, device_id, measurement, "test_source"
        )
        session.commit()
        observations = list(session.scalars(select(Observation)))

    assert first_created == 3
    assert second_created == 0
    assert first_raw_record_id == second_raw_record_id
    assert len(observations) == 3
    assert {observation.metric_code for observation in observations} == {
        "systolic_bp",
        "diastolic_bp",
        "heart_rate",
    }
    assert len({observation.observed_at for observation in observations}) == 1
    assert len({observation.raw_record_id for observation in observations}) == 1


def test_csv_parsing_checks_columns_and_timezone() -> None:
    dataframe = pd.DataFrame(
        [{"datetime": "2026-08-07 07:30", "systolic": 145, "diastolic": 92, "heart_rate": 78}]
    )
    measurements, errors = parse_csv_measurements(dataframe)

    assert errors == []
    assert len(measurements) == 1
    assert measurements[0].observed_at.utcoffset() == timedelta(hours=9)

    _, errors = parse_csv_measurements(dataframe.drop(columns="heart_rate"))
    assert errors == ["Missing columns: heart_rate"]


def test_feedback_is_descriptive_and_requires_enough_complete_data() -> None:
    records = [
        BloodPressureRecord(datetime(2026, 8, 5, tzinfo=timezone.utc), Decimal("120"), Decimal("80"), Decimal("70")),
        BloodPressureRecord(datetime(2026, 8, 6, tzinfo=timezone.utc), Decimal("122"), Decimal("81"), Decimal("71")),
        BloodPressureRecord(datetime(2026, 8, 7, tzinfo=timezone.utc), Decimal("124"), Decimal("82"), Decimal("72")),
    ]

    feedback = calculate_health_feedback(records)

    assert feedback.valid_measurement_count == 3
    assert feedback.completeness_percent == 100
    assert feedback.recent_average_systolic == Decimal("122")
    assert feedback.recent_average_diastolic == Decimal("81")
    assert feedback.trend == "increasing"
    assert feedback.interpretation_status == "normal"


def test_seven_day_summary_calculates_period_averages_and_descriptive_trend() -> None:
    records = []
    for day_offset in range(7):
        measurement_date = datetime(2026, 8, 1 + day_offset, tzinfo=TOKYO_TIMEZONE)
        records.extend(
            [
                BloodPressureRecord(
                    measurement_date.replace(hour=7, minute=30),
                    Decimal(str(130 + day_offset * 2)),
                    Decimal(str(80 + day_offset)),
                    Decimal("70"),
                ),
                BloodPressureRecord(
                    measurement_date.replace(hour=20, minute=30),
                    Decimal(str(132 + day_offset * 2)),
                    Decimal(str(81 + day_offset)),
                    Decimal("72"),
                ),
            ]
        )

    summary = calculate_seven_day_summary(records)

    assert summary.valid_measurement_count == 14
    assert summary.completeness_percent == 100
    assert summary.morning_average_systolic == Decimal("136")
    assert summary.morning_average_diastolic == Decimal("83")
    assert summary.evening_average_systolic == Decimal("138")
    assert summary.evening_average_diastolic == Decimal("84")
    assert summary.recent_three_day_average_systolic == Decimal("141")
    assert summary.previous_four_day_average_systolic == Decimal("134")
    assert summary.trend == "increasing"
    assert summary.interpretation_status == "normal"


def test_seven_day_summary_abstains_when_daily_trend_cannot_be_calculated() -> None:
    summary = calculate_seven_day_summary(
        [
            BloodPressureRecord(
                datetime(2026, 8, 7, tzinfo=timezone.utc),
                Decimal("140"),
                Decimal("90"),
                Decimal("70"),
            )
        ]
    )

    assert summary.trend == "insufficient_data"
    assert summary.interpretation_status == "insufficient_data"
