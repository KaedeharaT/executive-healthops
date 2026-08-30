"""Add the V0.1 raw, care-management, and insight entities.

Revision ID: 0002_add_v01_demo_entities
Revises: 0001_create_core_tables
Create Date: 2026-08-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_add_v01_demo_entities"
down_revision: Union[str, Sequence[str], None] = "0001_create_core_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid() -> sa.Uuid:
    return sa.Uuid()


def upgrade() -> None:
    op.create_table(
        "raw_data",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("patient_id", _uuid(), nullable=False),
        sa.Column("device_id", _uuid(), nullable=True),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("record_type", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("patient_id", "checksum", name="uq_raw_data_patient_checksum"),
    )
    with op.batch_alter_table("observations") as batch_op:
        batch_op.create_foreign_key("fk_observations_raw_record_id", "raw_data", ["raw_record_id"], ["id"])

    op.create_table(
        "sleep_sessions",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("patient_id", _uuid(), nullable=False),
        sa.Column("device_id", _uuid(), nullable=True),
        sa.Column("sleep_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sleep_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_sleep_minutes", sa.Integer(), nullable=False),
        sa.Column("deep_sleep_minutes", sa.Integer(), nullable=True),
        sa.Column("rem_sleep_minutes", sa.Integer(), nullable=True),
        sa.Column("awake_minutes", sa.Integer(), nullable=True),
        sa.Column("sleep_efficiency", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("avg_heart_rate", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("lowest_heart_rate", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("avg_hrv", sa.Numeric(precision=7, scale=2), nullable=True),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("raw_record_id", _uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["raw_record_id"], ["raw_data.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "medication_plans",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("patient_id", _uuid(), nullable=False),
        sa.Column("drug_name", sa.String(length=128), nullable=False),
        sa.Column("generic_name", sa.String(length=128), nullable=True),
        sa.Column("dose", sa.String(length=64), nullable=False),
        sa.Column("dose_unit", sa.String(length=32), nullable=False),
        sa.Column("frequency", sa.String(length=64), nullable=False),
        sa.Column("route", sa.String(length=64), nullable=False),
        sa.Column("scheduled_time", sa.Time(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("prescriber_name", sa.String(length=128), nullable=True),
        sa.Column("department", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "medication_events",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("patient_id", _uuid(), nullable=False),
        sa.Column("medication_plan_id", _uuid(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["medication_plan_id"], ["medication_plans.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "health_events",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("patient_id", _uuid(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=True),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "encounters",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("patient_id", _uuid(), nullable=False),
        sa.Column("encounter_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("encounter_type", sa.String(length=64), nullable=False),
        sa.Column("department", sa.String(length=128), nullable=False),
        sa.Column("clinician_name", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "clinical_recommendations",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("encounter_id", _uuid(), nullable=False),
        sa.Column("patient_id", _uuid(), nullable=False),
        sa.Column("department", sa.String(length=128), nullable=False),
        sa.Column("clinician_name", sa.String(length=128), nullable=False),
        sa.Column("recommendation_type", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounters.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "care_plans",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("patient_id", _uuid(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("condition", sa.String(length=160), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("primary_clinician", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "care_tasks",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("care_plan_id", _uuid(), nullable=False),
        sa.Column("patient_id", _uuid(), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["care_plan_id"], ["care_plans.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "ai_insights",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("patient_id", _uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("insight_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("evidence_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("needs_clinician_review", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    for table_name in (
        "ai_insights", "care_tasks", "care_plans", "clinical_recommendations", "encounters",
        "health_events", "medication_events", "medication_plans", "sleep_sessions",
    ):
        op.drop_table(table_name)
    with op.batch_alter_table("observations") as batch_op:
        batch_op.drop_constraint("fk_observations_raw_record_id", type_="foreignkey")
    op.drop_table("raw_data")
