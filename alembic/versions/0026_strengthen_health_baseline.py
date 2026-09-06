"""Strengthen annual, versioned and evidence-bound health baselines.

Revision ID: 0026_strengthen_health_baseline
Revises: 0025_add_agent_supervisor_v1
"""

from alembic import op
import sqlalchemy as sa


revision = "0026_strengthen_health_baseline"
down_revision = "0025_add_agent_supervisor_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("health_assessments") as batch:
        batch.add_column(sa.Column("management_cycle_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("cycle_year", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("cycle_start", sa.Date(), nullable=True))
        batch.add_column(sa.Column("cycle_end", sa.Date(), nullable=True))
        batch.add_column(sa.Column("collection_started_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("collection_due_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("collection_closed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("medical_review_required", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("medical_reviewed_by", sa.String(128), nullable=True))
        batch.add_column(sa.Column("medical_reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("parent_assessment_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("amendment_type", sa.String(32), nullable=True))
        batch.add_column(sa.Column("amendment_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("amended_by", sa.String(128), nullable=True))
        batch.add_column(sa.Column("superseded_by_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("snapshot_hash", sa.String(64), nullable=True))
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key("fk_health_assessment_cycle", "annual_health_accounts", ["management_cycle_id"], ["id"])
        batch.create_foreign_key("fk_health_assessment_parent", "health_assessments", ["parent_assessment_id"], ["id"])
        batch.create_foreign_key("fk_health_assessment_superseded", "health_assessments", ["superseded_by_id"], ["id"])
        batch.create_index("ix_health_assessments_management_cycle_id", ["management_cycle_id"])
        batch.create_index("ix_health_assessments_cycle_year", ["cycle_year"])
        batch.create_index("ix_health_assessments_parent_assessment_id", ["parent_assessment_id"])
        batch.create_index("ix_health_assessment_cycle_status", ["patient_id", "cycle_year", "status"])
        batch.create_unique_constraint(
            "uq_health_assessment_cycle_version",
            ["patient_id", "assessment_type", "cycle_year", "version"],
        )
    op.execute("UPDATE health_assessments SET updated_at = created_at WHERE updated_at IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("health_assessments") as batch:
        batch.drop_constraint("uq_health_assessment_cycle_version", type_="unique")
        batch.drop_index("ix_health_assessment_cycle_status")
        batch.drop_index("ix_health_assessments_parent_assessment_id")
        batch.drop_index("ix_health_assessments_cycle_year")
        batch.drop_index("ix_health_assessments_management_cycle_id")
        batch.drop_constraint("fk_health_assessment_superseded", type_="foreignkey")
        batch.drop_constraint("fk_health_assessment_parent", type_="foreignkey")
        batch.drop_constraint("fk_health_assessment_cycle", type_="foreignkey")
        batch.drop_column("updated_at")
        batch.drop_column("snapshot_hash")
        batch.drop_column("superseded_by_id")
        batch.drop_column("amended_by")
        batch.drop_column("amendment_reason")
        batch.drop_column("amendment_type")
        batch.drop_column("parent_assessment_id")
        batch.drop_column("medical_reviewed_at")
        batch.drop_column("medical_reviewed_by")
        batch.drop_column("medical_review_required")
        batch.drop_column("collection_closed_at")
        batch.drop_column("collection_due_at")
        batch.drop_column("collection_started_at")
        batch.drop_column("cycle_end")
        batch.drop_column("cycle_start")
        batch.drop_column("cycle_year")
        batch.drop_column("management_cycle_id")
