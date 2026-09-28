"""Read-only workspace projection over existing assessments, plans and calls."""
from datetime import date
from uuid import UUID, uuid4
from sqlalchemy import select
from executive_health_ai.models import AgentGoal, AgentRunTrace, Document, ReportExtractionRun
from executive_health_ai.services.assessment_import import AssessmentImportService, DATA_STEPS
from executive_health_ai.services.management_workflow import ManagementWorkflowService
from executive_health_ai.services.profile_ingestion import ProfileIngestionService
from executive_health_ai.services.agent_capabilities import load as support_for

LABELS=('基础资料','家族史','个人病史','手术 / 住院','过敏','用药','生活方式','环境与暴露','会员重点关注','专项症状评估')
STATUS={'已填写':'已完成','资料缺失':'待补充','待确认':'待确认','存在冲突':'存在冲突'}
PHASES=('资料接收','内容读取','健康信息提取','匹配健康档案','预填初始评估','等待健管确认','完成')
PHASE_INDEX={'RECEIVED':0,'PARSING':1,'NORMALIZING':2,'MATCHING':3,'REVIEW':5,'WRITING':6}
imports=AssessmentImportService()


def assessment(session, patient_id, row):
    if row:
        view=imports.project(session,patient_id,row.id)
        sections=[{**s,'label':label,'status':STATUS[s['status']],
            'prefilled':sum(g['safe'] for g in s['groups']),
            'pending':sum(not s['checked'] for g in s['groups']),
            'conflicts':sum(g['conflict'] for g in s['groups']) if not s['checked'] else 0}
            for label,s in zip(LABELS,view['steps'])]
    else:
        view=None
        sections=[dict(step=step,label=label,status='待补充',groups=[],prefilled=0,pending=0,conflicts=0)
                  for step,label in zip(DATA_STEPS,LABELS)]
    stats={'percent':sum(s['status']=='已完成' for s in sections)*10,
        'prefilled':sum(s['prefilled'] for s in sections),'pending':sum(s['pending'] for s in sections),
        'missing':sum(s['status']=='待补充' for s in sections),'conflicts':sum(s['conflicts'] for s in sections)}
    return view,sections,stats


def first_incomplete(session,patient_id,row):
    _,sections,_=assessment(session,patient_id,row)
    return next((s['step'] for s in sections if s['status']!='已完成'),'确认提交')


def upload(session,patient,view,files):
    """One automatic route; never reopen a submitted assessment implicitly."""
    from executive_health_ai.services.member_archive import require_active
    require_active(session,patient.id)
    if not files or len(files)>20 or sum(len(data) for _,data in files)>100*1024*1024:
        raise ValueError('请选择 1–20 份资料，每批不超过 100 MB。')
    row=view.intake
    if row is None:
        year=(view.program.cycle_year or view.program.start_date.year) if view.program else date.today().year
        row=ManagementWorkflowService().start_intake(session,patient.id,year,view.owner)
        session.flush()
    if row.status=='DRAFT':
        results=imports.upload_batch(session,patient.id,row.id,files,actor=view.owner)
    else:
        results=[]
        for name,data in files:
            try:
                with session.begin_nested():
                    goal,duplicate=ProfileIngestionService().upload(session,patient.id,name,data,'auto',actor=view.owner,role='HEALTH_MANAGER')
                results.append(dict(filename=name,goal_id=str(goal.id),duplicate=duplicate,error=None))
            except (ValueError,PermissionError,UnicodeError) as error:
                results.append(dict(filename=name,goal_id=None,duplicate=False,error=str(error)))
    batch=str(uuid4())
    for result in results:
        if result['goal_id'] and not result['duplicate']:
            goal=session.get(AgentGoal,UUID(result['goal_id']))
            goal.context_json={**goal.context_json,'workspace_batch':batch}
    return results


def project(session,patient_id,row,goal_id=None):
    imported,sections,stats=assessment(session,patient_id,row)
    goals=list(session.scalars(select(AgentGoal).where(AgentGoal.member_id==patient_id,AgentGoal.goal_type=='PROFILE_INTAKE')
        .order_by(AgentGoal.started_at.desc(),AgentGoal.id)))
    if goals:
        queued=[g for g in goals if g.status in {'RUNNING','PROCESSING','WRITING'}]
        selected=next((g for g in goals if str(g.id)==str(goal_id)),goals[0])
        batch=selected.context_json.get('workspace_batch')
        goals=[g for g in goals if g.context_json.get('workspace_batch')==batch] if batch else (
            imported['goals'] if imported and selected.context_json.get('intake_id')==str(row.id) else [selected])
        if not goal_id:
            goals=list({g.id:g for g in [*goals,*queued]}.values())
    goals=sorted(goals,key=lambda g:(g.started_at,str(g.id)))
    files=[];events=[]
    for goal in goals:
        doc=session.get(Document,UUID(goal.source_id));run=session.get(ReportExtractionRun,UUID(goal.context_json['run_id']))
        support,traces=support_for(session,goal)
        files.append(dict(goal=goal,document=doc,run=run,support=support,count=run.candidate_count or 0))
        events.extend((t.started_at,doc.title,t.result_summary) for t in traces if t.action=='profile_activity' and t.result_summary)
    pending=next((f for f in files if f['goal'].status in {'RUNNING','PROCESSING','WRITING'}),None)
    waiting=any(f['goal'].status in {'WAITING_MANAGER','WAITING_DOCTOR','ESCALATED'} for f in files)
    finished=bool(files) and all(f['goal'].status=='COMPLETED' for f in files)
    ready=bool(files) and not pending
    phase=PHASE_INDEX.get(pending['goal'].current_stage,1) if pending else 6 if finished else 5 if files else 0
    return dict(imported=imported,sections=sections,stats=stats,files=files,events=sorted(events,key=lambda e:e[0]),
        current=pending,processing=bool(pending),ready=ready,finished=finished,waiting=waiting,phase=phase,
        count=sum(f['count'] for f in files),processed=sum(f['goal'].status=='COMPLETED' or f['goal'].current_stage=='REVIEW' for f in files),
        updates=sum(sum((f['goal'].context_json.get('output') or {}).get(k,0) for k in ('profile','history','measurements')) for f in files))
