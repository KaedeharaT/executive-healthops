"""Add the human-reviewed health-operations workflow.

Revision ID: 0003_add_operations_workflow
Revises: 0002_add_v01_demo_entities
Create Date: 2026-08-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_add_operations_workflow"
down_revision: Union[str, Sequence[str], None] = "0002_add_v01_demo_entities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id() -> sa.Uuid:
    return sa.Uuid()


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", _id(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("name"),
    )
    with op.batch_alter_table("patients") as batch_op:
        batch_op.add_column(sa.Column("organization_id", _id(), nullable=True))
        batch_op.create_index("ix_patients_organization_id", ["organization_id"])
        batch_op.create_foreign_key("fk_patients_organization_id", "organizations", ["organization_id"], ["id"])

    op.create_table(
        "consents",
        sa.Column("id", _id(), nullable=False), sa.Column("patient_id", _id(), nullable=False),
        sa.Column("consent_type", sa.String(64), nullable=False), sa.Column("status", sa.String(32), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True)), sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
        sa.Column("source", sa.String(128), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consents_patient_id", "consents", ["patient_id"])
    op.create_table(
        "documents",
        sa.Column("id", _id(), nullable=False), sa.Column("patient_id", _id(), nullable=False),
        sa.Column("document_type", sa.String(64), nullable=False), sa.Column("title", sa.String(200), nullable=False),
        sa.Column("storage_reference", sa.String(512), nullable=False), sa.Column("source", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_patient_id", "documents", ["patient_id"])
    op.create_table(
        "health_problems",
        sa.Column("id", _id(), nullable=False), sa.Column("patient_id", _id(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False), sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False), sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("responsible_role", sa.String(64), nullable=False), sa.Column("owner", sa.String(128)),
        sa.Column("source", sa.String(128), nullable=False), sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)), *_timestamps(),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_health_problems_patient_id", "health_problems", ["patient_id"])
    op.create_table(
        "alerts",
        sa.Column("id", _id(), nullable=False), sa.Column("patient_id", _id(), nullable=False),
        sa.Column("health_problem_id", _id()), sa.Column("alert_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False), sa.Column("finding", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False), sa.Column("status", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False), sa.Column("responsible_role", sa.String(64), nullable=False),
        sa.Column("owner", sa.String(128)), sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", sa.String(128)), sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_note", sa.Text()), sa.Column("source", sa.String(128), nullable=False), *_timestamps(),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["health_problem_id"], ["health_problems.id"]), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_patient_id", "alerts", ["patient_id"])
    op.create_index("ix_alerts_health_problem_id", "alerts", ["health_problem_id"])
    op.create_index("ix_alerts_status", "alerts", ["status"])
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_table(
        "doctor_reviews",
        sa.Column("id", _id(), nullable=False), sa.Column("patient_id", _id(), nullable=False),
        sa.Column("health_problem_id", _id(), nullable=False), sa.Column("alert_id", _id()),
        sa.Column("doctor_name", sa.String(128), nullable=False), sa.Column("department", sa.String(128), nullable=False),
        sa.Column("doctor_brief", sa.Text(), nullable=False), sa.Column("question_for_doctor", sa.Text(), nullable=False),
        sa.Column("opinion", sa.Text(), nullable=False), sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]), sa.ForeignKeyConstraint(["health_problem_id"], ["health_problems.id"]),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"]), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_doctor_reviews_patient_id", "doctor_reviews", ["patient_id"])
    op.create_index("ix_doctor_reviews_health_problem_id", "doctor_reviews", ["health_problem_id"])
    op.create_table(
        "management_plans",
        sa.Column("id", _id(), nullable=False), sa.Column("patient_id", _id(), nullable=False),
        sa.Column("health_problem_id", _id(), nullable=False), sa.Column("doctor_review_id", _id()),
        sa.Column("title", sa.String(200), nullable=False), sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False), sa.Column("owner", sa.String(128)), sa.Column("source", sa.String(128), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False), sa.Column("end_date", sa.Date()), *_timestamps(),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]), sa.ForeignKeyConstraint(["health_problem_id"], ["health_problems.id"]),
        sa.ForeignKeyConstraint(["doctor_review_id"], ["doctor_reviews.id"]), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_management_plans_patient_id", "management_plans", ["patient_id"])
    op.create_index("ix_management_plans_health_problem_id", "management_plans", ["health_problem_id"])
    op.create_table(
        "tasks",
        sa.Column("id", _id(), nullable=False), sa.Column("patient_id", _id(), nullable=False),
        sa.Column("health_problem_id", _id()), sa.Column("management_plan_id", _id()), sa.Column("alert_id", _id()),
        sa.Column("title", sa.String(200), nullable=False), sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False), sa.Column("priority", sa.String(32), nullable=False),
        sa.Column("assignee", sa.String(128)), sa.Column("responsible_role", sa.String(64), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("source", sa.String(128), nullable=False), *_timestamps(),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]), sa.ForeignKeyConstraint(["health_problem_id"], ["health_problems.id"]),
        sa.ForeignKeyConstraint(["management_plan_id"], ["management_plans.id"]), sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"]), sa.PrimaryKeyConstraint("id"),
    )
    for name, cols in (("ix_tasks_patient_id", ["patient_id"]), ("ix_tasks_health_problem_id", ["health_problem_id"]), ("ix_tasks_status", ["status"])):
        op.create_index(name, "tasks", cols)
    op.create_table(
        "follow_ups",
        sa.Column("id", _id(), nullable=False), sa.Column("patient_id", _id(), nullable=False),
        sa.Column("health_problem_id", _id(), nullable=False), sa.Column("task_id", _id()), sa.Column("status", sa.String(32), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("outcome", sa.Text()), sa.Column("reviewed_by", sa.String(128)), sa.Column("source", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]), sa.ForeignKeyConstraint(["health_problem_id"], ["health_problems.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_follow_ups_patient_id", "follow_ups", ["patient_id"])
    op.create_index("ix_follow_ups_health_problem_id", "follow_ups", ["health_problem_id"])
    op.create_table("service_events", sa.Column("id", _id(), nullable=False), sa.Column("patient_id", _id(), nullable=False), sa.Column("event_type", sa.String(64), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("owner", sa.String(128)), sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False), sa.Column("detail", sa.Text()), sa.Column("source", sa.String(128), nullable=False), sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_service_events_patient_id", "service_events", ["patient_id"])
    op.create_table("agent_runs", sa.Column("id", _id(), nullable=False), sa.Column("patient_id", _id()), sa.Column("agent_name", sa.String(64), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("input_reference_json", sa.JSON(), nullable=False), sa.Column("output_json", sa.JSON(), nullable=False), sa.Column("model_version", sa.String(128), nullable=False), sa.Column("needs_human_review", sa.Boolean(), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_agent_runs_patient_id", "agent_runs", ["patient_id"])
    op.create_table("audit_logs", sa.Column("id", _id(), nullable=False), sa.Column("patient_id", _id()), sa.Column("actor", sa.String(128), nullable=False), sa.Column("actor_role", sa.String(64), nullable=False), sa.Column("action", sa.String(128), nullable=False), sa.Column("entity_type", sa.String(64), nullable=False), sa.Column("entity_id", sa.String(64), nullable=False), sa.Column("detail_json", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_audit_logs_patient_id", "audit_logs", ["patient_id"])


def downgrade() -> None:
    for table in ("audit_logs", "agent_runs", "service_events", "follow_ups", "tasks", "management_plans", "doctor_reviews", "alerts", "health_problems", "documents", "consents"):
        op.drop_table(table)
    with op.batch_alter_table("patients") as batch_op:
        batch_op.drop_constraint("fk_patients_organization_id", type_="foreignkey")
        batch_op.drop_index("ix_patients_organization_id")
        batch_op.drop_column("organization_id")
    op.drop_table("organizations")
