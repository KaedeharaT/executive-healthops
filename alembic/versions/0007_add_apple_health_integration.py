"""Add Apple Health sync metadata and source-deletion exclusion.

Revision ID: 0007_add_apple_health_integration
Revises: 0006_add_unified_health_data_gateway
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
revision: str = "0007_add_apple_health_integration"
down_revision: Union[str, Sequence[str], None] = "0006_add_unified_health_data_gateway"
branch_labels = None
depends_on = None
def upgrade() -> None:
    with op.batch_alter_table("ingestion_jobs") as batch:
        batch.add_column(sa.Column("installation_id", sa.String(128)))
        batch.add_column(sa.Column("external_sync_id", sa.String(128)))
        batch.create_index("ix_ingestion_jobs_external_sync_id", ["external_sync_id"])
    with op.batch_alter_table("raw_ingestion_records") as batch:
        batch.add_column(sa.Column("event_type", sa.String(32), nullable=False, server_default="UPSERT"))
    with op.batch_alter_table("observations") as batch:
        batch.add_column(sa.Column("source_deleted", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("excluded_from_analysis", sa.Boolean(), nullable=False, server_default=sa.false()))
def downgrade() -> None:
    with op.batch_alter_table("observations") as batch:
        batch.drop_column("excluded_from_analysis"); batch.drop_column("source_deleted")
    with op.batch_alter_table("raw_ingestion_records") as batch: batch.drop_column("event_type")
    with op.batch_alter_table("ingestion_jobs") as batch:
        batch.drop_index("ix_ingestion_jobs_external_sync_id"); batch.drop_column("external_sync_id"); batch.drop_column("installation_id")
