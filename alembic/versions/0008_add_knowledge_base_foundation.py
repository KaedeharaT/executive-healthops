"""Compatibility migration for the governed knowledge-base foundation.

Revision ID: 0008_add_knowledge_base_foundation
Revises: 0007_add_apple_health_integration
"""
from alembic import op
import sqlalchemy as sa
revision="0008_add_knowledge_base_foundation"; down_revision="0007_add_apple_health_integration"; branch_labels=None; depends_on=None
def upgrade():
    op.create_table("knowledge_documents",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("title",sa.String(256),nullable=False),sa.Column("category",sa.String(64),nullable=False),sa.Column("summary",sa.Text()),sa.Column("content_text",sa.Text()),sa.Column("source_type",sa.String(64),nullable=False),sa.Column("source_name",sa.String(256),nullable=False),sa.Column("source_reference",sa.Text()),sa.Column("file_reference",sa.String(512)),sa.Column("version",sa.String(64),nullable=False),sa.Column("tags",sa.JSON(),nullable=False),sa.Column("language",sa.String(16),nullable=False),sa.Column("review_status",sa.String(32),nullable=False),sa.Column("reviewed_by",sa.String(128)),sa.Column("reviewed_at",sa.DateTime(timezone=True)),sa.Column("effective_date",sa.Date()),sa.Column("expires_at",sa.Date()),sa.Column("processing_status",sa.String(32),nullable=False),sa.Column("is_active",sa.Boolean(),nullable=False),sa.Column("metadata_json",sa.JSON(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
def downgrade(): op.drop_table("knowledge_documents")
