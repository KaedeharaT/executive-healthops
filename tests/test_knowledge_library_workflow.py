"""Product workflow guards for governed, on-demand public knowledge sources."""

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.models import Base
from executive_health_ai.services.knowledge import KnowledgeService
from executive_health_ai.services.knowledge_sources import KnowledgeSearchResult


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)()


def _official_result(source_code: str = "MEDLINEPLUS") -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
        provider_code=source_code,
        external_id=f"{source_code}-hypertension-1",
        title="High Blood Pressure",
        subtitle="健康主题",
        summary="Official source snippet only.",
        category="PATIENT_EDUCATION",
        source_name="Official source",
        source_organization="Official organization",
        official_url="https://example.org/official-source",
        version="2026",
        retrieved_at=datetime.now(timezone.utc),
        structured_metadata={},
        language="en",
        attribution="Official attribution",
        license_note="Terms reviewed",
    )


def test_provider_cards_are_rendered_before_saved_documents_and_include_all_required_sources() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    renderer = source.split("def render_knowledge_library_entry", 1)[1].split("def render_more_workspace", 1)[0]
    assert "_render_knowledge_source_cards(sources)" in renderer
    assert renderer.index("_render_knowledge_source_cards(sources)") < renderer.index("_render_saved_knowledge(sources)")
    cards = source.split("KNOWLEDGE_SOURCE_CARD_CODES", 1)[1].split("def _knowledge_source_status", 1)[0]
    for code in ("MEDLINEPLUS", "RXNORM", "OPENFDA", "WHO_ICD11"):
        assert code in cards


def test_selectively_saved_official_result_is_visible_pending_then_approved_for_ai() -> None:
    with _session() as session:
        service = KnowledgeService()
        service.ensure_source_registry(session)
        document = service.cache_source_result(session, _official_result())
        session.commit()

        pending = service.search_documents(session, "blood pressure", review_status="PENDING_REVIEW")
        assert pending == [document]
        assert document.source_provider == "MEDLINEPLUS"
        assert document.source_url and document.attribution and document.license_note
        assert service.approved_documents_for_ai(session) == []

        service.approve_document(session, document, "授权审核人")
        assert service.approved_documents_for_ai(session) == [document]


def test_draft_pending_and_archived_documents_have_an_honest_library_review_path() -> None:
    with _session() as session:
        service = KnowledgeService()
        draft = service.create_document(
            session,
            title="Internal draft",
            category="INTERNAL_SOP",
            source_type="人工整理",
            source_name="内部资料",
            review_status="DRAFT",
        )
        pending = service.cache_source_result(session, _official_result("OPENFDA"))
        service.reject_document(session, pending, "授权审核人")
        service.archive_document(session, draft)
        session.commit()

        assert service.search_documents(session, "", review_status="REJECTED") == [pending]
        assert service.search_documents(session, "", review_status="ARCHIVED") == [draft]
        assert service.approved_documents_for_ai(session) == []


def test_renderer_keeps_network_failure_local_and_does_not_turn_sources_into_risk_rules() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    search = source.split("def _render_knowledge_search(sources", 1)[1].split("def _render_knowledge_source_cards", 1)[0]
    assert "暂时无法连接，请稍后重试" in search
    assert "_render_saved_knowledge" not in search
    governed = Path("src/executive_health_ai/services/knowledge.py").read_text(encoding="utf-8")
    assert 'review_status="PENDING_REVIEW"' in governed
    assert "RiskRule" not in governed


def test_saved_library_defaults_to_all_active_review_states_not_only_approved() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    saved = source.split("def _render_saved_knowledge", 1)[1].split("def render_knowledge_library_entry", 1)[0]
    assert '["全部状态", "DRAFT", "PENDING_REVIEW", "APPROVED", "REJECTED", "ARCHIVED"]' in saved
    assert "草稿、待审核和已批准资料均可在这里查看" in saved


def test_source_result_display_keeps_attribution_and_provider_specific_safety_boundary() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    search = source.split("def _render_knowledge_search(sources", 1)[1].split("def _render_knowledge_source_cards", 1)[0]
    assert "药物标准资料" in search
    assert "RxCUI：" not in search
    detail = source.split("def _render_knowledge_search_detail", 1)[1].split("def _render_knowledge_search(sources", 1)[0]
    assert "查看官方来源" in detail
    assert "不构成个体化诊疗或用药建议" in detail


def test_search_uses_separate_widget_and_business_state_without_late_widget_mutation() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    search = source.split("def _render_knowledge_search(sources", 1)[1].split("def _render_knowledge_source_cards", 1)[0]
    assert '"knowledge-search-query-ui"' in search
    assert '"knowledge-search-provider-ui"' in search
    assert '"knowledge_search_results"' in search
    assert '"knowledge_search_selected_result"' in search
    assert '"knowledge_search_provider_pending"' in search


def test_search_result_has_same_page_preview_and_no_result_list_external_link() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    search = source.split("def _render_knowledge_search(sources", 1)[1].split("def _render_knowledge_source_cards", 1)[0]
    detail = source.split("def _render_knowledge_search_detail", 1)[1].split("def _render_knowledge_search(sources", 1)[0]
    assert 'view.button("查看"' in search
    assert "_render_knowledge_search_detail(selected)" in search
    assert "link_button" not in search
    assert "link_button(\"查看官方来源\"" in detail


def test_on_demand_cache_declares_no_full_site_mirror() -> None:
    source = Path("src/executive_health_ai/services/knowledge.py").read_text(encoding="utf-8")
    assert '"on_demand_cache": True' in source
    assert '"no_full_text_mirror": True' in source
