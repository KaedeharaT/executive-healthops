"""Exercise five independent SQLite write sessions against a disposable UAT copy.

This is intentionally a limited-UAT diagnostic, not an assertion that SQLite
is suitable for production concurrency.  It copies the configured local
database first and never writes to the active UAT database.
"""

from __future__ import annotations

import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from executive_health_ai.database import get_database_url
from executive_health_ai.models import AuditLog, Patient


def _sqlite_path(url: str) -> Path:
    if not url.startswith("sqlite:///"):
        raise SystemExit("SKIPPED: concurrency smoke is SQLite-specific; use PostgreSQL load tests for PostgreSQL UAT.")
    return Path(url.removeprefix("sqlite:///"))


def main() -> None:
    source = _sqlite_path(get_database_url()).resolve()
    if not source.is_file():
        raise SystemExit("FAILED: source SQLite database does not exist")
    target_dir = Path(".runtime/uat_concurrency"); target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "concurrency_smoke.db"
    shutil.copy2(source, target)
    engine = create_engine(f"sqlite:///{target}", connect_args={"check_same_thread": False}, pool_pre_ping=True)
    with Session(engine) as session:
        member_id = session.scalar(select(Patient.id).limit(1))
    if member_id is None:
        raise SystemExit("SKIPPED: no synthetic member is available for the disposable write test")

    def write_once(index: int) -> None:
        with Session(engine) as session:
            session.add(AuditLog(
                patient_id=member_id,
                actor="uat_concurrency_smoke",
                actor_role="system",
                action="disposable_write",
                entity_type="UAT",
                entity_id=str(uuid4()),
                detail_json={"sequence": index},
            ))
            session.commit()

    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(write_once, range(5)))
    # Count using the list to avoid database-specific SQL in this small smoke
    # check and retain compatibility with the project's SQLAlchemy version.
    with Session(engine) as session:
        count = len(list(session.scalars(select(AuditLog.id).where(AuditLog.actor == "uat_concurrency_smoke"))))
    if count != 5:
        raise SystemExit(f"FAILED: expected 5 disposable writes, observed {count}")
    print("PASS: 5 concurrent disposable SQLite write sessions completed")


if __name__ == "__main__":
    main()
