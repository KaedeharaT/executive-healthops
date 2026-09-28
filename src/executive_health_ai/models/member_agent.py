"""Persistent member identity, not another execution engine."""
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import ForeignKey, String, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, synonym
from executive_health_ai.models.base import Base, UTCDateTime, utc_now


class MemberAgent(Base):
    __tablename__='member_agents'
    __table_args__=(CheckConstraint("status IN ('IDLE','RUNNING','WAITING_MANAGER','WAITING_DOCTOR','WAITING_MEMBER','WAITING_TIME','WAITING_INPUT','FAILED')",name='ck_member_agent_status'),)
    id: Mapped[UUID] = mapped_column(primary_key=True,default=uuid4)
    member_agent_id = synonym('id')
    member_id: Mapped[UUID] = mapped_column(ForeignKey('patients.id'),unique=True,nullable=False)
    status: Mapped[str] = mapped_column(String(24),default='IDLE')
    current_goal_id: Mapped[UUID | None] = mapped_column(ForeignKey('agent_goals.id'))
    last_event_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_active_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    waiting_for: Mapped[str | None] = mapped_column(String(32))
    next_wake_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    wake_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(),default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(),default=utc_now,onupdate=utc_now)


# Register alongside the model, so a fresh UI process that only confirms an
# existing goal also synchronizes the identity in that very transaction.
# The service is imported lazily after model registration; no I/O or commits.
from sqlalchemy import event
from sqlalchemy.orm import Session


@event.listens_for(Session,'before_flush')
def remember_goal_changes(session,context,instances):
    from executive_health_ai.models.agent import AgentGoal
    ids={g.member_id for g in set(session.new)|set(session.dirty) if isinstance(g,AgentGoal)}
    session.info.setdefault('member_agent_sync',set()).update(ids)


@event.listens_for(Session,'after_flush_postexec')
def project_goal_changes(session,context):
    ids=session.info.pop('member_agent_sync',set())
    if ids:
        from executive_health_ai.services.member_agents import synchronize
        for member in ids:synchronize(session,member)


@event.listens_for(Session,'after_soft_rollback')
def clear_goal_changes(session,previous):
    session.info.pop('member_agent_sync',None)
