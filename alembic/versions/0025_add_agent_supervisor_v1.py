"""Add durable state for the bounded HealthOps Agent Supervisor V1.

Revision ID: 0025_add_agent_supervisor_v1
Revises: 0024_align_service_delivery_with_bp
"""

from alembic import op
import sqlalchemy as sa


revision = "0025_add_agent_supervisor_v1"
down_revision = "0024_align_service_delivery_with_bp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("member_id", sa.Uuid(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload_summary", sa.Text(), nullable=True),
        sa.Column("dedup_key", sa.String(255), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("dedup_key", name="uq_agent_events_dedup_key"),
    )
    op.create_index("ix_agent_events_event_type", "agent_events", ["event_type"])
    op.create_index("ix_agent_events_member_id", "agent_events", ["member_id"])
    op.create_index("ix_agent_events_status", "agent_events", ["status"])

    op.create_table(
        "agent_goals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("member_id", sa.Uuid(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("goal_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("success_criteria", sa.JSON(), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("owner", sa.String(128), nullable=True),
        sa.Column("current_stage", sa.String(128), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column("current_plan_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("automation_paused", sa.Boolean(), nullable=False),
        sa.Column("takeover_by", sa.String(128), nullable=True),
        sa.Column("takeover_reason", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("goal_type", "source_type", "source_id", name="uq_agent_goal_source"),
    )
    op.create_index("ix_agent_goals_goal_type", "agent_goals", ["goal_type"])
    op.create_index("ix_agent_goals_member_id", "agent_goals", ["member_id"])
    op.create_index("ix_agent_goals_status", "agent_goals", ["status"])
    op.create_index("ix_agent_goals_next_check_at", "agent_goals", ["next_check_at"])
    op.create_index("ix_agent_goals_member_status", "agent_goals", ["member_id", "status"])

    op.create_table(
        "agent_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("goal_id", sa.Uuid(), sa.ForeignKey("agent_goals.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.UniqueConstraint("goal_id", "version", name="uq_agent_plan_version"),
    )
    op.create_index("ix_agent_plans_goal_id", "agent_plans", ["goal_id"])
    op.create_index("ix_agent_plans_status", "agent_plans", ["status"])

    op.create_table(
        "agent_plan_steps",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("plan_id", sa.Uuid(), sa.ForeignKey("agent_plans.id"), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(64), nullable=False),
        sa.Column("tool_name", sa.String(96), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("requires_approval", sa.Boolean(), nullable=False),
        sa.Column("approval_role", sa.String(32), nullable=True),
        sa.Column("wait_event_type", sa.String(64), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.UniqueConstraint("plan_id", "step_order", name="uq_agent_plan_step_order"),
    )
    op.create_index("ix_agent_plan_steps_plan_id", "agent_plan_steps", ["plan_id"])
    op.create_index("ix_agent_plan_steps_status", "agent_plan_steps", ["status"])
    op.create_index("ix_agent_plan_steps_status_schedule", "agent_plan_steps", ["status", "scheduled_for"])

    op.create_table(
        "agent_approval_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("goal_id", sa.Uuid(), sa.ForeignKey("agent_goals.id"), nullable=False),
        sa.Column("plan_step_id", sa.Uuid(), sa.ForeignKey("agent_plan_steps.id"), nullable=False),
        sa.Column("approval_type", sa.String(64), nullable=False),
        sa.Column("required_role", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.String(128), nullable=True),
        sa.Column("decision", sa.String(24), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.UniqueConstraint("plan_step_id", "approval_type", name="uq_agent_approval_step_type"),
    )
    op.create_index("ix_agent_approval_requests_goal_id", "agent_approval_requests", ["goal_id"])
    op.create_index("ix_agent_approval_requests_plan_step_id", "agent_approval_requests", ["plan_step_id"])
    op.create_index("ix_agent_approval_requests_required_role", "agent_approval_requests", ["required_role"])
    op.create_index("ix_agent_approval_requests_status", "agent_approval_requests", ["status"])

    op.create_table(
        "agent_run_traces",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("goal_id", sa.Uuid(), sa.ForeignKey("agent_goals.id"), nullable=False),
        sa.Column("plan_id", sa.Uuid(), sa.ForeignKey("agent_plans.id"), nullable=True),
        sa.Column("plan_step_id", sa.Uuid(), sa.ForeignKey("agent_plan_steps.id"), nullable=True),
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("agent_events.id"), nullable=True),
        sa.Column("tool_name", sa.String(96), nullable=True),
        sa.Column("action", sa.String(96), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("approval_id", sa.Uuid(), sa.ForeignKey("agent_approval_requests.id"), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_agent_run_traces_goal_id", "agent_run_traces", ["goal_id"])
    op.create_index("ix_agent_run_traces_goal_created", "agent_run_traces", ["goal_id", "started_at"])


def downgrade() -> None:
    op.drop_table("agent_run_traces")
    op.drop_table("agent_approval_requests")
    op.drop_table("agent_plan_steps")
    op.drop_table("agent_plans")
    op.drop_table("agent_goals")
    op.drop_table("agent_events")
