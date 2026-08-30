"""Regression coverage for the Chinese, source-bound evidence presentation."""

from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from streamlit.testing.v1 import AppTest

import streamlit_app as app
from executive_health_ai.models import Base, Document, Patient, ReportExtractionCandidate, ReportExtractionRun
from executive_health_ai.services.longitudinal import ReportComparisonService


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)()


def _candidate(*, patient_id, document_id, run_id, **kwargs):
    return ReportExtractionCandidate(
        patient_id=patient_id, document_id=document_id, extraction_run_id=run_id,
        candidate_type="OBSERVATION", canonical_code="ldl_c", raw_name="LDL-C",
        confidence="HIGH", extraction_method="TABLE", evidence_text="LDL-C | 4.15 ↑ | 0–3.40",
        status="CONFIRMED", **kwargs,
    )


def test_all_business_evidence_actions_use_the_chinese_label() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert 'st.button("查看依据"' in source
    assert "查看原文依据" not in source
    assert "查看残缺原文" not in source
    assert "View Evidence" not in source


def test_source_display_name_humanizes_and_marks_synthetic_filename() -> None:
    assert app._source_display_name(fallback="synthetic_progress_ui.txt") == "演示资料 · 健康进度记录"
    assert app._source_display_name(fallback="2026年度体检报告.pdf") == "2026年度体检报告.pdf"


def test_candidate_evidence_formats_pdf_table_and_excel_location() -> None:
    candidate = SimpleNamespace(
        extraction_method="TABLE", source_page=8, source_section="生化检查",
        structured_data_json={"sheet_name": "血糖", "cell_range": "B18:D18"},
        evidence_text="LDL-C | 4.15 ↑ | 0–3.40", summary="LDL-C 结果已整理",
        status="CONFIRMED", candidate_type="OBSERVATION", canonical_code="ldl_c", raw_name="LDL-C",
    )
    payload = app._candidate_evidence_payload(candidate, None)
    assert payload["evidence_type"] == "TABLE"
    assert "第 8 页" not in str(payload["location"])
    assert "Sheet：血糖" in str(payload["location"])
    assert "位置：B18:D18" in str(payload["location"])
    assert "LDL-C | 4.15" in str(payload["raw_evidence"])


def test_image_ocr_without_box_is_honestly_marked_as_unlocated() -> None:
    candidate = SimpleNamespace(
        extraction_method="OCR", source_page=2, source_section="胸部CT", structured_data_json={},
        evidence_text="左肺下叶背段少许炎症", summary="胸部CT结果", status="CONFIRMED",
        candidate_type="FINDING", canonical_code=None, raw_name=None,
    )
    payload = app._candidate_evidence_payload(candidate, None)
    assert payload["ocr"] is True and payload["has_bounding_box"] is False


def test_image_region_payload_keeps_saved_location_without_claiming_diagnosis() -> None:
    candidate = SimpleNamespace(
        extraction_method="OCR", source_page=12, source_section="IMAGING",
        structured_data_json={"evidence_type": "IMAGE_REGION", "bounding_box": [10, 20, 100, 80]},
        evidence_text="左肺下叶背段少许炎症", summary="左肺下叶背段少许炎症",
        status="PENDING_REVIEW", candidate_type="FINDING", canonical_code=None, raw_name=None,
    )
    payload = app._candidate_evidence_payload(candidate, None)
    assert payload["evidence_type"] == "IMAGE_REGION"
    assert payload["has_bounding_box"] is True
    assert "第 12 页" in str(payload["location"])


def test_missing_and_mismatch_evidence_have_human_readable_states() -> None:
    missing = SimpleNamespace(evidence_text="", structured_data_json={}, status="PENDING_REVIEW", candidate_type="OBSERVATION")
    mismatch = SimpleNamespace(evidence_text="原文", structured_data_json={"integrity_reason": "evidence_mismatch"}, status="PENDING_REVIEW", candidate_type="OBSERVATION")
    assert app._evidence_status_label(app._candidate_evidence_status(missing)) == "暂无足够依据"
    assert app._evidence_status_label(app._candidate_evidence_status(mismatch)) == "依据与结果不一致"


def test_document_and_candidate_evidence_are_member_scoped() -> None:
    session = _session()
    first, second = Patient(external_id="evidence-a", timezone="Asia/Tokyo"), Patient(external_id="evidence-b", timezone="Asia/Tokyo")
    session.add_all([first, second]); session.flush()
    document = Document(patient_id=first.id, document_type="report", title="报告.pdf", storage_reference="synthetic://report", source="synthetic")
    session.add(document); session.flush()
    run = ReportExtractionRun(document_id=document.id, patient_id=first.id, status="COMPLETED", parser_version="test", canonical_registry_version="test", file_hash="one", file_type="PDF")
    session.add(run); session.flush()
    candidate = _candidate(patient_id=first.id, document_id=document.id, run_id=run.id)
    session.add(candidate); session.flush()
    assert app._document_for_member_evidence(session, first.id, document.id) is document
    assert app._document_for_member_evidence(session, second.id, document.id) is None
    assert app._candidate_for_member_evidence(session, second.id, candidate.id) is None


def test_report_comparison_keeps_old_and_new_evidence_separate() -> None:
    session = _session(); member = Patient(external_id="comparison-evidence", timezone="Asia/Tokyo"); session.add(member); session.flush()
    old = Document(patient_id=member.id, document_type="report", title="2025报告.pdf", storage_reference="synthetic://old", source="synthetic")
    new = Document(patient_id=member.id, document_type="report", title="2026报告.pdf", storage_reference="synthetic://new", source="synthetic")
    session.add_all([old, new]); session.flush()
    old_run = ReportExtractionRun(document_id=old.id, patient_id=member.id, status="COMPLETED", parser_version="test", canonical_registry_version="test", file_hash="old", file_type="PDF")
    new_run = ReportExtractionRun(document_id=new.id, patient_id=member.id, status="COMPLETED", parser_version="test", canonical_registry_version="test", file_hash="new", file_type="PDF")
    session.add_all([old_run, new_run]); session.flush()
    old_candidate = _candidate(patient_id=member.id, document_id=old.id, run_id=old_run.id, normalized_value="3.8")
    new_candidate = _candidate(patient_id=member.id, document_id=new.id, run_id=new_run.id, normalized_value="4.1")
    session.add_all([old_candidate, new_candidate]); session.flush()
    change = ReportComparisonService().compare(session, member.id, old.id, new.id)["metric_changes"][0]
    assert change["previous_candidate_id"] == str(old_candidate.id)
    assert change["current_candidate_id"] == str(new_candidate.id)


def test_evidence_panel_defers_full_file_read_until_action_is_opened() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    action = source.split("def _render_evidence_action", 1)[1].split("@contextmanager", 1)[0]
    assert "path.read_bytes" not in action
    panel = source.split("def render_evidence_panel", 1)[1].split("def _render_evidence_action", 1)[0]
    assert "path.read_bytes" in panel


def test_report_summary_and_type_aware_evidence_are_business_facing() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    review = source.split("def render_report_review", 1)[1].split("def _render_baseline_draft_action", 1)[0]
    for title in ("报告整理摘要", "影像与检查", "关键健康指标", "主要异常与健康问题", "建议复查", "需要人工核对内容"):
        assert title in review
    panel = source.split("def render_evidence_panel", 1)[1].split("def _render_evidence_action", 1)[0]
    assert 'evidence_type in {"OBSERVATION", "DEVICE_DATA", "RISK"}' in panel
    assert "**数据来源**" in panel and "**规则依据**" in panel


def test_baseline_and_timeline_keep_candidate_level_report_evidence() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "source_candidate_id" in Path("src/executive_health_ai/services/longitudinal.py").read_text(encoding="utf-8")
    assert "_render_snapshot_item_evidence" in source
    timeline = source.split("def render_longitudinal_timeline", 1)[1].split("def _client_device_status", 1)[0]
    assert "timeline-report-finding" in timeline


def test_client_evidence_panel_hides_technical_fields() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    panel = source.split("def render_evidence_panel", 1)[1].split("def _render_evidence_action", 1)[0]
    assert "if not client_view:" in panel
    assert "高级信息" in panel


def test_member_overview_timeline_opens_evidence_from_normal_navigation() -> None:
    app_test = AppTest.from_file(Path(__file__).resolve().parents[1] / "streamlit_app.py")
    app_test.run(timeout=30)
    next(item for item in app_test.radio if item.label == "工作区").set_value("成员")
    app_test.run(timeout=30)
    next(item for item in app_test.button if item.label == "查看成员").click()
    app_test.run(timeout=30)
    next(item for item in app_test.button if item.label == "查看完整健康历程").click()
    app_test.run(timeout=30)
    next(item for item in app_test.radio if item.label == "事件筛选").set_value("体检")
    app_test.run(timeout=30)
    next(item for item in app_test.button if item.label == "查看依据").click()
    app_test.run(timeout=30)
    assert not app_test.exception
    visible = "\n".join(
        str(item.value)
        for collection in (app_test.button, app_test.markdown, app_test.subheader, app_test.caption, app_test.text)
        for item in collection
    )
    assert "来源文件" in visible and "确认状态" in visible
