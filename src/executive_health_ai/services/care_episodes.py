"""Explicit care relationships, stored as versioned references in existing history.

No parallel task/outcome store. A relationship receipt is clinical history,
not an automation event, and never wakes a MemberAgent.
"""
from uuid import UUID
from sqlalchemy import select
from executive_health_ai.models import HealthEvent, Observation, RiskEvent, DoctorReview, Task, OutcomeEvaluation, ServiceRequest, ManagementPlan, FollowUp, ClinicalRecommendation
from executive_health_ai.models.goal_data import CommunicationRecord, ManagementGoal
from executive_health_ai.models.management_workflow import ManagementLog, RecheckPlan, StageReview
from executive_health_ai.models.base import utc_now

MODELS = {m.__name__: m for m in (HealthEvent, Observation, RiskEvent, DoctorReview, Task,
    OutcomeEvaluation, ServiceRequest, ManagementPlan, CommunicationRecord, ManagementGoal,
    ManagementLog, RecheckPlan, StageReview, FollowUp, ClinicalRecommendation)}


def link_care_episode(session, member_id, trigger_id, *, links, actor, role):
    """Append an explicitly human-confirmed relation, preserving previous versions."""
    from executive_health_ai.models.archive_guard import locked_members
    member_id, trigger_id = UUID(str(member_id)), UUID(str(trigger_id))
    if role not in {'HEALTH_MANAGER', 'DOCTOR', 'ADMIN'} or not actor.strip():
        raise PermissionError('管理关系需要明确的责任人确认。')
    locked_members(session.connection(), {member_id})
    trigger = session.get(HealthEvent, trigger_id)
    if not trigger or trigger.member_id != member_id or trigger.event_type != 'MEANINGFUL_CHANGE':
        raise ValueError('请关联本会员的重要变化。')
    checked = []
    for ref in links:
        model = MODELS.get(ref.get('type'))
        row = session.get(model, UUID(str(ref['id']))) if model else None
        if not row or row.patient_id != member_id:
            raise ValueError('依据不存在或不属于此会员。')
        if isinstance(row, DoctorReview) and row.status != 'CONFIRMED':
            raise ValueError('医生意见尚未确认。')
        if isinstance(row, ClinicalRecommendation) and row.status.lower() != 'confirmed':
            raise ValueError('医生意见尚未确认。')
        checked.append({'type': model.__name__, 'id': str(row.id)})
    key = 'care-episode:' + str(trigger_id)
    prior = session.scalar(select(HealthEvent).where(HealthEvent.member_id == member_id,
        HealthEvent.event_type == 'CARE_EPISODE_LINK', HealthEvent.correlation_id == key)
        .order_by(HealthEvent.received_at.desc(), HealthEvent.source_id.desc()).limit(1))
    refs = { (r['type'], r['id']): r for r in ((prior.payload_ref or {}).get('links', []) if prior else []) }
    refs.update({(r['type'], r['id']): r for r in checked})
    refs = sorted(refs.values(), key=lambda r: (r['type'], r['id']))
    if prior and refs == prior.payload_ref['links']:
        return prior
    version = (prior.payload_ref['version'] + 1) if prior else 1
    row = HealthEvent(member_id=member_id, occurred_at=utc_now(), event_type='CARE_EPISODE_LINK',
        event_category=None, description='确认本次变化、管理行动与观察结果的关联', source='健管/医生确认',
        source_type='MANUAL', source_id=f'{key}:{version}', correlation_id=key,
        payload_ref={'trigger_id':str(trigger.id), 'links':refs, 'version':version,
            'confirmed_by':actor, 'confirmed_at':utc_now().isoformat(),
            'supersedes':str(prior.id) if prior else None}, status='STORED')
    session.add(row); session.flush()
    return row
