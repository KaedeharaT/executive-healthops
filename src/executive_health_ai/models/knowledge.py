"""Governed, non-member-specific knowledge assets for HealthOps."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from executive_health_ai.models.base import Base, UTCDateTime, utc_now


class KnowledgeDocument(Base):
    """A reviewed professional resource, never a member health-data record."""

    __tablename__ = "knowledge_documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_name: Mapped[str] = mapped_column(String(256), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_provider: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_external_id: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    license_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    attribution: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    file_reference: Mapped[str | None] = mapped_column(String(512), nullable=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1.0")
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="zh-CN")
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_due_at: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    supersedes_id: Mapped[UUID | None] = mapped_column(ForeignKey("knowledge_documents.id"), nullable=True, index=True)
    superseded_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("knowledge_documents.id"), nullable=True, index=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_REQUIRED")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)


class KnowledgeSourceRegistry(Base):
    """Governed external source metadata; registering a source does not approve content."""

    __tablename__ = "knowledge_source_registry"

    source_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    organization: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    official_url: Mapped[str] = mapped_column(Text, nullable=False)
    api_type: Mapped[str] = mapped_column(String(64), nullable=False)
    license_or_terms: Mapped[str] = mapped_column(Text, nullable=False)
    attribution_requirement: Mapped[str | None] = mapped_column(Text, nullable=True)
    commercial_use_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    cache_policy: Mapped[str] = mapped_column(String(128), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="CANDIDATE", index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="CANDIDATE", index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)


class KnowledgeUseRecord(Base):
    """An auditable record of knowledge actually supplied to a future AI output."""

    __tablename__ = "knowledge_use_records"
    __table_args__ = (UniqueConstraint("output_type", "output_reference", "knowledge_document_id", name="uq_knowledge_use_output_document"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    output_type: Mapped[str] = mapped_column(String(64), nullable=False)
    output_reference: Mapped[str] = mapped_column(String(256), nullable=False)
    knowledge_document_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_documents.id"), nullable=False, index=True)
    source_title: Mapped[str] = mapped_column(String(256), nullable=False)
    source_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_retrieved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    chunk_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    feature: Mapped[str | None] = mapped_column(String(64), nullable=True)
    member_id: Mapped[UUID | None] = mapped_column(ForeignKey("patients.id"), nullable=True, index=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    request_context_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)


class KnowledgeChunk(Base):
    """A source-located, bounded excerpt used for approved-knowledge retrieval."""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (UniqueConstraint("knowledge_document_id", "chunk_index", name="uq_knowledge_chunk_position"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    knowledge_document_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_documents.id"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str | None] = mapped_column(String(256), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_location: Mapped[str | None] = mapped_column(String(256), nullable=True)
    content_length: Mapped[int] = mapped_column(Integer, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)


class KnowledgeReviewAudit(Base):
    """Append-only governance history for approval, return and supersession."""

    __tablename__ = "knowledge_review_audits"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    knowledge_document_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_documents.id"), nullable=False, index=True)
    reviewer: Mapped[str] = mapped_column(String(128), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
