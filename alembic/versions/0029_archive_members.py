"""Archive members without deleting health records or changing foreign keys."""
from alembic import op
import sqlalchemy as sa

revision = '0029_archive_members'
down_revision = '0028_post_checkup_context'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('patients', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_patients_archived_at', 'patients', ['archived_at'])


def downgrade():
    op.drop_index('ix_patients_archived_at', table_name='patients')
    op.drop_column('patients', 'archived_at')
