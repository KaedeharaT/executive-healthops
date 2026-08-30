"""Link human operations to observation-driven risk events.

Revision ID: 0013_add_yellow_risk_operation_links
Revises: 0012_add_observation_risk_query_indexes
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_add_yellow_risk_operation_links"
down_revision = "0012_add_observation_risk_query_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("doctor_reviews") as batch:
        batch.add_column(sa.Column("risk_event_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key("fk_doctor_reviews_risk_event", "risk_events", ["risk_event_id"], ["id"])
        batch.create_index("ix_doctor_reviews_risk_event_id", ["risk_event_id"])
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("risk_event_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key("fk_tasks_risk_event", "risk_events", ["risk_event_id"], ["id"])
        batch.create_index("ix_tasks_risk_event_id", ["risk_event_id"])


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch:
        batch.drop_index("ix_tasks_risk_event_id")
        batch.drop_constraint("fk_tasks_risk_event", type_="foreignkey")
        batch.drop_column("risk_event_id")
    with op.batch_alter_table("doctor_reviews") as batch:
        batch.drop_index("ix_doctor_reviews_risk_event_id")
        batch.drop_constraint("fk_doctor_reviews_risk_event", type_="foreignkey")
        batch.drop_column("risk_event_id")
