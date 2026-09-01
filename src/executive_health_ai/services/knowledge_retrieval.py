"""Auditable first-pass keyword retrieval for approved knowledge chunks only.

This intentionally avoids a vector database and never sends an entire library
to a model.  A future hybrid/embedding layer can implement the same result
contract without changing governance rules.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

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
        categories: tuple[str, ...] = (), source_types: tuple[str, ...] = (),
        audience: str | None = None,
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
        if categories:
            statement = statement.where(KnowledgeDocument.category.in_(categories))
        if source_types:
            statement = statement.where(KnowledgeDocument.source_type.in_(source_types))

        tokens = [token for token in re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]{2,}", phrase) if token]
        # Chinese questions often contain no whitespace.  Bigrams make the
        # deterministic first-pass retrieval useful without inventing semantic
        # similarity or adding a vector-store dependency.
        expanded: list[str] = []
        for token in tokens or [phrase]:
            expanded.append(token)
            if any("\u4e00" <= char <= "\u9fff" for char in token) and len(token) > 2:
                expanded.extend(token[index:index + 2] for index in range(len(token) - 1))
        # Common question scaffolding must not make an unrelated query look
        # grounded merely because an SOP also contains words such as “流程”.
        stop_tokens = {
            "一个", "一些", "什么", "怎么", "如何", "应该", "当前", "以后",
            "知识", "知识库", "没有", "完全", "覆盖", "问题", "流程", "告诉",
        }
        tokens = [token for token in dict.fromkeys(expanded) if token not in stop_tokens]
        if not tokens:
            return []
        hits: list[KnowledgeRetrievalHit] = []
        for chunk, document in session.execute(statement).all():
            if not KnowledgeService._eligible_for_formal_ai(document):
                continue
            audiences = (document.metadata_json or {}).get("audience", [])
            if audience and audience not in audiences and "all" not in audiences:
                continue
            title = document.title.lower()
            body = f"{chunk.heading or ''}\n{chunk.content}".lower()
            score = sum(8 for token in tokens if token == title) + sum(4 for token in tokens if token in title)
            score += sum(body.count(token) for token in tokens)
            if score:
                hits.append(KnowledgeRetrievalHit(document=document, chunk=chunk, score=score))
        return sorted(hits, key=lambda item: (-item.score, item.document.title, item.chunk.chunk_index))[:limit]
