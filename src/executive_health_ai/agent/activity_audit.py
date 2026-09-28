"""Append business-safe capability metadata to the existing AgentRunTrace."""
from datetime import datetime
from executive_health_ai.models import AgentRunTrace
from executive_health_ai.models.base import utc_now

ALLOWED = {'kind', 'task', 'provider', 'request_sent', 'started_at', 'completed_at', 'latency_ms',
           'status', 'accepted', 'input_sources', 'result_count', 'knowledge_hit_count', 'citations',
           'reason', 'parse_method', 'retrieval_policy', 'operation_id', 'failure_reason'}
CITATION_KEYS = ('title', 'source', 'source_url', 'version', 'location', 'excerpt', 'retrieved_at', 'scope')


def record(session, goal, data):
    safe = {k: v for k, v in data.items() if k in ALLOWED}
    if 'citations' in safe:
        safe['citations'] = [{k: c[k] for k in CITATION_KEYS if k in c} for c in safe['citations']]
    now = utc_now()
    row = AgentRunTrace(goal_id=goal.id, plan_id=goal.current_plan_id,
        tool_name=safe['task'], action='capability_activity', status=safe['status'],
        started_at=datetime.fromisoformat(safe['started_at']) if safe.get('started_at') else now,
        completed_at=datetime.fromisoformat(safe['completed_at']) if safe.get('completed_at') else now,
        result_summary='已记录能力执行状态；资料与医学判断保持原有确认边界。', metadata_json={'capability': safe})
    session.add(row)
    session.flush()
    return row


def llm_calls(session, goal, calls, *, accepted, sources, result_count=None, operation_id=None):
    for call in calls:
        checked = accepted and call.get('accepted', True)
        data = {**call, 'accepted': bool(checked and call['status'] == 'SUCCESS'), 'input_sources': sources}
        if operation_id:
            data['operation_id'] = operation_id
        if call['status'] == 'SUCCESS' and not checked:
            data['status'] = 'UNUSABLE'
        if result_count is not None and 'result_count' not in data:
            data['result_count'] = result_count
        record(session, goal, data)
