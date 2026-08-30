"""Add safe local-LLM invocation audit fields to report extraction runs.

Revision ID: 0011_add_report_llm_audit
Revises: 0010_add_universal_health_report_parser
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_add_report_llm_audit"
down_revision = "0010_add_universal_health_report_parser"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("report_extraction_runs") as batch:
        batch.add_column(sa.Column("llm_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("llm_available", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("llm_provider", sa.String(32), nullable=True))
        batch.add_column(sa.Column("llm_model", sa.String(128), nullable=True))
        batch.add_column(sa.Column("llm_status", sa.String(32), nullable=False, server_default="NOT_NEEDED"))
        batch.add_column(sa.Column("llm_call_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("llm_success_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("llm_failure_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("llm_total_duration_ms", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("llm_processed_sections", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("llm_failure_reason", sa.String(256), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("report_extraction_runs") as batch:
        batch.drop_column("llm_failure_reason")
        batch.drop_column("llm_processed_sections")
        batch.drop_column("llm_total_duration_ms")
        batch.drop_column("llm_failure_count")
        batch.drop_column("llm_success_count")
        batch.drop_column("llm_call_count")
        batch.drop_column("llm_status")
        batch.drop_column("llm_model")
        batch.drop_column("llm_provider")
        batch.drop_column("llm_available")
        batch.drop_column("llm_enabled")
