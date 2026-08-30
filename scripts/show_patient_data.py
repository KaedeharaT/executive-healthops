"""Display the synthetic local SQLite patient demo in a readable format."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from executive_health_ai.database import SessionLocal, engine
from executive_health_ai.models import Device, Observation, Patient
from seed_demo_data import DEMO_PATIENT_EXTERNAL_ID, TOKYO_TIMEZONE


def format_datetime(value: datetime, patient_timezone: str) -> str:
    """Show both the patient's local time and normalized UTC storage time."""
    local_value = value.astimezone(TOKYO_TIMEZONE)
    utc_value = value.astimezone(timezone.utc)
    return f"{local_value.isoformat()} (stored UTC: {utc_value.isoformat()})"


def main() -> None:
    """Read and print the seeded local SQLite demo patient."""
    if engine.dialect.name != "sqlite":
        raise RuntimeError("This local demo only runs when DATABASE_URL points to SQLite.")

    with SessionLocal() as session:
        patient = session.scalar(
            select(Patient).where(Patient.external_id == DEMO_PATIENT_EXTERNAL_ID)
        )
        if patient is None:
            raise SystemExit("Demo patient not found. Run: python scripts/seed_demo_data.py")

        devices = list(
            session.scalars(
                select(Device).where(Device.patient_id == patient.id).order_by(Device.created_at)
            )
        )
        observations = list(
            session.scalars(
                select(Observation)
                .where(Observation.patient_id == patient.id)
                .order_by(Observation.observed_at, Observation.metric_code)
            )
        )

    print("Executive Health AI - Local SQLite Demo")
    print(f"Database: {engine.url}")
    print("\nPatient")
    print("-------")
    print(f"ID: {patient.id}")
    print(f"External ID: {patient.external_id}")
    print(f"Timezone: {patient.timezone}")
    print(f"Created at: {format_datetime(patient.created_at, patient.timezone)}")

    print("\nDevices")
    print("-------")
    for device in devices:
        device_label = f"{device.manufacturer} {device.model or ''}".rstrip()
        print(
            f"- {device_label}"
            f" | type={device.device_type}"
            f" | serial={device.serial_number or 'n/a'}"
            f" | source={device.source_system or 'n/a'}"
            f" | active={device.active}"
        )

    print("\nObservations (ordered by observed_at)")
    print("----------------------------------------")
    for observation in observations:
        print(
            f"- {format_datetime(observation.observed_at, patient.timezone)}"
            f" | {observation.metric_code}={observation.value_numeric} {observation.unit}"
            f" | source={observation.source}"
            f" | raw_record_id={observation.raw_record_id}"
        )


if __name__ == "__main__":
    main()
