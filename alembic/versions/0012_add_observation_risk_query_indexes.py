"""Add indexes for observation-driven risk windows and active-event lookup.

Revision ID: 0012_add_observation_risk_query_indexes
Revises: 0011_add_report_llm_audit
"""

from alembic import op


revision = "0012_add_observation_risk_query_indexes"
down_revision = "0011_add_report_llm_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_observations_patient_metric_observed_at",
        "observations",
        ["patient_id", "metric_code", "observed_at"],
    )
    op.create_index(
        "ix_risk_events_patient_rule_status",
        "risk_events",
        ["patient_id", "risk_rule_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_risk_events_patient_rule_status", table_name="risk_events")
    op.drop_index("ix_observations_patient_metric_observed_at", table_name="observations")
