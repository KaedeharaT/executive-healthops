"""Add longitudinal HealthOps records and deterministic routing metadata.

Revision ID: 0014_add_longitudinal_health_operations
Revises: 0013_add_yellow_risk_operation_links
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_add_longitudinal_health_operations"
down_revision = "0013_add_yellow_risk_operation_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("risk_rules", sa.Column("recommended_route", sa.String(length=64), nullable=False, server_default="HEALTH_MANAGER"))
    op.add_column("risk_events", sa.Column("recommended_route", sa.String(length=64), nullable=False, server_default="HEALTH_MANAGER"))
    op.add_column("sleep_sessions", sa.Column("stage_segments_json", sa.JSON(), nullable=False, server_default="[]"))
    op.create_table(
        "health_assessments",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id"), nullable=False, index=True),
        sa.Column("assessment_type", sa.String(32), nullable=False), sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False), sa.Column("summary", sa.Text(), nullable=False), sa.Column("baseline_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False), sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "management_rules",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("name", sa.String(200), nullable=False), sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("canonical_code", sa.String(100), nullable=False), sa.Column("condition_type", sa.String(64), nullable=False), sa.Column("threshold_config", sa.JSON(), nullable=False), sa.Column("window_config", sa.JSON(), nullable=False),
        sa.Column("recommended_route", sa.String(64), nullable=False), sa.Column("version", sa.String(64), nullable=False), sa.Column("review_status", sa.String(32), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_management_rules_code", "management_rules", ["code"])
    op.create_index("ix_management_rules_canonical_code", "management_rules", ["canonical_code"])
    op.create_index("ix_management_rules_review_status", "management_rules", ["review_status"])
    op.create_table(
        "management_signals",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id"), nullable=False), sa.Column("management_rule_id", sa.Uuid(), sa.ForeignKey("management_rules.id"), nullable=False), sa.Column("observation_id", sa.Uuid(), sa.ForeignKey("observations.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False), sa.Column("recommended_route", sa.String(64), nullable=False), sa.Column("summary", sa.Text(), nullable=False), sa.Column("evidence_json", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("patient_id", "management_rule_id", "observation_id", "status"):
        op.create_index(f"ix_management_signals_{column}", "management_signals", [column])
    op.create_table(
        "member_device_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id"), nullable=False), sa.Column("provider", sa.String(64), nullable=False), sa.Column("device_category", sa.String(32), nullable=False), sa.Column("assignment_status", sa.String(32), nullable=False), sa.Column("connection_status", sa.String(32), nullable=False), sa.Column("assigned_by", sa.String(128), nullable=False), sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False), sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True), sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_member_device_assignments_patient_id", "member_device_assignments", ["patient_id"])
    op.create_index("ix_member_device_assignments_provider", "member_device_assignments", ["provider"])
    op.create_table(
        "external_referrals",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id"), nullable=False), sa.Column("doctor_review_id", sa.Uuid(), sa.ForeignKey("doctor_reviews.id"), nullable=True), sa.Column("specialty", sa.String(128), nullable=False), sa.Column("reason", sa.Text(), nullable=False), sa.Column("question", sa.Text(), nullable=False), sa.Column("organization", sa.String(200), nullable=True), sa.Column("doctor_name", sa.String(128), nullable=True), sa.Column("appointment_at", sa.DateTime(timezone=True), nullable=True), sa.Column("status", sa.String(32), nullable=False), sa.Column("feedback", sa.Text(), nullable=True), sa.Column("attachment_reference", sa.String(512), nullable=True), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_external_referrals_patient_id", "external_referrals", ["patient_id"])
    op.create_index("ix_external_referrals_doctor_review_id", "external_referrals", ["doctor_review_id"])
    op.create_index("ix_external_referrals_status", "external_referrals", ["status"])


def downgrade() -> None:
    for table, indexes in (("external_referrals", ["ix_external_referrals_status", "ix_external_referrals_doctor_review_id", "ix_external_referrals_patient_id"]), ("member_device_assignments", ["ix_member_device_assignments_provider", "ix_member_device_assignments_patient_id"]), ("management_signals", ["ix_management_signals_status", "ix_management_signals_observation_id", "ix_management_signals_management_rule_id", "ix_management_signals_patient_id"]), ("management_rules", ["ix_management_rules_review_status", "ix_management_rules_canonical_code", "ix_management_rules_code"])):
        for index in indexes: op.drop_index(index, table_name=table)
        op.drop_table(table)
    op.drop_column("sleep_sessions", "stage_segments_json")
    op.drop_column("risk_events", "recommended_route")
    op.drop_column("risk_rules", "recommended_route")
