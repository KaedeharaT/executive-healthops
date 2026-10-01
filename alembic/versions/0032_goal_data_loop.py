"""Add goal governance and versioned longitudinal summaries without reseeding."""
from alembic import op
import sqlalchemy as sa

revision = '0032_goal_data_loop'
down_revision = '0031_member_wait_input'
branch_labels = None
depends_on = None


def upgrade():
    from executive_health_ai.models.goal_data import (
        ManagementGoal, ReportCandidateRevision, DailyHealthSummary,
        DailySummaryRevision, SummaryWorkItem, CommunicationRecord,
    )
    for model in (ManagementGoal, ReportCandidateRevision, DailyHealthSummary,
                  DailySummaryRevision, SummaryWorkItem, CommunicationRecord):
        model.__table__.create(op.get_bind())
    with op.batch_alter_table('observations') as batch:
        batch.add_column(sa.Column('source_type', sa.String(32)))
        batch.add_column(sa.Column('confirmation_status', sa.String(32), nullable=False, server_default='GOVERNED'))
        batch.add_column(sa.Column('confirmed_by', sa.String(128)))
        batch.add_column(sa.Column('confirmed_at', sa.DateTime(timezone=True)))
        batch.add_column(sa.Column('evidence_ref', sa.String(256)))
        batch.add_column(sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
        batch.add_column(sa.Column('supersedes_id', sa.Uuid()))
        batch.add_column(sa.Column('provenance_json', sa.JSON(), nullable=False, server_default='{}'))
        batch.create_foreign_key('fk_observation_supersedes', 'observations', ['supersedes_id'], ['id'])
        batch.create_index('ix_observations_supersedes_id', ['supersedes_id'])


def downgrade():
    # Explicit destructive downgrade only; normal startup never runs this.
    with op.batch_alter_table('observations') as batch:
        batch.drop_index('ix_observations_supersedes_id')
        batch.drop_constraint('fk_observation_supersedes', type_='foreignkey')
        for name in ('provenance_json', 'supersedes_id', 'version', 'evidence_ref',
                     'confirmed_at', 'confirmed_by', 'confirmation_status', 'source_type'):
            batch.drop_column(name)
    for name in ('communication_records', 'summary_work_items', 'daily_summary_revisions',
                 'daily_health_summaries', 'report_candidate_revisions', 'management_goals'):
        op.drop_table(name)
