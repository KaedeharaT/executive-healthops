"""Validate and build the governed HealthOps Knowledge Foundation V1."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from executive_health_ai.database import SessionLocal
from executive_health_ai.services.knowledge_foundation import FOUNDATION_SOURCES, sync_source_registry, validate_source_catalog
from executive_health_ai.services.public_knowledge_seed import PUBLIC_SEEDS, seed_public_knowledge
from executive_health_ai.services.healthops_internal_knowledge import seed_healthops_internal_knowledge

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try: stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError): pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--approve-public-demo", action="store_true", help="Only for an isolated synthetic Portfolio database")
    args = parser.parse_args()
    if errors := validate_source_catalog():
        raise SystemExit("Registry invalid: " + "; ".join(errors))
    strategies = Counter(item.content_strategy for item in FOUNDATION_SOURCES)
    print(f"Sources: {len(FOUNDATION_SOURCES)}; public seed documents: {len(PUBLIC_SEEDS)}")
    print("Strategies:", dict(sorted(strategies.items())))
    for item in FOUNDATION_SOURCES:
        print(f"- {item.source_id}: {item.status} / {item.content_strategy} / {item.license}")
    coverage = json.loads((ROOT / "knowledge" / "coverage.json").read_text(encoding="utf-8"))
    print("Coverage domains:", len(coverage["domains"]))
    if args.dry_run: return 0
    with SessionLocal() as session:
        sync_source_registry(session)
        seed_healthops_internal_knowledge(session)
        docs, chunks = seed_public_knowledge(session, approve_for_portfolio=args.approve_public_demo)
        session.commit()
    print(f"Imported documents: {docs}; chunks: {chunks}; public review status: {'APPROVED demo' if args.approve_public_demo else 'PENDING_REVIEW'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
