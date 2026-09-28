"""Reject stale ORM writes for archived members; historical reads remain available."""
from sqlalchemy import event, inspect, select, update
from sqlalchemy.orm import Session
from executive_health_ai.models.patient import Patient


def owner_id(connection, table, values, seen=()):
    if table.name in seen:
        return None
    if table.name == 'patients':
        return values.get('id')
    for name in ('patient_id','member_id'):
        if values.get(name) is not None:
            return values[name]
    # Existing plan/step, phase, and event records can have an indirect owner.
    for name in ('goal_id','plan_id','program_id','task_id','document_id','encounter_id'):
        if values.get(name) is None or name not in table.c:
            continue
        for fk in table.c[name].foreign_keys:
            target=fk.column.table
            row=connection.execute(select(target).where(fk.column==values[name])).mappings().first()
            if row:
                member_id=owner_id(connection,target,row,(*seen,table.name))
                if member_id:
                    return member_id
    return None


def locked_members(connection, ids):
    """Serialize archive against writes, including another already-open session."""
    table=Patient.__table__
    if connection.dialect.name == 'sqlite':
        # A no-op takes SQLite's writer reservation without changing timestamps.
        connection.execute(update(table).where(table.c.id.in_(ids)).values(updated_at=table.c.updated_at))
    return dict(connection.execute(select(table.c.id,table.c.archived_at).where(table.c.id.in_(ids)).with_for_update()).all())


@event.listens_for(Session, 'before_flush')
def protect_archived_members(session, flush_context, instances):
    connection=session.connection()
    owners=set()
    for row in set(session.new) | set(session.dirty) | set(session.deleted):
        state=inspect(row)
        if row in session.dirty and not session.is_modified(row,include_collections=False):
            continue
        table=state.mapper.local_table
        # Audit is append-only; late events may record that execution was ignored.
        if row in session.new and table.name in {'audit_logs','agent_run_traces'}:
            continue
        if table.name in {'agent_events','health_events'} and row not in session.deleted and row.status=='IGNORED':
            continue
        values={column.key:getattr(row,column.key,None) for column in state.mapper.columns}
        member_id=owner_id(connection,table,values)
        if member_id:
            owners.add(member_id)
        if isinstance(row,Patient) and row not in session.new and state.attrs.archived_at.history.has_changes():
            if session.info.get('archiving_member') != row.id:
                raise ValueError('成员归档必须通过带确认的归档操作。')
    owners.discard(session.info.get('archiving_member'))
    if not owners:
        return
    if any(at is not None for at in locked_members(connection,owners).values()):
        raise ValueError('成员已归档，不能继续写入或执行工作；历史记录保留供管理员查阅。')
