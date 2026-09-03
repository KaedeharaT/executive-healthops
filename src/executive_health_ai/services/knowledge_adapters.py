"""Local and partner knowledge adapters with a source-complete result contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import re
from typing import Callable, Protocol
from urllib import request
from uuid import UUID

from sqlalchemy.orm import Session

from executive_health_ai.services.knowledge_retrieval import KnowledgeRetrievalService


class KnowledgeAdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class KnowledgeResult:
    external_chunk_id: str
    title: str
    content: str
    section: str
    source_name: str
    organization: str
    source_url: str
    version: str
    retrieved_at: datetime
    license_note: str
    document_id: UUID | None = None
    chunk_id: UUID | None = None

    def __post_init__(self) -> None:
        for field in ("external_chunk_id", "title", "content", "section", "source_name", "organization", "source_url", "version", "license_note"):
            if not str(getattr(self, field)).strip():
                raise KnowledgeAdapterError(f"Partner knowledge result missing {field}.")
        if self.retrieved_at.tzinfo is None:
            raise KnowledgeAdapterError("Partner knowledge retrieved_at must be timezone-aware.")


class KnowledgeAdapter(Protocol):
    def search(self, query: str, *, category: str | None = None, audience: str | None = None, jurisdiction: str | None = None, top_k: int = 5) -> list[KnowledgeResult]: ...


_QUERY_REDACTIONS = (
    re.compile(r"[\u4e00-\u9fff][某Xx]{1,3}"),
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,36}\b"),
)


def deidentify_knowledge_query(query: str) -> str:
    sanitized = query.strip()
    for pattern in _QUERY_REDACTIONS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    return sanitized[:500]


class LocalKnowledgeAdapter:
    def __init__(self, session: Session, retrieval: KnowledgeRetrievalService | None = None) -> None:
        self.session = session
        self.retrieval = retrieval or KnowledgeRetrievalService()

    def search(self, query: str, *, category: str | None = None, audience: str | None = None, jurisdiction: str | None = None, top_k: int = 5) -> list[KnowledgeResult]:
        hits = self.retrieval.search(
            self.session, query, category=category, audience=audience,
            jurisdiction=jurisdiction, limit=max(1, min(top_k, 8)),
        )
        return [KnowledgeResult(
            external_chunk_id=str(hit.chunk.id), title=hit.document.title,
            content=hit.chunk.content, section=hit.chunk.source_location or hit.chunk.heading or "未标章节",
            source_name=hit.document.source_name,
            organization=hit.document.attribution or hit.document.source_name,
            source_url=hit.document.source_url or hit.document.source_reference or "local://approved-knowledge",
            version=hit.document.source_version or hit.document.version,
            retrieved_at=hit.document.retrieved_at or datetime.now(timezone.utc),
            license_note=hit.document.license_note or "Internal governed knowledge",
            document_id=hit.document.id, chunk_id=hit.chunk.id,
        ) for hit in hits]


Transport = Callable[[str, dict[str, object], dict[str, str], float], object]


def _http_transport(url: str, payload: dict[str, object], headers: dict[str, str], timeout: float) -> object:
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=encoded, headers={**headers, "Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=timeout) as response:  # nosec B310 - URL is explicit operator configuration
        return json.loads(response.read().decode("utf-8"))


class ExternalPartnerKnowledgeAdapter:
    """Consume partner chunks without sending member context or caching fulltext."""

    def __init__(self, *, api_base: str | None = None, api_key: str | None = None, timeout_seconds: float = 5.0, transport: Transport | None = None) -> None:
        self.api_base = (api_base or os.getenv("KNOWLEDGE_API_BASE", "")).rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("KNOWLEDGE_API_KEY", "")
        self.timeout_seconds = timeout_seconds
        self.transport = transport or _http_transport

    def search(self, query: str, *, category: str | None = None, audience: str | None = None, jurisdiction: str | None = None, top_k: int = 5) -> list[KnowledgeResult]:
        if not self.api_base:
            raise KnowledgeAdapterError("Partner knowledge provider is not configured.")
        payload: dict[str, object] = {
            "query": deidentify_knowledge_query(query), "category": category,
            "audience": audience, "jurisdiction": jurisdiction,
            "top_k": max(1, min(top_k, 8)),
        }
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            raw = self.transport(f"{self.api_base}/search", payload, headers, self.timeout_seconds)
        except Exception as exc:
            raise KnowledgeAdapterError("Partner knowledge provider is unavailable.") from exc
        rows = raw.get("results") if isinstance(raw, dict) else raw
        if not isinstance(rows, list):
            raise KnowledgeAdapterError("Partner knowledge response must contain a results list.")
        results: list[KnowledgeResult] = []
        for row in rows[: payload["top_k"]]:
            if not isinstance(row, dict):
                raise KnowledgeAdapterError("Partner knowledge result must be an object.")
            try:
                retrieved_at = datetime.fromisoformat(str(row["retrieved_at"]).replace("Z", "+00:00"))
                results.append(KnowledgeResult(
                    external_chunk_id=str(row["external_chunk_id"]), title=str(row["title"]),
                    content=str(row["content"]), section=str(row["section"]),
                    source_name=str(row["source_name"]), organization=str(row["organization"]),
                    source_url=str(row["source_url"]), version=str(row["version"]),
                    retrieved_at=retrieved_at, license_note=str(row["license_note"]),
                ))
            except (KeyError, TypeError, ValueError) as exc:
                raise KnowledgeAdapterError("Partner knowledge result has incomplete source metadata.") from exc
        return results


class FallbackKnowledgeAdapter:
    def __init__(self, primary: KnowledgeAdapter, fallback: KnowledgeAdapter) -> None:
        self.primary = primary
        self.fallback = fallback

    def search(self, query: str, **filters) -> list[KnowledgeResult]:
        try:
            results = self.primary.search(query, **filters)
        except KnowledgeAdapterError:
            results = []
        return results or self.fallback.search(query, **filters)


class RoutedKnowledgeAdapter:
    """Prefer local SOPs and partner medical knowledge without mixing policy."""

    LOCAL_FIRST = {"INTERNAL_SOP", "COMMUNICATION", "SERVICE_SOP", "AI_SAFETY", "PRIVACY"}

    def __init__(self, *, local: KnowledgeAdapter, partner: KnowledgeAdapter) -> None:
        self.local = local
        self.partner = partner

    def search(self, query: str, *, category: str | None = None, audience: str | None = None, jurisdiction: str | None = None, top_k: int = 5) -> list[KnowledgeResult]:
        filters = {"category": category, "audience": audience, "jurisdiction": jurisdiction, "top_k": top_k}
        first, second = (self.local, self.partner) if category in self.LOCAL_FIRST else (self.partner, self.local)
        return FallbackKnowledgeAdapter(first, second).search(query, **filters)


def knowledge_adapter_from_env(session: Session) -> KnowledgeAdapter:
    """Build the configured adapter without exposing its API key."""
    local = LocalKnowledgeAdapter(session)
    provider = os.getenv("KNOWLEDGE_PROVIDER", "local").strip().lower()
    if provider == "local":
        return local
    if provider == "partner":
        return RoutedKnowledgeAdapter(local=local, partner=ExternalPartnerKnowledgeAdapter())
    raise KnowledgeAdapterError("KNOWLEDGE_PROVIDER must be local or partner.")
