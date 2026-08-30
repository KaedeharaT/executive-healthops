"""AppTest coverage for the in-product knowledge-search interaction."""

from datetime import datetime, timezone
from pathlib import Path

from streamlit.testing.v1 import AppTest

from executive_health_ai.services.knowledge import KnowledgeService
from executive_health_ai.services.knowledge_sources import KnowledgeSearchResult


APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def _result() -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
        provider_code="RXNORM",
        external_id="6809",
        title="metformin",
        subtitle="标准药物名称",
        summary="RxNorm 药物概念；仅用于名称标准化。",
        category="MEDICATION",
        source_name="RxNorm / RxNav",
        source_organization="U.S. National Library of Medicine / NIH",
        official_url="https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm=6809",
        version=None,
        retrieved_at=datetime.now(timezone.utc),
        structured_metadata={"rxcui": "6809", "term_type": "IN", "synonym": None},
        language="en",
        attribution="NLM attribution",
        license_note="Terms reviewed",
    )


def _knowledge_library() -> AppTest:
    app = AppTest.from_file(APP)
    app.run(timeout=30)
    next(item for item in app.radio if item.label == "工作区").set_value("更多")
    app.run(timeout=30)
    next(item for item in app.button if item.key == "more-open-知识库").click()
    app.run(timeout=30)
    assert not app.exception
    return app


def test_search_button_calls_provider_and_renders_normalized_results_in_same_page(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_query(self, session, source_code, query, *, limit=5):
        calls.append((source_code, query))
        return [_result()]

    monkeypatch.setattr(KnowledgeService, "query_source", fake_query)
    app = _knowledge_library()
    next(item for item in app.text_input if item.label == "关键词").set_value("metformin")
    next(item for item in app.selectbox if item.label == "来源").set_value("RXNORM")
    next(item for item in app.button if item.key == "knowledge-source-search").click()
    app.run(timeout=30)

    assert calls == [("RXNORM", "metformin")]
    assert len(app.session_state["knowledge_search_results"]) == 1
    assert any("metformin" in str(item.value).lower() for item in app.markdown)
    assert any(item.label == "查看" for item in app.button)
    assert not app.exception


def test_provider_card_safely_sets_search_provider_and_same_page_detail_persists(monkeypatch) -> None:
    def fake_query(self, session, source_code, query, *, limit=5):
        return [_result()]

    monkeypatch.setattr(KnowledgeService, "query_source", fake_query)
    app = _knowledge_library()
    next(item for item in app.button if item.key == "knowledge-source-card-RXNORM").click()
    app.run(timeout=30)
    assert next(item for item in app.selectbox if item.label == "来源").value == "RXNORM"

    next(item for item in app.text_input if item.label == "关键词").set_value("metformin")
    next(item for item in app.button if item.key == "knowledge-source-search").click()
    app.run(timeout=30)
    next(item for item in app.button if item.label == "查看").click()
    app.run(timeout=30)

    assert len(app.session_state["knowledge_search_results"]) == 1
    assert any("资料预览" in str(item.value) for item in app.markdown)
    assert not app.exception


def test_who_without_credentials_recovers_with_plain_language_state() -> None:
    app = _knowledge_library()
    next(item for item in app.text_input if item.label == "关键词").set_value("hypertension")
    next(item for item in app.selectbox if item.label == "来源").set_value("WHO_ICD11")
    next(item for item in app.button if item.key == "knowledge-source-search").click()
    app.run(timeout=30)

    assert any("尚未配置 WHO ICD-11 API 凭证" in str(item.value) for item in app.warning)
    assert not app.exception


def test_knowledge_center_first_screen_has_exactly_the_four_governance_sections() -> None:
    app = _knowledge_library()
    visible = "\n".join(str(item.value) for item in app.markdown)
    for heading in ("搜索知识", "知识来源", "已保存知识", "待审核"):
        assert heading in visible
    assert "医学知识中心" in "\n".join(str(item.value) for item in app.title)
    assert not app.exception
