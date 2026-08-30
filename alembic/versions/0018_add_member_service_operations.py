"""Add configurable member-service operations.

Revision ID: 0018_add_member_service_operations
Revises: 0017_add_risk_rule_scope
"""
from alembic import op
import sqlalchemy as sa

revision = "0018_add_member_service_operations"
down_revision = "0017_add_risk_rule_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("service_catalog_items", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("code", sa.String(100), nullable=False, unique=True), sa.Column("category", sa.String(100), nullable=False), sa.Column("name", sa.String(200), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("is_major_timeline_service", sa.Boolean(), nullable=False), sa.Column("status", sa.String(32), nullable=False))
    op.create_index("ix_service_catalog_items_category", "service_catalog_items", ["category"])
    op.create_table("service_plans", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("name", sa.String(200), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("version", sa.String(64), nullable=False), sa.Column("effective_from", sa.DateTime(timezone=True)), sa.Column("effective_to", sa.DateTime(timezone=True)))
    op.create_table("service_plan_items", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("service_plan_id", sa.Uuid(), sa.ForeignKey("service_plans.id"), nullable=False), sa.Column("service_item_id", sa.Uuid(), sa.ForeignKey("service_catalog_items.id"), nullable=False), sa.Column("included", sa.Boolean(), nullable=False), sa.Column("quota_type", sa.String(32), nullable=False), sa.Column("included_quantity", sa.Integer()), sa.Column("discount", sa.String(64)), sa.Column("coverage", sa.Text()), sa.Column("notes", sa.Text()))
    op.create_table("member_entitlements", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id"), nullable=False), sa.Column("service_plan_id", sa.Uuid(), sa.ForeignKey("service_plans.id"), nullable=False), sa.Column("service_item_id", sa.Uuid(), sa.ForeignKey("service_catalog_items.id"), nullable=False), sa.Column("total_quota", sa.Integer()), sa.Column("used_quota", sa.Integer(), nullable=False), sa.Column("valid_from", sa.DateTime(timezone=True)), sa.Column("valid_to", sa.DateTime(timezone=True)), sa.Column("status", sa.String(32), nullable=False), sa.UniqueConstraint("patient_id", "service_item_id", name="uq_member_entitlement_item"))
    op.create_index("ix_member_entitlements_patient_id", "member_entitlements", ["patient_id"])
    op.create_table("service_requests", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id"), nullable=False), sa.Column("service_item_id", sa.Uuid(), sa.ForeignKey("service_catalog_items.id"), nullable=False), sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False), sa.Column("requested_by", sa.String(128), nullable=False), sa.Column("reason", sa.Text(), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("assigned_manager", sa.String(128)), sa.Column("scheduled_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("result_summary", sa.Text()), sa.Column("related_problem_id", sa.Uuid(), sa.ForeignKey("health_problems.id")), sa.Column("related_risk_event_id", sa.Uuid(), sa.ForeignKey("risk_events.id")), sa.Column("related_doctor_review_id", sa.Uuid(), sa.ForeignKey("doctor_reviews.id")))
    op.create_index("ix_service_requests_patient_id", "service_requests", ["patient_id"]); op.create_index("ix_service_requests_status", "service_requests", ["status"])
    op.create_table("member_plan_choices", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id"), nullable=False), sa.Column("proposal", sa.Text(), nullable=False), sa.Column("recommended_by", sa.String(128)), sa.Column("reason", sa.Text()), sa.Column("member_choice", sa.String(32), nullable=False), sa.Column("member_comment", sa.Text()), sa.Column("chosen_at", sa.DateTime(timezone=True), nullable=False), sa.Column("manager_followup", sa.Text()))
    op.create_index("ix_member_plan_choices_patient_id", "member_plan_choices", ["patient_id"])


def downgrade() -> None:
    for table in ("member_plan_choices", "service_requests", "member_entitlements", "service_plan_items", "service_plans", "service_catalog_items"):
        op.drop_table(table)
