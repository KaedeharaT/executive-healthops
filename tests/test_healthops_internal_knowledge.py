from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from executive_health_ai.models import Base, KnowledgeChunk, KnowledgeDocument, KnowledgeReviewAudit, KnowledgeUseRecord
from executive_health_ai.services.grounded_ai import GROUNDED, INSUFFICIENT_EVIDENCE, GroundedAnswerService
from executive_health_ai.services.healthops_internal_knowledge import HEALTHOPS_INTERNAL_KNOWLEDGE_V1, seed_healthops_internal_knowledge


class CitingGenerator:
    def generate(self, **kwargs):
        return {"content": "根据已审核内部资料处理。[K1]", "citations": ["K1"]}, {"provider": "test", "model": "test"}


def make_db() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = Session(engine)
    seed_healthops_internal_knowledge(session)
    session.commit()
    return session


def answer(session: Session, question: str):
    return GroundedAnswerService(generator=CitingGenerator()).answer(
        session, question=question, feature="sop_workflow_assistant",
        categories=("INTERNAL_SOP", "COMMUNICATION", "SERVICE_SOP", "AI_SAFETY"),
        audience="health_manager",
    )


def test_internal_foundation_contains_twelve_approved_sectioned_documents():
    with make_db() as session:
        assert len(HEALTHOPS_INTERNAL_KNOWLEDGE_V1) == 12
        counts = {category: session.scalar(select(func.count()).select_from(KnowledgeDocument).where(
            KnowledgeDocument.category == category, KnowledgeDocument.review_status == "APPROVED"
        )) for category in ("INTERNAL_SOP", "COMMUNICATION", "SERVICE_SOP", "AI_SAFETY")}
        assert counts == {"INTERNAL_SOP": 9, "COMMUNICATION": 1, "SERVICE_SOP": 1, "AI_SAFETY": 1}
        assert session.scalar(select(func.count()).select_from(KnowledgeChunk)) == 59
        assert session.scalar(select(func.count()).select_from(KnowledgeReviewAudit)) == 12
        assert all(2 <= len(spec.sections) <= 7 for spec in HEALTHOPS_INTERNAL_KNOWLEDGE_V1)


def test_sop_queries_retrieve_expected_approved_documents():
    queries = [
        ("Yellow Risk 接手后下一步做什么？", "Yellow Risk健管处理SOP"),
        ("什么时候应该提交内部医生？", "健管到内部医生升级规范"),
        ("成员上传体检报告以后我先做什么？", "体检报告审核SOP"),
        ("客户希望调整健康计划怎么办？", "健康计划建立与成员确认规范"),
        ("服务申请通过后下一步是什么？", "服务申请、安排与结果回流SOP"),
        ("Outcome之后怎么办？", "Outcome阶段复盘与下一步规范"),
        ("健康数据很久没有更新怎么办？", "健康数据缺失与陈旧数据处理规范"),
    ]
    with make_db() as session:
        for question, expected_title in queries:
            result = answer(session, question)
            assert result.grounded == GROUNDED
            assert result.knowledge_citations[0].title == expected_title


def test_sop_citation_is_actual_used_chunk():
    with make_db() as session:
        result = answer(session, "Yellow Risk接手以后如何处理？")
        usage = session.scalar(select(KnowledgeUseRecord).where(KnowledgeUseRecord.answer_id == result.answer_id))
        citation = result.knowledge_citations[0]
        assert usage is not None and str(citation.chunk_id) in usage.chunk_ids
        assert session.get(KnowledgeChunk, citation.chunk_id).content == citation.excerpt


def test_uncovered_workflow_question_still_refuses():
    with make_db() as session:
        result = answer(session, "量子航天器轨道发动机怎么校准？")
        assert result.grounded == INSUFFICIENT_EVIDENCE
        assert not result.knowledge_citations
