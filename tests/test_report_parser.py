"""Synthetic-only tests for universal report parsing and human confirmation."""

from __future__ import annotations

from pathlib import Path
from io import BytesIO
from uuid import UUID

import pytest
from pypdf import PdfWriter
from openpyxl import Workbook
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.api import create_app
from executive_health_ai.integrations.codes import canonical_code
from executive_health_ai.llm.local_llm_client import LocalLLMHealth, LocalLLMUnavailable
from executive_health_ai.models import Base, HealthProblem, Observation, Patient, ReportExtractionCandidate, Task
from executive_health_ai.services.report_parsing import ALLOW_EXTERNAL_PHI_LLM, DocumentPreflightService, ReportParsingService, ReportSemanticFallback

FIXTURES = Path(__file__).parent / "fixtures"


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session)()


def _report(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_generic_parser_maps_multi_hospital_aliases_and_preserves_evidence(tmp_path: Path) -> None:
    service = ReportParsingService(); service.storage_root = tmp_path
    with _session() as session:
        patient = Patient(external_id="synthetic-report-a", timezone="Asia/Tokyo"); session.add(patient); session.flush()
        document, run, duplicate = service.upload_and_parse(session, patient.id, "synthetic_lab_report.txt", _report("synthetic_lab_report.txt"), "tester")
        session.commit()
        candidates = service.candidates(session, document.id)
        run_status = run.status
    assert not duplicate and run_status == "COMPLETED"
    assert any(item.canonical_code == "ldl_c" and item.source_page == 1 and "LDL-C" in item.evidence_text for item in candidates)
    assert any(item.canonical_code is None and item.raw_name == "未知合成指标" for item in candidates)
    assert any(item.candidate_type == "FINDING" for item in candidates)
    assert any(item.candidate_type == "FOLLOWUP" for item in candidates)
    assert canonical_code("低密度脂蛋白").canonical_code == "ldl_c"
    assert canonical_code("LDL-C").canonical_code == "ldl_c"
    assert canonical_code("低密度脂蛋白胆固醇").canonical_code == "ldl_c"


def test_xlsx_metric_candidate_preserves_sheet_header_and_cell_range(tmp_path: Path) -> None:
    workbook = Workbook(); worksheet = workbook.active; worksheet.title = "生化"
    worksheet.append(["指标", "结果", "参考范围"])
    worksheet.append(["LDL-C", "4.15", "0–3.40"])
    buffer = BytesIO(); workbook.save(buffer)
    service = ReportParsingService(); service.storage_root = tmp_path
    with _session() as session:
        patient = Patient(external_id="synthetic-xlsx-evidence", timezone="Asia/Tokyo"); session.add(patient); session.flush()
        document, _, _ = service.upload_and_parse(session, patient.id, "体检化验.xlsx", buffer.getvalue(), "tester")
        candidates = service.candidates(session, document.id)
    candidate = next(item for item in candidates if item.canonical_code == "ldl_c")
    assert candidate.extraction_method == "TABLE"
    assert candidate.structured_data_json["sheet_name"] == "生化"
    assert candidate.structured_data_json["cell_range"] == "A2:C2"
    assert candidate.structured_data_json["table_header"] == "指标\t结果\t参考范围"
    assert candidate.structured_data_json["table_row"] == "LDL-C\t4.15\t0–3.40"


def test_pdf_style_tabular_metric_preserves_only_its_header_and_row(tmp_path: Path) -> None:
    report = "生化检查\n指标\t结果\t参考范围\nLDL-C\t4.15\t0–3.40\n甘油三酯\t1.89\t0–1.70\n".encode("utf-8")
    service = ReportParsingService(); service.storage_root = tmp_path
    with _session() as session:
        patient = Patient(external_id="synthetic-table-evidence", timezone="Asia/Tokyo"); session.add(patient); session.flush()
        document, _, _ = service.upload_and_parse(session, patient.id, "2026体检报告.txt", report, "tester")
        candidates = service.candidates(session, document.id)
    ldl = next(item for item in candidates if item.canonical_code == "ldl_c")
    triglycerides = next(item for item in candidates if item.canonical_code == "triglycerides")
    assert ldl.structured_data_json["table_header"] == "指标\t结果\t参考范围"
    assert ldl.structured_data_json["table_row"] == "LDL-C\t4.15\t0–3.40"
    assert triglycerides.structured_data_json["table_row"] == "甘油三酯\t1.89\t0–1.70"


def test_duplicate_document_and_scanned_pdf_are_safe(tmp_path: Path) -> None:
    service = ReportParsingService(); service.storage_root = tmp_path
    with _session() as session:
        patient = Patient(external_id="synthetic-report-b", timezone="Asia/Tokyo"); session.add(patient); session.flush()
        document, run, duplicate = service.upload_and_parse(session, patient.id, "a.txt", _report("synthetic_unknown_hospital_report.txt"), "tester")
        _, second_run, second_duplicate = service.upload_and_parse(session, patient.id, "renamed.txt", _report("synthetic_unknown_hospital_report.txt"), "tester")
        writer = PdfWriter(); writer.add_blank_page(width=200, height=200); binary = __import__("io").BytesIO(); writer.write(binary)
        _, scanned_run, _ = service.upload_and_parse(session, patient.id, "synthetic_scan.pdf", binary.getvalue(), "tester")
        session.commit()
        same_document = second_run.document_id == run.document_id
        distinct_run = second_run.id != run.id
        stored_files = list(tmp_path.iterdir())
        scanned_status, scanned_flag = scanned_run.status, scanned_run.is_scanned
    assert not duplicate and second_duplicate and same_document and distinct_run and len(stored_files) == 2
    assert scanned_status == "NEEDS_OCR" and scanned_flag is True


def test_report_upload_rejects_empty_unsupported_and_path_traversal_names_before_storage(tmp_path: Path) -> None:
    service = ReportParsingService(); service.storage_root = tmp_path
    with _session() as session:
        patient = Patient(external_id="synthetic-upload-safety", timezone="Asia/Tokyo"); session.add(patient); session.flush()
        with pytest.raises(ValueError, match="为空"):
            service.upload_and_parse(session, patient.id, "empty.txt", b"", "tester")
        with pytest.raises(ValueError, match="仅支持"):
            service.upload_and_parse(session, patient.id, "report.exe", b"not a report", "tester")
        document, _, _ = service.upload_and_parse(session, patient.id, "../../safe.txt", _report("synthetic_lab_report.txt"), "tester")
    assert document.title == "safe.txt"
    assert list(tmp_path.iterdir()) and all(".." not in item.name for item in tmp_path.iterdir())


def test_unknown_hospital_uses_generic_parser_and_hospital_b_keeps_same_canonical_code(tmp_path: Path) -> None:
    service = ReportParsingService(); service.storage_root = tmp_path
    with _session() as session:
        patient = Patient(external_id="synthetic-report-multi", timezone="Asia/Tokyo"); session.add(patient); session.flush()
        b_document, _, _ = service.upload_and_parse(session, patient.id, "hospital-b.txt", _report("synthetic_hospital_b_report.txt"), "tester")
        unknown_document, unknown_run, _ = service.upload_and_parse(session, patient.id, "unknown.txt", _report("synthetic_unknown_hospital_report.txt"), "tester")
        session.flush()
        b_codes = {item.canonical_code for item in service.candidates(session, b_document.id)}
        unknown_codes = {item.canonical_code for item in service.candidates(session, unknown_document.id)}
    assert unknown_run.status == "COMPLETED"
    assert "ldl_c" in b_codes and "ldl_c" in unknown_codes


def test_candidates_require_human_confirmation_before_observation_and_workflows(tmp_path: Path) -> None:
    service = ReportParsingService(); service.storage_root = tmp_path
    with _session() as session:
        patient = Patient(external_id="synthetic-report-c", timezone="Asia/Tokyo"); session.add(patient); session.flush()
        document, _, _ = service.upload_and_parse(session, patient.id, "a.txt", _report("synthetic_lab_report.txt"), "tester")
        session.flush()
        candidates = service.candidates(session, document.id)
        ldl = next(item for item in candidates if item.canonical_code == "ldl_c")
        finding = next(item for item in candidates if item.candidate_type == "FINDING")
        followup = next(item for item in candidates if item.candidate_type == "FOLLOWUP")
        assert session.scalar(select(Observation).where(Observation.patient_id == patient.id)) is None
        observation = service.confirm_candidate(session, ldl, "manager")
        assert observation is not None and observation.source_record_id == str(ldl.id)
        service.action_finding(session, finding, "manager", "RECORD")
        assert session.scalar(select(HealthProblem).where(HealthProblem.patient_id == patient.id)) is None
        service.action_finding(session, finding, "manager", "MANAGE") if finding.status == "PENDING_REVIEW" else None
        # A fresh finding demonstrates explicit creation rather than parser automation.
        extra = ReportExtractionCandidate(extraction_run_id=candidates[0].extraction_run_id, document_id=document.id, patient_id=patient.id, candidate_type="FINDING", summary="合成影像结论", structured_data_json={}, confidence="HIGH", extraction_method="MANUAL", source_page=1, evidence_text="合成证据", status="PENDING_REVIEW")
        session.add(extra); session.flush(); problem = service.action_finding(session, extra, "manager", "MANAGE")
        task = service.create_followup_task(session, followup, "manager")
        task_source = task.source
        session.commit()
    assert problem is not None and task_source.startswith("confirmed_report_followup:")


def test_external_phi_llm_is_disabled_by_default() -> None:
    assert ALLOW_EXTERNAL_PHI_LLM is False


class _AuditFallbackClient:
    def health_check(self): return LocalLLMHealth(True, True, "local_llm", "local LLM", "http://127.0.0.1:11434")
    def generate_structured(self, **_kwargs):
        return {"exam_name": "胸部CT", "findings": [{"summary": "双肺小结节", "body_system": "肺", "reported_change": "小结节", "reported_severity": "", "evidence": "双肺可见多个小结节"}], "recommendations": [{"action": "复查胸部CT", "department": "", "interval_text": "约3个月后", "evidence": "建议约3个月后复查胸部CT"}]}


def test_complex_narrative_records_llm_audit_and_source_without_auto_confirmation(tmp_path: Path) -> None:
    service = ReportParsingService(semantic_fallback=ReportSemanticFallback(client=_AuditFallbackClient())); service.storage_root = tmp_path
    content = "胸部CT检查结论：左肺下叶见少许条索影。双肺可见多个小结节。建议约3个月后复查胸部CT。".encode()
    with _session() as session:
        patient = Patient(external_id="synthetic-report-audit", timezone="Asia/Tokyo"); session.add(patient); session.flush()
        document, run, _ = service.upload_and_parse(session, patient.id, "synthetic_ct.txt", content, "tester")
        session.flush()
        candidates = service.candidates(session, document.id)
        assert session.scalar(select(Observation).where(Observation.patient_id == patient.id)) is None
    assert run.llm_status == "USED" and run.llm_call_count == run.llm_success_count == 1
    assert run.llm_total_duration_ms >= 0 and run.llm_processed_sections == ["胸部CT"]
    assert any(item.extraction_method == "LLM" and item.evidence_text for item in candidates)


class _MixedAuditFallbackClient:
    def __init__(self) -> None: self.calls = 0
    def health_check(self): return LocalLLMHealth(True, True, "local_llm", "local LLM", "http://127.0.0.1:11434")
    def generate_structured(self, *, user_prompt: str, **_kwargs):
        self.calls += 1
        if "腹部彩超" in user_prompt:
            return {"exam_name": "腹部彩超", "findings": [{"summary": "肝脏回声增粗", "evidence": "肝脏回声增粗"}], "recommendations": []}
        if "肺功能" in user_prompt:
            return {"exam_name": "肺功能", "findings": [{"summary": "小气道功能障碍", "evidence": "小气道功能障碍"}], "recommendations": []}
        if "健康建议" in user_prompt:
            return {"exam_name": "健康建议", "findings": [], "recommendations": [{"action": "复查胸部CT", "evidence": "建议约3个月后复查胸部CT"}]}
        return {"exam_name": "胸部CT", "findings": [{"summary": "双肺多发小结节", "evidence": "双肺可见多个小结节"}], "recommendations": []}


def test_mixed_report_persists_rule_and_local_llm_candidates_with_four_section_calls(tmp_path: Path) -> None:
    client = _MixedAuditFallbackClient()
    service = ReportParsingService(semantic_fallback=ReportSemanticFallback(client=client)); service.storage_root = tmp_path
    content = "\n".join((
        "HbA1c  6.3 %",
        "LDL-C  4.15 mmol/L",
        "胸部CT检查结论：左肺下叶见少许条索影。双肺可见多个小结节。建议结合既往检查持续观察。",
        "腹部彩超检查结论：肝脏回声增粗。胆囊壁欠光滑。建议结合临床进一步评估。",
        "肺功能检查结论：小气道功能障碍。其余指标基本正常。建议结合呼吸专科意见。",
        "健康建议：建议约3个月后复查胸部CT。请根据专科意见安排后续检查。",
    )).encode()
    with _session() as session:
        patient = Patient(external_id="synthetic-mixed-local_llm", timezone="Asia/Tokyo"); session.add(patient); session.flush()
        document, run, _ = service.upload_and_parse(session, patient.id, "synthetic_mixed.txt", content, "tester")
        session.flush()
        candidates = service.candidates(session, document.id)
        run_count = len(service.runs(session, document.id))
    assert run.llm_status == "USED" and run.llm_call_count == run.llm_success_count == client.calls == 4
    assert run.rule_candidate_count >= 2 and run.llm_candidate_count >= 2
    assert run_count == 1 and all(item.status == "PENDING_REVIEW" for item in candidates)
    assert any(item.canonical_code == "hba1c" and item.extraction_method in {"RULE", "TABLE"} for item in candidates)
    assert any(item.canonical_code == "ldl_c" and item.extraction_method in {"RULE", "TABLE"} for item in candidates)
    assert any(item.extraction_method == "LLM" and item.candidate_type == "FINDING" for item in candidates)
    assert any(item.extraction_method == "LLM" and item.candidate_type == "FOLLOWUP" for item in candidates)


def test_parse_and_reparse_emit_one_complete_live_progress_lifecycle(tmp_path: Path) -> None:
    client = _MixedAuditFallbackClient()
    service = ReportParsingService(semantic_fallback=ReportSemanticFallback(client=client)); service.storage_root = tmp_path
    content = "\n".join((
        "HbA1c  6.3 %", "LDL-C  4.15 mmol/L",
        "胸部CT检查结论：左肺下叶见少许条索影。双肺可见多个小结节。建议结合既往检查持续观察。",
        "腹部彩超检查结论：肝脏回声增粗。胆囊壁欠光滑。建议结合临床进一步评估。",
        "肺功能检查结论：小气道功能障碍。其余指标基本正常。建议结合呼吸专科意见。",
        "健康建议：建议约3个月后复查胸部CT。请根据专科意见安排后续检查。",
    )).encode()
    first_events, second_events = [], []
    with _session() as session:
        patient = Patient(external_id="synthetic-live-progress", timezone="Asia/Tokyo"); session.add(patient); session.flush()
        document, first_run, _ = service.upload_and_parse(session, patient.id, "progress.txt", content, "tester", progress_callback=first_events.append)
        second_run = service.reparse_document(session, document.id, "tester", progress_callback=second_events.append)
        session.flush()
        run_count = len(service.runs(session, document.id))

    for events in (first_events, second_events):
        stages = [event.stage for event in events]
        assert stages[:2] == ["READING_REPORT", "PREFLIGHT_COMPLETED"]
        assert "RULE_PARSE_STARTED" in stages and "RULE_PARSE_COMPLETED" in stages
        llm_start = next(event for event in events if event.stage == "LLM_STARTED")
        starts = [event for event in events if event.stage == "LLM_SECTION_STARTED"]
        completed = [event for event in events if event.stage == "LLM_SECTION_COMPLETED"]
        assert llm_start.total == 4 and [(event.current, event.total) for event in starts] == [(1, 4), (2, 4), (3, 4), (4, 4)]
        assert len(completed) == 4 and all(event.section_name in {"胸部CT", "腹部彩超", "肺功能", "随访建议"} for event in completed)
        assert "MERGING" in stages and "EVIDENCE_VALIDATION" in stages and "DEDUPLICATION" in stages and "SAVING" in stages
        completed_event = events[-1]
        assert completed_event.stage == "COMPLETED" and completed_event.elapsed_ms is not None
        assert completed_event.llm_call_count == 4 and completed_event.llm_success_count == 4
        assert completed_event.finding_count is not None and completed_event.followup_count is not None
    assert first_run.id != second_run.id and run_count == 2 and client.calls == 8


class _PartiallyFailingFallbackClient(_MixedAuditFallbackClient):
    def generate_structured(self, *, user_prompt: str, **kwargs):
        if "肺功能" in user_prompt:
            self.calls += 1
            raise LocalLLMUnavailable("合成本地模型失败")
        return super().generate_structured(user_prompt=user_prompt, **kwargs)


def test_llm_section_failure_emits_progress_and_keeps_remaining_sections_running(tmp_path: Path) -> None:
    client = _PartiallyFailingFallbackClient()
    service = ReportParsingService(semantic_fallback=ReportSemanticFallback(client=client)); service.storage_root = tmp_path
    content = "\n".join((
        "HbA1c  6.3 %", "胸部CT检查结论：双肺可见多个小结节。建议持续观察。",
        "腹部彩超检查结论：肝脏回声增粗。建议进一步评估。",
        "肺功能检查结论：小气道功能障碍。建议结合呼吸专科意见。",
        "健康建议：建议约3个月后复查胸部CT。请安排后续检查。",
    )).encode()
    events = []
    with _session() as session:
        patient = Patient(external_id="synthetic-progress-failure", timezone="Asia/Tokyo"); session.add(patient); session.flush()
        _, run, _ = service.upload_and_parse(session, patient.id, "partial.txt", content, "tester", progress_callback=events.append)

    failure = next(event for event in events if event.stage == "LLM_SECTION_FAILED")
    later_completion = [event for event in events if event.stage == "LLM_SECTION_COMPLETED" and event.current and failure.current and event.current > failure.current]
    assert failure.section_name == "肺功能" and later_completion
    assert run.status == "PARTIAL_SUCCESS" and run.llm_failure_count == 1 and run.llm_success_count == 3


def test_same_uploaded_document_creates_fresh_rule_and_local_llm_run_each_time(tmp_path: Path) -> None:
    client = _MixedAuditFallbackClient()
    service = ReportParsingService(semantic_fallback=ReportSemanticFallback(client=client)); service.storage_root = tmp_path
    content = "\n".join((
        "HbA1c  6.3 %",
        "LDL-C  4.15 mmol/L",
        "胸部CT检查结论：左肺下叶见少许条索影。双肺可见多个小结节。建议结合既往检查持续观察。",
        "腹部彩超检查结论：肝脏回声增粗。胆囊壁欠光滑。建议结合临床进一步评估。",
        "肺功能检查结论：小气道功能障碍。其余指标基本正常。建议结合呼吸专科意见。",
        "健康建议：建议约3个月后复查胸部CT。请根据专科意见安排后续检查。",
    )).encode()
    with _session() as session:
        patient = Patient(external_id="synthetic-repeat-explicit-parse", timezone="Asia/Tokyo"); session.add(patient); session.flush()
        document, first_run, first_duplicate = service.upload_and_parse(session, patient.id, "same_report.txt", content, "tester")
        session.flush()
        first_candidates = service.candidates(session, document.id, first_run.id)
        same_document, second_run, second_duplicate = service.upload_and_parse(session, patient.id, "same_report.txt", content, "tester")
        session.flush()
        second_candidates = service.candidates(session, same_document.id, second_run.id)
        runs = service.runs(session, document.id)

    assert first_duplicate is False and second_duplicate is True
    assert same_document.id == document.id and first_run.id != second_run.id
    assert len(runs) == 2 and runs[0].id == second_run.id
    assert client.calls == 8
    assert first_run.llm_call_count == second_run.llm_call_count == 4
    assert first_run.rule_candidate_count > 0 and second_run.rule_candidate_count > 0
    assert first_run.llm_candidate_count > 0 and second_run.llm_candidate_count > 0
    assert {item.id for item in first_candidates}.isdisjoint({item.id for item in second_candidates})
    assert all(item.status == "PENDING_REVIEW" for item in second_candidates)
    assert len(list(tmp_path.iterdir())) == 1


def test_explicit_parse_is_rejected_while_the_same_document_is_processing(tmp_path: Path) -> None:
    service = ReportParsingService(); service.storage_root = tmp_path
    with _session() as session:
        patient = Patient(external_id="synthetic-processing-lock", timezone="Asia/Tokyo"); session.add(patient); session.flush()
        document, run, _ = service.upload_and_parse(session, patient.id, "processing.txt", _report("synthetic_lab_report.txt"), "tester")
        run.status = "PROCESSING"; session.flush()
        try:
            service.upload_and_parse(session, patient.id, "processing.txt", _report("synthetic_lab_report.txt"), "tester")
        except ValueError as error:
            message = str(error)
        else:
            message = ""
    assert "正在解析" in message


def test_post_parse_always_creates_a_fresh_run(tmp_path: Path) -> None:
    """A parse command is intentionally non-idempotent, unlike document intake."""
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    service = ReportParsingService(); service.storage_root = tmp_path
    with session_factory() as session:
        patient = Patient(external_id="synthetic-api-explicit-parse", timezone="Asia/Tokyo")
        session.add(patient); session.flush()
        document, first_run, _ = service.upload_and_parse(session, patient.id, "api-report.txt", _report("synthetic_lab_report.txt"), "tester")
        document_id, first_run_id = document.id, first_run.id
        session.commit()

    response = TestClient(create_app(session_factory)).post(f"/reports/{document_id}/parse")

    assert response.status_code == 200
    assert response.json()["run_id"] != str(first_run_id)
    with session_factory() as session:
        runs = ReportParsingService().runs(session, document_id)
    assert len(runs) == 2 and runs[0].id != first_run_id


class _UnavailableNarrativeClient:
    def __init__(self) -> None: self.calls = 0
    def health_check(self): return LocalLLMHealth(True, False, "local_llm", "local LLM", "http://127.0.0.1:11434", "合成本地模型不可用")
    def generate_structured(self, **_kwargs): self.calls += 1; raise AssertionError("纯结构化报告不应调用LLM")


def test_first_lab_only_parse_is_rule_only_even_when_optional_local_llm_is_unavailable(tmp_path: Path) -> None:
    client = _UnavailableNarrativeClient()
    service = ReportParsingService(semantic_fallback=ReportSemanticFallback(client=client)); service.storage_root = tmp_path
    content = "HbA1c  6.3 %\nLDL-C  4.15 mmol/L\nALT  28 IU/L\nAST  22 IU/L".encode()
    with _session() as session:
        patient = Patient(external_id="synthetic-lab-only", timezone="Asia/Tokyo"); session.add(patient); session.flush()
        document, run, _ = service.upload_and_parse(session, patient.id, "synthetic_lab_only.txt", content, "tester")
        session.flush()
        candidates = service.candidates(session, document.id, run.id)
    assert run.status == "COMPLETED" and run.llm_status == "NOT_NEEDED" and run.llm_call_count == client.calls == 0
    assert run.rule_candidate_count == len(candidates) and run.llm_candidate_count == 0


def test_first_parse_and_reparse_share_the_same_rule_and_local_llm_pipeline(tmp_path: Path) -> None:
    client = _AuditFallbackClient()
    service = ReportParsingService(semantic_fallback=ReportSemanticFallback(client=client)); service.storage_root = tmp_path
    content = "胸部CT检查结论：左肺下叶见少许条索影。双肺可见多个小结节。建议约3个月后复查胸部CT。".encode()
    with _session() as session:
        patient = Patient(external_id="synthetic-shared-pipeline", timezone="Asia/Tokyo"); session.add(patient); session.flush()
        document, first_run, _ = service.upload_and_parse(session, patient.id, "shared_pipeline.txt", content, "tester")
        session.flush()
        second_run = service.reparse_document(session, document.id, "tester")
    assert first_run.llm_status == second_run.llm_status == "USED"
    assert first_run.llm_call_count == second_run.llm_call_count == 1


def test_reparse_creates_a_new_run_without_overwriting_confirmed_observation(tmp_path: Path) -> None:
    service = ReportParsingService(); service.storage_root = tmp_path
    with _session() as session:
        patient = Patient(external_id="synthetic-report-reparse", timezone="Asia/Tokyo"); session.add(patient); session.flush()
        document, first_run, _ = service.upload_and_parse(session, patient.id, "reparse.txt", _report("synthetic_lab_report.txt"), "tester")
        session.flush()
        first_ldl = next(item for item in service.candidates(session, document.id, first_run.id) if item.canonical_code == "ldl_c")
        observation = service.confirm_candidate(session, first_ldl, "manager")
        assert observation is not None
        session.flush()

        second_run = service.reparse_document(session, document.id, "manager")
        session.flush()
        first_candidates = service.candidates(session, document.id, first_run.id)
        second_candidates = service.candidates(session, document.id, second_run.id)
        runs = service.runs(session, document.id)
        duplicate_ldl = next(item for item in second_candidates if item.canonical_code == "ldl_c")

        assert second_run.id != first_run.id
        assert len(runs) == 2 and runs[0].id == second_run.id
        assert first_ldl.status == "CONFIRMED"
        assert session.get(Observation, observation.id) is not None
        assert all(item.status == "PENDING_REVIEW" for item in second_candidates)
        assert service.possible_duplicate_observation(session, duplicate_ldl) is not None
        assert len(first_candidates) == len(second_candidates)


def test_duplicate_reparsed_candidate_cannot_write_a_second_observation(tmp_path: Path) -> None:
    service = ReportParsingService(); service.storage_root = tmp_path
    with _session() as session:
        patient = Patient(external_id="synthetic-report-reparse-duplicate", timezone="Asia/Tokyo"); session.add(patient); session.flush()
        document, first_run, _ = service.upload_and_parse(session, patient.id, "duplicate.txt", _report("synthetic_lab_report.txt"), "tester")
        session.flush()
        first_ldl = next(item for item in service.candidates(session, document.id, first_run.id) if item.canonical_code == "ldl_c")
        service.confirm_candidate(session, first_ldl, "manager")
        second_run = service.reparse_document(session, document.id, "manager")
        session.flush()
        second_ldl = next(item for item in service.candidates(session, document.id, second_run.id) if item.canonical_code == "ldl_c")
        try:
            service.confirm_candidate(session, second_ldl, "manager")
        except ValueError as error:
            message = str(error)
        else:
            message = ""
    assert "可能已经入档" in message
