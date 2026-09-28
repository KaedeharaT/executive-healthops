"""Preserve input waits on the existing member identity."""
from alembic import op
revision='0031_member_wait_input'
down_revision='0030_member_health_event_runtime'
branch_labels=None
depends_on=None


def constraint(include_input):
    states="'IDLE','RUNNING','WAITING_MANAGER','WAITING_DOCTOR','WAITING_MEMBER','WAITING_TIME','FAILED'"
    if include_input:states+=",'WAITING_INPUT'"
    with op.batch_alter_table('member_agents') as batch:
        batch.drop_constraint('ck_member_agent_status',type_='check')
        batch.create_check_constraint('ck_member_agent_status',f'status IN ({states})')


def upgrade():constraint(True)


def downgrade():
    op.execute("UPDATE member_agents SET status='WAITING_MANAGER' WHERE status='WAITING_INPUT'")
    constraint(False)
