"""Add universal health-check report extraction runs and candidates.

Revision ID: 0010_add_universal_health_report_parser
Revises: 0009_add_risk_triage_engine
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_add_universal_health_report_parser"
down_revision = "0009_add_risk_triage_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_extraction_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("parser_version", sa.String(64), nullable=False),
        sa.Column("canonical_registry_version", sa.String(64), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("file_type", sa.String(32), nullable=False),
        sa.Column("detected_hospital", sa.String(256)),
        sa.Column("detected_report_type", sa.String(128)),
        sa.Column("detected_report_date", sa.Date()),
        sa.Column("page_count", sa.Integer()),
        sa.Column("has_text_layer", sa.Boolean(), nullable=False),
        sa.Column("is_scanned", sa.Boolean(), nullable=False),
        sa.Column("adapter_used", sa.String(128)),
        sa.Column("template_fingerprint", sa.String(128)),
        sa.Column("ocr_used", sa.Boolean(), nullable=False),
        sa.Column("llm_used", sa.Boolean(), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("high_confidence_count", sa.Integer(), nullable=False),
        sa.Column("medium_confidence_count", sa.Integer(), nullable=False),
        sa.Column("low_confidence_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_report_extraction_runs_document_id", "report_extraction_runs", ["document_id"])
    op.create_index("ix_report_extraction_runs_patient_id", "report_extraction_runs", ["patient_id"])
    op.create_index("ix_report_extraction_runs_status", "report_extraction_runs", ["status"])
    op.create_index("ix_report_extraction_runs_file_hash", "report_extraction_runs", ["file_hash"])
    op.create_table(
        "report_extraction_candidates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("extraction_run_id", sa.Uuid(), sa.ForeignKey("report_extraction_runs.id"), nullable=False),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("candidate_type", sa.String(32), nullable=False),
        sa.Column("canonical_code", sa.String(100)),
        sa.Column("raw_name", sa.String(256)),
        sa.Column("raw_value", sa.String(256)),
        sa.Column("normalized_value", sa.String(256)),
        sa.Column("unit", sa.String(64)),
        sa.Column("reference_range", sa.String(128)),
        sa.Column("abnormal_flag", sa.String(32)),
        sa.Column("summary", sa.Text()),
        sa.Column("structured_data_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.String(16), nullable=False),
        sa.Column("extraction_method", sa.String(32), nullable=False),
        sa.Column("source_page", sa.Integer()),
        sa.Column("source_section", sa.String(64)),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reviewed_by", sa.String(128)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("extraction_run_id", "document_id", "patient_id", "candidate_type", "canonical_code", "status"):
        op.create_index(f"ix_report_extraction_candidates_{column}", "report_extraction_candidates", [column])


def downgrade() -> None:
    op.drop_table("report_extraction_candidates")
    op.drop_table("report_extraction_runs")
