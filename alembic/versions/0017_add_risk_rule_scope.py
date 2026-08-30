"""Add explicit UAT safety scope to deterministic risk rules.

Revision ID: 0017_add_risk_rule_scope
Revises: 0016_add_assessment_governance
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_add_risk_rule_scope"
down_revision = "0016_add_assessment_governance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {item["name"] for item in sa.inspect(bind).get_columns("risk_rules")}
    if "scope" not in columns:
        # Existing rules are not silently promoted to clinical use.
        op.add_column("risk_rules", sa.Column("scope", sa.String(length=16), nullable=False, server_default="TEST"))
        op.create_index("ix_risk_rules_scope", "risk_rules", ["scope"])


def downgrade() -> None:
    op.drop_index("ix_risk_rules_scope", table_name="risk_rules")
    op.drop_column("risk_rules", "scope")
