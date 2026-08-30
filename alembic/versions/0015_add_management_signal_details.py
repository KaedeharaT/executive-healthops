"""Add auditable lifestyle-management signal details.

Revision ID: 0015_add_management_signal_details
Revises: 0014_add_longitudinal_health_operations
"""
from alembic import op
import sqlalchemy as sa


revision = "0015_add_management_signal_details"
down_revision = "0014_add_longitudinal_health_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite cannot add a non-null column with CURRENT_TIMESTAMP as a default.
    # Add nullable timestamps, backfill only schema metadata from created_at,
    # then use batch mode to enforce the final schema.  Column checks also make
    # a retry safe if a local SQLite migration was interrupted mid-upgrade.
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("management_signals")}
    if "signal_category" not in existing:
        op.add_column("management_signals", sa.Column("signal_category", sa.String(length=64), nullable=False, server_default="LIFESTYLE_MANAGEMENT"))
    if "metric_code" not in existing:
        op.add_column("management_signals", sa.Column("metric_code", sa.String(length=100), nullable=False, server_default="unknown"))
    if "severity" not in existing:
        op.add_column("management_signals", sa.Column("severity", sa.String(length=32), nullable=False, server_default="WATCH"))
    if "first_detected_at" not in existing:
        op.add_column("management_signals", sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=True))
    if "last_detected_at" not in existing:
        op.add_column("management_signals", sa.Column("last_detected_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(sa.text("UPDATE management_signals SET first_detected_at = created_at WHERE first_detected_at IS NULL"))
    op.execute(sa.text("UPDATE management_signals SET last_detected_at = updated_at WHERE last_detected_at IS NULL"))
    with op.batch_alter_table("management_signals") as batch:
        batch.alter_column("first_detected_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch.alter_column("last_detected_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    indexes = {item["name"] for item in sa.inspect(bind).get_indexes("management_signals")}
    if "ix_management_signals_metric_code" not in indexes:
        op.create_index("ix_management_signals_metric_code", "management_signals", ["metric_code"])


def downgrade() -> None:
    op.drop_index("ix_management_signals_metric_code", table_name="management_signals")
    op.drop_column("management_signals", "last_detected_at")
    op.drop_column("management_signals", "first_detected_at")
    op.drop_column("management_signals", "severity")
    op.drop_column("management_signals", "metric_code")
    op.drop_column("management_signals", "signal_category")
