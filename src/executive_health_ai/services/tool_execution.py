"""Atomic, auditable execution over the existing trace store and service boundary."""
import hashlib
import json
from sqlalchemy import select
from executive_health_ai.models import AgentRunTrace
from executive_health_ai.models.base import utc_now


def execute(session, tool, goal, context):
    from executive_health_ai.models.archive_guard import locked_members
    from executive_health_ai.services.member_agents import ensure_member_agent
    # Services here are short database commands only. External I/O runs in the
    # existing worker's detached extraction phase, before invoking these tools.
    if tool.name == 'parse_profile_document':
        # Extraction owns the existing claim/progress/fencing protocol. Do not
        # acquire a write lock or SAVEPOINT before its file / model I/O.
        started = utc_now()
        result = tool.handler(session, goal, context)
        session.add(AgentRunTrace(goal_id=goal.id, plan_id=goal.current_plan_id,
            tool_name=tool.name, action='tool_execution', status='COMPLETED',
            started_at=started, completed_at=utc_now(),
            metadata_json={'member_agent_id': goal.context_json.get('member_agent_id'),
                'input_reference': goal.source_id, 'result_reference': result,
                'responsibility': tool.responsibility}))
        session.flush()
        return result
    key = context.get('idempotency_key')
    if tool.mode == 'write':
        locked_members(session.connection(), {goal.member_id})
    agent = ensure_member_agent(session, goal.member_id)
    encoded = json.dumps(context, sort_keys=True, ensure_ascii=False, default=str)
    fingerprint = hashlib.sha256(encoded.encode()).hexdigest()
    if not key and tool.mode=='write' and tool.idempotent:
        key='plan:'+str(goal.current_plan_id)+':'+fingerprint
    if key:
        prior = session.scalar(select(AgentRunTrace).where(
            AgentRunTrace.goal_id == goal.id, AgentRunTrace.tool_name == tool.name,
            AgentRunTrace.action == 'tool_execution',
            AgentRunTrace.metadata_json['idempotency_key'].as_string() == str(key),
            AgentRunTrace.status == 'COMPLETED'))
        if prior:
            if prior.metadata_json['input_hash'] != fingerprint:
                raise ValueError('同一业务请求不能更换内容。')
            return prior.metadata_json['result_reference']
    trace = AgentRunTrace(goal_id=goal.id, plan_id=goal.current_plan_id,
        tool_name=tool.name, action='tool_execution', status='RUNNING',
        metadata_json={'member_agent_id': str(agent.id), 'input_reference': context.get('source_reference'),
            'input_hash': fingerprint, 'idempotency_key': str(key) if key else None,
            'responsibility': tool.responsibility})
    session.add(trace)
    session.flush()
    try:
        with session.begin_nested():
            result = tool.handler(session, goal, context)
    except Exception as exc:
        trace.status, trace.completed_at = 'FAILED', utc_now()
        trace.error_summary = type(exc).__name__ + ': ' + str(exc)[:400]
        session.flush()
        raise
    result = json.loads(json.dumps(result, default=str, ensure_ascii=False))
    trace.status, trace.completed_at = 'COMPLETED', utc_now()
    trace.metadata_json = {**trace.metadata_json, 'result_reference': result}
    trace.result_summary = json.dumps(result, ensure_ascii=False)
    session.flush()
    return result
