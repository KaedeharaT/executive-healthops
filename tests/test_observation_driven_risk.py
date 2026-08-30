"""Synthetic, non-clinical regression coverage for observation-driven risk."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.api import create_app
from executive_health_ai.blood_pressure import TOKYO_TIMEZONE
from executive_health_ai.integrations.service import ingest, manually_correct_record
from executive_health_ai.models import (
    Base, Document, IngestionJob, Observation, Patient, RawIngestionRecord,
    ReportExtractionCandidate, ReportExtractionRun, RiskEvent, RiskRule,
)
from executive_health_ai.services.report_parsing import ReportParsingService
from executive_health_ai.services.risk_triage import RiskEvaluationService


def _factory():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def _member(session: Session) -> Patient:
    member = Patient(external_id="synthetic-risk-member", timezone="Asia/Tokyo")
    session.add(member)
    session.flush()
    return member


def _rule(
    session: Session,
    *,
    code: str = "SYNTHETIC_STEPS_YELLOW",
    status: str = "APPROVED",
    active: bool = True,
    metric: str = "steps",
    unit: str = "count",
    window: dict[str, object] | None = None,
) -> RiskRule:
    """An explicitly non-clinical test rule; it is never a medical threshold."""
    rule = RiskRule(
        name="合成测试规则：步数记录验证",
        code=code,
        applicable_device_class="ANY",
        canonical_code=metric,
        risk_level="YELLOW",
        condition_type="SYNTHETIC_TEST_THRESHOLD",
        threshold_config={"metric": metric, "operator": ">=", "value": "8000", "unit": unit},
        window_config=window or {},
        requires_repeated_measurement=False,
        requires_symptom_confirmation=False,
        action_type="SYNTHETIC_TEST_ONLY",
        source_reference="SYNTHETIC TEST RULE ONLY — 非临床规则，不用于任何医疗判断。",
        review_status=status,
        reviewed_by="synthetic test reviewer" if status == "APPROVED" else None,
        is_active=active,
    )
    session.add(rule)
    session.flush()
    return rule


def _observation(
    session: Session,
    member: Patient,
    *,
    value: str = "9000",
    observed_at: datetime | None = None,
    quality: str = "valid",
    source: str = "synthetic_gateway",
    excluded: bool = False,
    source_deleted: bool = False,
) -> Observation:
    record = Observation(
        patient_id=member.id,
        observed_at=observed_at or datetime(2026, 8, 17, 9, 0, tzinfo=TOKYO_TIMEZONE),
        metric_code="steps",
        value_numeric=Decimal(value),
        unit="count",
        source=source,
        quality_flag=quality,
        excluded_from_analysis=excluded,
        source_deleted=source_deleted,
    )
    session.add(record)
    session.flush()
    return record


def test_eligible_observation_executes_only_approved_active_rules_and_creates_evidence() -> None:
    factory = _factory()
    with factory() as session:
        member = _member(session)
        approved = _rule(session)
        _rule(session, code="DRAFT", status="DRAFT")
        _rule(session, code="INACTIVE", active=False)
        _rule(session, code="METRIC_MISMATCH", metric="weight", unit="kg")
        _rule(session, code="UNIT_MISMATCH", unit="kg")
        observation = _observation(session, member)

        result = RiskEvaluationService().evaluate_observation(session, observation.id)
        event = session.scalar(select(RiskEvent).where(RiskEvent.risk_rule_id == approved.id))

        assert result.eligible and result.evaluated_rule_count == 2
        assert result.created_event_count == 1 and event is not None
        assert event.evidence_json["source"] == "observation_driven"
        assert event.evidence_json["metric"] == "steps"
        assert event.evidence_json["observation_ids"] == [str(observation.id)]
        assert event.evidence_json["matched_count"] == 1


def test_duplicate_gateway_observation_does_not_duplicate_a_real_risk_event() -> None:
    factory = _factory()
    with factory() as session:
        member = _member(session)
        _rule(session)
        payload = {"records": [{
            "id": "same-synthetic-steps", "metric": "steps", "value": 9000, "unit": "count",
            "observed_at": "2026-08-17T09:00:00+09:00",
        }]}
        first = ingest(session, "json", payload, member_id=member.id)
        second = ingest(session, "json", payload, member_id=member.id)
        assert first.created == 1 and second.duplicates == 1
        assert len(list(session.scalars(select(RiskEvent)))) == 1


def test_invalid_suspect_deleted_and_excluded_observations_are_never_evaluated() -> None:
    factory = _factory()
    with factory() as session:
        member = _member(session)
        _rule(session)
        service = RiskEvaluationService()
        for kwargs in (
            {"quality": "invalid"}, {"quality": "suspect"},
            {"excluded": True}, {"source_deleted": True},
        ):
            result = service.evaluate_observation(session, _observation(session, member, **kwargs).id)
            assert not result.eligible
        assert session.scalars(select(RiskEvent)).first() is None
        corrected = _observation(session, member, quality="manually_corrected", source="manual_correction:json")
        assert service.evaluate_observation(session, corrected.id).created_event_count == 1


def test_window_repeats_idempotency_and_cooldown_are_deterministic() -> None:
    factory = _factory()
    with factory() as session:
        member = _member(session)
        rule = _rule(session, window={"lookback_minutes": 30, "minimum_samples": 3, "required_matches": 3, "cooldown_minutes": 30})
        service = RiskEvaluationService()
        start = datetime(2026, 8, 17, 9, 0, tzinfo=TOKYO_TIMEZONE)
        for offset in (0, 10):
            result = service.evaluate_observation(session, _observation(session, member, observed_at=start + timedelta(minutes=offset)).id)
            assert result.created_event_count == 0
        third = _observation(session, member, observed_at=start + timedelta(minutes=20))
        first = service.evaluate_observation(session, third.id)
        again = service.evaluate_observation(session, third.id)
        event = session.scalar(select(RiskEvent).where(RiskEvent.risk_rule_id == rule.id))
        assert first.created_event_count == 1 and again.updated_event_count == 1
        assert event is not None and event.evidence_json["trigger_count"] == 2
        event.status, event.resolved_at = "CLOSED", datetime.now(TOKYO_TIMEZONE)
        fourth = _observation(session, member, observed_at=start + timedelta(minutes=25))
        cooldown = service.evaluate_observation(session, fourth.id)
        assert cooldown.created_event_count == 0
        event.resolved_at = datetime.now(TOKYO_TIMEZONE) - timedelta(minutes=31)
        assert service.evaluate_observation(session, fourth.id).created_event_count == 1


def test_gateway_and_manual_correction_both_use_the_same_observation_entrypoint() -> None:
    factory = _factory()
    with factory() as session:
        member = _member(session)
        _rule(session)
        summary = ingest(session, "json", {"records": [{
            "id": "synthetic-steps", "metric": "steps", "value": 9000, "unit": "count",
            "observed_at": "2026-08-17T09:00:00+09:00",
        }]}, member_id=member.id)
        assert summary.created == 1
        assert session.scalars(select(RiskEvent)).first() is not None

        event = session.scalars(select(RiskEvent)).first()
        assert event is not None
        event.status = "CLOSED"
        job = session.get(IngestionJob, summary.job_id)
        assert job is not None
        raw = RawIngestionRecord(
            job_id=job.id, patient_id=member.id, source_system="json", source_type="file",
            source_record_id="synthetic-correction", payload_json={}, adapter_name="synthetic",
            adapter_version="v1", status="INVALID", normalization_json={"metric_code": "steps", "unit": "count"},
        )
        session.add(raw)
        session.flush()
        corrected = manually_correct_record(session, raw, "9000", "synthetic correction", "manager")
        assert corrected.quality_flag == "manually_corrected"
        assert len(list(session.scalars(select(RiskEvent)))) == 2


def test_manual_observation_api_returns_real_evaluation_summary() -> None:
    factory = _factory()
    with factory() as session:
        member = _member(session)
        _rule(session)
        session.commit()
        member_id = member.id
    client = TestClient(create_app(factory))
    response = client.post("/observations", json={
        "member_id": str(member_id), "metric_code": "steps", "value": "9000", "unit": "count",
        "observed_at": "2026-08-17T09:00:00+09:00", "source": "manual_entry", "quality_flag": "valid",
    })
    assert response.status_code == 201
    assert response.json()["risk_evaluation_summary"]["created_events"] == 1


def test_report_candidate_does_not_trigger_until_human_confirmation_then_uses_risk_entrypoint(tmp_path: Path) -> None:
    factory = _factory()
    with factory() as session:
        member = _member(session)
        _rule(session)
        document = Document(patient_id=member.id, document_type="health_check_report", title="synthetic.txt", storage_reference=str(tmp_path / "synthetic.txt"), source="synthetic", status="PENDING_HUMAN_REVIEW")
        session.add(document)
        session.flush()
        run = ReportExtractionRun(
            document_id=document.id, patient_id=member.id, status="COMPLETED", parser_version="synthetic",
            canonical_registry_version="synthetic", file_hash="a" * 64, file_type="txt", page_count=1,
            has_text_layer=True, is_scanned=False, llm_used=False, metadata_json={},
        )
        session.add(run)
        session.flush()
        candidate = ReportExtractionCandidate(
            extraction_run_id=run.id, document_id=document.id, patient_id=member.id,
            candidate_type="OBSERVATION", canonical_code="steps", raw_name="合成步数", raw_value="9000",
            normalized_value="9000", unit="count", reference_range=None, abnormal_flag=None,
            summary=None, structured_data_json={}, confidence="HIGH", extraction_method="RULE",
            source_page=1, source_section="VITALS", evidence_text="合成步数 9000", status="PENDING_REVIEW",
        )
        session.add(candidate)
        session.flush()
        assert session.scalars(select(RiskEvent)).first() is None
        observation = ReportParsingService().confirm_candidate(session, candidate, "synthetic manager")
        assert observation is not None
        event = session.scalars(select(RiskEvent)).first()
        assert event is not None and event.evidence_json["source"] == "observation_driven"


def test_risk_engine_is_deterministic_and_has_no_local_llm_dependency() -> None:
    source = Path("src/executive_health_ai/services/risk_triage.py").read_text(encoding="utf-8").lower()
    assert "from executive_health_ai.llm" not in source
    assert "local_llm_client" not in source


def test_workbench_has_a_business_facing_source_and_evidence_caption_for_real_events() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "健康数据自动监测" in source
    assert "健康数据自动监测" in source
    assert "_risk_event_evidence_caption(event)" in source
