"""Persist bounded report-to-care drafts on the existing goal."""
from alembic import op
import sqlalchemy as sa

revision = '0028_post_checkup_context'
down_revision = '0027_real_management_workflow'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('agent_goals', sa.Column('context_json', sa.JSON(), nullable=False, server_default='{}'))


def downgrade():
    op.drop_column('agent_goals', 'context_json')
