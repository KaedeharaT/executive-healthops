from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


ROOT = Path(__file__).resolve().parents[1]


def migrate(database: Path, revision: str) -> None:
    config = Config(str(ROOT / "alembic.ini"))
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
    try:
        command.upgrade(config, revision)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


def test_upgrade_from_0022_adds_feedback_governance_without_rewriting_0021(tmp_path):
    database = tmp_path / "old.db"
    migrate(database, "0022_add_knowledge_source_governance")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    assert inspect(engine).has_table("training_sessions")
    assert not inspect(engine).has_table("feedback_records")
    engine.dispose()

    migrate(database, "head")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    inspector = inspect(engine)
    assert inspector.has_table("training_sessions")
    assert {"feedback_records", "feedback_dataset_versions", "model_version_registry", "risk_rule_review_candidates"} <= set(inspector.get_table_names())
    usage = {item["name"]: item for item in inspector.get_columns("knowledge_use_records")}
    assert usage["knowledge_document_id"]["nullable"] is True
    assert "external_chunk_ids" in usage
    engine.dispose()
