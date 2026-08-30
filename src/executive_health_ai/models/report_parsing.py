"""Human-reviewed health-check report parsing records.

These models retain parser evidence separately from canonical health facts.
Candidates are never clinical conclusions and do not enter risk evaluation until
an authorised person explicitly confirms an observation candidate.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from executive_health_ai.models.base import Base, UTCDateTime, utc_now


class ReportExtractionRun(Base):
    __tablename__ = "report_extraction_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", index=True)
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_registry_version: Mapped[str] = mapped_column(String(64), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    detected_hospital: Mapped[str | None] = mapped_column(String(256), nullable=True)
    detected_report_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detected_report_date: Mapped[date | None] = mapped_column(nullable=True)
    page_count: Mapped[int | None] = mapped_column(nullable=True)
    has_text_layer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_scanned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    adapter_used: Mapped[str | None] = mapped_column(String(128), nullable=True)
    template_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ocr_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    llm_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    llm_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    llm_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    llm_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    llm_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_NEEDED")
    llm_call_count: Mapped[int] = mapped_column(nullable=False, default=0)
    llm_success_count: Mapped[int] = mapped_column(nullable=False, default=0)
    llm_failure_count: Mapped[int] = mapped_column(nullable=False, default=0)
    llm_total_duration_ms: Mapped[int] = mapped_column(nullable=False, default=0)
    llm_processed_sections: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    llm_failure_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    candidate_count: Mapped[int] = mapped_column(nullable=False, default=0)
    high_confidence_count: Mapped[int] = mapped_column(nullable=False, default=0)
    medium_confidence_count: Mapped[int] = mapped_column(nullable=False, default=0)
    low_confidence_count: Mapped[int] = mapped_column(nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(nullable=False, default=0)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)

    @property
    def rule_candidate_count(self) -> int:
        """Persisted rule-derived candidate total, including table extraction."""
        return int(self.metadata_json.get("rule_candidate_count", 0))

    @property
    def llm_candidate_count(self) -> int:
        """Persisted local LLM candidate total; distinct from HTTP call count."""
        return int(self.metadata_json.get("llm_candidate_count", 0))


class ReportExtractionCandidate(Base):
    __tablename__ = "report_extraction_candidates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    extraction_run_id: Mapped[UUID] = mapped_column(ForeignKey("report_extraction_runs.id"), nullable=False, index=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    candidate_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    canonical_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    raw_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    raw_value: Mapped[str | None] = mapped_column(String(256), nullable=True)
    normalized_value: Mapped[str | None] = mapped_column(String(256), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference_range: Mapped[str | None] = mapped_column(String(128), nullable=True)
    abnormal_flag: Mapped[str | None] = mapped_column(String(32), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_data_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="LOW")
    extraction_method: Mapped[str] = mapped_column(String(32), nullable=False)
    source_page: Mapped[int | None] = mapped_column(nullable=True)
    source_section: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING_REVIEW", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)
