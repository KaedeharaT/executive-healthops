"""Synthetic Apple Health gateway tests; no HealthKit runtime is required."""
from __future__ import annotations
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from executive_health_ai.api import create_app
from executive_health_ai.integrations.adapters import PROVIDERS
from executive_health_ai.integrations.apple_health import AppleHealthAdapter
from executive_health_ai.integrations.service import ingest
from executive_health_ai.models import Base, ExternalIdentity, Observation, Patient, SleepSession

def _factory():
    engine=create_engine("sqlite+pysqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool); Base.metadata.create_all(engine); return sessionmaker(bind=engine,class_=Session,expire_on_commit=False)
def _payload(): return {"external_member_id":"APPLE-SYNTHETIC","device_installation_id":"install-1","sync_id":"sync-1","sync_started_at":"2026-08-15T08:00:00+09:00","samples":[{"sample_id":"steps-1","type":"stepCount","value":12032,"unit":"count","start_date":"2026-08-14T00:00:00+09:00","end_date":"2026-08-14T23:00:00+09:00","source":{"name":"Synthetic"},"device":{"model":"Watch"}},{"sample_id":"spo2-1","type":"oxygenSaturation","value":0.97,"unit":"percent","start_date":"2026-08-14T07:00:00+09:00","end_date":"2026-08-14T07:00:00+09:00"},{"sample_id":"sleep-1","type":"sleepAnalysis","value":"asleepCore","start_date":"2026-08-13T23:30:00+09:00","end_date":"2026-08-14T06:00:00+09:00"}]}
def test_apple_provider_maps_samples_and_merges_sleep():
    records=AppleHealthAdapter().parse(_payload()); assert "apple_health" in PROVIDERS; assert {r.metric for r in records} == {"steps","spo2","sleep_duration"}; assert records[-1].value == 390
def test_apple_idempotency_and_deleted_source_exclusion():
    factory=_factory()
    with factory() as s:
        p=Patient(external_id="a",timezone="Asia/Tokyo");s.add(p);s.flush();s.add(ExternalIdentity(patient_id=p.id,provider="apple_health",external_id="APPLE-SYNTHETIC"));a=ingest(s,"apple_health",{"samples":_payload()["samples"]},external_member_id="APPLE-SYNTHETIC");b=ingest(s,"apple_health",{"samples":_payload()["samples"]},external_member_id="APPLE-SYNTHETIC");s.commit();assert a.created==3 and b.duplicates==3;assert s.scalar(select(Observation).where(Observation.metric_code=="spo2")).unit=="%"
def test_apple_sleep_phases_are_preserved_only_when_the_source_supplies_them():
    factory=_factory()
    samples=[
        {"sample_id":"sleep-light","type":"sleepAnalysis","value":"asleepCore","start_date":"2026-08-13T23:30:00+09:00","end_date":"2026-08-14T02:00:00+09:00"},
        {"sample_id":"sleep-deep","type":"sleepAnalysis","value":"asleepDeep","start_date":"2026-08-14T02:00:00+09:00","end_date":"2026-08-14T03:20:00+09:00"},
        {"sample_id":"sleep-rem","type":"sleepAnalysis","value":"asleepREM","start_date":"2026-08-14T03:20:00+09:00","end_date":"2026-08-14T04:20:00+09:00"},
        {"sample_id":"sleep-awake","type":"sleepAnalysis","value":"awake","start_date":"2026-08-14T04:20:00+09:00","end_date":"2026-08-14T04:35:00+09:00"},
    ]
    with factory() as s:
        p=Patient(external_id="a",timezone="Asia/Tokyo");s.add(p);s.flush();s.add(ExternalIdentity(patient_id=p.id,provider="apple_health",external_id="APPLE-SYNTHETIC"));ingest(s,"apple_health",{"samples":samples},external_member_id="APPLE-SYNTHETIC");s.commit()
        sleep=s.scalar(select(SleepSession))
        assert sleep and sleep.deep_sleep_minutes==80 and sleep.awake_minutes==15
        assert [segment["stage"] for segment in sleep.stage_segments_json]==["LIGHT","DEEP","REM","AWAKE"]
def test_apple_sync_api_uses_identity_and_returns_truthful_status(monkeypatch):
    monkeypatch.setenv("APPLE_HEALTH_BRIDGE_TOKEN","test-token");factory=_factory()
    with factory() as s:
        p=Patient(external_id="a",timezone="Asia/Tokyo");s.add(p);s.flush();s.add(ExternalIdentity(patient_id=p.id,provider="apple_health",external_id="APPLE-SYNTHETIC"));s.commit()
    c=TestClient(create_app(factory));r=c.post("/integrations/apple-health/sync",json=_payload(),headers={"Authorization":"Bearer test-token"});assert r.status_code==201 and r.json()["created"]==3
    status=c.get("/integrations/apple-health/status/APPLE-SYNTHETIC").json()
    assert status["status"]=="SYNCED" and status["provider_readiness"] == {"backend":"BACKEND_READY", "ios_bridge":"IOS_SOURCE_READY", "real_device":"REAL_DEVICE_VERIFIED"}
