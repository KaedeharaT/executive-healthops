"""VNext Apple Health bridge contracts; iOS runtime stays for real-device QA."""

from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.integrations.apple_health import AppleHealthAdapter, TYPE_MAPPING
from executive_health_ai.integrations.service import ingest, mark_source_deleted
from executive_health_ai.models import Base, ExternalIdentity, IngestionJob, Observation, Patient


ROOT = Path(__file__).resolve().parents[1]
IOS = ROOT / "ios" / "ExecutiveHealthBridge"
APP = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)()


def _member(session: Session) -> Patient:
    member = Patient(external_id="apple-vnext-member", timezone="Asia/Tokyo")
    session.add(member); session.flush()
    session.add(ExternalIdentity(patient_id=member.id, provider="apple_health", external_id="APPLE-VNEXT"))
    session.flush()
    return member


def test_canonical_registry_covers_the_supported_healthkit_measurements() -> None:
    assert TYPE_MAPPING == {
        "stepCount": ("steps", "count"), "appleExerciseTime": ("exercise_minutes", "minutes"),
        "activeEnergyBurned": ("active_calories", "kcal"), "heartRate": ("heart_rate", "bpm"),
        "restingHeartRate": ("resting_heart_rate", "bpm"), "oxygenSaturation": ("spo2", "%"),
        "bodyMass": ("weight", "kg"),
    }


def test_adapter_accepts_all_supported_measurements_without_inventing_missing_values() -> None:
    payload = {"samples": [
        {"sample_id": "steps", "type": "stepCount", "value": 1, "start_date": "2026-08-01T00:00:00+09:00", "end_date": "2026-08-01T00:01:00+09:00"},
        {"sample_id": "energy", "type": "activeEnergyBurned", "value": 2, "start_date": "2026-08-01T00:00:00+09:00", "end_date": "2026-08-01T00:01:00+09:00"},
        {"sample_id": "exercise", "type": "appleExerciseTime", "value": 3, "start_date": "2026-08-01T00:00:00+09:00", "end_date": "2026-08-01T00:01:00+09:00"},
        {"sample_id": "hr", "type": "heartRate", "value": 60, "start_date": "2026-08-01T00:00:00+09:00", "end_date": "2026-08-01T00:01:00+09:00"},
        {"sample_id": "rhr", "type": "restingHeartRate", "value": 55, "start_date": "2026-08-01T00:00:00+09:00", "end_date": "2026-08-01T00:01:00+09:00"},
        {"sample_id": "spo2", "type": "oxygenSaturation", "value": 0.97, "unit": "percent", "start_date": "2026-08-01T00:00:00+09:00", "end_date": "2026-08-01T00:01:00+09:00"},
        {"sample_id": "weight", "type": "bodyMass", "value": 70, "start_date": "2026-08-01T00:00:00+09:00", "end_date": "2026-08-01T00:01:00+09:00"},
        {"sample_id": "not-present", "type": "bloodGlucose", "value": 6, "start_date": "2026-08-01T00:00:00+09:00", "end_date": "2026-08-01T00:01:00+09:00"},
    ]}
    records = AppleHealthAdapter().parse(payload)
    assert {record.metric for record in records} == {"steps", "active_calories", "exercise_minutes", "heart_rate", "resting_heart_rate", "spo2", "weight"}


def test_deleted_sleep_sample_excludes_the_derived_sleep_observation() -> None:
    with _session() as session:
        member = _member(session)
        payload = {"samples": [
            {"sample_id": "sleep-core", "type": "sleepAnalysis", "value": "asleepCore", "start_date": "2026-08-01T23:00:00+09:00", "end_date": "2026-08-02T05:00:00+09:00"},
            {"sample_id": "sleep-deep", "type": "sleepAnalysis", "value": "asleepDeep", "start_date": "2026-08-02T05:00:00+09:00", "end_date": "2026-08-02T06:00:00+09:00"},
        ]}
        summary = ingest(session, "apple_health", payload, external_member_id="APPLE-VNEXT")
        job = session.get(IngestionJob, summary.job_id); assert job is not None
        assert mark_source_deleted(session, "apple_health", member.id, ["sleep-deep"], job) == 1
        observation = session.scalar(select(Observation).where(Observation.metric_code == "sleep_duration"))
        assert observation and observation.source_deleted and observation.excluded_from_analysis


def test_ios_source_uses_authorization_anchored_sync_observers_and_truthful_copy() -> None:
    manager = (IOS / "HealthKitManager.swift").read_text(encoding="utf-8")
    sync = (IOS / "HealthSyncService.swift").read_text(encoding="utf-8")
    types = (IOS / "HealthKitTypes.swift").read_text(encoding="utf-8")
    assert "requestAuthorization" in manager and "HKAnchoredObjectQuery" in manager
    assert "HKObserverQuery" in manager and "enableBackgroundDelivery" in manager
    assert "health.commit(delta)" in sync and "deleted_sample_ids" in sync
    assert all(stage in manager for stage in ("inBed", "awake", "asleepCore", "asleepDeep", "asleepREM"))
    assert "不承诺实时" in sync or "not real-time" in manager
    assert "全部权限" in (IOS / "ContentView.swift").read_text(encoding="utf-8")


def test_ios_bridge_token_is_local_configuration_not_source_and_sync_does_not_call_qwen() -> None:
    config = (IOS / "BridgeConfiguration.swift").read_text(encoding="utf-8")
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    sync = (IOS / "HealthSyncService.swift").read_text(encoding="utf-8")
    assert "HEALTHOPS_BRIDGE_TOKEN" in config and "BridgeSecrets.xcconfig" in ignored
    assert "qwen" not in sync.lower() and "llm" not in sync.lower()
    assert "真实设备验证" not in APP
    assert "真机验证：" in APP and "已收到桥接同步" in APP

