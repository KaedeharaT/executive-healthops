from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session
from executive_health_ai.models import KnowledgeChunk, KnowledgeDocument, TrainingSession
from executive_health_ai.services.schema_guard import DatabaseSchemaOutdated, require_training_schema


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


def test_empty_database_upgrade_head_creates_training_schema(tmp_path):
    database = tmp_path / "empty.db"
    migrate(database, "head")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    assert inspect(engine).has_table("training_sessions")
    assert "answer_id" in {column["name"] for column in inspect(engine).get_columns("knowledge_use_records")}
    engine.dispose()


def test_old_revision_upgrades_without_data_loss_and_legacy_training_table_remains_usable(tmp_path):
    database = tmp_path / "old.db"
    migrate(database, "0020_add_knowledge_center_governance")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    assert not inspect(engine).has_table("training_sessions")
    engine.dispose()

    migrate(database, "head")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with Session(engine) as session:
        record = TrainingSession(mode="Q&A", status="IN_PROGRESS")
        session.add(record)
        session.flush()
        record_id = record.id
        session.commit()
    with Session(engine) as session:
        reloaded = session.scalar(select(TrainingSession).where(TrainingSession.id == record_id))
        assert reloaded is not None and reloaded.mode == "Q&A" and reloaded.status == "IN_PROGRESS"
    engine.dispose()


def test_portfolio_builder_rebuild_creates_training_tables():
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_portfolio_demo.py"), "--rebuild"],
        cwd=ROOT, check=True, capture_output=True, text=True, timeout=90,
    )
    database = ROOT / "data" / "portfolio_demo.db"
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    assert inspect(engine).has_table("training_sessions")
    with Session(engine) as session:
        approved = session.scalar(select(func.count()).select_from(KnowledgeDocument).where(
            KnowledgeDocument.source_provider == "HEALTHOPS_INTERNAL",
            KnowledgeDocument.review_status == "APPROVED",
        ))
        chunks = session.scalar(select(func.count()).select_from(KnowledgeChunk).join(KnowledgeDocument).where(
            KnowledgeDocument.source_provider == "HEALTHOPS_INTERNAL",
        ))
        assert approved == 12 and chunks == 59
    engine.dispose()


def test_schema_guard_rejects_old_database_before_insert(tmp_path):
    database = tmp_path / "old.db"
    migrate(database, "0020_add_knowledge_center_governance")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with Session(engine) as session:
        try:
            require_training_schema(session)
        except DatabaseSchemaOutdated as exc:
            assert "数据库升级" in str(exc)
        else:
            raise AssertionError("Old schema was not rejected")
    engine.dispose()


def test_portfolio_launcher_upgrades_before_starting_services():
    source = (ROOT / "scripts" / "start_portfolio_demo.ps1").read_text(encoding="utf-8")
    assert source.index("-m alembic upgrade head") < source.index("Start-Process -FilePath $python")
