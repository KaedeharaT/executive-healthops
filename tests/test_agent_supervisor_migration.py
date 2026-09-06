"""Alembic contract for the durable agent orchestration tables."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect


ROOT = Path(__file__).resolve().parents[1]


def test_empty_database_upgrade_head_creates_agent_supervisor_tables(tmp_path: Path) -> None:
    database = tmp_path / "agent-migration.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True, capture_output=True, text=True)
    tables = set(inspect(create_engine(env["DATABASE_URL"])).get_table_names())
    assert {
        "agent_events", "agent_goals", "agent_plans", "agent_plan_steps",
        "agent_approval_requests", "agent_run_traces",
    } <= tables
