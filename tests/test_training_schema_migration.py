from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import shutil
from datetime import datetime, timedelta, timezone

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session
from executive_health_ai.models import (
    HealthAssessment, KnowledgeChunk, KnowledgeDocument, Observation, Patient,
    ReportExtractionCandidate, TrainingSession,
)
from executive_health_ai.services.baseline_visualization import BaselineVisualizationService
from executive_health_ai.services.health_visualization import HealthVisualizationService
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


def test_portfolio_builder_rebuild_creates_training_tables(tmp_path):
    # The builder deliberately restricts its target to ROOT/data. Exercise the
    # real entry point in a disposable project, never the developer's Demo DB.
    project = tmp_path / 'portfolio-project'
    project.mkdir()
    for name in ('scripts', 'alembic', 'docs'):
        shutil.copytree(ROOT / name, project / name, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(ROOT / 'alembic.ini', project / 'alembic.ini')
    result = subprocess.run(
        [sys.executable, str(project / "scripts" / "build_portfolio_demo.py"), "--rebuild"],
        cwd=project, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    database = project / "data" / "portfolio_demo.db"
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
        member = session.scalar(select(Patient).where(Patient.external_id == "portfolio-demo-executive-a"))
        assert member is not None
        from executive_health_ai.models.management_workflow import IntakeAssessment
        workflow_member = session.scalar(select(Patient).where(Patient.external_id == "synthetic-real-workflow-v1"))
        assert workflow_member is not None
        intake = session.scalar(select(IntakeAssessment).where(IntakeAssessment.patient_id == workflow_member.id))
        assert intake is not None and intake.status == "DRAFT"
        baseline = session.scalar(select(HealthAssessment).where(
            HealthAssessment.patient_id == member.id,
            HealthAssessment.cycle_year == 2026,
            HealthAssessment.status == "CONFIRMED",
        ))
        assert baseline is not None
        required = {"weight", "bmi", "ldl_c", "hba1c", "systolic_bp", "diastolic_bp"}
        candidates = set(session.scalars(select(ReportExtractionCandidate.canonical_code).where(
            ReportExtractionCandidate.patient_id == member.id,
            ReportExtractionCandidate.status == "CONFIRMED",
            ReportExtractionCandidate.canonical_code.in_(required),
        )))
        assert candidates == required
        follow_ups = list(session.scalars(select(Observation).where(
            Observation.patient_id == member.id,
            Observation.source == "confirmed_synthetic_follow_up",
        )))
        assert len(follow_ups) == 19
        recent = [row for row in follow_ups if row.observed_at >= datetime.now(timezone.utc)-timedelta(days=30)]
        assert sum(row.metric_code == "systolic_bp" for row in recent) >= 3
        assert sum(row.metric_code == "diastolic_bp" for row in recent) >= 3
        report_trends = HealthVisualizationService().report_series(session, member.id)
        assert {row.code for row in report_trends if row.has_trend} == required
        view = BaselineVisualizationService().build(session, member.id, cycle_year=2026)
        assert len(view.metrics) == 6
        assert sum(trend.has_follow_up for trend in view.trends) == 6
        assert sum(len(trend.points) for trend in view.trends) == 27  # Two confirmed synthetic report observations extend existing metric history.
        assert len(view.comparisons) == 6
        assert len(view.coverage) == 6
        assert view.covered_count >= 4
        assert all(metric.source_candidate_id for metric in view.metrics)
        empty_member = Patient(external_id="portfolio-empty-isolation", display_name="空资料成员", timezone="Asia/Tokyo")
        session.add(empty_member); session.flush()
        assert BaselineVisualizationService().available_years(session, empty_member.id) == ()
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


def test_portfolio_launcher_preserves_database_and_requires_explicit_maintenance():
    source = (ROOT / "scripts" / "start_portfolio_demo.ps1").read_text(encoding="utf-8")
    assert "--ensure-current" not in source
    assert "-m alembic" not in source
    assert "record_care_responsibility.py" not in source
    assert "Launcher does not rebuild databases" in source
    assert "invoke_healthops_launcher.ps1" in source
