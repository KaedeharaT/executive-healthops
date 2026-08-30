"""Seed optional V0.3 gateway jobs for the existing synthetic demo member."""
from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path

from sqlalchemy import select

from executive_health_ai.blood_pressure import DEMO_PATIENT_EXTERNAL_ID, TOKYO_TIMEZONE
from executive_health_ai.database import SessionLocal
from executive_health_ai.integrations.service import ingest
from executive_health_ai.models import ExternalIdentity, Patient


def _identity(session, patient: Patient, provider: str, external_id: str) -> None:
    identity = session.scalar(select(ExternalIdentity).where(ExternalIdentity.provider == provider, ExternalIdentity.external_id == external_id))
    if identity is None:
        session.add(ExternalIdentity(patient_id=patient.id, provider=provider, external_id=external_id))
    else:
        # Synthetic reseeding can recreate the demo member with a new UUID.
        # Rebind only these known demo identities instead of leaving mock CGM
        # records in the unmatched review queue.
        identity.patient_id = patient.id
        identity.status = "ACTIVE"


def main() -> None:
    with SessionLocal() as session:
        member = session.scalar(select(Patient).where(Patient.external_id == DEMO_PATIENT_EXTERNAL_ID))
        if member is None: raise RuntimeError("Run seed_full_demo.py before seeding the gateway demo.")
        _identity(session, member, "mock_yuwell", "YUWELL-DEMO-001")
        _identity(session, member, "mock_oura", "OURA-DEMO-001")
        _identity(session, member, "mock_cgm", "CGM-DEMO-001")
        _identity(session, member, "apple_health", "APPLE-DEMO-001")
        session.flush()
        start = datetime(2026, 8, 10, 7, 30, tzinfo=TOKYO_TIMEZONE)
        for day in range(5):
            ingest(session, "mock_yuwell", {"user_id": "YUWELL-DEMO-001", "device_id": "BP-DEMO-01", "measure_time": (start + timedelta(days=day)).isoformat(), "sys": 148, "dia": 94, "pulse": 76}, external_member_id="YUWELL-DEMO-001", created_by="synthetic_gateway_demo")
        ingest(session, "mock_oura", {"user_id": "OURA-DEMO-001", "day": "2026-08-14", "total_sleep_duration": 21120, "score": 72, "resting_heart_rate": 61}, external_member_id="OURA-DEMO-001", created_by="synthetic_gateway_demo")
        cgm_start = datetime(2026, 8, 1, 0, 0, tzinfo=TOKYO_TIMEZONE)
        rows = [{"id": f"cgm-{index}", "timestamp": (cgm_start + timedelta(minutes=5 * index)).isoformat(), "glucose": 110 + index % 20, "unit": "mg/dL"} for index in range(14 * 288)]
        ingest(session, "mock_cgm", {"user_id": "CGM-DEMO-001", "device_id": "CGM-DEMO-01", "records": rows}, external_member_id="CGM-DEMO-001", created_by="synthetic_gateway_demo")
        apple_payload = json.loads((Path(__file__).parents[1] / "sample_data" / "apple_health" / "mock_apple_health_sync.json").read_text(encoding="utf-8"))
        ingest(session, "apple_health", {"samples": apple_payload["samples"]}, external_member_id="APPLE-DEMO-001", created_by="synthetic_gateway_demo")
        session.commit()
    print("V0.3 Synthetic Data Gateway demo seeded (Yuwell, Oura, CGM).")


if __name__ == "__main__": main()
