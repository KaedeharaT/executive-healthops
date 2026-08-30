"""Safety regression tests for reconstructed report text and review-only fragments."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.llm.local_llm_client import LocalLLMHealth
from executive_health_ai.models import Base, Patient
from executive_health_ai.services.report_parsing import (
    ExtractedPage,
    GenericReportParser,
    ReportParsingService,
    ReportSemanticFallback,
    ReportTextReconstructor,
    SentenceCompletenessValidator,
)


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session)()


def test_adjacent_lines_are_reconstructed_before_followup_parsing() -> None:
    pages = ReportTextReconstructor.reconstruct([ExtractedPage(1, "本次体检发现您的癌胚抗原：5.37 ng/ml↑；建议2~3月后复查，若呈进行性增高时,\n请及时到消化内科诊治。")])
    assert "若呈进行性增高时, 请及时到消化内科诊治。" in pages[0].text
    drafts = GenericReportParser().extract(pages)
    followups = [item for item in drafts if item.candidate_type == "FOLLOWUP"]
    assert followups and all(SentenceCompletenessValidator.is_complete(item.evidence_text) for item in followups)


def test_cross_page_sentence_is_reconstructed_with_source_span() -> None:
    pages = ReportTextReconstructor.reconstruct([
        ExtractedPage(4, "建议3个月后复查胸部"),
        ExtractedPage(5, "CT。"),
    ])
    assert pages[0].text == "建议3个月后复查胸部 CT。"
    assert pages[0].page_span == (4, 5)


def test_unrecoverable_fragment_becomes_manual_review_not_followup(tmp_path: Path) -> None:
    service = ReportParsingService(); service.storage_root = tmp_path
    content = "检查建议：建议2~3月后复查，若呈进行性增高时,".encode()
    with _session() as session:
        patient = Patient(external_id="synthetic-incomplete-report", timezone="Asia/Tokyo"); session.add(patient); session.flush()
        document, run, _ = service.upload_and_parse(session, patient.id, "fragment.txt", content, "tester")
        candidates = service.candidates(session, document.id, run.id)
        incomplete = next(item for item in candidates if item.candidate_type == "INCOMPLETE")
        assert incomplete.status == "NEEDS_MANUAL_REVIEW"
        with pytest.raises(ValueError):
            service.confirm_candidate(session, incomplete, "tester")
        with pytest.raises(ValueError):
            service.create_followup_task(session, incomplete, "tester")
    assert not [item for item in candidates if item.candidate_type == "FOLLOWUP"]


def test_one_collapsed_metric_row_creates_one_candidate_per_metric() -> None:
    drafts = GenericReportParser().extract([ExtractedPage(1, "甘油三酯 1.89 mmol/L 总胆固醇 5.86 mmol/L")])
    observed = {(item.canonical_code, item.normalized_value) for item in drafts if item.candidate_type == "OBSERVATION"}
    assert ("triglycerides", "1.89") in observed
    assert ("total_cholesterol", "5.86") in observed
    assert len(observed) == 2


def test_complex_imaging_paragraph_is_split_into_atomic_findings() -> None:
    drafts = GenericReportParser().extract([ExtractedPage(1, "胸部CT检查结论：肺部炎症。双肺多发小结节。小气道功能异常。")])
    summaries = [item.summary for item in drafts if item.candidate_type == "FINDING"]
    assert summaries == ["肺部炎症", "双肺多发小结节", "小气道功能异常"]


class _DepartmentMismatchClient:
    def health_check(self): return LocalLLMHealth(True, True, "local_llm", "local LLM", "http://127.0.0.1:11434")
    def generate_structured(self, **_kwargs):
        return {"exam_name": "腹部彩超", "findings": [], "recommendations": [{"action": "建议胸外科就诊", "department": "胸外科", "interval_text": "", "evidence": "建议泌尿外科就诊。"}]}


def test_department_must_exactly_match_evidence_and_never_be_inferred() -> None:
    result = ReportSemanticFallback(client=_DepartmentMismatchClient()).extract(
        pages=[ExtractedPage(1, "腹部彩超检查结论：右侧肾上腺结节。建议泌尿外科就诊。")], existing=[], document_id=uuid4(),
    )
    assert not [item for item in result.drafts if item.candidate_type == "FOLLOWUP"]
    manual = [item for item in result.drafts if item.candidate_type == "INCOMPLETE"]
    assert manual and manual[0].structured_data["integrity_reason"] == "evidence_mismatch"


def test_local_llm_does_not_receive_or_complete_an_incomplete_section() -> None:
    class Client:
        calls = 0
        def health_check(self): return LocalLLMHealth(True, True, "local_llm", "local LLM", "http://127.0.0.1:11434")
        def generate_structured(self, **_kwargs):
            self.calls += 1
            return {"exam_name": "", "findings": [], "recommendations": []}

    client = Client()
    result = ReportSemanticFallback(client=client).extract(
        pages=[ExtractedPage(1, "胸部CT检查结论：双肺小结节。建议2~3月后复查，若呈进行性增高时,")], existing=[], document_id=uuid4(),
    )
    assert client.calls == 0
    assert any(item.candidate_type == "INCOMPLETE" for item in result.drafts)


def test_review_workspace_keeps_technical_metadata_collapsed_and_groups_manual_queue() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert '_page_header(_source_display_name(document, "体检报告")' in source
    assert "需要医生复核" in source and "健康管理跟进" in source and "需要人工核对内容" in source
    assert 'with st.expander("查看解析详情（高级信息）")' in source
    assert '"指标": _report_candidate_label(item)' in source
    assert '_render_evidence_action(_candidate_evidence_payload' in source
