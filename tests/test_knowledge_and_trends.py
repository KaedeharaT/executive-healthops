"""Knowledge-governance and lightweight trend-display regressions."""

from datetime import datetime, timedelta
from decimal import Decimal
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.blood_pressure import TOKYO_TIMEZONE
from executive_health_ai.models import Base, KnowledgeDocument, Observation, Patient
from executive_health_ai.services.health_data_summary import HealthDataSummaryService
from executive_health_ai.services.knowledge import KnowledgeService
from streamlit_app import _downsample_for_chart, _long_metric_summary, _observation_text


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session)()


def test_knowledge_document_manual_and_file_registration_are_governed() -> None:
    with _session() as session:
        service = KnowledgeService()
        draft = service.create_document(
            session, title="90天代谢健康管理模板（演示）", category="MANAGEMENT_PROGRAM",
            source_type="人工整理", source_name="合成演示资料", content_text="演示内容", tags=["代谢"], review_status="DRAFT",
        )
        uploaded = service.create_document(
            session, title="苹果健康数据接入说明", category="DATA_DEVICE", source_type="设备厂商资料",
            source_name="合成演示资料", file_reference="knowledge_uploads/demo.txt", processing_status="TEXT_EXTRACTED",
            review_status="PENDING_REVIEW",
        )
        session.commit()

        assert draft.review_status == "DRAFT"
        assert uploaded.file_reference == "knowledge_uploads/demo.txt"
        assert [item.title for item in service.search_documents(session, "苹果健康")] == [uploaded.title]
        assert service.search_documents(session, "代谢") == [draft]
        assert service.approved_documents_for_ai(session) == []

        service.approve_document(session, draft, "审核医生")
        assert service.approved_documents_for_ai(session) == [draft]
        service.archive_document(session, uploaded)
        assert session.get(KnowledgeDocument, uploaded.id).is_active is False


def test_health_data_helpers_preserve_missing_data_and_downsample_cgm() -> None:
    assert _observation_text(None) == "暂无数据"
    cgm = pd.DataFrame({"记录时间": pd.date_range("2026-08-01", periods=4032, freq="5min"), "数值": range(4032)})
    assert len(_downsample_for_chart(cgm)) <= 321


def test_cgm_trend_query_is_bounded_to_the_selected_window() -> None:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session)
    now = datetime.now(TOKYO_TIMEZONE)
    with factory() as session:
        patient = Patient(external_id="synthetic-cgm", timezone="Asia/Tokyo")
        session.add(patient)
        session.flush()
        for offset in range(24 * 12 * 10):
            observed_at = now - timedelta(minutes=5 * offset)
            session.add(Observation(
                patient_id=patient.id, observed_at=observed_at, metric_code="glucose",
                value_numeric=Decimal("5.6"), unit="mmol/L", source="mock_cgm", quality_flag="valid",
            ))
        session.add(Observation(
            patient_id=patient.id, observed_at=now - timedelta(minutes=10), metric_code="glucose",
            value_numeric=Decimal("999"), unit="mmol/L", source="mock_cgm", quality_flag="invalid",
        ))
        session.commit()
        patient_id = patient.id
    with factory() as session:
        service = HealthDataSummaryService()
        day_records = service.get_cgm_series(session, patient_id, hours=24, limit=500)
        week_records = service.get_cgm_series(session, patient_id, hours=24 * 7, limit=2_000)
    assert day_records and week_records
    assert len(day_records) <= 500
    assert len(week_records) <= 2_000
    assert all(item.observed_at >= now - timedelta(days=1, minutes=1) for item in day_records)
    assert all(item.quality_flag.lower() != "invalid" for item in day_records)
    assert all(float(item.value_numeric) != 999 for item in day_records)


def test_long_term_summary_uses_observable_values_without_medical_conclusion() -> None:
    now = datetime.now(TOKYO_TIMEZONE)
    records = [
        Observation(patient_id=None, observed_at=now - timedelta(days=30), metric_code="weight", value_numeric=Decimal("86"), unit="kg", source="synthetic", quality_flag="valid"),
        Observation(patient_id=None, observed_at=now, metric_code="weight", value_numeric=Decimal("82.4"), unit="kg", source="synthetic", quality_flag="valid"),
    ]
    summary = _long_metric_summary(records, "weight")
    assert summary == ("86 → 82.4 kg", "↓ 3.6 kg")
