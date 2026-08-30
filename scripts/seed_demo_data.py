"""Seed one idempotent synthetic blood-pressure demo into local SQLite."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.blood_pressure import (
    BloodPressureMeasurement,
    TOKYO_TIMEZONE,
    persist_measurement,
)
from executive_health_ai.database import SessionLocal, engine
from executive_health_ai.models import Device, Observation, Patient
from executive_health_ai.services.ingestion import get_or_create_raw_data

DEMO_PATIENT_EXTERNAL_ID = "demo-executive-001"
DEMO_DEVICE_SERIAL_NUMBER = "DEMO-YUWELL-0001"
DEMO_RAW_RECORD_ID = UUID("11111111-1111-4111-8111-111111111111")
DEMO_SOURCE = "yuwell_local_demo"
DEMO_TIMEZONE = "Asia/Tokyo"
DEMO_OBSERVED_AT = datetime(2026, 8, 7, 7, 30, tzinfo=TOKYO_TIMEZONE)
DEMO_INITIAL_MEASUREMENT = BloodPressureMeasurement(
    observed_at=DEMO_OBSERVED_AT,
    systolic_bp=Decimal("145"),
    diastolic_bp=Decimal("92"),
    heart_rate=Decimal("78"),
)
DEMO_WEEKLY_MEASUREMENTS: tuple[BloodPressureMeasurement, ...] = (
    BloodPressureMeasurement(datetime(2026, 8, 1, 7, 30, tzinfo=TOKYO_TIMEZONE), Decimal("133"), Decimal("84"), Decimal("68")),
    BloodPressureMeasurement(datetime(2026, 8, 1, 20, 30, tzinfo=TOKYO_TIMEZONE), Decimal("135"), Decimal("85"), Decimal("70")),
    BloodPressureMeasurement(datetime(2026, 8, 2, 7, 30, tzinfo=TOKYO_TIMEZONE), Decimal("135"), Decimal("85"), Decimal("69")),
    BloodPressureMeasurement(datetime(2026, 8, 2, 20, 30, tzinfo=TOKYO_TIMEZONE), Decimal("137"), Decimal("86"), Decimal("71")),
    BloodPressureMeasurement(datetime(2026, 8, 3, 7, 30, tzinfo=TOKYO_TIMEZONE), Decimal("137"), Decimal("86"), Decimal("70")),
    BloodPressureMeasurement(datetime(2026, 8, 3, 20, 30, tzinfo=TOKYO_TIMEZONE), Decimal("139"), Decimal("87"), Decimal("72")),
    BloodPressureMeasurement(datetime(2026, 8, 4, 7, 30, tzinfo=TOKYO_TIMEZONE), Decimal("139"), Decimal("87"), Decimal("71")),
    BloodPressureMeasurement(datetime(2026, 8, 4, 20, 30, tzinfo=TOKYO_TIMEZONE), Decimal("141"), Decimal("88"), Decimal("73")),
    BloodPressureMeasurement(datetime(2026, 8, 5, 7, 30, tzinfo=TOKYO_TIMEZONE), Decimal("141"), Decimal("88"), Decimal("72")),
    BloodPressureMeasurement(datetime(2026, 8, 5, 20, 30, tzinfo=TOKYO_TIMEZONE), Decimal("143"), Decimal("89"), Decimal("74")),
    BloodPressureMeasurement(datetime(2026, 8, 6, 7, 30, tzinfo=TOKYO_TIMEZONE), Decimal("143"), Decimal("89"), Decimal("73")),
    BloodPressureMeasurement(datetime(2026, 8, 6, 20, 30, tzinfo=TOKYO_TIMEZONE), Decimal("145"), Decimal("90"), Decimal("75")),
    DEMO_INITIAL_MEASUREMENT,
    BloodPressureMeasurement(datetime(2026, 8, 7, 20, 30, tzinfo=TOKYO_TIMEZONE), Decimal("147"), Decimal("93"), Decimal("80")),
)


def seed_demo_data(session_factory: Callable[[], Session] = SessionLocal) -> dict[str, int]:
    """Create missing synthetic demo records without changing existing records."""
    created = {"patients": 0, "devices": 0, "observations": 0}

    with session_factory() as session:
        patient = session.scalar(
            select(Patient).where(Patient.external_id == DEMO_PATIENT_EXTERNAL_ID)
        )
        if patient is None:
            patient = Patient(
                external_id=DEMO_PATIENT_EXTERNAL_ID,
                timezone=DEMO_TIMEZONE,
            )
            session.add(patient)
            session.flush()
            created["patients"] += 1

        device = session.scalar(
            select(Device).where(
                Device.patient_id == patient.id,
                Device.serial_number == DEMO_DEVICE_SERIAL_NUMBER,
            )
        )
        if device is None:
            device = Device(
                patient_id=patient.id,
                manufacturer="Yuwell",
                model="YE670A",
                device_type="bp_monitor",
                serial_number=DEMO_DEVICE_SERIAL_NUMBER,
                source_system=DEMO_SOURCE,
                active=True,
            )
            session.add(device)
            session.flush()
            created["devices"] += 1

        for measurement in DEMO_WEEKLY_MEASUREMENTS:
            if measurement == DEMO_INITIAL_MEASUREMENT:
                created["observations"] += _persist_initial_measurement(
                    session, patient.id, device.id
                )
            else:
                inserted, _ = persist_measurement(
                    session,
                    patient.id,
                    device.id,
                    measurement,
                    DEMO_SOURCE,
                )
                created["observations"] += inserted
        session.commit()

    return created


def _persist_initial_measurement(session: Session, patient_id: UUID, device_id: UUID) -> int:
    """Preserve the original one-reading demo as the final morning measurement."""
    get_or_create_raw_data(
        session,
        patient_id=patient_id,
        device_id=device_id,
        source=DEMO_SOURCE,
        record_type="blood_pressure",
        payload_json={
            "datetime": DEMO_INITIAL_MEASUREMENT.observed_at.isoformat(),
            "systolic": str(DEMO_INITIAL_MEASUREMENT.systolic_bp),
            "diastolic": str(DEMO_INITIAL_MEASUREMENT.diastolic_bp),
            "heart_rate": str(DEMO_INITIAL_MEASUREMENT.heart_rate),
        },
        recorded_at=DEMO_INITIAL_MEASUREMENT.observed_at,
        raw_id=DEMO_RAW_RECORD_ID,
    )
    existing_metric_codes = set(
        session.scalars(
            select(Observation.metric_code).where(
                Observation.patient_id == patient_id,
                Observation.device_id == device_id,
                Observation.raw_record_id == DEMO_RAW_RECORD_ID,
            )
        )
    )
    values = (
        ("systolic_bp", DEMO_INITIAL_MEASUREMENT.systolic_bp, "mmHg"),
        ("diastolic_bp", DEMO_INITIAL_MEASUREMENT.diastolic_bp, "mmHg"),
        ("heart_rate", DEMO_INITIAL_MEASUREMENT.heart_rate, "bpm"),
    )
    inserted = 0
    for metric_code, value_numeric, unit in values:
        if metric_code in existing_metric_codes:
            continue
        session.add(
            Observation(
                patient_id=patient_id,
                device_id=device_id,
                observed_at=DEMO_INITIAL_MEASUREMENT.observed_at,
                metric_code=metric_code,
                value_numeric=value_numeric,
                unit=unit,
                source=DEMO_SOURCE,
                quality_flag="valid",
                raw_record_id=DEMO_RAW_RECORD_ID,
            )
        )
        inserted += 1
    return inserted


def main() -> None:
    """Seed the default local SQLite database and report the outcome."""
    if engine.dialect.name != "sqlite":
        raise RuntimeError("This local demo only runs when DATABASE_URL points to SQLite.")

    created = seed_demo_data()
    print("Local SQLite demo data is ready.")
    print(f"Database: {engine.url}")
    print(
        "Created: "
        f"patient={created['patients']}, "
        f"device={created['devices']}, "
        f"observations={created['observations']}"
    )


if __name__ == "__main__":
    main()
