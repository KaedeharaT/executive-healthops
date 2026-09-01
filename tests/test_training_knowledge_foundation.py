from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from executive_health_ai.models import Base, KnowledgeChunk, KnowledgeDocument, KnowledgeReviewAudit, KnowledgeUseRecord
from executive_health_ai.services.grounded_ai import GROUNDED, INSUFFICIENT_EVIDENCE, GroundedAnswerService
from executive_health_ai.services.training_copilot import TRAINING_RUBRICS, TrainingCopilotService
from executive_health_ai.services.training_knowledge import TRAINING_KNOWLEDGE_V1, seed_training_knowledge


class CitingGenerator:
    def generate(self, **kwargs):
        return {"content": "根据已审核培训资料处理。[K1]", "citations": ["K1"]}, {"provider": "test", "model": "test"}


@pytest.fixture()
def training_db() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_training_knowledge(session)
        session.commit()
        yield session


def copilot() -> TrainingCopilotService:
    return TrainingCopilotService(GroundedAnswerService(generator=CitingGenerator()))


def test_training_foundation_contains_twelve_approved_sectioned_documents(training_db):
    assert len(TRAINING_KNOWLEDGE_V1) == 12
    counts = {
        category: training_db.scalar(select(func.count()).select_from(KnowledgeDocument).where(
            KnowledgeDocument.category == category, KnowledgeDocument.review_status == "APPROVED"
        ))
        for category in ("INTERNAL_SOP", "TRAINING_MATERIAL")
    }
    assert counts == {"INTERNAL_SOP": 6, "TRAINING_MATERIAL": 6}
    assert training_db.scalar(select(func.count()).select_from(KnowledgeChunk)) == 59
    assert training_db.scalar(select(func.count()).select_from(KnowledgeReviewAudit)) == 12
    assert all(2 <= len(spec.sections) <= 7 for spec in TRAINING_KNOWLEDGE_V1)


@pytest.mark.parametrize(("question", "expected_title"), [
    ("Yellow Risk 接手后下一步做什么？", "Yellow Risk健管处理SOP"),
    ("什么时候应该提交内部医生？", "健管到内部医生升级规范"),
    ("成员上传体检报告以后我先做什么？", "体检报告审核SOP"),
    ("客户希望调整健康计划怎么办？", "健康计划建立与成员确认规范"),
    ("服务申请通过后下一步是什么？", "服务申请、安排与结果回流SOP"),
    ("Outcome之后怎么办？", "Outcome阶段复盘与下一步规范"),
    ("健康数据很久没有更新怎么办？", "健康数据缺失与陈旧数据处理规范"),
])
def test_golden_training_queries_retrieve_the_expected_approved_sop(training_db, question, expected_title):
    answer = copilot().answer_question(training_db, question)
    assert answer.grounded == GROUNDED
    assert answer.knowledge_citations
    assert answer.knowledge_citations[0].title == expected_title
    document = training_db.get(KnowledgeDocument, answer.knowledge_citations[0].document_id)
    assert document is not None and document.review_status == "APPROVED"


def test_used_citation_is_the_actual_retrieved_chunk(training_db):
    answer = copilot().answer_question(training_db, "Yellow Risk接手以后如何处理？")
    usage = training_db.scalar(select(KnowledgeUseRecord).where(KnowledgeUseRecord.answer_id == answer.answer_id))
    citation = answer.knowledge_citations[0]
    assert usage is not None
    assert str(citation.chunk_id) in usage.chunk_ids
    assert training_db.get(KnowledgeChunk, citation.chunk_id).content == citation.excerpt


def test_all_training_rubrics_resolve_to_approved_knowledge(training_db):
    service = GroundedAnswerService(generator=CitingGenerator())
    for rubric in TRAINING_RUBRICS.values():
        answer = service.answer(
            training_db, question=rubric.title, knowledge_query=rubric.knowledge_query,
            feature="rubric_contract", categories=("INTERNAL_SOP", "TRAINING_MATERIAL"),
            source_types=("INTERNAL_SOP", "TRAINING_MATERIAL"), audience="health_manager",
        )
        assert answer.grounded == GROUNDED, rubric.rubric_id


def test_uncovered_training_question_still_refuses(training_db):
    answer = copilot().answer_question(training_db, "量子航天器轨道发动机怎么校准？")
    assert answer.grounded == INSUFFICIENT_EVIDENCE
    assert not answer.knowledge_citations


def test_training_layout_is_two_columns_and_stacks_on_narrow_screens():
    source = (Path(__file__).resolve().parents[1] / "src/executive_health_ai/ui/pages/training.py").read_text(encoding="utf-8")
    assert 'st.columns([2, 1], gap="medium")' in source
    assert "@media (max-width: 900px)" in source
    assert "flex-direction: column" in source
    assert "training-copilot-layout" in source
    assert "more-navigation" not in source
