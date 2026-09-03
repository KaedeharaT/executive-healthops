from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from executive_health_ai.models import Base, KnowledgeUseRecord
from executive_health_ai.services.grounded_ai import GROUNDED, INSUFFICIENT_EVIDENCE, GroundedAnswerService
from executive_health_ai.services.knowledge import KnowledgeService
from executive_health_ai.services.knowledge_adapters import (
    ExternalPartnerKnowledgeAdapter, FallbackKnowledgeAdapter, KnowledgeAdapterError,
    LocalKnowledgeAdapter,
)


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def add_local(db: Session) -> None:
    service = KnowledgeService()
    document = service.create_document(
        db, title="Yellow Risk健管处理SOP", category="INTERNAL_SOP", source_type="INTERNAL_SOP",
        source_name="HealthOps Internal", source_url="https://example.invalid/internal",
        version="v1.0", content_text="# 首次确认\nYellow Risk接手后核对依据、负责人和下一动作。",
        review_status="DRAFT", metadata_json={"audience": ["health_manager"], "jurisdiction": ["GLOBAL"]},
    )
    service.approve_document(db, document, "synthetic reviewer")


def partner_row() -> dict[str, object]:
    return {
        "external_chunk_id": "partner-chunk-1", "title": "Official LDL Education",
        "content": "LDL-C is interpreted with the wider health context.", "section": "Overview",
        "source_name": "Partner Knowledge", "organization": "Official Health Organization",
        "source_url": "https://example.org/ldl", "version": "2026-01",
        "retrieved_at": "2026-09-03T00:00:00Z", "license_note": "Public summary with attribution",
    }


class FakeGenerator:
    def __init__(self) -> None:
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return {"content": "依据合作方资料解释。[K1]", "citations": ["K1"]}, {"provider": "test", "model": "test"}


def test_local_knowledge_adapter_returns_approved_chunk(db):
    add_local(db)
    results = LocalKnowledgeAdapter(db).search("Yellow Risk接手", category="INTERNAL_SOP", audience="health_manager")
    assert results and results[0].title == "Yellow Risk健管处理SOP"
    assert results[0].external_chunk_id and results[0].organization
    assert results[0].document_id is not None and results[0].chunk_id is not None


def test_partner_adapter_sends_only_deidentified_query_and_filters():
    captured = {}
    def transport(url, payload, headers, timeout):
        captured.update({"url": url, "payload": payload, "headers": headers, "timeout": timeout})
        return {"results": [partner_row()]}
    adapter = ExternalPartnerKnowledgeAdapter(api_base="https://partner.example", api_key="secret", transport=transport)
    results = adapter.search("蔡XX，手机号13812345678，LDL-C升高健康教育", category="PATIENT_EDUCATION", audience="MEMBER", jurisdiction="CN")
    assert results[0].external_chunk_id == "partner-chunk-1"
    sent = str(captured["payload"])
    assert "蔡XX" not in sent and "13812345678" not in sent
    assert "member_id" not in sent and "report" not in captured["payload"]


def test_partner_timeout_falls_back_to_local_approved_knowledge(db):
    add_local(db)
    def timeout(*args):
        raise TimeoutError("synthetic timeout")
    partner = ExternalPartnerKnowledgeAdapter(api_base="https://partner.example", transport=timeout)
    adapter = FallbackKnowledgeAdapter(partner, LocalKnowledgeAdapter(db))
    results = adapter.search("Yellow Risk接手", category="INTERNAL_SOP", audience="health_manager")
    assert results and results[0].source_name == "HealthOps Internal"


@pytest.mark.parametrize("payload", [{"unexpected": []}, {"results": [{"title": "missing provenance"}]}])
def test_partner_bad_or_source_incomplete_response_is_rejected(payload):
    adapter = ExternalPartnerKnowledgeAdapter(api_base="https://partner.example", transport=lambda *args: payload)
    with pytest.raises(KnowledgeAdapterError):
        adapter.search("LDL")


def test_partner_result_drives_grounded_answer_and_external_chunk_audit(db):
    adapter = ExternalPartnerKnowledgeAdapter(
        api_base="https://partner.example", transport=lambda *args: {"results": [partner_row()]},
    )
    answer = GroundedAnswerService(generator=FakeGenerator()).answer_with_adapter(
        db, question="什么是LDL？", feature="member_health_explanation", adapter=adapter,
        category="PATIENT_EDUCATION", audience="MEMBER", jurisdiction="CN",
    )
    assert answer.grounded == GROUNDED
    assert answer.knowledge_citations[0].source_url == "https://example.org/ldl"
    usage = db.scalar(select(KnowledgeUseRecord))
    assert usage and usage.knowledge_document_id is None
    assert usage.external_chunk_ids == ["partner-chunk-1"]
    assert usage.citation_snapshot_json[0]["title"] == "Official LDL Education"


def test_local_adapter_grounded_answer_keeps_internal_document_and_chunk_audit(db):
    add_local(db)
    answer = GroundedAnswerService(generator=FakeGenerator()).answer_with_adapter(
        db, question="Yellow Risk接手后做什么？", feature="workflow_guidance",
        adapter=LocalKnowledgeAdapter(db), category="INTERNAL_SOP", audience="health_manager",
    )
    usage = db.scalar(select(KnowledgeUseRecord))
    assert answer.grounded == GROUNDED
    assert answer.knowledge_citations[0].document_id is not None
    assert usage and usage.knowledge_document_id is not None
    assert usage.chunk_ids and usage.external_chunk_ids == []


def test_partner_no_source_preserves_refusal_and_does_not_call_model(db):
    fake = FakeGenerator()
    adapter = ExternalPartnerKnowledgeAdapter(
        api_base="https://partner.example", transport=lambda *args: {"results": []},
    )
    answer = GroundedAnswerService(generator=fake).answer_with_adapter(
        db, question="uncovered", feature="member_health_explanation", adapter=adapter,
    )
    assert answer.grounded == INSUFFICIENT_EVIDENCE and fake.calls == []
