"""Non-destructive SQLite backup/restore smoke check for limited UAT."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def _sqlite_path(url: str) -> Path:
    if not url.startswith("sqlite:///"):
        raise SystemExit("SKIPPED: backup smoke currently supports SQLite only")
    return Path(url.removeprefix("sqlite:///"))


def main() -> None:
    database_url = os.getenv("DATABASE_URL", "sqlite:///./executive_health_ai.db")
    source = _sqlite_path(database_url).resolve()
    if not source.is_file():
        raise SystemExit("FAILED: source SQLite database does not exist")
    target_dir = Path(".runtime/uat_backup"); target_dir.mkdir(parents=True, exist_ok=True)
    backup = target_dir / "executive_health_ai_uat_backup.db"
    restored = target_dir / "executive_health_ai_uat_restore.db"
    for target in (backup, restored):
        if target.exists():
            target.unlink()
    with sqlite3.connect(source) as source_connection, sqlite3.connect(backup) as backup_connection:
        source_connection.backup(backup_connection)
    with sqlite3.connect(backup) as backup_connection, sqlite3.connect(restored) as restored_connection:
        backup_connection.backup(restored_connection)
    with sqlite3.connect(restored) as restored_connection:
        restored_connection.execute("SELECT 1 FROM patients LIMIT 1").fetchone()
        table_count = restored_connection.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    print(f"PASS: backup={backup.name} restore={restored.name} tables={table_count}")


if __name__ == "__main__":
    main()
