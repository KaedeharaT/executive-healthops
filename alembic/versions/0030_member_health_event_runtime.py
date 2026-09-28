"""Expand the existing health-event ledger and add one persistent member identity."""
from alembic import op
import sqlalchemy as sa
from uuid import uuid4
from datetime import datetime, timezone

revision='0030_member_health_event_runtime'
down_revision='0029_archive_members'
branch_labels=None
depends_on=None


def upgrade():
    for column in [sa.Column('event_category',sa.String(32)),sa.Column('source_type',sa.String(16)),
        sa.Column('source_id',sa.String(256)),sa.Column('received_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.current_timestamp()),
        sa.Column('payload_ref',sa.JSON()),sa.Column('correlation_id',sa.String(128)),
        sa.Column('idempotency_key',sa.String(256)),sa.Column('status',sa.String(24),nullable=False,server_default='STORED'),
        sa.Column('route_action',sa.String(32)),sa.Column('goal_id',sa.Uuid())]:
        # SQLite requires a literal default when adding columns to existing rows.
        if column.name=='received_at':column=sa.Column('received_at',sa.DateTime(timezone=True),nullable=True)
        op.add_column('health_events',column)
    op.execute('UPDATE health_events SET received_at = start_at WHERE received_at IS NULL')
    with op.batch_alter_table('health_events') as batch:
        batch.alter_column('received_at',existing_type=sa.DateTime(timezone=True),nullable=False)
        batch.create_foreign_key('fk_health_event_goal','agent_goals',['goal_id'],['id'])
    op.create_index('uq_health_event_idempotency','health_events',['idempotency_key'],unique=True)
    op.create_index('uq_health_event_origin','health_events',['patient_id','event_type','source_id'],unique=True)
    op.create_index('ix_health_event_pending','health_events',['status','received_at'])
    op.create_table('member_agents',sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('member_id',sa.Uuid(),sa.ForeignKey('patients.id'),nullable=False,unique=True),
        sa.Column('status',sa.String(24),nullable=False),sa.Column('current_goal_id',sa.Uuid(),sa.ForeignKey('agent_goals.id')),
        sa.Column('last_event_at',sa.DateTime(timezone=True)),sa.Column('last_active_at',sa.DateTime(timezone=True)),
        sa.Column('waiting_for',sa.String(32)),sa.Column('next_wake_at',sa.DateTime(timezone=True)),
        sa.Column('wake_count',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint("status IN ('IDLE','RUNNING','WAITING_MANAGER','WAITING_DOCTOR','WAITING_MEMBER','WAITING_TIME','FAILED')",name='ck_member_agent_status'))
    conn=op.get_bind();now=datetime.now(timezone.utc)
    rows=conn.execute(sa.text('SELECT DISTINCT patient_id FROM health_programs WHERE patient_id IN (SELECT id FROM patients WHERE archived_at IS NULL)'))
    for (member,) in rows:
        conn.execute(sa.text('INSERT INTO member_agents (id,member_id,status,wake_count,created_at,updated_at) VALUES (:id,:member,\'IDLE\',0,:now,:now)'),{'id':uuid4().hex,'member':member,'now':now})


def downgrade():
    op.drop_table('member_agents')
    for index in ('ix_health_event_pending','uq_health_event_origin','uq_health_event_idempotency'):op.drop_index(index,table_name='health_events')
    with op.batch_alter_table('health_events') as batch:
        batch.drop_constraint('fk_health_event_goal',type_='foreignkey')
        for name in ('goal_id','route_action','status','idempotency_key','correlation_id','payload_ref','received_at','source_id','source_type','event_category'):
            batch.drop_column(name)
