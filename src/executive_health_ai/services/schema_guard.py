"""Small schema readiness checks for optional application surfaces."""

from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.orm import Session


TRAINING_SCHEMA_MESSAGE = "培训数据结构尚未初始化，请完成数据库升级后重试。"


class DatabaseSchemaOutdated(RuntimeError):
    """Raised before a feature writes against a database with an old schema."""


def require_training_schema(session: Session) -> None:
    """Fail clearly before Training Copilot attempts any persistence."""
    if not inspect(session.get_bind()).has_table("training_sessions"):
        raise DatabaseSchemaOutdated(TRAINING_SCHEMA_MESSAGE)
