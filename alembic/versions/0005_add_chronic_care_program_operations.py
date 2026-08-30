"""Add chronic-care journey and program operations.

Revision ID: 0005_add_chronic_care_program_operations
Revises: 0004_add_member_display_name
Create Date: 2026-08-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_add_chronic_care_program_operations"
down_revision: Union[str, Sequence[str], None] = "0004_add_member_display_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id() -> sa.Uuid:
    return sa.Uuid()


def upgrade() -> None:
    op.create_table(
        "health_journeys",
        sa.Column("id", _id(), primary_key=True), sa.Column("patient_id", _id(), nullable=False),
        sa.Column("current_stage", sa.String(32), nullable=False), sa.Column("status", sa.String(32), nullable=False),
        sa.Column("risk_level", sa.String(32), nullable=False), sa.Column("assessment_summary", sa.Text(), nullable=False),
        sa.Column("main_focus", sa.Text(), nullable=False), sa.Column("supporting_goals_json", sa.JSON(), nullable=False),
        sa.Column("baseline_json", sa.JSON(), nullable=False), sa.Column("owner", sa.String(128)), sa.Column("doctor", sa.String(128)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
    )
    op.create_index("ix_health_journeys_patient_id", "health_journeys", ["patient_id"])
    op.create_index("ix_health_journeys_current_stage", "health_journeys", ["current_stage"])
    op.create_table(
        "health_programs",
        sa.Column("id", _id(), primary_key=True), sa.Column("patient_id", _id(), nullable=False), sa.Column("journey_id", _id(), nullable=False),
        sa.Column("program_type", sa.String(32), nullable=False), sa.Column("title", sa.String(200), nullable=False), sa.Column("main_goal", sa.Text(), nullable=False),
        sa.Column("supporting_goals_json", sa.JSON(), nullable=False), sa.Column("status", sa.String(40), nullable=False), sa.Column("current_phase", sa.String(32)),
        sa.Column("owner", sa.String(128)), sa.Column("doctor", sa.String(128)), sa.Column("start_date", sa.Date(), nullable=False), sa.Column("end_date", sa.Date()),
        sa.Column("next_decision", sa.String(32)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]), sa.ForeignKeyConstraint(["journey_id"], ["health_journeys.id"]),
    )
    for name, cols in (("ix_health_programs_patient_id", ["patient_id"]), ("ix_health_programs_journey_id", ["journey_id"]), ("ix_health_programs_program_type", ["program_type"]), ("ix_health_programs_status", ["status"])):
        op.create_index(name, "health_programs", cols)
    op.create_table(
        "program_phases",
        sa.Column("id", _id(), primary_key=True), sa.Column("program_id", _id(), nullable=False), sa.Column("phase_code", sa.String(32), nullable=False),
        sa.Column("title", sa.String(100), nullable=False), sa.Column("sequence", sa.Integer(), nullable=False), sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["program_id"], ["health_programs.id"]),
    )
    op.create_index("ix_program_phases_program_id", "program_phases", ["program_id"])
    op.create_table(
        "execution_barriers",
        sa.Column("id", _id(), primary_key=True), sa.Column("patient_id", _id(), nullable=False), sa.Column("program_id", _id(), nullable=False), sa.Column("task_id", _id()),
        sa.Column("reason", sa.String(40), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_by", sa.String(128), nullable=False), sa.Column("resolution", sa.Text()), sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]), sa.ForeignKeyConstraint(["program_id"], ["health_programs.id"]), sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
    )
    op.create_index("ix_execution_barriers_patient_id", "execution_barriers", ["patient_id"])
    op.create_index("ix_execution_barriers_program_id", "execution_barriers", ["program_id"])
    op.create_table(
        "weekly_reviews",
        sa.Column("id", _id(), primary_key=True), sa.Column("program_id", _id(), nullable=False), sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("task_completion", sa.String(40), nullable=False), sa.Column("data_completeness", sa.String(40), nullable=False), sa.Column("key_changes", sa.Text(), nullable=False),
        sa.Column("execution_barriers", sa.Text()), sa.Column("manager_notes", sa.Text()), sa.Column("adjustment", sa.Text()), sa.Column("next_week_focus", sa.Text(), nullable=False),
        sa.Column("reviewed_by", sa.String(128), nullable=False), sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["program_id"], ["health_programs.id"]),
    )
    op.create_index("ix_weekly_reviews_program_id", "weekly_reviews", ["program_id"])
    op.create_table(
        "outcome_evaluations",
        sa.Column("id", _id(), primary_key=True), sa.Column("patient_id", _id(), nullable=False), sa.Column("program_id", _id(), nullable=False),
        sa.Column("metric", sa.String(128), nullable=False), sa.Column("baseline_value", sa.String(128), nullable=False), sa.Column("current_value", sa.String(128), nullable=False),
        sa.Column("target_value", sa.String(128)), sa.Column("unit", sa.String(32), nullable=False), sa.Column("direction", sa.String(32), nullable=False),
        sa.Column("evaluation_date", sa.Date(), nullable=False), sa.Column("evaluator", sa.String(128), nullable=False), sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("result", sa.String(40), nullable=False), sa.Column("notes", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]), sa.ForeignKeyConstraint(["program_id"], ["health_programs.id"]),
    )
    op.create_index("ix_outcome_evaluations_patient_id", "outcome_evaluations", ["patient_id"])
    op.create_index("ix_outcome_evaluations_program_id", "outcome_evaluations", ["program_id"])
    op.create_table(
        "annual_health_accounts",
        sa.Column("id", _id(), primary_key=True), sa.Column("patient_id", _id(), nullable=False), sa.Column("journey_id", _id(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False), sa.Column("annual_goal", sa.Text(), nullable=False), sa.Column("owner", sa.String(128)), sa.Column("status", sa.String(32), nullable=False),
        sa.Column("next_review_date", sa.Date()), sa.Column("next_year_recommendation", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]), sa.ForeignKeyConstraint(["journey_id"], ["health_journeys.id"]),
    )
    op.create_index("ix_annual_health_accounts_patient_id", "annual_health_accounts", ["patient_id"])
    op.create_index("ix_annual_health_accounts_journey_id", "annual_health_accounts", ["journey_id"])
    for table, fk_name in (("health_problems", "fk_health_problems_program_id"), ("alerts", "fk_alerts_program_id"), ("management_plans", "fk_management_plans_program_id"), ("doctor_reviews", "fk_doctor_reviews_program_id"), ("tasks", "fk_tasks_program_id")):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("program_id", _id(), nullable=True))
            batch.create_index(f"ix_{table}_program_id", ["program_id"])
            batch.create_foreign_key(fk_name, "health_programs", ["program_id"], ["id"])
    with op.batch_alter_table("health_problems") as batch:
        batch.add_column(sa.Column("priority_rank", sa.Integer(), nullable=True))
    with op.batch_alter_table("management_plans") as batch:
        batch.add_column(sa.Column("adjustment_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("adjusted_by", sa.String(128), nullable=True))
        batch.add_column(sa.Column("adjusted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Downstream foreign-key columns are deliberately retained on downgrade in this prototype;
    # removing them safely requires per-dialect table rebuilds and is not used in normal operation.
    for table in ("annual_health_accounts", "outcome_evaluations", "weekly_reviews", "execution_barriers", "program_phases", "health_programs", "health_journeys"):
        op.drop_table(table)
