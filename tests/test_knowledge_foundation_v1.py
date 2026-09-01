from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from executive_health_ai.models import Base, KnowledgeDocument, RiskRule
from executive_health_ai.services.knowledge_foundation import (
    FOUNDATION_SOURCES, KnowledgeQueryClassifier, sync_source_registry, update_policies, validate_source_catalog,
)
from executive_health_ai.services.knowledge_retrieval import KnowledgeRetrievalService
from executive_health_ai.services.public_knowledge_seed import seed_public_knowledge
from scripts.run_knowledge_golden_queries import run


ROOT = Path(__file__).resolve().parents[1]


def test_source_registry_contract_and_license_strategies() -> None:
    assert validate_source_catalog() == []
    assert len(FOUNDATION_SOURCES) >= 30
    strategies = {item.content_strategy for item in FOUNDATION_SOURCES}
    assert {"OPEN_FULLTEXT", "PUBLIC_SUMMARY", "METADATA_ONLY", "API_ON_DEMAND", "LINK_ONLY", "DO_NOT_INGEST"} <= strategies
    assert next(item for item in FOUNDATION_SOURCES if item.source_id == "UPTODATE").enabled is False
    assert next(item for item in FOUNDATION_SOURCES if item.source_id == "LOINC").status == "CONDITIONAL"


def test_registry_persists_extended_governance_without_approving_documents() -> None:
    engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
    with Session(engine) as session:
        assert sync_source_registry(session) == len(FOUNDATION_SOURCES)
        medline = session.get(__import__("executive_health_ai.models", fromlist=["KnowledgeSourceRegistry"]).KnowledgeSourceRegistry, "MEDLINEPLUS")
        assert medline.governance_metadata["jurisdiction"] == "US"
        assert session.scalar(select(KnowledgeDocument)) is None


def test_public_seed_defaults_to_pending_and_never_creates_clinical_rule() -> None:
    engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
    with Session(engine) as session:
        docs, chunks = seed_public_knowledge(session)
        assert docs == 12 and chunks == 24
        assert {doc.review_status for doc in session.scalars(select(KnowledgeDocument))} == {"PENDING_REVIEW"}
        assert session.scalar(select(RiskRule)) is None


def test_retrieval_filters_jurisdiction_audience_and_intended_use() -> None:
    engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_public_knowledge(session, approve_for_portfolio=True); session.commit()
        service = KnowledgeRetrievalService()
        assert service.search(session, "HbA1c", audience="MEMBER", jurisdiction="US", intended_use="EXPLANATION")
        assert service.search(session, "HbA1c", audience="MEMBER", jurisdiction="JP", intended_use="EXPLANATION") == []
        assert service.search(session, "HbA1c", audience="ADMIN", jurisdiction="US", intended_use="EXPLANATION") == []
        assert service.search(session, "HbA1c", audience="MEMBER", jurisdiction="US", intended_use="NORMALIZATION") == []


def test_query_router_is_deterministic_and_not_a_risk_decider() -> None:
    classifier = KnowledgeQueryClassifier()
    assert classifier.classify("metformin 标准名称") == "MEDICATION"
    assert classifier.classify("Yellow Risk 接手") == "WORKFLOW"
    assert classifier.classify("Apple HealthKit 数据") == "DEVICE"


def test_source_updates_are_never_auto_approved() -> None:
    policies = update_policies()
    assert len(policies) == len(FOUNDATION_SOURCES)
    assert all(policy.auto_approve is False for policy in policies)


def test_jurisdiction_conflicts_are_preserved_not_silently_merged() -> None:
    engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_public_knowledge(session, approve_for_portfolio=True); session.commit()
        service = KnowledgeRetrievalService()
        us_hits = service.search_routed(session, "身体活动", audience="MEMBER", jurisdiction="US", limit=10)
        jp_hits = service.search_routed(session, "身体活动", audience="MEMBER", jurisdiction="JP", limit=10)
        assert any(hit.document.source_provider == "CDC" for hit in us_hits)
        assert not any(hit.document.source_provider == "CDC" for hit in jp_hits)


def test_golden_query_file_has_at_least_fifty_governed_retrieval_cases() -> None:
    payload = json.loads((ROOT / "knowledge" / "golden_queries.json").read_text(encoding="utf-8"))
    assert len(payload) >= 50
    assert all({"query", "expected_source", "expected_concept", "jurisdiction", "intended_use"} <= set(item) for item in payload)


def test_golden_query_suite() -> None:
    passed, failures = run()
    assert passed >= 50, failures
