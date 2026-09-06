"""Migration coverage for annual baseline fields and legacy data preservation."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


def _alembic(database: Path, revision: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
    subprocess.run([str(PYTHON), "-m", "alembic", "upgrade", revision], cwd=ROOT, env=env, check=True, capture_output=True, text=True)


def test_upgrade_adds_versioned_baseline_fields_and_preserves_legacy_snapshot(tmp_path: Path) -> None:
    database = tmp_path / "baseline-migration.db"
    _alembic(database, "0025_add_agent_supervisor_v1")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO patients (id, external_id, timezone, created_at, updated_at) "
            "VALUES ('11111111111111111111111111111111', 'legacy-baseline', 'Asia/Tokyo', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
        connection.execute(text(
            "INSERT INTO health_assessments "
            "(id, patient_id, assessment_type, version, title, summary, baseline_json, created_by, status, source_references_json, assessed_at, created_at) "
            "VALUES ('22222222222222222222222222222222', '11111111111111111111111111111111', 'BASELINE', 1, 'Legacy', 'Legacy snapshot', '{}', 'manager', 'CONFIRMED', '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
    _alembic(database, "head")
    columns = {column["name"] for column in inspect(engine).get_columns("health_assessments")}
    assert {"cycle_year", "collection_due_at", "medical_review_required", "parent_assessment_id", "snapshot_hash"} <= columns
    with engine.connect() as connection:
        row = connection.execute(text("SELECT title, status, version, updated_at FROM health_assessments")).one()
    assert row.title == "Legacy" and row.status == "CONFIRMED" and row.version == 1 and row.updated_at is not None
