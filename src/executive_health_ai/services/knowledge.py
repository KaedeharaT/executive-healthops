"""Small, auditable knowledge-asset service; retrieval is separate and clinical automation is prohibited."""

from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import re
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from executive_health_ai.models import (
    KnowledgeChunk, KnowledgeDocument, KnowledgeReviewAudit,
    KnowledgeSourceRegistry, KnowledgeUseRecord,
)
from executive_health_ai.services.knowledge_sources import (
    SOURCE_DEFINITIONS, KnowledgeSearchResult, provider_for,
)


class KnowledgeService:
    """Create and govern reusable professional material independently of members."""

    def create_document(
        self,
        session: Session,
        *,
        title: str,
        category: str,
        source_type: str,
        source_name: str,
        summary: str | None = None,
        content_text: str | None = None,
        source_reference: str | None = None,
        source_provider: str | None = None,
        source_external_id: str | None = None,
        source_url: str | None = None,
        source_version: str | None = None,
        retrieved_at: datetime | None = None,
        license_note: str | None = None,
        attribution: str | None = None,
        file_reference: str | None = None,
        version: str = "v1.0",
        tags: Iterable[str] = (),
        review_status: str = "DRAFT",
        processing_status: str = "NOT_REQUIRED",
        review_due_at: date | None = None,
        effective_date: date | None = None,
        expires_at: date | None = None,
        supersedes_id=None,
        metadata_json: dict | None = None,
    ) -> KnowledgeDocument:
        normalized_content = content_text.strip() if content_text else None
        document = KnowledgeDocument(
            title=title.strip(),
            category=category,
            summary=summary.strip() if summary else None,
            content_text=normalized_content,
            source_type=source_type,
            source_name=source_name.strip(),
            source_reference=source_reference.strip() if source_reference else None,
            source_provider=source_provider,
            source_external_id=source_external_id,
            source_url=source_url,
            source_version=source_version,
            retrieved_at=retrieved_at,
            license_note=license_note,
            attribution=attribution,
            content_hash=sha256((normalized_content or summary or title).encode("utf-8")).hexdigest(),
            file_reference=file_reference,
            version=version.strip() or "v1.0",
            tags=[tag.strip() for tag in tags if tag.strip()],
            review_status=review_status,
            processing_status=processing_status,
            review_due_at=review_due_at,
            effective_date=effective_date,
            expires_at=expires_at,
            supersedes_id=supersedes_id,
            metadata_json=metadata_json or {},
        )
        session.add(document)
        session.flush()
        return document

    @staticmethod
    def _source_text(document: KnowledgeDocument) -> str:
        return (document.content_text or document.summary or "").strip()

    @staticmethod
    def _split_chunks(content: str, *, default_heading: str, maximum_length: int = 1_000) -> list[tuple[str | None, str, str]]:
        """Bound excerpts conservatively and retain the nearest document heading."""
        heading = default_heading
        chunks: list[tuple[str | None, str, str]] = []
        current = ""
        for line in content.splitlines() or [content]:
            value = line.strip()
            if not value:
                continue
            if value.startswith("#"):
                if current:
                    chunks.append((heading, current.strip(), heading))
                    current = ""
                heading = value.lstrip("#").strip() or default_heading
                continue
            proposed = f"{current}\n{value}".strip()
            if current and len(proposed) > maximum_length:
                chunks.append((heading, current.strip(), heading))
                current = value
            else:
                current = proposed
        if current:
            chunks.append((heading, current.strip(), heading))
        if not chunks and content.strip():
            plain = re.sub(r"\s+", " ", content).strip()
            chunks = [(default_heading, plain[index:index + maximum_length], default_heading) for index in range(0, len(plain), maximum_length)]
        return chunks

    def create_chunks(self, session: Session, document: KnowledgeDocument) -> list[KnowledgeChunk]:
        """Replace derived chunks only; the original document remains unchanged."""
        session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.knowledge_document_id == document.id))
        content = self._source_text(document)
        if not content:
            return []
        created: list[KnowledgeChunk] = []
        for index, (heading, content_value, source_location) in enumerate(self._split_chunks(content, default_heading=document.title)):
            chunk = KnowledgeChunk(
                knowledge_document_id=document.id,
                chunk_index=index,
                heading=heading,
                content=content_value,
                source_location=source_location,
                content_length=len(content_value),
                token_estimate=max(1, len(content_value) // 4),
            )
            session.add(chunk)
            created.append(chunk)
        session.flush()
        return created

    def ensure_approved_chunks(self, session: Session) -> int:
        """Backfill bounded chunks for legacy approved assets without changing source text.

        The earlier governed-library release stored approved summaries before
        chunk retrieval existed.  This makes those legitimately approved
        assets searchable under the new retrieval contract.
        """
        created = 0
        documents = list(session.scalars(select(KnowledgeDocument).where(
            KnowledgeDocument.is_active.is_(True), KnowledgeDocument.review_status == "APPROVED"
        )))
        for document in documents:
            if not self._eligible_for_formal_ai(document):
                continue
            has_chunk = session.scalar(select(KnowledgeChunk.id).where(
                KnowledgeChunk.knowledge_document_id == document.id
            ).limit(1))
            if has_chunk is None:
                created += len(self.create_chunks(session, document))
        return created

    def ensure_source_registry(self, session: Session) -> list[KnowledgeSourceRegistry]:
        """Upsert audited metadata only; never downloads external source corpora."""
        rows: list[KnowledgeSourceRegistry] = []
        for definition in SOURCE_DEFINITIONS:
            row = session.get(KnowledgeSourceRegistry, definition.source_code)
            if row is None:
                row = KnowledgeSourceRegistry(source_code=definition.source_code)
                session.add(row)
            row.display_name = definition.display_name
            row.provider = definition.provider
            row.organization = definition.provider
            row.source_type = definition.source_type
            row.official_url = definition.official_url
            row.api_type = definition.api_type
            row.license_or_terms = definition.license_or_terms
            row.attribution_requirement = definition.attribution_requirement
            row.commercial_use_note = definition.commercial_use_note
            row.cache_policy = definition.cache_policy
            row.language = definition.language
            row.version = definition.version
            row.review_status = definition.review_status
            row.status = definition.review_status
            row.enabled = definition.enabled
            rows.append(row)
        session.flush()
        return rows

    def list_sources(self, session: Session) -> list[KnowledgeSourceRegistry]:
        self.ensure_source_registry(session)
        return list(session.scalars(select(KnowledgeSourceRegistry).order_by(KnowledgeSourceRegistry.source_code)))

    def query_source(self, session: Session, source_code: str, query: str, *, limit: int = 5) -> list[KnowledgeSearchResult]:
        """Query an enabled official provider on demand; callers choose whether to cache a result."""
        registry = session.get(KnowledgeSourceRegistry, source_code.upper())
        if registry is None:
            self.ensure_source_registry(session)
            registry = session.get(KnowledgeSourceRegistry, source_code.upper())
        if registry is None or registry.review_status != "APPROVED_SOURCE" or not registry.enabled:
            return []
        return provider_for(source_code).search(query, limit=limit)

    def cache_source_result(self, session: Session, result: KnowledgeSearchResult) -> KnowledgeDocument:
        """Cache a selected result only as a pending-review reference, never an approved rule."""
        existing = session.scalar(select(KnowledgeDocument).where(
            KnowledgeDocument.source_provider == result.source_code,
            KnowledgeDocument.source_external_id == result.external_id,
            KnowledgeDocument.is_active.is_(True),
        ))
        if existing is not None:
            return existing
        return self.create_document(
            session, title=result.title, category=result.category, summary=result.summary,
            source_type="公开医学来源", source_name=result.source_name,
            source_reference=result.source_url, source_provider=result.source_code,
            source_external_id=result.external_id, source_url=result.source_url,
            source_version=result.source_version, retrieved_at=result.retrieved_at,
            license_note=result.license_note, attribution=result.attribution,
            review_status="PENDING_REVIEW", tags=(result.source_code, "公开来源"),
            metadata_json={
                "on_demand_cache": True,
                "no_full_text_mirror": True,
                "structured_metadata": result.structured_metadata,
            },
        )

    def cached_source_result(self, session: Session, result: KnowledgeSearchResult) -> KnowledgeDocument | None:
        """Return a previous saved result so the UI can prevent duplicates."""
        return session.scalar(select(KnowledgeDocument).where(
            KnowledgeDocument.source_provider == result.provider_code,
            KnowledgeDocument.source_external_id == result.external_id,
            KnowledgeDocument.is_active.is_(True),
        ))

    def get_document(self, session: Session, document_id) -> KnowledgeDocument | None:
        return session.get(KnowledgeDocument, document_id)

    def list_documents(
        self, session: Session, *, category: str | None = None, review_status: str | None = None
    ) -> list[KnowledgeDocument]:
        # Archived material remains reviewable in the library.  It is simply
        # excluded from the normal active and AI-eligible collections.
        statement = select(KnowledgeDocument)
        if review_status != "ARCHIVED":
            statement = statement.where(KnowledgeDocument.is_active.is_(True))
        if category:
            statement = statement.where(KnowledgeDocument.category == category)
        if review_status:
            statement = statement.where(KnowledgeDocument.review_status == review_status)
        return list(session.scalars(statement.order_by(KnowledgeDocument.updated_at.desc())))

    def search_documents(
        self, session: Session, query: str, *, category: str | None = None, review_status: str | None = None
    ) -> list[KnowledgeDocument]:
        statement = select(KnowledgeDocument)
        if review_status != "ARCHIVED":
            statement = statement.where(KnowledgeDocument.is_active.is_(True))
        if category:
            statement = statement.where(KnowledgeDocument.category == category)
        if review_status:
            statement = statement.where(KnowledgeDocument.review_status == review_status)
        documents = list(session.scalars(statement.order_by(KnowledgeDocument.updated_at.desc())))
        phrase = query.strip().lower()
        if not phrase:
            return documents
        return [
            document for document in documents
            if phrase in document.title.lower()
            or phrase in (document.summary or "").lower()
            or any(phrase in tag.lower() for tag in document.tags)
        ]

    def _review_audit(
        self, session: Session, document: KnowledgeDocument, *, reviewer: str,
        previous_status: str | None, new_status: str, comment: str | None = None,
    ) -> None:
        session.add(KnowledgeReviewAudit(
            knowledge_document_id=document.id,
            reviewer=reviewer.strip() or "授权审核人",
            previous_status=previous_status,
            new_status=new_status,
            review_comment=comment.strip() if comment else None,
        ))

    @staticmethod
    def _eligible_for_formal_ai(document: KnowledgeDocument) -> bool:
        today = date.today()
        return bool(
            document.is_active
            and document.review_status == "APPROVED"
            and (document.effective_date is None or document.effective_date <= today)
            and (document.review_due_at is None or document.review_due_at >= today)
            and (document.expires_at is None or document.expires_at >= today)
        )

    def approve_document(self, session: Session, document: KnowledgeDocument, reviewer: str, comment: str | None = None) -> None:
        previous_status = document.review_status
        document.review_status = "APPROVED"
        document.reviewed_by = reviewer.strip()
        document.reviewed_at = datetime.now(timezone.utc)
        document.review_comment = comment.strip() if comment else None
        self.create_chunks(session, document)
        self._review_audit(session, document, reviewer=reviewer, previous_status=previous_status, new_status="APPROVED", comment=comment)
        # A replacement remains a draft/pending asset until a human approves it.
        # At that point the prior version is archived rather than overwritten.
        if document.supersedes_id:
            previous = session.get(KnowledgeDocument, document.supersedes_id)
            if previous is not None and previous.is_active:
                previous.superseded_by_id = document.id
                self.archive_document(session, previous, reviewer=reviewer, comment=comment or "已由新版本替代")
        session.flush()

    def archive_document(self, session: Session, document: KnowledgeDocument, reviewer: str = "授权审核人", comment: str | None = None) -> None:
        previous_status = document.review_status
        document.review_status = "ARCHIVED"
        document.is_active = False
        if comment:
            document.review_comment = comment.strip()
        self._review_audit(session, document, reviewer=reviewer, previous_status=previous_status, new_status="ARCHIVED", comment=comment)
        session.flush()

    def reject_document(self, session: Session, document: KnowledgeDocument, reviewer: str, comment: str | None = None) -> None:
        """Keep a reviewable record while preventing formal AI use."""
        previous_status = document.review_status
        document.review_status = "REJECTED"
        document.reviewed_by = reviewer.strip()
        document.reviewed_at = datetime.now(timezone.utc)
        document.review_comment = comment.strip() if comment else None
        self._review_audit(session, document, reviewer=reviewer, previous_status=previous_status, new_status="REJECTED", comment=comment)
        session.flush()

    def supersede_document(
        self, session: Session, *, previous: KnowledgeDocument, replacement: KnowledgeDocument,
        reviewer: str, comment: str | None = None,
    ) -> None:
        """Preserve both versions and remove only the old version from formal AI use."""
        replacement.supersedes_id = previous.id
        previous.superseded_by_id = replacement.id
        self.archive_document(session, previous, reviewer=reviewer, comment=comment or "已由新版本替代")
        session.flush()

    def approved_documents_for_ai(self, session: Session) -> list[KnowledgeDocument]:
        """Formal retrieval boundary: only approved, active, current material is eligible."""
        self.ensure_approved_chunks(session)
        approved = list(session.scalars(select(KnowledgeDocument).where(
            KnowledgeDocument.is_active.is_(True), KnowledgeDocument.review_status == "APPROVED"
        ).order_by(KnowledgeDocument.updated_at.desc())))
        return [
            document for document in approved
            if self._eligible_for_formal_ai(document)
            and session.scalar(select(KnowledgeChunk.id).where(KnowledgeChunk.knowledge_document_id == document.id).limit(1)) is not None
        ]

    def record_ai_usage(
        self, session: Session, *, output_type: str, output_reference: str,
        documents: Iterable[KnowledgeDocument] = (),
        chunks: Iterable[KnowledgeChunk] = (),
        feature: str | None = None,
        member_id=None,
        model: str | None = None,
        request_context_hash: str | None = None,
        session_id: str | None = None,
        conversation_id: str | None = None,
        answer_id: str | None = None,
        retrieved_at: datetime | None = None,
        citation_snapshots: dict | None = None,
    ) -> list[KnowledgeUseRecord]:
        """Record the exact approved chunks actually cited by one AI output."""
        chunk_list = list(chunks)
        document_by_id = {document.id: document for document in documents}
        for chunk in chunk_list:
            document = session.get(KnowledgeDocument, chunk.knowledge_document_id)
            if document is not None:
                document_by_id[document.id] = document
        chunk_ids_by_document: dict = {}
        for chunk in chunk_list:
            chunk_ids_by_document.setdefault(chunk.knowledge_document_id, []).append(str(chunk.id))

        records: list[KnowledgeUseRecord] = []
        for document in document_by_id.values():
            if not self._eligible_for_formal_ai(document):
                raise ValueError("未审核知识资料不得作为 AI 正式引用来源。")
            existing = session.scalar(select(KnowledgeUseRecord).where(
                KnowledgeUseRecord.output_type == output_type,
                KnowledgeUseRecord.output_reference == output_reference,
                KnowledgeUseRecord.knowledge_document_id == document.id,
            ))
            if existing is None:
                existing = KnowledgeUseRecord(
                    output_type=output_type, output_reference=output_reference,
                    knowledge_document_id=document.id, source_title=document.title,
                    source_provider=document.source_provider, source_version=document.source_version or document.version,
                    source_retrieved_at=document.retrieved_at,
                    chunk_ids=chunk_ids_by_document.get(document.id, []),
                    feature=feature, member_id=member_id, model=model,
                    request_context_hash=request_context_hash,
                    session_id=session_id, conversation_id=conversation_id,
                    answer_id=answer_id, retrieved_at=retrieved_at,
                    citation_snapshot_json=(citation_snapshots or {}).get(document.id, []),
                )
                session.add(existing)
            elif chunk_ids_by_document.get(document.id):
                existing.chunk_ids = chunk_ids_by_document[document.id]
                if (citation_snapshots or {}).get(document.id):
                    existing.citation_snapshot_json = (citation_snapshots or {})[document.id]
            records.append(existing)
        session.flush()
        return records

    def review_audits(self, session: Session, document_id) -> list[KnowledgeReviewAudit]:
        return list(session.scalars(select(KnowledgeReviewAudit).where(
            KnowledgeReviewAudit.knowledge_document_id == document_id
        ).order_by(KnowledgeReviewAudit.created_at.desc())))
