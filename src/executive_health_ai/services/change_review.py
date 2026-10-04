"""Read-only presentation of the evidence captured when a change was handled.

Never rerun retrieval on page open or infer a completed check from a risk colour.
"""
from executive_health_ai.services.goal_metrics import METRIC_LABELS


def review_summary(payload, risk_level=None, context=None):
    payload = payload or {}
    context = context or {}
    look = payload.get('lookback') or {}
    metric = (payload.get('change') or {}).get('metric')
    history = [r for r in look.get('history_30d', []) if isinstance(r, dict)]
    dated = sorted({str(r['date']) for r in history
                    if r.get('date') and metric in (r.get('metrics') or {})})
    checked = []
    if dated:
        checked.append(f"{METRIC_LABELS.get(metric, '相关指标')}记录：{len(dated)} 个记录日期（{dated[0]} 至 {dated[-1]}）")
    if look.get('annual_baseline'):
        checked.append('个人年度基线')
    if look.get('goal'):
        checked.append('当时的管理目标：' + str(look['goal'].get('title') or '已确认目标'))
    if any({'steps', 'exercise_minutes'}.intersection(r.get('metrics') or {}) for r in history):
        checked.append('同期活动记录')
    for field, label in [('relevant_notes', '相关沟通记录'),
                         ('management_logs', '近期管理记录'), ('doctor_opinions', '相关医生意见')]:
        if field in look:
            count = len(look[field] or [])
            checked.append(f'{label}：{count} 条' if count else f'{label}：未找到相关记录')
    route = (context.get('responsibility') or {}).get('route_type')
    no_action = context.get('no_action_reason')
    if risk_level == 'RED':
        decision = '优先处理 · 需要医生判断' if route == 'DOCTOR' else '优先处理 · 需要人工接手'
    elif risk_level == 'YELLOW':
        decision = '需要关注 · 资料已准备，需要医生判断' if route == 'DOCTOR' else '需要关注 · 请健管联系会员核实原因'
    elif risk_level == 'GREEN':
        decision = '正常跟进 · 本次变化由系统记录，无需新增人工待办'
    elif no_action and (payload.get('change') or {}).get('kind') == 'GOAL_PROGRESS_CHANGE':
        decision = '目标进展已记录 · 无需新增人工待办'
    else:
        decision = '尚未留存明确的处理结论，以当前待办为准'
    return {'available': bool(checked), 'checked': checked,
            'message': '系统发现近期状态发生变化，已进一步核对相关记录。' if checked else
                       '系统记录了本次状态变化；尚未留存可核验的历史核对记录。',
            'decision': decision, 'dates': dated}
