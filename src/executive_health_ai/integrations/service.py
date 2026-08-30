"""Batch ingestion orchestration: matching → raw retention → normalization → observation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.integrations.adapters import IncomingRecord, get_adapter
from executive_health_ai.integrations.codes import canonical_code
from executive_health_ai.integrations.normalization import normalize_unit, quality_for
from executive_health_ai.models import (
    AuditLog, ExternalIdentity, IngestionJob, Observation, Patient, RawData, RawIngestionRecord, SleepSession,
)
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.ingestion import get_or_create_raw_data
from executive_health_ai.services.risk_triage import RiskEvaluationService
from executive_health_ai.services.longitudinal import ManagementRoutingService
from executive_health_ai.blood_pressure import coerce_observed_at


@dataclass(frozen=True)
class IngestionSummary:
    job_id: UUID
    status: str
    received: int
    valid: int
    invalid: int
    duplicates: int
    created: int
    unmatched: int


def match_member(session: Session, provider: str, external_member_id: str | None, member_id: UUID | None = None) -> Patient | None:
    if member_id is not None:
        return session.get(Patient, member_id)
    if not external_member_id:
        return None
    identity = session.scalar(select(ExternalIdentity).where(ExternalIdentity.provider == provider, ExternalIdentity.external_id == external_member_id, ExternalIdentity.status == "ACTIVE"))
    return session.get(Patient, identity.patient_id) if identity else None


def ingest(
    session: Session, provider: str, payload: Any, *, external_member_id: str | None = None,
    member_id: UUID | None = None, mapping: dict[str, str] | None = None, created_by: str = "health_manager",
    dry_run: bool = False,
) -> IngestionSummary:
    adapter = get_adapter(provider)
    member = match_member(session, provider, external_member_id, member_id)
    job = IngestionJob(source_system=provider, source_type=adapter.source_type, patient_id=member.id if member else None, status="RUNNING", created_by=created_by)
    session.add(job); session.flush()
    try:
        records = adapter.parse(payload, mapping)
    except Exception as error:
        job.status, job.error_count, job.completed_at = "FAILED", 1, utc_now()
        session.add(RawIngestionRecord(job_id=job.id, patient_id=member.id if member else None, source_system=provider, source_type=adapter.source_type, source_record_id="parse-error", payload_json={"payload_type": type(payload).__name__}, adapter_name=adapter.provider_name, adapter_version=adapter.adapter_version, status="INVALID", error_message=str(error), normalization_json={}))
        return IngestionSummary(job.id, job.status, 0, 0, 1, 0, 0, 0)
    job.records_received = len(records)
    counters = {"valid": 0, "invalid": 0, "duplicates": 0, "created": 0, "unmatched": 0}
    for record in records:
        _ingest_record(session, job, member, adapter.provider_name, adapter.adapter_version, adapter.source_type, record, counters, dry_run)
    job.records_valid, job.records_invalid, job.records_duplicate, job.records_created = counters["valid"], counters["invalid"], counters["duplicates"], counters["created"]
    job.error_count = counters["invalid"] + counters["unmatched"]
    job.completed_at = utc_now()
    job.status = "SUCCESS" if not job.error_count else "PARTIAL_SUCCESS" if counters["valid"] or counters["duplicates"] else "FAILED"
    if member is not None:
        session.add(AuditLog(patient_id=member.id, actor=created_by, actor_role="health_manager", action="completed_ingestion_job", entity_type="IngestionJob", entity_id=str(job.id), detail_json={"provider": provider, "status": job.status, "created": counters["created"], "duplicates": counters["duplicates"]}))
    session.flush()
    return IngestionSummary(job.id, job.status, len(records), counters["valid"], counters["invalid"], counters["duplicates"], counters["created"], counters["unmatched"])


def _ingest_record(session: Session, job: IngestionJob, member: Patient | None, adapter_name: str, adapter_version: str, source_type: str, record: IncomingRecord, counters: dict[str, int], dry_run: bool) -> None:
    base = dict(job_id=job.id, patient_id=member.id if member else None, source_system=job.source_system, source_type=source_type, source_record_id=record.source_record_id, payload_json=record.payload, observed_at=record.observed_at, adapter_name=adapter_name, adapter_version=adapter_version)
    if member is None:
        session.add(RawIngestionRecord(**base, status="UNMATCHED", error_message="No verified external identity; member was not guessed.", normalization_json={}))
        counters["unmatched"] += 1; return
    code = canonical_code(record.metric)
    if code is None:
        session.add(RawIngestionRecord(**base, status="INVALID", error_message="Unsupported observation code.", normalization_json={}))
        counters["invalid"] += 1; return
    try:
        value, unit = normalize_unit(code, record.value, record.unit)
        quality, notes = quality_for(code, value)
    except ValueError as error:
        session.add(RawIngestionRecord(**base, status="INVALID", error_message=str(error), normalization_json={}))
        counters["invalid"] += 1; return
    normalized = {"metric_code": code.canonical_code, "value": str(value), "unit": unit, "quality_flag": quality}
    if quality == "invalid":
        session.add(RawIngestionRecord(**base, status="INVALID", error_message=notes, normalization_json=normalized))
        counters["invalid"] += 1; return
    if dry_run:
        session.add(RawIngestionRecord(**base, status="VALID" if quality == "valid" else "SUSPECT", error_message=notes, normalization_json=normalized))
        counters["valid"] += 1; return
    # A vendor measurement can expand into systolic/diastolic/pulse.  Preserve
    # its original payload once so existing BP grouping treats those metrics as
    # one measurement, while RawIngestionRecord retains each derived metric id.
    raw_payload = {"provider": job.source_system, "payload": record.payload}
    raw, raw_created = get_or_create_raw_data(session, patient_id=member.id, device_id=None, source=job.source_system, record_type="gateway_observation", payload_json=raw_payload, recorded_at=record.observed_at)
    existing = session.scalar(select(Observation).where(Observation.patient_id == member.id, Observation.raw_record_id == raw.id, Observation.metric_code == code.canonical_code))
    if existing is not None:
        session.add(RawIngestionRecord(**base, raw_data_id=raw.id, status="DUPLICATE", error_message=None, normalization_json=normalized))
        counters["duplicates"] += 1; return
    observation = Observation(patient_id=member.id, observed_at=record.observed_at, metric_code=code.canonical_code, value_numeric=value, unit=unit, source=job.source_system, quality_flag=quality, raw_record_id=raw.id, ingestion_job_id=job.id, source_record_id=record.source_record_id, quality_notes=notes)
    session.add(observation)
    session.add(RawIngestionRecord(**base, raw_data_id=raw.id, status="VALID" if quality == "valid" else "SUSPECT", error_message=notes, normalization_json=normalized))
    # Risk evaluation consumes the persisted canonical fact, never adapter
    # payloads.  The safe wrapper records an evaluator failure without losing
    # the ingestion observation itself.
    session.flush()
    RiskEvaluationService().evaluate_observation_safely(session, observation.id)
    ManagementRoutingService().evaluate_observation(session, observation.id)
    _upsert_source_sleep_session(session, member, raw.id, observation, record, job.source_system)
    counters["valid"] += 1; counters["created"] += 1


def _upsert_source_sleep_session(session: Session, member: Patient, raw_id: UUID, observation: Observation, record: IncomingRecord, source: str) -> None:
    """Keep provider-supplied sleep phases separate from canonical observations.

    This deliberately ignores a generic sleep_duration record unless the
    provider gave the original session boundaries.  It never fabricates stage
    segments from a duration measurement.
    """
    if observation.metric_code != "sleep_duration" or not isinstance(record.payload, dict):
        return
    payload = record.payload
    if not payload.get("sleep_start") or not payload.get("sleep_end"):
        return
    try:
        start, end = coerce_observed_at(payload["sleep_start"]), coerce_observed_at(payload["sleep_end"])
    except (TypeError, ValueError):
        return
    if end <= start:
        return
    segments = list(payload.get("stage_segments") or [])
    existing = session.scalar(select(SleepSession).where(SleepSession.raw_record_id == raw_id))
    if existing is None:
        def stage_total(stage: str) -> int | None:
            values = [float(item.get("duration_minutes", 0) or 0) for item in segments if str(item.get("stage")).upper() == stage]
            return int(round(sum(values))) if values else None
        session.add(SleepSession(
            patient_id=member.id, sleep_start=start, sleep_end=end,
            total_sleep_minutes=int(round(float(observation.value_numeric))),
            deep_sleep_minutes=stage_total("DEEP"), rem_sleep_minutes=stage_total("REM"),
            awake_minutes=stage_total("AWAKE"), stage_segments_json=segments,
            source=source, raw_record_id=raw_id,
        ))
    elif segments and not existing.stage_segments_json:
        existing.stage_segments_json = segments


def manually_correct_record(session: Session, record: RawIngestionRecord, value: str, reason: str, actor: str) -> Observation:
    """Append a corrected standardized value without mutating its raw payload."""
    if record.patient_id is None: raise ValueError("Bind a member before correction.")
    normalized = record.normalization_json
    code = canonical_code(str(normalized.get("metric_code", "")))
    if code is None: raise ValueError("Record has no correctable canonical code.")
    amount, unit = normalize_unit(code, value, str(normalized.get("unit") or code.default_unit))
    observation = Observation(patient_id=record.patient_id, observed_at=record.observed_at or utc_now(), metric_code=code.canonical_code, value_numeric=amount, unit=unit, source=f"manual_correction:{record.source_system}", quality_flag="manually_corrected", raw_record_id=record.raw_data_id, ingestion_job_id=record.job_id, source_record_id=f"{record.source_record_id}:corrected", quality_notes=reason)
    session.add(observation)
    record.status, record.error_message = "MANUALLY_CORRECTED", reason
    session.add(AuditLog(patient_id=record.patient_id, actor=actor, actor_role="health_manager", action="manually_corrected_ingestion_record", entity_type="RawIngestionRecord", entity_id=str(record.id), detail_json={"reason": reason, "new_value": value}))
    session.flush()
    RiskEvaluationService().evaluate_observation_safely(session, observation.id)
    ManagementRoutingService().evaluate_observation(session, observation.id)
    return observation


def mark_source_deleted(session: Session, provider: str, member_id: UUID, source_record_ids: list[str], job: IngestionJob) -> int:
    """Retain audit history but exclude source-deleted samples from analysis.

    HealthKit sleep is intentionally stored as one aggregated overnight
    session.  A deleted constituent HealthKit UUID therefore excludes that
    derived session too, rather than silently retaining a stale formal fact.
    """
    affected_observation_ids: set[UUID] = set()
    provider_raw = list(session.scalars(select(RawData).where(
        RawData.patient_id == member_id, RawData.source == provider,
    )))
    for source_id in source_record_ids:
        observations = list(session.scalars(select(Observation).where(
            Observation.patient_id == member_id,
            Observation.source == provider,
            Observation.source_record_id == source_id,
        )))
        # Direct samples keep their HealthKit UUID as source_record_id. Sleep
        # summaries keep the UUID list only in immutable raw provenance.
        for raw in provider_raw:
            payload = raw.payload_json.get("payload") if isinstance(raw.payload_json, dict) else None
            source_ids = payload.get("source_sample_ids", []) if isinstance(payload, dict) else []
            if source_id in source_ids:
                observations.extend(session.scalars(select(Observation).where(
                    Observation.patient_id == member_id,
                    Observation.raw_record_id == raw.id,
                )))
        session.add(RawIngestionRecord(job_id=job.id, patient_id=member_id, source_system=provider, source_type=job.source_type, source_record_id=f"deleted:{source_id}", payload_json={"source_record_id": source_id}, adapter_name="AppleHealthAdapter", adapter_version="v1", status="SOURCE_DELETED", normalization_json={}, event_type="DELETE"))
        for observation in observations:
            if observation.id not in affected_observation_ids:
                observation.source_deleted, observation.excluded_from_analysis = True, True
                affected_observation_ids.add(observation.id)
    return len(affected_observation_ids)
