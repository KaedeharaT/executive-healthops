"""Synthetic V0.3 gateway regression tests; no real health data is used."""
from __future__ import annotations

import base64
import io
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.ai.signal_agent import screen_persistent_bp_signal
from executive_health_ai.api import create_app
from executive_health_ai.blood_pressure import TOKYO_TIMEZONE
from executive_health_ai.integrations.adapters import CSVAdapter, MockCGMAdapter, MockOuraAdapter, MockYuwellAdapter
from executive_health_ai.integrations.codes import canonical_code
from executive_health_ai.integrations.normalization import normalize_unit, quality_for
from executive_health_ai.integrations.service import ingest, manually_correct_record
from executive_health_ai.models import AuditLog, Base, ExternalIdentity, IngestionJob, Observation, Patient, RawIngestionRecord
from executive_health_ai.services.timeline import build_patient_timeline


def _factory():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def _member(session: Session) -> Patient:
    member = Patient(external_id="synthetic-gateway-member", timezone="Asia/Tokyo")
    session.add(member); session.flush()
    session.add(ExternalIdentity(patient_id=member.id, provider="mock_yuwell", external_id="YUWELL-SYNTHETIC"))
    return member


def test_adapter_contract_code_aliases_and_explicit_unit_conversion() -> None:
    assert len(MockYuwellAdapter().parse({"user_id": "u", "measure_time": "2026-08-01T07:30:00+09:00", "sys": 148, "dia": 94, "pulse": 76})) == 3
    assert MockOuraAdapter().parse({"user_id": "u", "day": "2026-08-01", "total_sleep_duration": 3600, "score": 70, "resting_heart_rate": 60})[0].value == 60
    assert len(MockCGMAdapter().parse({"user_id": "u", "records": [{"timestamp": "2026-08-01T00:00:00+09:00", "glucose": 6, "unit": "mmol/L"}]})) == 1
    csv = "timestamp,高压,低压\n2026-08-01T07:30:00+09:00,148,94\n"
    assert len(CSVAdapter().parse(csv, {"timestamp": "observed_at", "高压": "systolic_bp", "低压": "diastolic_bp"})) == 2
    code = canonical_code("高压")
    assert code and code.canonical_code == "systolic_bp"
    assert str(normalize_unit(canonical_code("glucose"), "6", "mmol/L")[0]).startswith("108")  # type: ignore[arg-type]
    assert quality_for(code, normalize_unit(code, "850", "mmHg")[0])[0] == "invalid"


def test_gateway_is_idempotent_preserves_raw_records_and_invalid_data_does_not_create_observation() -> None:
    factory = _factory()
    with factory() as session:
        member = _member(session)
        payload = {"user_id": "YUWELL-SYNTHETIC", "device_id": "bp-1", "measure_time": "2026-08-01T07:30:00+09:00", "sys": 148, "dia": 94, "pulse": 76}
        first = ingest(session, "mock_yuwell", payload, external_member_id="YUWELL-SYNTHETIC")
        second = ingest(session, "mock_yuwell", payload, external_member_id="YUWELL-SYNTHETIC")
        invalid = ingest(session, "mock_yuwell", {**payload, "id": "bad", "sys": 850}, external_member_id="YUWELL-SYNTHETIC")
        session.commit()
        assert first.created == 3 and second.created == 0 and second.duplicates == 3
        assert invalid.invalid == 1
        assert session.scalar(select(Observation).where(Observation.source_record_id == "bad-sys")) is None
        raw = session.scalar(select(RawIngestionRecord).where(RawIngestionRecord.status == "INVALID"))
        assert raw and raw.payload_json["sys"] == 850
        corrected = manually_correct_record(session, raw, "148", "Synthetic source typo", "manager")
        session.commit()
        assert corrected.quality_flag == "manually_corrected"
        assert session.scalar(select(AuditLog).where(AuditLog.action == "manually_corrected_ingestion_record")) is not None


def test_unmatched_partial_success_cgm_batch_and_valid_imported_bp_reaches_existing_signal() -> None:
    factory = _factory()
    with factory() as session:
        member = _member(session)
        unmatched = ingest(session, "mock_yuwell", {"user_id": "unknown", "measure_time": "2026-08-01T07:30:00+09:00", "sys": 148, "dia": 94, "pulse": 76}, external_member_id="unknown")
        assert unmatched.status == "FAILED" and unmatched.unmatched == 3
        start = datetime(2026, 8, 1, 7, 30, tzinfo=TOKYO_TIMEZONE)
        for day in range(5):
            ingest(session, "mock_yuwell", {"id": f"bp-{day}", "user_id": "YUWELL-SYNTHETIC", "measure_time": (start + timedelta(days=day)).isoformat(), "sys": 148, "dia": 94, "pulse": 76}, external_member_id="YUWELL-SYNTHETIC")
        cgm = ingest(session, "mock_cgm", {"user_id": "u", "records": [{"id": f"cgm-{index}", "timestamp": (start + timedelta(minutes=5 * index)).isoformat(), "glucose": 110, "unit": "mg/dL"} for index in range(288)]}, member_id=member.id)
        alert = screen_persistent_bp_signal(session, member.id)
        session.commit()
        assert cgm.created == 288
        assert alert is not None and alert.alert_type == "persistent_bp_screen"
        assert session.scalar(select(IngestionJob).where(IngestionJob.status == "SUCCESS")) is not None


def test_ingestion_api_returns_job_summary_and_review_queue() -> None:
    factory = _factory()
    with factory() as session:
        member = _member(session); session.commit(); member_id = member.id
    client = TestClient(create_app(factory))
    response = client.post("/ingestion/observations", json={"provider": "json", "member_id": str(member_id), "records": [{"id": "weight-1", "metric": "weight", "value": 180, "unit": "lb", "observed_at": "2026-08-01T08:00:00+09:00"}]})
    assert response.status_code == 201 and response.json()["created"] == 1
    bad = client.post("/ingestion/observations", json={"provider": "json", "member_id": str(member_id), "records": [{"id": "bad-1", "metric": "weight", "value": 860, "unit": "kg", "observed_at": "2026-08-01T08:00:00+09:00"}]})
    assert bad.status_code == 201 and bad.json()["invalid"] == 1
    assert len(client.get("/ingestion/review-queue").json()) >= 1
    csv_content = b"timestamp,high\n2026-08-02T08:00:00+09:00,130\n"
    file_response = client.post("/ingestion/files", json={"provider": "csv", "filename": "synthetic.csv", "content_base64": base64.b64encode(csv_content).decode(), "member_id": str(member_id), "mapping": {"timestamp": "observed_at", "high": "systolic_bp"}})
    assert file_response.status_code == 201 and file_response.json()["created"] == 1
    pdf_response = client.post("/ingestion/files", json={"provider": "pdf", "filename": "synthetic-report.pdf", "content_base64": base64.b64encode(b"%PDF-synthetic").decode(), "member_id": str(member_id)})
    assert pdf_response.status_code == 201 and pdf_response.json()["status"] == "PARTIAL_SUCCESS"


def test_dry_run_records_preview_without_standardized_observations() -> None:
    factory = _factory()
    with factory() as session:
        member = _member(session)
        summary = ingest(session, "json", {"records": [{"id": "preview", "metric": "weight", "value": 80, "unit": "kg", "observed_at": "2026-08-01T08:00:00+09:00"}]}, member_id=member.id, dry_run=True)
        assert summary.created == 0 and summary.valid == 1
        assert session.scalar(select(Observation)) is None
        assert session.scalar(select(RawIngestionRecord).where(RawIngestionRecord.status == "VALID")) is not None


def test_suspect_data_is_retained_for_review_but_not_considered_valid() -> None:
    factory = _factory()
    with factory() as session:
        member = _member(session)
        summary = ingest(session, "json", {"records": [{"id": "near-boundary", "metric": "systolic_bp", "value": 290, "unit": "mmHg", "observed_at": "2026-08-01T08:00:00+09:00"}]}, member_id=member.id)
        session.commit()
        observation = session.scalar(select(Observation))
        assert summary.created == 1 and observation and observation.quality_flag == "suspect"


def test_excel_adapter_parses_in_memory_xlsx_with_canonical_mapping() -> None:
    import pandas as pd
    content = io.BytesIO()
    pd.DataFrame([{"timestamp": "2026-08-01T08:00:00+09:00", "SYS": 130}]).to_excel(content, index=False)
    records = __import__("executive_health_ai.integrations.adapters", fromlist=["ExcelAdapter"]).ExcelAdapter().parse(content.getvalue(), {"timestamp": "observed_at", "SYS": "systolic_bp"})
    assert records[0].metric == "systolic_bp" and records[0].value == "130"


def test_external_identity_is_required_instead_of_guessing_member() -> None:
    factory = _factory()
    with factory() as session:
        member = _member(session)
        assert ingest(session, "mock_yuwell", {"user_id": "not-linked", "measure_time": "2026-08-01T08:00:00+09:00", "sys": 130, "dia": 80, "pulse": 70}, external_member_id="not-linked").unmatched == 3
        assert ingest(session, "mock_yuwell", {"user_id": "YUWELL-SYNTHETIC", "measure_time": "2026-08-01T08:00:00+09:00", "sys": 130, "dia": 80, "pulse": 70}, external_member_id="YUWELL-SYNTHETIC").created == 3


def test_cgm_timeline_is_aggregated_as_an_import_event() -> None:
    factory = _factory()
    with factory() as session:
        member = _member(session)
        start = datetime(2026, 8, 1, 7, 30, tzinfo=TOKYO_TIMEZONE)
        ingest(session, "mock_cgm", {"records": [{"id": f"g-{i}", "timestamp": (start + timedelta(minutes=5 * i)).isoformat(), "glucose": 110, "unit": "mg/dL"} for i in range(288)]}, member_id=member.id)
        session.commit()
        items = build_patient_timeline(session, member.id, days=30)
        assert len([item for item in items if item.title == "CGM data imported"]) == 1


def test_job_detail_api_exposes_provenance_samples() -> None:
    factory = _factory()
    with factory() as session:
        member = _member(session); session.commit(); member_id = member.id
    client = TestClient(create_app(factory))
    result = client.post("/ingestion/observations", json={"provider": "json", "member_id": str(member_id), "records": [{"id": "provenance", "metric": "weight", "value": 80, "unit": "kg", "observed_at": "2026-08-01T08:00:00+09:00"}]}).json()
    detail = client.get(f"/ingestion/jobs/{result['job_id']}")
    assert detail.status_code == 200 and len(detail.json()["records"]) == 1
