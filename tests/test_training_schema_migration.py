from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session
from streamlit.testing.v1 import AppTest

from executive_health_ai.models import KnowledgeChunk, KnowledgeDocument, TrainingSession
from executive_health_ai.services.schema_guard import DatabaseSchemaOutdated, require_training_schema
from executive_health_ai.services.training_copilot import TrainingCopilotService
from scripts.build_portfolio_demo import _verify_training_schema


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


def test_old_revision_upgrades_without_data_loss_and_copilot_session_persists(tmp_path):
    database = tmp_path / "old.db"
    migrate(database, "0020_add_knowledge_center_governance")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    assert not inspect(engine).has_table("training_sessions")
    engine.dispose()

    migrate(database, "head")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with Session(engine) as session:
        record = TrainingCopilotService.start_session(session, mode="Q&A")
        record_id = record.id
        session.commit()
    with Session(engine) as session:
        reloaded = session.scalar(select(TrainingSession).where(TrainingSession.id == record_id))
        assert reloaded is not None and reloaded.mode == "Q&A" and reloaded.status == "IN_PROGRESS"
    engine.dispose()


def test_portfolio_schema_verifier_accepts_migrated_database(tmp_path):
    database = tmp_path / "portfolio_demo.db"
    migrate(database, "head")
    _verify_training_schema(database)


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
            KnowledgeDocument.source_provider == "PORTFOLIO_TRAINING",
            KnowledgeDocument.review_status == "APPROVED",
        ))
        chunks = session.scalar(select(func.count()).select_from(KnowledgeChunk).join(KnowledgeDocument).where(
            KnowledgeDocument.source_provider == "PORTFOLIO_TRAINING",
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


def test_training_page_shows_friendly_old_schema_message_without_traceback(tmp_path):
    database = tmp_path / "unmigrated.db"
    app = AppTest.from_string(
        "from sqlalchemy import create_engine\n"
        "from sqlalchemy.orm import sessionmaker\n"
        "from executive_health_ai.ui.pages.training import render_training_copilot\n"
        f"engine=create_engine('sqlite:///{database.as_posix()}')\n"
        "render_training_copilot(sessionmaker(bind=engine))\n"
    )
    app.run(timeout=20)
    assert not app.exception
    assert any("培训数据结构尚未初始化" in str(item.value) for item in app.error)


def test_portfolio_launcher_upgrades_before_starting_services():
    source = (ROOT / "scripts" / "start_portfolio_demo.ps1").read_text(encoding="utf-8")
    assert source.index("-m alembic upgrade head") < source.index("Start-Process -FilePath $python")
