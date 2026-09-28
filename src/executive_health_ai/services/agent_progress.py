"""Read-only business progress from the existing plan and execution evidence.

Time changes elapsed labels only. A batch has completed a business step only
when every file has completed it; file throughput is a separate measure.
"""
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from sqlalchemy import select
from executive_health_ai.models import AgentPlanStep, AgentRunTrace

PROFILE_STEPS=('资料接收','内容读取','健康信息提取','档案匹配','初评预填','健管确认','完成')
CARE_STEPS=('报告接收','系统分析','责任分流','专业确认','行动建立','完成')
ACTIVE={'RUNNING','PROCESSING','WRITING'}
FAILED={'FAILED','ESCALATED','CANCELLED'}


def stamp(value):
    if isinstance(value,str):value=datetime.fromisoformat(value)
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def seconds(start,end):
    return max(0,int((stamp(end)-stamp(start)).total_seconds())) if start and end else 0


@dataclass(frozen=True)
class AgentProgressProjection:
    labels: tuple
    done: tuple
    current_step: int
    total_steps: int
    completed_steps: int
    progress_percent: int
    current_activity: str
    started_at: object
    elapsed_seconds: int
    stage_elapsed_seconds: int
    running: bool
    status: str
    file_total: int=0
    file_completed: int=0
    current_file: str=''
    ai_running: bool=False
    ai_started_at: object=None
    ai_elapsed_seconds: int=0
    ai_used: bool=False
    ai_count: int=0
    ai_status: str='NOT_USED'
    timeout: bool=False

    @property
    def step_label(self):return self.labels[self.current_step-1]

    @property
    def wait_message(self):
        if not self.running:return ''
        if self.stage_elapsed_seconds>=90:return '处理时间较长，系统仍在等待结果'
        if self.stage_elapsed_seconds>=30:return f'仍在处理中 · 已等待 {self.stage_elapsed_seconds}秒'
        return ''


def project(goal,steps=(),traces=(),*,now=None):
    now=stamp(now or datetime.now(timezone.utc))
    ctx=goal.context_json or {};events=ctx.get('progress_events',{})
    states={s.step_type:s for s in steps}
    complete=lambda name: name in states and states[name].status=='COMPLETED'
    ended=goal.status=='COMPLETED'
    running=goal.status in ACTIVE and not getattr(goal,'automation_paused',False)
    profile=goal.goal_type=='PROFILE_INTAKE'
    if profile:
        read=bool(events.get('CONTENT_READ')) or complete('PARSING')
        done=(complete('RECEIVED'),read,complete('PARSING'),complete('MATCHING'),
              complete('MATCHING'),complete('REVIEW'),ended)
        labels=PROFILE_STEPS
    else:
        from executive_health_ai.agent.post_checkup import is_care_goal
        if is_care_goal(goal):
            doctor=states.get('WAITING_DOCTOR_REVIEW')
            confirmed=complete('WAITING_MANAGER_REVIEW') and bool(doctor and doctor.status in {'COMPLETED','SKIPPED'})
            routed=complete('ANALYZING') and any(t.action=='responsibility_routed' for t in traces)
            done=(complete('REPORT_RECEIVED'),complete('ANALYZING'),routed,confirmed,complete('CREATING_ACTIONS'),ended)
            labels=CARE_STEPS
        else:
            # Legacy plans retain their own actual step count, never the intake seven.
            labels=tuple('业务步骤 '+str(i+1) for i in range(len(steps))) or ('流程完成',)
            done=tuple(s.status=='COMPLETED' for s in steps) or (False,)
    if ended:done=(True,)*len(labels)
    elif all(done):done=(*done[:-1],False)
    count=sum(done);index=next((i for i,d in enumerate(done) if not d),len(done)-1)
    current=states.get(goal.current_stage)
    stage_start=(ctx.get('execution') or {}).get('event_at') or (current.started_at if current else None) or goal.started_at
    end=getattr(goal,'completed_at',None) if ended else now
    calls=[t for t in traces if t.action=='capability_activity' and
           (t.metadata_json or {}).get('capability',{}).get('kind')=='LLM' and
           t.metadata_json['capability'].get('request_sent')]
    attempt=stamp(events.get('PARSING_STARTED') or (ctx.get('execution') or {}).get('started_at')) if profile else None
    if attempt:calls=[t for t in calls if stamp(t.started_at)>=attempt]
    call=max(calls,key=lambda t:stamp(t.started_at),default=None)
    data=call.metadata_json['capability'] if call else {}
    ai_start=stamp(events.get('AI_REQUEST_STARTED'))
    ai_end=max((stamp(events[k]) for k in ('AI_REQUEST_FINISHED','AI_REQUEST_FAILED','AI_REQUEST_TIMEOUT','AI_UNAVAILABLE','AI_RESULT_CHECKED') if events.get(k)),default=None)
    ai_running=running and bool(ai_start and (not ai_end or ai_start>ai_end))
    if call and (not ai_start or stamp(call.started_at)>ai_start):
        ai_start=stamp(call.started_at);ai_end=stamp(call.completed_at)
    timeout=bool(events.get('AI_REQUEST_TIMEOUT') and (not ai_start or stamp(events['AI_REQUEST_TIMEOUT'])>=ai_start)) or data.get('failure_reason')=='TIMEOUT'
    activity=('等待健管确认' if goal.status=='WAITING_MANAGER' else '等待医生判断' if goal.status=='WAITING_DOCTOR'
              else '处理未完成，需要人工处理' if goal.status in FAILED else '本次流程已完成' if ended
              else '自动处理已暂停' if not running else '本地AI正在整理自由文本健康资料' if ai_running else '正在'+labels[index])
    return AgentProgressProjection(labels,tuple(done),index+1,len(labels),count,round(count/len(labels)*100),activity,
        stamp(goal.started_at),seconds(goal.started_at,end),seconds(stage_start,now),running,goal.status,
        ai_running=ai_running,ai_started_at=ai_start,ai_elapsed_seconds=seconds(ai_start,now if ai_running else ai_end),
        ai_used=bool(ai_start or calls),ai_count=sum(t.metadata_json['capability'].get('result_count',0) for t in calls if t.metadata_json['capability'].get('accepted')),
        ai_status='RUNNING' if ai_running else data.get('status','UNAVAILABLE' if timeout or events.get('AI_UNAVAILABLE') else 'SUCCESS' if ai_end else 'NOT_USED'),timeout=timeout)


def load(session,goal,*,now=None):
    steps=list(session.scalars(select(AgentPlanStep).where(AgentPlanStep.plan_id==goal.current_plan_id).order_by(AgentPlanStep.step_order)))
    traces=list(session.scalars(select(AgentRunTrace).where(AgentRunTrace.goal_id==goal.id)))
    return project(goal,steps,traces,now=now)


def batch(files):
    if not files:return None
    projections=[f['progress'] for f in files]
    done=tuple(all(p.done[i] for p in projections) for i in range(7))
    # An active file is the current action; overall completion remains the
    # intersection of completed steps, including failed/paused files.
    selected=next((f for f in files if f['progress'].ai_running),None) or next((f for f in files if f['progress'].running),None)
    selected=selected or next((f for f in files if f['progress'].status in FAILED),None) or min(files,key=lambda f:f['progress'].completed_steps)
    p=selected['progress'];count=sum(done)
    return replace(p,done=done,current_step=next((i+1 for i,d in enumerate(done) if not d),7),completed_steps=count,
        progress_percent=round(count/7*100),started_at=min(p.started_at for p in projections),
        elapsed_seconds=max(p.elapsed_seconds for p in projections),file_total=len(files),
        file_completed=sum(f['progress'].done[2] for f in files),current_file=selected['document'].title)
