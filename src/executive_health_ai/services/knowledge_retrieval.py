"""Auditable first-pass keyword retrieval for approved knowledge chunks only.

This intentionally avoids a vector database and never sends an entire library
to a model.  A future hybrid/embedding layer can implement the same result
contract without changing governance rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.models import KnowledgeChunk, KnowledgeDocument
from executive_health_ai.services.knowledge import KnowledgeService


@dataclass(frozen=True)
class KnowledgeRetrievalHit:
    document: KnowledgeDocument
    chunk: KnowledgeChunk
    score: int

    def citation(self) -> dict[str, str | None]:
        """A UI-safe citation based only on the exact retrieved chunk."""
        return {
            "title": self.document.title,
            "source": self.document.source_name,
            "source_url": self.document.source_url,
            "version": self.document.source_version or self.document.version,
            "retrieved_at": self.document.retrieved_at.isoformat() if self.document.retrieved_at else None,
            "location": self.chunk.source_location or self.chunk.heading,
            "excerpt": self.chunk.content[:500],
        }


class KnowledgeRetrievalService:
    """Stable keyword/BM25-ready boundary for formal AI knowledge use."""

    def search(
        self, session: Session, query: str, *, category: str | None = None,
        source_provider: str | None = None, language: str | None = None, limit: int = 6,
    ) -> list[KnowledgeRetrievalHit]:
        phrase = query.strip().lower()
        if not phrase:
            return []
        # Safe one-time backfill for previously approved, text-bearing assets.
        KnowledgeService().ensure_approved_chunks(session)
        statement = select(KnowledgeChunk, KnowledgeDocument).join(
            KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.knowledge_document_id
        ).where(
            KnowledgeDocument.is_active.is_(True),
            KnowledgeDocument.review_status == "APPROVED",
        )
        if category:
            statement = statement.where(KnowledgeDocument.category == category)
        if source_provider:
            statement = statement.where(KnowledgeDocument.source_provider == source_provider)
        if language:
            statement = statement.where(KnowledgeDocument.language == language)

        tokens = [token for token in phrase.split() if token] or [phrase]
        hits: list[KnowledgeRetrievalHit] = []
        for chunk, document in session.execute(statement).all():
            if not KnowledgeService._eligible_for_formal_ai(document):
                continue
            title = document.title.lower()
            body = f"{chunk.heading or ''}\n{chunk.content}".lower()
            score = sum(8 for token in tokens if token == title) + sum(4 for token in tokens if token in title)
            score += sum(body.count(token) for token in tokens)
            if score:
                hits.append(KnowledgeRetrievalHit(document=document, chunk=chunk, score=score))
        return sorted(hits, key=lambda item: (-item.score, item.document.title, item.chunk.chunk_index))[:limit]
