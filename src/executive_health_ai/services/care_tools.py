"""Small service adapters for longitudinal operations, not new medical abilities."""
from datetime import date, datetime
from uuid import UUID
from sqlalchemy import select
from executive_health_ai.models import Patient, HealthProgram, DoctorReview, ServiceCatalogItem
from executive_health_ai.models.management_workflow import ManagementLog
from executive_health_ai.services.management_workflow import ManagementWorkflowService, owned, task
from executive_health_ai.services.management_action_loop import ManagementActionLoop
from executive_health_ai.models.base import utc_now


def reference(context):
    if not context.get('source_reference') or not context.get('idempotency_key'):
        raise ValueError('自动写入必须有业务来源和幂等键。')


def program(session, goal, context):
    return owned(session, HealthProgram, context['program_id'], goal.member_id)


def state(session, goal, context):
    return ManagementActionLoop().project(session, goal.member_id,
        UUID(context['program_id']) if context.get('program_id') else None)


def profile(session, goal, context):
    p = session.get(Patient, goal.member_id)
    return {'member_id': str(p.id), 'name': p.display_name, 'sex': p.sex,
        'birth_date': str(p.birth_date) if p.birth_date else None}


def archive(session, goal, context):
    # Read through the same projection used by Member360, without a memory copy.
    from executive_health_ai.services.longitudinal import HealthAssessmentService
    return HealthAssessmentService().current_profile(session, goal.member_id)


def phase(session, goal, context):
    row = state(session, goal, context)['phase']
    return {'id': str(row.id), 'goal': row.goal, 'owner': row.owner,
        'start': row.start_date, 'end': row.end_date, 'status': row.status} if row else {}


def items(session, goal, context):
    return {'items': [{'id': i.id, 'title': i.title, 'owner': i.owner,
        'due': i.due, 'status': i.status} for i in state(session, goal, context)['items']]}


def logs(session, goal, context):
    rows = session.scalars(select(ManagementLog).where(ManagementLog.patient_id == goal.member_id)
        .order_by(ManagementLog.occurred_at.desc()).limit(20))
    return {'records': [{'id': str(r.id), 'time': r.occurred_at, 'result': r.result,
        'source': r.evidence, 'next': r.next_action} for r in rows]}


def doctor(session, goal, context):
    rows = session.scalars(select(DoctorReview).where(DoctorReview.patient_id == goal.member_id)
        .order_by(DoctorReview.created_at.desc()).limit(10))
    return {'reviews': [{'id': str(r.id), 'status': r.status, 'question': r.question_for_doctor,
        'opinion': r.opinion if r.status == 'CONFIRMED' else ''} for r in rows]}


def create_item(session, goal, context):
    reference(context)
    p = program(session, goal, context)
    row = task(session, goal.member_id, p.id, context['title'], context['instruction'],
        context.get('owner') or p.owner, datetime.fromisoformat(context['due_at']),
        'followup:' + str(goal.id) + ':' + context['idempotency_key'])
    return {'task_id': str(row.id), 'due_at': row.due_at}


def write_log(session, goal, context):
    reference(context)
    p = program(session, goal, context)
    data = dict(context['data'])
    data.setdefault('occurred_at', utc_now())
    if isinstance(data['occurred_at'], str): data['occurred_at'] = datetime.fromisoformat(data['occurred_at'])
    data['evidence'] = str(context['source_reference'])
    row = ManagementWorkflowService().record_log(session, goal.member_id, p.id,
        actor=goal.owner or p.owner, request_key=context['idempotency_key'], **data)
    return {'log_id': str(row.id)}


def recheck(session, goal, context):
    reference(context)
    p = program(session, goal, context)
    data = dict(context['data'])
    data['planned_at'] = datetime.fromisoformat(data['planned_at'])
    # Existing service requires actual medical advice evidence; a member's wish
    # to get tested is not sufficient to register a formal medical instruction.
    if data.get('doctor_review_id'): data['doctor_review_id'] = UUID(data['doctor_review_id'])
    row = ManagementWorkflowService().create_recheck(session, goal.member_id, p.id, **data)
    return {'recheck_id': str(row.id)}


def complete_item(session, goal, context):
    reference(context)
    from executive_health_ai.services.task_transitions import TaskTransitionService
    from executive_health_ai.models import Task
    row = owned(session, Task, context['task_id'], goal.member_id)
    if row.risk_event_id or row.responsible_role == 'doctor':
        raise PermissionError('医学和风险事项必须经过原有专业流程。')
    TaskTransitionService().complete(session, row.id, actor=context.get('actor') or goal.owner,
        outcome=context['result'])
    return {'task_id': str(row.id), 'status': row.status}


def prepare_review(session, goal, context):
    current = state(session, goal, context)
    if not current['review_ready']: raise ValueError('当前阶段尚未满足复盘条件。')
    return {'phase_id': str(current['phase'].id), 'summary': ManagementActionLoop().stage_summary(current),
        'needs_manager': True}


def next_phase(session, goal, context):
    reference(context)
    p = program(session, goal, context)
    data = dict(context['data'])
    data['start'], data['end'] = date.fromisoformat(data['start']), date.fromisoformat(data['end'])
    row = ManagementActionLoop().enter_next_phase(session, goal.member_id, p.id,
        UUID(context['phase_id']), **data)
    return {'phase_id': str(row.id), 'status': row.status}


def apply_result(session,goal,context):
    reference(context)
    values={k:context[k] for k in ('actor','result','outcome','next_action','request_key')}
    values['follow_at']=datetime.fromisoformat(context['follow_at']) if context.get('follow_at') else None
    row=ManagementActionLoop().process_task(session,goal.member_id,UUID(context['program_id']),
        UUID(context['task_id']),**values)
    return {'log_id':str(row.id)}


def register(registry):
    from executive_health_ai.agent.tools import AgentTool, AUTO, MANAGER_APPROVAL
    from executive_health_ai.services.care_memory import longitudinal
    reads = {'get_member_profile': profile, 'get_health_record': archive,
        'get_observations': registry._observations, 'get_annual_baseline': registry._baseline,
        'get_current_phase': phase, 'get_open_management_items': items,
        'get_recent_management_logs': logs, 'get_doctor_review': doctor,
        'get_care_context': lambda s,g,c: {'context':longitudinal(s,g.member_id)},
        'prepare_stage_review': prepare_review}
    for name, handler in reads.items():
        registry.register(AgentTool(name, '读取已有会员业务事实与来源', AUTO, 'read', True, 10, handler))
    for name, handler, permission in (
        ('create_management_item', create_item, MANAGER_APPROVAL),
        ('create_followup', create_item, AUTO), ('create_recheck', recheck, MANAGER_APPROVAL),
        ('write_management_log', write_log, AUTO),
        ('apply_management_result', apply_result, MANAGER_APPROVAL),
        ('complete_management_item', complete_item, MANAGER_APPROVAL),
        ('start_next_phase', next_phase, MANAGER_APPROVAL)):
        registry.register(AgentTool(name, '复用现有服务，保留业务来源及责任边界', permission, 'write', True, 15, handler))
    registry.register(AgentTool('knowledge_search', '知识库未配置', AUTO, 'read', True, 10,
        lambda s, g, c: {}, enabled=False))
