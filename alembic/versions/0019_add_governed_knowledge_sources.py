"""Add governed public knowledge-source registry and provenance fields.

Revision ID: 0019_add_governed_knowledge_sources
Revises: 0018_add_member_service_operations
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_add_governed_knowledge_sources"
down_revision = "0018_add_member_service_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_source_registry",
        sa.Column("source_code", sa.String(64), primary_key=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("official_url", sa.Text(), nullable=False),
        sa.Column("api_type", sa.String(64), nullable=False),
        sa.Column("license_or_terms", sa.Text(), nullable=False),
        sa.Column("attribution_requirement", sa.Text()),
        sa.Column("commercial_use_note", sa.Text()),
        sa.Column("cache_policy", sa.String(128), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("version", sa.String(128)),
        sa.Column("retrieved_at", sa.DateTime(timezone=True)),
        sa.Column("review_status", sa.String(32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    with op.batch_alter_table("knowledge_documents") as batch:
        batch.add_column(sa.Column("source_provider", sa.String(64)))
        batch.add_column(sa.Column("source_external_id", sa.String(256)))
        batch.add_column(sa.Column("source_url", sa.Text()))
        batch.add_column(sa.Column("source_version", sa.String(128)))
        batch.add_column(sa.Column("retrieved_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("license_note", sa.Text()))
        batch.add_column(sa.Column("attribution", sa.Text()))
        batch.add_column(sa.Column("content_hash", sa.String(64)))
        batch.create_index("ix_knowledge_documents_source_provider", ["source_provider"])
        batch.create_index("ix_knowledge_documents_source_external_id", ["source_external_id"])
        batch.create_index("ix_knowledge_documents_content_hash", ["content_hash"])
    op.create_table(
        "knowledge_use_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("output_type", sa.String(64), nullable=False),
        sa.Column("output_reference", sa.String(256), nullable=False),
        sa.Column("knowledge_document_id", sa.Uuid(), sa.ForeignKey("knowledge_documents.id"), nullable=False),
        sa.Column("source_title", sa.String(256), nullable=False),
        sa.Column("source_provider", sa.String(64)),
        sa.Column("source_version", sa.String(128)),
        sa.Column("source_retrieved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("output_type", "output_reference", "knowledge_document_id", name="uq_knowledge_use_output_document"),
    )


def downgrade() -> None:
    op.drop_table("knowledge_use_records")
    with op.batch_alter_table("knowledge_documents") as batch:
        batch.drop_index("ix_knowledge_documents_content_hash")
        batch.drop_index("ix_knowledge_documents_source_external_id")
        batch.drop_index("ix_knowledge_documents_source_provider")
        batch.drop_column("content_hash")
        batch.drop_column("attribution")
        batch.drop_column("license_note")
        batch.drop_column("retrieved_at")
        batch.drop_column("source_version")
        batch.drop_column("source_url")
        batch.drop_column("source_external_id")
        batch.drop_column("source_provider")
    op.drop_table("knowledge_source_registry")
