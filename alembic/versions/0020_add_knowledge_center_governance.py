"""Add chunk retrieval and governance audit records for the knowledge center.

Revision ID: 0020_add_knowledge_center_governance
Revises: 0019_add_governed_knowledge_sources
"""

from alembic import op
import sqlalchemy as sa


revision = "0020_add_knowledge_center_governance"
down_revision = "0019_add_governed_knowledge_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite DDL can commit a preceding batch operation before a later batch
    # fails.  These guards make a rerun safe on a developer database without
    # touching any existing knowledge records.
    inspector = sa.inspect(op.get_bind())
    source_columns = {item["name"] for item in inspector.get_columns("knowledge_source_registry")}
    source_indexes = {item["name"] for item in inspector.get_indexes("knowledge_source_registry")}
    if {"organization", "status"} - source_columns or "ix_knowledge_source_registry_status" not in source_indexes:
        with op.batch_alter_table("knowledge_source_registry") as batch:
            if "organization" not in source_columns:
                batch.add_column(sa.Column("organization", sa.String(128)))
            if "status" not in source_columns:
                batch.add_column(sa.Column("status", sa.String(32), nullable=False, server_default="CANDIDATE"))
            if "ix_knowledge_source_registry_status" not in source_indexes:
                batch.create_index("ix_knowledge_source_registry_status", ["status"])

    document_columns = {item["name"] for item in inspector.get_columns("knowledge_documents")}
    document_indexes = {item["name"] for item in inspector.get_indexes("knowledge_documents")}
    if {"review_comment", "review_due_at", "supersedes_id", "superseded_by_id"} - document_columns:
        with op.batch_alter_table("knowledge_documents") as batch:
            if "review_comment" not in document_columns:
                batch.add_column(sa.Column("review_comment", sa.Text()))
            if "review_due_at" not in document_columns:
                batch.add_column(sa.Column("review_due_at", sa.Date()))
            if "supersedes_id" not in document_columns:
                batch.add_column(sa.Column("supersedes_id", sa.Uuid(), sa.ForeignKey("knowledge_documents.id", name="fk_knowledge_documents_supersedes")))
            if "superseded_by_id" not in document_columns:
                batch.add_column(sa.Column("superseded_by_id", sa.Uuid(), sa.ForeignKey("knowledge_documents.id", name="fk_knowledge_documents_superseded_by")))
            if "ix_knowledge_documents_review_due_at" not in document_indexes:
                batch.create_index("ix_knowledge_documents_review_due_at", ["review_due_at"])
            if "ix_knowledge_documents_supersedes_id" not in document_indexes:
                batch.create_index("ix_knowledge_documents_supersedes_id", ["supersedes_id"])
            if "ix_knowledge_documents_superseded_by_id" not in document_indexes:
                batch.create_index("ix_knowledge_documents_superseded_by_id", ["superseded_by_id"])

    usage_columns = {item["name"] for item in inspector.get_columns("knowledge_use_records")}
    usage_indexes = {item["name"] for item in inspector.get_indexes("knowledge_use_records")}
    if {"chunk_ids", "feature", "member_id", "model", "request_context_hash"} - usage_columns:
        with op.batch_alter_table("knowledge_use_records") as batch:
            if "chunk_ids" not in usage_columns:
                batch.add_column(sa.Column("chunk_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
            if "feature" not in usage_columns:
                batch.add_column(sa.Column("feature", sa.String(64)))
            if "member_id" not in usage_columns:
                batch.add_column(sa.Column("member_id", sa.Uuid(), sa.ForeignKey("patients.id", name="fk_knowledge_use_records_member")))
            if "model" not in usage_columns:
                batch.add_column(sa.Column("model", sa.String(128)))
            if "request_context_hash" not in usage_columns:
                batch.add_column(sa.Column("request_context_hash", sa.String(64)))
            if "ix_knowledge_use_records_member_id" not in usage_indexes:
                batch.create_index("ix_knowledge_use_records_member_id", ["member_id"])

    if not inspector.has_table("knowledge_chunks"):
        op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("knowledge_document_id", sa.Uuid(), sa.ForeignKey("knowledge_documents.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(256)),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_location", sa.String(256)),
        sa.Column("content_length", sa.Integer(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("knowledge_document_id", "chunk_index", name="uq_knowledge_chunk_position"),
        )
        op.create_index("ix_knowledge_chunks_knowledge_document_id", "knowledge_chunks", ["knowledge_document_id"])
    if not inspector.has_table("knowledge_review_audits"):
        op.create_table(
        "knowledge_review_audits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("knowledge_document_id", sa.Uuid(), sa.ForeignKey("knowledge_documents.id"), nullable=False),
        sa.Column("reviewer", sa.String(128), nullable=False),
        sa.Column("previous_status", sa.String(32)),
        sa.Column("new_status", sa.String(32), nullable=False),
        sa.Column("review_comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_knowledge_review_audits_knowledge_document_id", "knowledge_review_audits", ["knowledge_document_id"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_review_audits_knowledge_document_id", table_name="knowledge_review_audits")
    op.drop_table("knowledge_review_audits")
    op.drop_index("ix_knowledge_chunks_knowledge_document_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    with op.batch_alter_table("knowledge_use_records") as batch:
        batch.drop_index("ix_knowledge_use_records_member_id")
        batch.drop_column("request_context_hash")
        batch.drop_column("model")
        batch.drop_column("member_id")
        batch.drop_column("feature")
        batch.drop_column("chunk_ids")
    with op.batch_alter_table("knowledge_documents") as batch:
        batch.drop_index("ix_knowledge_documents_superseded_by_id")
        batch.drop_index("ix_knowledge_documents_supersedes_id")
        batch.drop_index("ix_knowledge_documents_review_due_at")
        batch.drop_column("superseded_by_id")
        batch.drop_column("supersedes_id")
        batch.drop_column("review_due_at")
        batch.drop_column("review_comment")
    with op.batch_alter_table("knowledge_source_registry") as batch:
        batch.drop_index("ix_knowledge_source_registry_status")
        batch.drop_column("status")
        batch.drop_column("organization")
