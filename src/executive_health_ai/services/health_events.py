"""Unified trusted ingestion API for MANUAL, MOBILE, DEVICE and SYSTEM facts.

Caller owns the transaction. Router/runtime never parse files or call a model.
AgentEvent remains the compatibility receipt for established bounded policies.
"""
from uuid import UUID, uuid4
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from executive_health_ai.models import HealthEvent, AgentEvent, AgentGoal, Patient
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.member_agents import ensure_member_agent, wake, synchronize
from executive_health_ai.services.health_event_router import EventRouter

SOURCES={'MANUAL','MOBILE','DEVICE','SYSTEM'}
CATEGORIES={'NEW_INFORMATION','MEANINGFUL_CHANGE','TIME_DUE'}
MIGRATED={'HEALTH_DOCUMENT_UPLOADED':'HEALTH_DOCUMENT_UPLOADED','REPORT_UPLOADED':'CHECKUP_REPORT_UPLOADED',
          'DOCTOR_REVIEW_COMPLETED':'DOCTOR_REVIEW_COMPLETED','REVIEW_DUE':'TIME_DUE'}
LABELS={'HEALTH_DOCUMENT_UPLOADED':'收到新的健康资料','CHECKUP_REPORT_UPLOADED':'收到新的体检报告',
        'DOCTOR_REVIEW_COMPLETED':'收到医生已确认的意见','TIME_DUE':'计划跟进时间已到',
        'MEANINGFUL_CHANGE':'检测到健康状态发生值得关注的变化'}
SOURCE_LABELS={'MANUAL':'人工上传 / 录入','MOBILE':'手机提交','DEVICE':'健康设备','SYSTEM':'系统业务结果'}


def ingest_health_event(session: Session,**values) -> tuple[HealthEvent,bool]:
    """Accept one fact atomically; return its durable receipt and created flag.

    The caller commits. ``dispatch=False`` queues the receipt for the existing
    worker. Future TIME_DUE receipts always wait for their actual due time.
    References and member bindings must come from authenticated adapters.
    """
    # Own a savepoint, never the caller's commit. Reserve the member before a
    # SQLite SAVEPOINT so rollback cannot accidentally leave a committed receipt.
    from executive_health_ai.models.archive_guard import locked_members
    locked_members(session.connection(),{UUID(str(values['member_id']))})
    with session.begin_nested():return _ingest_health_event(session,**values)


def _ingest_health_event(session,*,member_id,event_type,event_category,source_type,source_id,
                        payload_ref=None,occurred_at=None,correlation_id=None,idempotency_key=None,dispatch=True,supervisor=None):
    member_id=UUID(str(member_id));source_id=str(source_id)
    if source_type not in SOURCES or event_category not in CATEGORIES:raise ValueError('事件来源或分类无效。')
    if not source_id or len(source_id)>256 or not event_type or len(event_type)>64:raise ValueError('事件来源标识无效。')
    if event_type.endswith('_RAW_MEASUREMENT') and event_category!='NEW_INFORMATION':raise ValueError('原始测量不能声明为健康变化。')
    if event_type in {'HEALTH_DOCUMENT_UPLOADED','CHECKUP_REPORT_UPLOADED','DOCTOR_REVIEW_COMPLETED'} and event_category!='NEW_INFORMATION':raise ValueError('事件分类不匹配。')
    if event_type in {'DOCTOR_REVIEW_COMPLETED','MEANINGFUL_CHANGE','TIME_DUE'} and source_type!='SYSTEM':raise ValueError('此事件必须由系统业务或规则产生。')
    if event_type in {'MEANINGFUL_CHANGE','TIME_DUE'} and event_category!=event_type:raise ValueError('事件分类不匹配。')
    at=occurred_at or utc_now()
    if at.tzinfo is None or at.utcoffset() is None:raise ValueError('事件发生时间必须包含时区。')
    member=session.get(Patient,member_id)
    if not member:raise ValueError('会员不存在。')
    from hashlib import sha256
    key=idempotency_key or sha256(f'{member_id}:{event_type}:{source_id}'.encode()).hexdigest()
    if len(key)>256:raise ValueError('幂等键过长。')
    origin=(HealthEvent.member_id==member_id,HealthEvent.event_type==event_type,HealthEvent.source_id==source_id)
    prior=session.scalar(select(HealthEvent).where(HealthEvent.idempotency_key==key))
    if prior and (prior.member_id,prior.event_type,prior.source_id)!=(member_id,event_type,source_id):raise ValueError('幂等键已属于其它业务事件。')
    prior=prior or session.scalar(select(HealthEvent).where(*origin))
    created=False
    if prior:
        if prior.source_type!=source_type:raise ValueError('重复事件来源不一致。')
        event=prior
    else:
        event=HealthEvent(member_id=member_id,occurred_at=at,event_type=event_type,event_category=event_category,
            source_type=source_type,source_id=source_id,source=SOURCE_LABELS[source_type],description=LABELS.get(event_type,'收到新的业务信息'),
            received_at=utc_now(),payload_ref=payload_ref or {},correlation_id=correlation_id or uuid4().hex,
            idempotency_key=key,status='IGNORED' if member.archived_at else 'PENDING')
        try:
            with session.begin_nested():session.add(event);session.flush()
            created=True
        except IntegrityError:
            event=session.scalar(select(HealthEvent).where(*origin))
            if event is None:raise
        if created and event.status!='IGNORED' and event_type in {'DEVICE_RAW_MEASUREMENT','MOBILE_RAW_MEASUREMENT'}:
            from executive_health_ai.services.health_event_measurements import store_measurement
            store_measurement(session,event)
    if event.event_category=='TIME_DUE' and event.status=='PENDING':
        ensure_member_agent(session,member_id)
        synchronize(session,member_id)
    if dispatch and event.status=='PENDING' and (event.event_category!='TIME_DUE' or event.occurred_at<=utc_now()):
        dispatch_event(session,event,supervisor=supervisor)
    return event,created


def from_legacy(session,legacy,supervisor):
    kind=MIGRATED[legacy.event_type]
    origin=(legacy.metadata_json or {}).get('origin_type','MANUAL' if kind.endswith('UPLOADED') else 'SYSTEM')
    event,_=ingest_health_event(session,member_id=legacy.member_id,event_type=kind,
        event_category='TIME_DUE' if kind=='TIME_DUE' else 'NEW_INFORMATION',source_type=origin,
        source_id=str(legacy.id) if kind=='TIME_DUE' else legacy.source_id,occurred_at=legacy.occurred_at,
        payload_ref={'agent_event_id':str(legacy.id)},supervisor=supervisor)
    if event.status=='IGNORED' and legacy.processed_at is None:
        legacy.status,legacy.processed_at='IGNORED',utc_now()
    from executive_health_ai.services.member_archive import is_archived
    if is_archived(session,legacy.member_id):return None
    return session.get(AgentGoal,event.goal_id) if event.goal_id else None


def dispatch_event(session,event,*,supervisor=None):
    from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
    from executive_health_ai.services.member_archive import is_archived
    supervisor=supervisor or HealthOpsAgentSupervisor()
    claim=session.execute(update(HealthEvent).where(HealthEvent.id==event.id,HealthEvent.status=='PENDING')
        .values(status='ROUTING')).rowcount
    if claim!=1:return
    if is_archived(session,event.member_id):
        event.status,event.route_action='IGNORED','IGNORE';session.flush();return
    decision=EventRouter().decide(session,event)
    event.route_action=decision.action
    if decision.action in {'IGNORE','STORE_ONLY'}:
        event.status='IGNORED' if decision.action=='IGNORE' else 'STORED';session.flush();return
    agent=ensure_member_agent(session,event.member_id)
    wake(session,agent,event)
    goal=None
    payload=event.payload_ref or {}
    if event.event_type in {'HEALTH_DOCUMENT_UPLOADED','CHECKUP_REPORT_UPLOADED','DOCTOR_REVIEW_COMPLETED'}:
        legacy=session.get(AgentEvent,UUID(payload['agent_event_id'])) if payload.get('agent_event_id') else None
        if legacy is None:
            from executive_health_ai.services.event_service import EventService
            kind={'CHECKUP_REPORT_UPLOADED':'REPORT_UPLOADED'}.get(event.event_type,event.event_type)
            object_type={'HEALTH_DOCUMENT_UPLOADED':'health_document','CHECKUP_REPORT_UPLOADED':'document','DOCTOR_REVIEW_COMPLETED':'doctor_review'}[event.event_type]
            metadata=dict(payload.get('metadata') or {})
            if kind=='REPORT_UPLOADED':metadata['workflow']='post_checkup_v1'
            legacy,_=EventService().publish(session,event_type=kind,member_id=event.member_id,source_type=object_type,
                source_id=event.source_id,metadata=metadata,dedup_key='health-event:'+str(event.id))
        expected={'CHECKUP_REPORT_UPLOADED':'REPORT_UPLOADED'}.get(event.event_type,event.event_type)
        if legacy.member_id!=event.member_id or legacy.source_id!=event.source_id or legacy.event_type!=expected:
            raise ValueError('事件引用与会员来源不一致。')
        legacy.metadata_json={**legacy.metadata_json,'health_event_id':str(event.id),'member_agent_id':str(agent.id),
            'routed_goal_id':str(decision.goal_id) if decision.goal_id else None,'defer_external_io':True}
        goal=supervisor._receive_business_event(session,legacy)
    elif event.event_type=='TIME_DUE' and payload.get('agent_event_id'):
        legacy=session.get(AgentEvent,UUID(payload['agent_event_id']))
        if not legacy or legacy.member_id!=event.member_id:raise ValueError('到期事件来源无效。')
        goal=supervisor._receive_business_event(session,legacy)
    else:
        # Phase 1A wake/check only: no general planner, risk decision or new task.
        goal=session.get(AgentGoal,decision.goal_id) if decision.goal_id else None
    if goal:
        event.goal_id=goal.id
        goal.context_json={**goal.context_json,'member_agent_id':str(agent.id),'health_event_id':str(event.id),
            'trigger_reason':LABELS.get(event.event_type,'收到新的业务信息'),'trigger_source':SOURCE_LABELS[event.source_type]}
    event.status='PROCESSED';session.flush();synchronize(session,event.member_id)


def process_pending(session,supervisor,limit=100,now=None):
    from sqlalchemy import or_
    now=now or utc_now()
    rows=list(session.scalars(select(HealthEvent).where(HealthEvent.status=='PENDING',HealthEvent.event_category.is_not(None),
        or_(HealthEvent.event_category!='TIME_DUE',HealthEvent.occurred_at<=now))
        .order_by(HealthEvent.received_at).limit(limit)))
    from executive_health_ai.models.archive_guard import locked_members
    for event in rows:
        locked_members(session.connection(),{event.member_id})
        try:
            with session.begin_nested():dispatch_event(session,event,supervisor=supervisor)
        except (ValueError,KeyError,PermissionError) as exc:
            # Invalid queued business input must not starve all other members.
            # The entire wake/goal attempt rolls back; retain the failed receipt.
            import logging
            logging.getLogger(__name__).exception('health_event_routing_rejected')
            event.status='FAILED'
            event.payload_ref={**(event.payload_ref or {}),'routing_error':type(exc).__name__+': '+str(exc)[:240]}
            session.flush()
            synchronize(session,event.member_id)
    return len(rows)
