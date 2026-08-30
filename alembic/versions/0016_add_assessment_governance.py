"""Add explicit HealthAssessment governance and provenance.

Revision ID: 0016_add_assessment_governance
Revises: 0015_add_management_signal_details
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_add_assessment_governance"
down_revision = "0015_add_management_signal_details"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind(); columns = {item["name"] for item in sa.inspect(bind).get_columns("health_assessments")}
    if "status" not in columns:
        op.add_column("health_assessments", sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"))
        op.create_index("ix_health_assessments_status", "health_assessments", ["status"])
    if "reviewed_by" not in columns:
        op.add_column("health_assessments", sa.Column("reviewed_by", sa.String(length=128), nullable=True))
    if "confirmed_at" not in columns:
        op.add_column("health_assessments", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    if "source_references_json" not in columns:
        op.add_column("health_assessments", sa.Column("source_references_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))


def downgrade() -> None:
    op.drop_column("health_assessments", "source_references_json")
    op.drop_column("health_assessments", "confirmed_at")
    op.drop_column("health_assessments", "reviewed_by")
    op.drop_index("ix_health_assessments_status", table_name="health_assessments")
    op.drop_column("health_assessments", "status")
