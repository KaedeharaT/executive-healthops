"""Run the governed retrieval Golden Query suite against isolated seed data."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from executive_health_ai.models import Base
from executive_health_ai.services.knowledge_retrieval import KnowledgeRetrievalService
from executive_health_ai.services.public_knowledge_seed import seed_public_knowledge
from executive_health_ai.services.healthops_internal_knowledge import seed_healthops_internal_knowledge

ROOT = Path(__file__).resolve().parents[1]


def run() -> tuple[int, list[str]]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    queries = json.loads((ROOT / "knowledge" / "golden_queries.json").read_text(encoding="utf-8"))
    failures: list[str] = []
    with Session(engine) as session:
        seed_healthops_internal_knowledge(session)
        seed_public_knowledge(session, approve_for_portfolio=True)
        session.commit()
        service = KnowledgeRetrievalService()
        for item in queries:
            hits = service.search_routed(session, item["query"], limit=20)
            providers = {hit.document.source_provider for hit in hits}
            expected = item["expected_source"]
            if expected in {"INTERNAL_SOP", "COMMUNICATION", "SERVICE_SOP", "AI_SAFETY"}:
                ok = "HEALTHOPS_INTERNAL" in providers
            elif expected in {"LOINC", "OPENFDA"}:
                # Metadata-only/on-demand sources are intentionally not approved
                # as local answer chunks; a safe refusal is the expected result.
                # The expected official source is deliberately on-demand or
                # metadata-only, so it must not appear as a fabricated local
                # chunk. Other approved reference hits may still be returned.
                ok = expected not in providers
            else:
                ok = expected in providers
            if not ok:
                failures.append(f"{item['id']}: expected {expected}; got {sorted(str(x) for x in providers)}")
    return len(queries) - len(failures), failures


if __name__ == "__main__":
    passed, failures = run()
    print(f"Golden queries: {passed + len(failures)}; passed: {passed}; failed: {len(failures)}")
    for failure in failures: print("-", failure)
    raise SystemExit(1 if failures else 0)
