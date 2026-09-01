"""Add extensible governance metadata to knowledge sources.

Revision ID: 0022_add_knowledge_source_governance
Revises: 0021_add_grounded_ai_training
"""

from alembic import op
import sqlalchemy as sa


revision = "0022_add_knowledge_source_governance"
down_revision = "0021_add_grounded_ai_training"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns("knowledge_source_registry")}
    if "governance_metadata" not in columns:
        with op.batch_alter_table("knowledge_source_registry") as batch:
            batch.add_column(sa.Column("governance_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns("knowledge_source_registry")}
    if "governance_metadata" in columns:
        with op.batch_alter_table("knowledge_source_registry") as batch:
            batch.drop_column("governance_metadata")
