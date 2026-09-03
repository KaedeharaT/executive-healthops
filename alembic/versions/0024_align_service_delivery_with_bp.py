"""Align service delivery records with the BP responsibility loop.

Revision ID: 0024_align_service_delivery_with_bp
Revises: 0023_add_ai_feedback_governance
"""

from alembic import op
import sqlalchemy as sa


revision = "0024_align_service_delivery_with_bp"
down_revision = "0023_add_ai_feedback_governance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("service_requests") as batch:
        batch.add_column(sa.Column("service_provider", sa.String(200), nullable=True))
        batch.add_column(sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("completion_evidence", sa.Text(), nullable=True))
        batch.add_column(sa.Column("next_action", sa.Text(), nullable=True))
        batch.create_index("ix_service_requests_sla_due_at", ["sla_due_at"])
    op.execute("UPDATE service_requests SET next_action = '健康管理师确认下一步' WHERE next_action IS NULL")
    op.execute("UPDATE service_requests SET status = 'IN_SERVICE' WHERE status = 'IN_PROGRESS'")


def downgrade() -> None:
    op.execute("UPDATE service_requests SET status = 'IN_PROGRESS' WHERE status = 'IN_SERVICE'")
    with op.batch_alter_table("service_requests") as batch:
        batch.drop_index("ix_service_requests_sla_due_at")
        batch.drop_column("next_action")
        batch.drop_column("completion_evidence")
        batch.drop_column("sla_due_at")
        batch.drop_column("service_provider")
