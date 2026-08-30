"""Governance and retrieval contracts for the four-frame Knowledge Center."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.models import Base, KnowledgeChunk, KnowledgeReviewAudit, KnowledgeUseRecord
from executive_health_ai.services.knowledge import KnowledgeService
from executive_health_ai.services.knowledge_retrieval import KnowledgeRetrievalService


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)()


def _document(service: KnowledgeService, session: Session, *, title: str = "高血压健康教育", status: str = "PENDING_REVIEW", content: str = "# 症状\n高血压需要持续监测。\n# 说明\n资料仅供健康教育使用。"):
    return service.create_document(
        session,
        title=title,
        category="PATIENT_EDUCATION",
        summary="健康教育资料摘要。",
        content_text=content,
        source_type="GUIDELINE",
        source_name="官方来源",
        source_provider="MEDLINEPLUS",
        source_url="https://medlineplus.gov/",
        version="v1.0",
        review_status=status,
        license_note="仅按许可保存摘要与出处。",
        attribution="NLM",
    )


def test_three_knowledge_layers_remain_separate_from_risk_execution() -> None:
    source = Path("src/executive_health_ai/services/knowledge.py").read_text(encoding="utf-8")
    ui = Path("streamlit_app.py").read_text(encoding="utf-8")
    assert "RiskRule" not in source
    assert "不会自动生成临床风险规则" in ui
    assert 'review_status="PENDING_REVIEW"' in source


def test_approved_document_is_chunked_and_only_approved_chunks_are_retrieved() -> None:
    with _session() as session:
        service = KnowledgeService()
        pending = _document(service, session, title="待审核的血压资料")
        approved = _document(service, session, title="高血压健康教育")
        service.approve_document(session, approved, "审核医生", "来源与许可已核对")
        session.commit()

        chunks = list(session.scalars(select(KnowledgeChunk).where(KnowledgeChunk.knowledge_document_id == approved.id)))
        assert len(chunks) == 2
        hits = KnowledgeRetrievalService().search(session, "高血压")
        assert {hit.document.id for hit in hits} == {approved.id}
        assert all(hit.document.id != pending.id for hit in hits)
        assert hits[0].citation()["location"] == "症状"


def test_archived_or_review_due_documents_are_excluded_from_formal_ai_retrieval() -> None:
    with _session() as session:
        service = KnowledgeService()
        expired = _document(service, session, title="过期血压资料")
        expired.review_due_at = date.today() - timedelta(days=1)
        service.approve_document(session, expired, "审核医生")
        archived = _document(service, session, title="已归档血压资料")
        service.approve_document(session, archived, "审核医生")
        service.archive_document(session, archived, "审核医生")
        session.commit()

        assert service.approved_documents_for_ai(session) == []
        assert KnowledgeRetrievalService().search(session, "血压") == []


def test_review_audit_and_ai_usage_record_actual_chunk_ids() -> None:
    with _session() as session:
        service = KnowledgeService()
        document = _document(service, session)
        service.approve_document(session, document, "审核医生", "批准用于解释")
        chunks = list(session.scalars(select(KnowledgeChunk).where(KnowledgeChunk.knowledge_document_id == document.id)))
        records = service.record_ai_usage(
            session,
            output_type="健康解释",
            output_reference="output-001",
            chunks=[chunks[0]],
            feature="member_health_explanation",
            model="local LLM",
            request_context_hash="safe-context-hash",
        )
        session.commit()

        assert records[0].chunk_ids == [str(chunks[0].id)]
        assert records[0].feature == "member_health_explanation"
        assert session.scalar(select(KnowledgeReviewAudit).where(KnowledgeReviewAudit.knowledge_document_id == document.id)).new_status == "APPROVED"
        assert session.scalar(select(KnowledgeUseRecord).where(KnowledgeUseRecord.knowledge_document_id == document.id)).model == "local LLM"


def test_unapproved_document_cannot_be_recorded_as_formal_ai_evidence() -> None:
    with _session() as session:
        service = KnowledgeService()
        document = _document(service, session)
        with pytest.raises(ValueError, match="未审核知识资料"):
            service.record_ai_usage(session, output_type="健康解释", output_reference="output-002", documents=[document])


def test_replacement_version_archives_previous_only_after_human_approval() -> None:
    with _session() as session:
        service = KnowledgeService()
        previous = _document(service, session, title="内部随访 SOP")
        service.approve_document(session, previous, "审核医生")
        replacement = _document(service, session, title="内部随访 SOP", content="# v1.1\n更新后的随访说明")
        replacement.version = "v1.1"
        replacement.supersedes_id = previous.id
        session.flush()
        assert previous.is_active is True
        service.approve_document(session, replacement, "审核医生")
        session.commit()

        assert previous.review_status == "ARCHIVED"
        assert previous.superseded_by_id == replacement.id
        assert replacement.supersedes_id == previous.id


def test_internal_sop_and_authorized_textbook_follow_the_same_review_then_chunk_path() -> None:
    with _session() as session:
        service = KnowledgeService()
        sop = service.create_document(
            session, title="内部随访 SOP", category="INTERNAL_SOP", content_text="# 随访\n记录复核结果。",
            source_type="INTERNAL_SOP", source_name="内部运营", review_status="DRAFT",
        )
        textbook = service.create_document(
            session, title="授权教材样章", category="TEXTBOOK_REFERENCE", content_text="# 第八章\n高血压背景知识。",
            source_type="TEXTBOOK", source_name="合法授权上传", review_status="PENDING_REVIEW",
            license_note="已确认内部使用授权。",
        )
        service.approve_document(session, sop, "审核医生")
        service.approve_document(session, textbook, "审核医生")
        session.commit()
        assert KnowledgeRetrievalService().search(session, "复核")
        assert KnowledgeRetrievalService().search(session, "高血压")


def test_ui_keeps_four_main_frames_and_inline_details_without_a_third_route() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    renderer = source.split("def render_knowledge_library_entry", 1)[1].split("def render_more_workspace", 1)[0]
    assert "医学知识中心" in renderer
    for call in ("_render_knowledge_search(sources)", "_render_knowledge_source_cards(sources)", "_render_saved_knowledge(sources)", "_render_pending_knowledge(sources)"):
        assert call in renderer
    assert "_render_knowledge_detail(selected" in source
    assert "st.switch_page" not in source[source.index("def _render_knowledge_search"):source.index("def render_more_workspace")]


def test_uploaded_textbook_requires_a_license_note_in_the_ui() -> None:
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    add_form = source.split("def _render_knowledge_add_form", 1)[1].split("def _render_saved_knowledge", 1)[0]
    assert "版权/授权说明" in add_form
    assert "authorized_upload" in add_form
    assert "作者（如适用）" in add_form
    assert "出版社（如适用）" in add_form
    assert "出版年份（如适用）" in add_form
    assert "不会自动作为 AI 来源或医疗规则" in add_form
