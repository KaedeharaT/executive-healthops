"""No-network tests for the optional, evidence-bound local Qwen fallback."""

from __future__ import annotations

from uuid import uuid4

import pytest

from executive_health_ai import config
from executive_health_ai.llm.qwen_client import LocalQwenClient, LocalQwenHealth, LocalQwenSettings, LocalQwenUnavailable, parse_json_object, sanitize_for_llm
from executive_health_ai.services.report_parsing import CandidateDraft, ExtractedPage, ReportParsingService, ReportSemanticFallback


class _Response:
    ok = True
    def raise_for_status(self) -> None: pass
    def json(self): return {"models": [{"name": "qwen2.5:7b"}], "message": {"content": '{"exam_name":"胸部CT","findings":[{"summary":"左肺小结节","body_system":"肺","reported_change":"小结节","reported_severity":"","evidence":"左肺见小结节"}],"recommendations":[]}'}}


def _post(*_args, **_kwargs): return _Response()


def _get(*_args, **_kwargs): return _Response()


def test_qwen_client_uses_local_ollama_contract_without_api_key() -> None:
    settings = LocalQwenSettings(True, "qwen", "http://127.0.0.1:11434", "qwen2.5:7b", 3, 3000)
    get_urls: list[str] = []

    def tracking_get(url: str, **kwargs):
        get_urls.append(url)
        return _get(url, **kwargs)

    client = LocalQwenClient(settings, http_post=_post, http_get=tracking_get)
    assert client.available()
    assert get_urls == ["http://127.0.0.1:11434/api/tags"]
    result = client.generate_structured(task="report_semantic_fallback", system_prompt="system", user_prompt="左肺见小结节", document_id="synthetic-doc", page=2)
    assert result["exam_name"] == "胸部CT"


def test_qwen_client_refuses_non_loopback_endpoint_without_making_a_request() -> None:
    settings = LocalQwenSettings(True, "qwen", "https://example.invalid", "qwen2.5:7b", 3, 3000)
    client = LocalQwenClient(settings, http_post=lambda *_args, **_kwargs: pytest.fail("不应访问外部地址"), http_get=lambda *_args, **_kwargs: pytest.fail("不应访问外部地址"))
    assert client.available() is False
    with pytest.raises(LocalQwenUnavailable):
        client.generate_structured(task="report_semantic_fallback", system_prompt="system", user_prompt="合成文本", document_id="synthetic-doc", page=1)


def test_sanitizer_and_json_parser_do_not_keep_common_direct_identifiers() -> None:
    text = "姓名：合成成员\n电话：00000000000\n档案号：ABC-123\n左肺见小结节"
    sanitized = sanitize_for_llm(text)
    assert "合成成员" not in sanitized and "00000000000" not in sanitized and "ABC-123" not in sanitized
    assert parse_json_object("```json\n{\"ok\": true}\n```") == {"ok": True}


def test_project_env_loader_uses_root_file_and_preserves_explicit_values(tmp_path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("LOCAL_LLM_ENABLED=true\nLOCAL_LLM_PROVIDER=qwen\nLOCAL_LLM_MODEL=qwen2.5:7b\nOLLAMA_BASE_URL=http://127.0.0.1:11434\nALLOW_EXTERNAL_PHI_LLM=false\n", encoding="utf-8")
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    for name in ("LOCAL_LLM_ENABLED", "LOCAL_LLM_PROVIDER", "LOCAL_LLM_MODEL", "OLLAMA_BASE_URL", "ALLOW_EXTERNAL_PHI_LLM"):
        monkeypatch.delenv(name, raising=False)
    config.load_project_environment()
    settings = LocalQwenSettings.from_environment()
    assert settings.enabled and settings.provider == "qwen" and settings.model == "qwen2.5:7b"
    monkeypatch.setenv("LOCAL_LLM_MODEL", "explicit-model")
    config.load_project_environment()
    assert LocalQwenSettings.from_environment().model == "explicit-model"


class _FallbackClient:
    def available(self) -> bool: return True
    def health_check(self): return LocalQwenHealth(True, True, "qwen", "qwen2.5:7b", "http://127.0.0.1:11434")
    def generate_structured(self, **_kwargs):
        return {"exam_name": "胸部CT", "findings": [{"summary": "左肺小结节", "body_system": "肺", "reported_change": "小结节", "reported_severity": "", "evidence": "左肺见小结节"}, {"summary": "无证据内容", "evidence": "报告中不存在"}], "recommendations": [{"action": "建议复查", "department": "", "interval_text": "", "evidence": "建议一年后复查"}], "uncertainties": []}


def test_semantic_fallback_accepts_only_evidence_backed_candidates() -> None:
    fallback = ReportSemanticFallback(client=_FallbackClient())
    page = ExtractedPage(2, "胸部CT影像描述：左肺见小结节，双肺未见其他明显异常。建议一年后复查胸部CT，以便持续观察。")
    result = fallback.extract(pages=[page], existing=[], document_id=uuid4())
    assert result.used is True
    assert result.status == "USED" and result.call_count == result.success_count == 1
    assert [(item.candidate_type, item.summary, item.extraction_method) for item in result.drafts] == [("FINDING", "左肺小结节", "LLM"), ("FOLLOWUP", "建议复查", "LLM")]


class _UnavailableFallbackClient:
    def health_check(self): return LocalQwenHealth(True, False, "qwen", "qwen2.5:7b", "http://127.0.0.1:11434", "无法连接本地 Ollama")


def test_semantic_fallback_distinguishes_not_needed_and_unavailable() -> None:
    unavailable = ReportSemanticFallback(client=_UnavailableFallbackClient()).extract(pages=[ExtractedPage(1, "胸部CT检查结论：这是合成的复杂文本。建议复查。")], existing=[], document_id=uuid4())
    not_needed = ReportSemanticFallback(client=_FallbackClient()).extract(pages=[ExtractedPage(1, "身高 175 cm")], existing=[], document_id=uuid4())
    assert unavailable.status == "UNAVAILABLE" and unavailable.failure_reason == "无法连接本地 Ollama"
    assert not_needed.status == "NOT_NEEDED" and not_needed.call_count == 0


class _MixedNarrativeClient:
    def __init__(self) -> None: self.calls: list[str] = []
    def health_check(self): return LocalQwenHealth(True, True, "qwen", "qwen2.5:7b", "http://127.0.0.1:11434")
    def generate_structured(self, *, user_prompt: str, **_kwargs):
        self.calls.append(user_prompt)
        if "腹部彩超" in user_prompt:
            return {"exam_name": "腹部彩超", "findings": [{"summary": "肝脏回声增粗", "evidence": "肝脏回声增粗"}], "recommendations": []}
        if "肺功能" in user_prompt:
            return {"exam_name": "肺功能", "findings": [{"summary": "小气道功能障碍", "evidence": "小气道功能障碍"}], "recommendations": []}
        if "健康建议" in user_prompt:
            return {"exam_name": "健康建议", "findings": [], "recommendations": [{"action": "复查胸部CT", "evidence": "建议约3个月后复查胸部CT"}]}
        return {"exam_name": "胸部CT", "findings": [{"summary": "双肺多发小结节", "evidence": "双肺可见多个小结节"}], "recommendations": []}


def test_mixed_report_uses_qwen_for_complex_narratives_but_not_structured_metrics() -> None:
    client = _MixedNarrativeClient()
    pages = [
        ExtractedPage(1, "HbA1c 6.3 %\nLDL-C 4.15 mmol/L"),
        ExtractedPage(2, "胸部CT检查结论：左肺下叶见少许条索影。双肺可见多个小结节。建议结合既往检查持续观察。"),
        ExtractedPage(3, "腹部彩超检查结论：肝脏回声增粗。胆囊壁欠光滑。建议结合临床进一步评估。"),
        ExtractedPage(4, "肺功能检查结论：小气道功能障碍。其余指标基本正常。建议结合呼吸专科意见。"),
        ExtractedPage(5, "健康建议：建议约3个月后复查胸部CT。请根据专科意见安排后续检查。"),
    ]
    result = ReportSemanticFallback(client=client).extract(pages=pages, existing=[], document_id=uuid4())
    assert result.status == "USED" and result.call_count == result.success_count == 4
    assert len(client.calls) == 4
    assert {draft.extraction_method for draft in result.drafts} == {"LLM"}
    assert {"FINDING", "FOLLOWUP"}.issubset({draft.candidate_type for draft in result.drafts})


def test_named_section_is_sent_to_qwen_once_and_exact_rule_duplicate_prefers_llm() -> None:
    client = _MixedNarrativeClient()
    result = ReportSemanticFallback(client=client).extract(pages=[
        ExtractedPage(1, "胸部CT检查结论：双肺可见多个小结节。建议结合既往检查持续观察。"),
        ExtractedPage(2, "胸部CT补充描述：双肺可见多个小结节。建议结合既往检查持续观察。"),
    ], existing=[], document_id=uuid4())
    rule = CandidateDraft("FINDING", None, None, None, None, None, None, None, "双肺结节", {}, "MEDIUM", "RULE", 1, "IMAGING", "双肺可见多个小结节")
    qwen = CandidateDraft("FINDING", None, None, None, None, None, None, None, "双肺多发小结节", {}, "MEDIUM", "LLM", 1, "IMAGING", "双肺可见多个小结节")
    merged = ReportParsingService._deduplicate_combined_candidates([rule, qwen])
    assert result.call_count == 1 and len(client.calls) == 1
    assert merged == [qwen]
