"""V1 adapter: existing risk/review facts -> shared policy -> existing audit log."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from executive_health_ai.models import AgentRunTrace, DoctorReview, RiskEvent
from executive_health_ai.services.responsibility import ResponsibilityRouter, ResponsibilityRoute


def latest(session, goal):
    row = session.scalar(select(AgentRunTrace).where(AgentRunTrace.goal_id == goal.id,
        AgentRunTrace.action == 'responsibility_routed').order_by(AgentRunTrace.started_at.desc(), AgentRunTrace.id.desc()))
    if row:
        data = dict(row.metadata_json['responsibility'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        for key in ('reason_codes', 'rule_refs', 'evidence_refs'):
            data[key] = tuple(data[key])
        return ResponsibilityRoute(**data)


def facts(session, goal):
    ctx = goal.context_json or {}
    risks = list(session.scalars(select(RiskEvent).where(RiskEvent.patient_id == goal.member_id,
        RiskEvent.status.not_in(('CLOSED', 'DISMISSED_DATA_ISSUE')))))
    review = session.get(DoctorReview, UUID(ctx['review_id'])) if ctx.get('review_id') else None
    if review and review.patient_id != goal.member_id:
        raise ValueError('医生判断不属于此会员。')
    return risks, review


def evaluate(session, goal, *, stage=None, codes=(), actor=None, ai_suggestion=None,
             escalation_cleared=False, ignore_pause=False):
    ctx, stage = goal.context_json or {}, stage or goal.current_stage
    risks, review = facts(session, goal)
    doctor_done = bool(review and review.status == 'CONFIRMED')
    previous = latest(session, goal)
    reasons = list(codes)
    refs, evidence = [], ['document:'+goal.source_id]
    if ctx.get('baseline'):
        evidence.append('baseline:'+ctx['baseline']['id'])
    if ctx.get('review_id'):
        evidence.append('doctor_review:'+ctx['review_id'])
    for risk in risks:
        # Only an explicit emergency flag causes emergency escalation. RED by
        # itself preserves the existing doctor-review requirement.
        if risk.requires_emergency_action:
            reasons.append('EMERGENCY_RULE')
        elif (not doctor_done or (review.reviewed_at and risk.created_at > review.reviewed_at)) and (risk.requires_doctor_review or risk.risk_level == 'RED'):
            reasons.append('RULE_DOCTOR')
        else:
            continue
        refs.append('risk_rule:'+str(risk.risk_rule_id))
        evidence.append('risk_event:'+str(risk.id))
    if not doctor_done and (ctx.get('requires_medical_review') or review):
        reasons.append('MANAGER_REQUEST' if review else 'RULE_DOCTOR')
    if goal.automation_paused and not ignore_pause:
        reasons.append('HUMAN_TAKEOVER')
    if ctx.get('structured') is False:
        reasons.append('UNREADABLE_REPORT')
    # A contradiction is exact same code/unit with different values, not an
    # invented physiological threshold or a model-generated risk assessment.
    values = {}
    for finding in ctx.get('findings', []):
        key = (finding['code'], finding['unit'])
        if key in values and values[key] != finding['value']:
            reasons.append('DATA_CONFLICT')
            evidence.append('report_candidate:'+finding['candidate_id'])
        values[key] = finding['value']
    if stage in {'ESCALATED', 'FAILED'} and not reasons and not escalation_cleared:
        reasons.append('UNSAFE_CONTINUATION')
    base = {'WAITING_MANAGER_REVIEW': 'MANAGER_CONFIRMATION', 'WAITING_ACTION_APPROVAL': 'ACTION_APPROVAL',
            'WAITING_DOCTOR_REVIEW': 'MANAGER_REQUEST', 'CREATING_ACTIONS': 'CONFIRMED_ARRANGEMENTS',
            'COMPLETED': 'CONFIRMED_ARRANGEMENTS'}.get(stage, 'NON_MEDICAL_PREPARATION')
    reasons.append('NON_MEDICAL_PREPARATION' if doctor_done and base == 'MANAGER_REQUEST' else base)
    return ResponsibilityRouter().decide(reason_codes=reasons, rule_refs=refs, evidence_refs=evidence,
        previous=previous, doctor_cleared=doctor_done, escalation_cleared=escalation_cleared,
        ai_suggestion=ai_suggestion, confirmed_by=actor)


def record(session, goal, decision):
    old = latest(session, goal)
    if old and all(getattr(old, k) == getattr(decision, k) for k in
                   ('route_type', 'reason_codes', 'rule_refs', 'evidence_refs', 'confirmed_by')):
        return old
    session.add(AgentRunTrace(goal_id=goal.id, plan_id=goal.current_plan_id,
        action='responsibility_routed', status='COMPLETED', started_at=decision.created_at,
        completed_at=decision.created_at, result_summary=decision.reason_summary,
        metadata_json={'responsibility': decision.payload()}))
    session.flush()
    return decision


def route(session, goal, **kwargs):
    return record(session, goal, evaluate(session, goal, **kwargs))


def guard(session, goal, *, actions=False):
    decision = evaluate(session, goal)
    if decision.route_type == 'ESCALATE':
        raise ValueError('需要优先人工处理：'+decision.reason_summary)
    if actions and decision.route_type == 'DOCTOR':
        raise ValueError('医生判断尚未完成，不能建立后续安排。')
    return decision


def medical_reasons(text):
    """Conservative routing of requested actions, never a diagnosis from text."""
    patterns = {'DIAGNOSIS': ('诊断', '医学异常', '医学判断', 'diagnos'),
        'MEDICATION': ('用药', '停药', '开药', '剂量', '药物', 'medication', 'prescri'),
        'TREATMENT': ('治疗', 'treatment'), 'EXAMINATION': ('进一步检查', '医学检查', '进一步医学', 'medical test'),
        'REFERRAL': ('转诊', 'referral'), 'MEDICAL_RISK': ('医学风险', 'medical risk'),
        'DISEASE_CHANGE': ('疾病变化', '病情变化', 'disease progression')}
    return tuple(code for code, words in patterns.items() if any(word in (text or '').lower() for word in words))
