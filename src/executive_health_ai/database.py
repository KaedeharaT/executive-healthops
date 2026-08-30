"""Database engine and session configuration."""

from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DATABASE_URL = "sqlite:///./executive_health_ai.db"


def get_database_url() -> str:
    """Return the configured database URL, defaulting to local SQLite."""
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def create_database_engine(database_url: str | None = None) -> Engine:
    """Create an engine compatible with SQLite now and PostgreSQL later."""
    url = database_url or get_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
