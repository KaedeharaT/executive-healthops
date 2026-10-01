"""Bounded risk handling on DAILY_CARE, existing rules, services and waits.

No model is called here. Preparation precedes the human gate; RiskEvent remains
the single human responsibility. A doctor result resumes, never replaces, a goal.
"""
from uuid import UUID
from sqlalchemy import select
from executive_health_ai.models import RiskEvent, RiskRule, Observation, Task, DoctorReview
from executive_health_ai.services import care_runtime as runtime
from executive_health_ai.services.autonomy import current_risk, POLICY_VERSION
from executive_health_ai.services.responsibility import ResponsibilityRouter


def responsibility_for(session, risk):
    # Use the event's versioned rule result, not mutable model text or a new rule
    # version installed after the observation was evaluated.
    route = (risk.evidence_json or {}).get('recommended_route') or risk.recommended_route
    reason = ('RULE_DOCTOR' if route == 'DOCTOR' else 'EMERGENCY_RULE' if route in {'ESCALATE', 'EMERGENCY'}
        else 'CONFIRMED_ARRANGEMENTS' if risk.risk_level == 'GREEN'
        else 'MANAGER_CONFIRMATION' if route in {'MANAGER', 'HEALTH_MANAGER'} or risk.risk_level == 'YELLOW'
        else 'EMERGENCY_RULE')
    return ResponsibilityRouter().decide(reason_codes=[reason],
        rule_refs=[str(risk.risk_rule_id)], evidence_refs=[str(risk.id)])


def evaluate_event(session, event):
    """One evaluation per deduplicated change, with owned normalized evidence."""
    payload = event.payload_ref or {}
    if event.event_category != 'MEANINGFUL_CHANGE':
        return current_risk(session, event.member_id)
    if 'risk_evaluation' not in payload and payload.get('observation_ids'):
        ids = [UUID(str(i)) for i in payload['observation_ids']]
        rows = list(session.scalars(select(Observation).where(Observation.id.in_(ids))))
        if len(rows) != len(set(ids)) or any(r.patient_id != event.member_id for r in rows):
            raise ValueError('变化依据必须属于当前会员。')
        from executive_health_ai.services.risk_triage import RiskEvaluationService
        latest = max(rows, key=lambda r: r.observed_at)
        result = RiskEvaluationService().evaluate_observation(session, latest.id)
        event.payload_ref = {**payload, 'risk_evaluation': {'observation_id': str(latest.id),
            'engine': 'deterministic', 'policy_version': POLICY_VERSION,
            'created_events': result.created_event_count}}
        session.flush()
    return current_risk(session, event.member_id)


def advance(session, goal, supervisor):
    risk = session.get(RiskEvent, UUID(goal.context_json['risk_event_id']))
    if not risk or risk.patient_id != goal.member_id:
        raise ValueError('风险依据与当前会员不一致。')
    ctx = goal.context_json
    if risk.status in {'CLOSED', 'DISMISSED_DATA_ISSUE'}:
        goal.context_json = {**ctx, 'no_action_reason': '原风险已有授权处理结果，保留历史并继续管理'}
        return runtime.finish(session, goal)
    # Keep this goal bound to its original issue. Tool policy independently uses
    # the highest current risk; rebinding would let an old opinion clear a newer
    # issue or leave two goals waiting on the same doctor's result.
    route = responsibility_for(session, risk)
    goal.context_json = {**ctx, 'responsibility': route.payload(), 'risk_event_id': str(risk.id),
        'preparation_complete': True, 'policy_version': POLICY_VERSION}
    runtime.trace(session, goal, 'autonomy_prepared', '已核对当前阶段、开放事项和医生意见',
        risk_event_id=str(risk.id), risk_level=risk.risk_level, rule_version=(risk.evidence_json or {}).get('rule_version'),
        responsibility=route.payload(), policy_version=POLICY_VERSION)
    if risk.risk_level == 'GREEN':
        supervisor.registry.execute(session, 'record_goal_progress', goal,
            {'summary': '已核对确定性规则、当前计划和开放事项；本次变化无需新增人工判断。',
             'idempotency_key': 'green-check'})
        goal.context_json = {**goal.context_json, 'no_action_reason': '已完成规则与现有安排核对，无需新增人工事项'}
        return runtime.finish(session, goal)
    if route.route_type == 'DOCTOR':
        review = session.get(DoctorReview, UUID(ctx['review_id'])) if ctx.get('review_id') else None
        if review and (review.patient_id != goal.member_id or review.risk_event_id != risk.id):
            # A returned opinion for an earlier issue cannot clear a newer RED.
            review = None
        if review and review.status == 'CONFIRMED':
            # The existing doctor service creates the actual follow-up. No risk
            # downgrade, automatic medical conclusion or automatic RED closure.
            next_task = session.scalar(select(Task).where(Task.risk_event_id == risk.id,
                Task.status.not_in(('COMPLETED', 'CANCELLED'))).order_by(Task.created_at.desc()))
            goal.context_json = {**goal.context_json, 'doctor_result_reference': str(review.id)}
            runtime.wait(session, goal, 'WAITING_MANAGER', next_action=next_task.instruction if next_task else '按医生意见确认后续安排',
                expected_event='RISK_RESOLVED', expected_source=risk.id)
        else:
            result = supervisor.registry.execute(session, 'request_doctor_review', goal,
                {'idempotency_key': 'risk-review:' + str(risk.id)})
            goal.context_json = {**goal.context_json, 'review_id': result['doctor_review_id']}
            runtime.wait(session, goal, 'WAITING_DOCTOR', next_action='资料已准备，等待医生判断；健管跟踪交接',
                expected_event='DOCTOR_REVIEW_COMPLETED', expected_source=result['doctor_review_id'])
    else:
        risk.requires_manager_review = True
        risk.acknowledged_by = risk.acknowledged_by or goal.owner or '健康管理师'
        runtime.wait(session, goal, 'WAITING_MANAGER',
            next_action=('优先接手，核对异常依据并记录处置结果' if risk.risk_level == 'RED'
                else '联系会员确认近期情况；已核对数据、当前方案和现有安排'),
            expected_event='RISK_RESOLVED', expected_source=risk.id)
    return goal


def doctor_return(session, event, goal, supervisor):
    if runtime.resume(session, goal, event_type=event.event_type, source_id=event.source_id):
        from executive_health_ai.services.daily_care import advance as continue_goal
        continue_goal(session, goal, supervisor)
    return goal
