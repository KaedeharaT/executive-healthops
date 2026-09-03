from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


ROOT = Path(__file__).resolve().parents[1]


def _migrate(database: Path, revision: str) -> None:
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


def test_bp_service_delivery_fields_upgrade_from_previous_head(tmp_path: Path) -> None:
    database = tmp_path / "bp-upgrade.db"
    _migrate(database, "0023_add_ai_feedback_governance")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    before = {column["name"] for column in inspect(engine).get_columns("service_requests")}
    assert "sla_due_at" not in before
    engine.dispose()

    _migrate(database, "head")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    after = {column["name"] for column in inspect(engine).get_columns("service_requests")}
    assert {"service_provider", "sla_due_at", "completion_evidence", "next_action"} <= after
    assert "ix_service_requests_sla_due_at" in {index["name"] for index in inspect(engine).get_indexes("service_requests")}
    engine.dispose()
