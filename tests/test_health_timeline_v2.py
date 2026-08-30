"""Regression coverage for the aggregated longitudinal health story."""
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.blood_pressure import TOKYO_TIMEZONE
from executive_health_ai.models import Base, Document, Observation, Patient, ReportExtractionCandidate, ReportExtractionRun
from executive_health_ai.services.longitudinal import MonthlyTimelineSummaryService, HealthTimelineService


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)()


def _member(session: Session) -> Patient:
    member = Patient(external_id="synthetic-timeline-v2", timezone="Asia/Tokyo")
    session.add(member)
    session.flush()
    return member


def test_one_report_has_one_grouped_timeline_node_and_findings_stay_in_detail() -> None:
    session = _session()
    member = _member(session)
    document = Document(patient_id=member.id, document_type="report", title="2026年度体检", storage_reference="synthetic://report", source="synthetic")
    session.add(document)
    session.flush()
    first = ReportExtractionRun(document_id=document.id, patient_id=member.id, status="COMPLETED", parser_version="v1", canonical_registry_version="v1", file_hash="same", file_type="TXT", created_at=datetime(2026, 8, 1, tzinfo=TOKYO_TIMEZONE))
    second = ReportExtractionRun(document_id=document.id, patient_id=member.id, status="COMPLETED", parser_version="v2", canonical_registry_version="v2", file_hash="same", file_type="TXT", created_at=datetime(2026, 8, 2, tzinfo=TOKYO_TIMEZONE))
    session.add_all((first, second))
    session.flush()
    for title in ("甲状腺结节", "肺部炎症", "肺结节"):
        session.add(ReportExtractionCandidate(extraction_run_id=second.id, document_id=document.id, patient_id=member.id, candidate_type="FINDING", summary=title, confidence="HIGH", extraction_method="RULE", evidence_text="synthetic", status="CONFIRMED"))
    session.flush()

    events = HealthTimelineService().get_timeline(session, member.id)
    report_events = [item for item in events if item.event_type == "report"]
    assert len(report_events) == 1
    assert report_events[0].group_key == f"REPORT:{document.id}"
    assert report_events[0].expandable_details["findings"] == 3
    assert not any(item.title in {"甲状腺结节", "肺部炎症", "肺结节"} for item in events)


def test_monthly_hardware_data_is_one_bounded_summary_node() -> None:
    session = _session()
    member = _member(session)
    start = datetime(2026, 7, 1, 8, tzinfo=TOKYO_TIMEZONE)
    for offset in range(31):
        at = start + timedelta(days=offset)
        session.add_all((
            Observation(patient_id=member.id, observed_at=at, metric_code="steps", value_numeric=Decimal("8000"), unit="steps", source="synthetic", quality_flag="valid"),
            Observation(patient_id=member.id, observed_at=at, metric_code="sleep_duration", value_numeric=Decimal("420"), unit="min", source="synthetic", quality_flag="valid"),
        ))
    session.flush()

    events = MonthlyTimelineSummaryService().monthly_summaries(session, member.id, start=start - timedelta(days=1), end=start + timedelta(days=31))
    assert len(events) == 1
    event = events[0]
    assert event.event_type == "health_data_summary"
    assert event.group_key == f"HEALTH_DATA_SUMMARY:{member.id}:2026-07"
    assert {item["metric"] for item in event.expandable_details["metrics"]} == {"steps", "sleep_duration"}
    assert event.actions == ("view_health_data",)


def test_timeline_only_reads_major_entities_and_never_promotes_raw_observations() -> None:
    session = _session()
    member = _member(session)
    session.add(Observation(patient_id=member.id, observed_at=datetime(2026, 8, 1, tzinfo=TOKYO_TIMEZONE), metric_code="heart_rate", value_numeric=Decimal("62"), unit="bpm", source="synthetic", quality_flag="valid"))
    session.flush()

    events = HealthTimelineService().get_timeline(session, member.id)
    assert all(item.event_type != "observation" for item in events)
    assert not any(item.title == "heart_rate" for item in events)
