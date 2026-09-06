"""Idempotent ingestion of compact business events for the agent supervisor."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.agent.events import EVENT_TYPES
from executive_health_ai.models import AgentEvent


class EventService:
    def publish(self, session: Session, *, event_type: str, member_id: UUID, source_type: str, source_id: str | UUID, payload_summary: str | None = None, metadata: dict[str, Any] | None = None, dedup_key: str | None = None) -> tuple[AgentEvent, bool]:
        if event_type not in EVENT_TYPES:
            raise ValueError("Unsupported agent event type.")
        source = str(source_id)
        key = dedup_key or f"{event_type}:{source_type}:{source}"
        existing = session.scalar(select(AgentEvent).where(AgentEvent.dedup_key == key))
        if existing:
            return existing, False
        event = AgentEvent(event_type=event_type, member_id=member_id, source_type=source_type, source_id=source, payload_summary=(payload_summary or "")[:1000] or None, metadata_json=metadata or {}, dedup_key=key)
        session.add(event)
        session.flush()
        return event, True
