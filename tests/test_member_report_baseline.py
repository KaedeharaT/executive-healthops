"""Synthetic coverage for member-report to manager-confirmed baseline flow."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.models import (
    Base, Document, HealthAssessment, Observation, Patient,
    ReportExtractionCandidate, ReportExtractionRun,
)
from executive_health_ai.services.longitudinal import HealthAssessmentService, HealthTimelineService
from executive_health_ai.services.operational_worklist import OperationalWorklistService


APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)()


def _prepared_report(session: Session, member: Patient, *, title: str = "合成年度体检") -> tuple[Document, ReportExtractionRun, ReportExtractionCandidate]:
    document = Document(patient_id=member.id, document_type="health_check_report", title=title, storage_reference="synthetic://report", source="member_surface")
    session.add(document); session.flush()
    run = ReportExtractionRun(document_id=document.id, patient_id=member.id, status="COMPLETED", parser_version="synthetic", canonical_registry_version="synthetic", file_hash=str(document.id), file_type="TXT")
    session.add(run); session.flush()
    candidate = ReportExtractionCandidate(
        extraction_run_id=run.id, document_id=document.id, patient_id=member.id,
        candidate_type="OBSERVATION", canonical_code="synthetic_metric", normalized_value="7.2", unit="x",
        confidence="HIGH", extraction_method="RULE", evidence_text="synthetic complete evidence", status="CONFIRMED",
    )
    session.add(candidate); session.flush()
    session.add(Observation(
        patient_id=member.id, observed_at=datetime.now(timezone.utc), metric_code="synthetic_metric",
        value_numeric=Decimal("7.2"), unit="x", source="confirmed_health_check_report",
        source_record_id=str(candidate.id), quality_flag="valid",
    ))
    session.flush()
    return document, run, candidate


def test_confirmed_report_creates_traceable_draft_and_manager_confirmation_adds_timeline_node() -> None:
    session = _session()
    member = Patient(external_id="member-report-baseline", timezone="Asia/Tokyo"); session.add(member); session.flush()
    document, run, confirmed = _prepared_report(session, member)
    pending = ReportExtractionCandidate(
        extraction_run_id=run.id, document_id=document.id, patient_id=member.id,
        candidate_type="INCOMPLETE", confidence="LOW", extraction_method="RULE", evidence_text="truncated,", status="NEEDS_MANUAL_REVIEW",
    )
    session.add(pending); session.flush()
    service = HealthAssessmentService()

    draft = service.create_draft_from_report(session, member.id, document.id, created_by="health_manager")
    assert draft.status == "DRAFT"
    assert str(confirmed.id) in draft.source_references_json["source_candidate_ids"]
    assert str(pending.id) not in draft.source_references_json["source_candidate_ids"]
    assert draft.baseline_json["basic_information"]["age"] == "待补充"
    assert draft.baseline_json["current_medications"]["label"] == "待补充"
    assert draft.baseline_json["procedures_or_hospitalizations"]["label"] == "待补充"

    service.update_member_reported(session, draft.id, {"既往史": "成员自述合成既往史", "当前用药": "成员自述合成用药"})
    assert draft.baseline_json["member_reported"]["source"] == "MEMBER_REPORTED"
    confirmed_baseline = service.confirm(session, draft.id, "health_manager")
    assert confirmed_baseline.status == "CONFIRMED" and confirmed_baseline.version == 1
    events = HealthTimelineService().get_timeline(session, member.id)
    assessment = next(item for item in events if item.event_type == "assessment")
    assert assessment.expandable_details["key_metrics"][0]["metric"] == "synthetic_metric"


def test_unconfirmed_or_incomplete_report_cannot_create_baseline_draft() -> None:
    session = _session()
    member = Patient(external_id="unconfirmed-report", timezone="Asia/Tokyo"); session.add(member); session.flush()
    document = Document(patient_id=member.id, document_type="health_check_report", title="未确认报告", storage_reference="synthetic://unconfirmed", source="member_surface")
    session.add(document); session.flush()
    run = ReportExtractionRun(document_id=document.id, patient_id=member.id, status="COMPLETED", parser_version="synthetic", canonical_registry_version="synthetic", file_hash="unconfirmed", file_type="TXT")
    session.add(run); session.flush()
    session.add(ReportExtractionCandidate(extraction_run_id=run.id, document_id=document.id, patient_id=member.id, candidate_type="INCOMPLETE", confidence="LOW", extraction_method="RULE", evidence_text="fragment,", status="NEEDS_MANUAL_REVIEW")); session.flush()
    with pytest.raises(ValueError, match="人工确认"):
        HealthAssessmentService().create_draft_from_report(session, member.id, document.id, created_by="health_manager")
    assert session.query(HealthAssessment).count() == 0


def test_second_report_never_overwrites_confirmed_baseline_and_report_task_is_deduplicated() -> None:
    session = _session()
    member = Patient(external_id="second-report", timezone="Asia/Tokyo"); session.add(member); session.flush()
    document, _, _ = _prepared_report(session, member)
    service = HealthAssessmentService()
    draft = service.create_draft_from_report(session, member.id, document.id, created_by="health_manager")
    service.confirm(session, draft.id, "health_manager")
    newer, _, _ = _prepared_report(session, member, title="合成下一年度体检")
    with pytest.raises(ValueError, match="不会覆盖"):
        service.create_draft_from_report(session, member.id, newer.id, created_by="health_manager")
    first_task = service.ensure_report_review_task(session, member.id, newer)
    assert service.ensure_report_review_task(session, member.id, newer).id == first_task.id
    item = next(item for item in OperationalWorklistService().list_items(session, datetime.now(timezone.utc)) if item.source_type == "report_review")
    assert item.member_id == member.id and item.document_id == newer.id and item.next_action == "审核报告并进入长期比较"


def test_member_surface_uses_existing_intake_but_has_no_confirmation_controls() -> None:
    source = APP.read_text(encoding="utf-8")
    member_upload = source.split("def render_member_report_upload", 1)[1].split("def _render_member_baseline_center", 1)[0]
    client_baseline = source.split("def _render_member_baseline_center", 1)[1].split("def _render_member_center_baseline_entry", 1)[0]
    assert "ReportParsingService().upload_and_parse" in member_upload
    assert "patient.id" in member_upload and "ensure_report_review_task" in member_upload
    assert "confirm_candidate" not in member_upload and "confirm(" not in member_upload
    assert "update_member_reported" in client_baseline and "确认健康基线" not in client_baseline


def test_member_health_checkup_exposes_the_existing_upload_flow_without_new_confirmation_controls() -> None:
    source = APP.read_text(encoding="utf-8")
    archive = source.split("def _render_client_checkup_page", 1)[1].split("def _render_client_medical_archive", 1)[0]
    labels = source.split("def _report_upload_label", 1)[1].split("def _report_upload_state", 1)[0]
    assert "上传体检报告" in labels and "上传新体检报告" in labels
    assert "render_member_report_upload(patient)" in archive
    assert "confirm_candidate" not in archive and "确认健康基线" not in archive
