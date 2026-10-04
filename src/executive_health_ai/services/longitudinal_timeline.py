"""Read-only, bounded health-state / care-action projection. No LLM or raw scans."""
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID
from sqlalchemy import select
from executive_health_ai.models import (Patient, Observation, HealthAssessment, HealthEvent,
    HealthProgram, ProgramPhase, RiskEvent, DoctorReview, Task, OutcomeEvaluation,
    MedicationPlan, ManagementPlan, ServiceRequest, AgentGoal, AgentRunTrace, RawData, FollowUp,
    ClinicalRecommendation, Encounter)
from executive_health_ai.models.goal_data import ManagementGoal, DailyHealthSummary, DailySummaryRevision, CommunicationRecord
from executive_health_ai.models.management_workflow import ManagementLog, RecheckPlan, StageReview
from executive_health_ai.services.goal_metrics import usable, METRIC_LABELS, REGISTRY, progress
from executive_health_ai.models.base import utc_now

RISK_LABELS = {'GREEN':'正常', 'YELLOW':'需关注', 'RED':'优先处理'}
OUTCOMES = {'IMPROVED':'改善', 'STABLE':'无明显变化', 'WORSENED':'恶化',
    'INSUFFICIENT_DATA':'数据不足', 'NEEDS_MEDICAL_REVIEW':'待医生判断',
    'NOT_EXECUTED':'未执行', 'REFUSED':'会员拒绝', 'INTERRUPTED':'中断'}
FILTERS = ('全部', '健康变化', '管理行动', '医疗', '阶段')


def ref(row):
    return {'type':type(row).__name__, 'id':str(row.id)}


def identity(source):
    return source['type'] + ':' + source['id']


def source_references(sources):
    """Nullable legacy references are absent evidence, never fabricated links."""
    return [source for source in (sources or []) if isinstance(source,dict)
            and source.get('type') and source.get('id')]


def at_day(day):
    return datetime.combine(day, time(12), timezone.utc)


def number(value):
    try:
        return format(Decimal(str(value)).normalize(), 'f')
    except (InvalidOperation, ValueError):
        return str(value)


@dataclass(frozen=True)
class HealthStateSnapshot:
    member_id: UUID
    snapshot_at: datetime
    snapshot_type: str
    baseline_reference: dict | None = None
    goal_reference: dict | None = None
    metric_summary: dict = field(default_factory=dict)
    medication_summary: tuple = ()
    risk_summary: str = '未记录正式风险评估'
    phase_summary: str = '未记录阶段'
    data_completeness: dict = field(default_factory=dict)
    source_refs: tuple = ()
    version: int = 1


@dataclass
class TimelineEntry:
    entry_id: str
    member_id: UUID
    occurred_at: datetime
    entry_type: str
    track: str
    title: str
    summary: str
    status: str = ''
    risk_level: str | None = None
    goal_id: str | None = None
    phase_id: str | None = None
    care_episode_id: str | None = None
    source_refs: list = field(default_factory=list)
    detail_target: dict = field(default_factory=dict)
    snapshot: HealthStateSnapshot | None = None
    details: dict = field(default_factory=dict)
    metric: str | None = None


@dataclass(frozen=True)
class CareEpisode:
    episode_id: str
    trigger_id: str
    entry_ids: tuple
    outcome_ids: tuple
    outcome_status: str


@dataclass
class TimelineView:
    member_id: UUID
    entries: list
    episodes: dict
    start: datetime
    end: datetime
    story: str
    empty: bool
    has_earlier: bool
    truncated: bool = False
    _all_entries: list = field(default_factory=list, repr=False)


def baseline_metrics(row):
    data = row.baseline_json or {}
    result = {}
    for code, value in data.items():
        if code in REGISTRY and isinstance(value, (int, float, str)):
            try: result[code] = {'value':number(Decimal(str(value))), 'unit':REGISTRY[code].default_unit}
            except InvalidOperation: pass  # Never guess a unit from free text.
    for item in data.get('key_metrics') or []:
        code = item.get('metric') if isinstance(item, dict) else None
        if code in REGISTRY and item.get('value') is not None:
            result[code] = {'value':str(item['value']), 'unit':item.get('unit') or REGISTRY[code].default_unit}
    return result


class LongitudinalTimelineProjection:
    """All business reads live here. UI receives detached presentation objects."""
    def daily_snapshot(self, session, member_id, day):
        row = session.scalar(select(DailyHealthSummary).where(DailyHealthSummary.patient_id==member_id,
            DailyHealthSummary.summary_date==day))
        if not row: return None
        return HealthStateSnapshot(member_id, at_day(day), 'DAILY_SUMMARY', metric_summary=row.metrics,
            data_completeness=row.completeness, source_refs=(ref(row),), version=row.version)

    def build(self, session, member_id, time_range=None, filters='全部', *, now=None):
        member_id = UUID(str(member_id)); now = now or utc_now()
        if filters not in FILTERS: raise ValueError('不支持此历程筛选。')
        if not session.get(Patient, member_id): raise ValueError('会员不存在。')
        start, end = time_range or (now - timedelta(days=365), now)
        if start.tzinfo is None or end.tzinfo is None or start > end: raise ValueError('历程时间范围无效。')
        entries = []; truncated = False
        def rows(model, field_name='patient_id', *conditions):
            nonlocal truncated
            query = select(model).where(getattr(model, field_name) == member_id, *conditions)
            time_field = next((getattr(model, c) for c in ('occurred_at','observed_at','assessed_at','reviewed_at','created_at') if hasattr(model,c)), model.id)
            result = list(session.scalars(query.order_by(time_field.desc(), model.id).limit(501)))
            truncated = truncated or len(result)>500
            return result[:500]
        baselines = rows(HealthAssessment, 'patient_id', HealthAssessment.status.in_(('CONFIRMED','AMENDED')),
            HealthAssessment.assessed_at <= end)
        goals = rows(ManagementGoal, 'patient_id', ManagementGoal.confirmed_at.is_not(None), ManagementGoal.confirmed_at <= end)
        programs = rows(HealthProgram)
        program_ids = [p.id for p in programs]
        phases = list(session.scalars(select(ProgramPhase).where(ProgramPhase.program_id.in_(program_ids))
            .order_by(ProgramPhase.start_date.desc()).limit(500))) if program_ids else []
        medications = rows(MedicationPlan)
        risks = rows(RiskEvent, 'patient_id', RiskEvent.created_at <= end)
        events = rows(HealthEvent, 'patient_id', HealthEvent.event_type.in_(('MEANINGFUL_CHANGE','CARE_EPISODE_LINK')),
            HealthEvent.occurred_at <= end)
        goal_map = {str(g.id):g for g in goals}
        def context(at):
            b = next((r for r in sorted(baselines,key=lambda b:(b.assessed_at,b.version),reverse=True)
                if r.assessed_at <= at and (not r.confirmed_at or r.confirmed_at<=at)), None)
            g = next((r for r in goals if r.confirmed_at <= at and r.start_date <= at.date() <= r.target_date), None)
            p = next((r for r in phases if r.start_date<=at.date()<=r.end_date and (not g or r.program_id==g.program_id)), None)
            return b,g,p
        def snapshot(at, kind, metrics=None, refs=(), version=1, completeness=None, risk=None):
            b,g,p = context(at)
            # Historical mutable medication/risk/phase state is not reconstructed as fact.
            meds = tuple(f'{m.drug_name} {m.dose} {m.dose_unit} · {m.frequency}' for m in medications
                if kind=='CURRENT_STATE' and m.start_date<=at.date() and (not m.end_date or m.end_date>=at.date())
                and m.status.upper()=='ACTIVE')
            return HealthStateSnapshot(member_id, at, kind, ref(b) if b else None, ref(g) if g else None,
                metrics or {}, meds, RISK_LABELS.get(risk,'未记录正式风险评估'), p.title if p else '未记录阶段',
                completeness or {}, tuple(refs), version)
        def add(row, at, kind, track, title, summary, *, risk=None, status='', goal=None, phase=None, metric=None, details=None, snap=None, episode=None, refs=None):
            source = ref(row)
            e = TimelineEntry(identity(source)+':'+kind, member_id, at, kind, track, title, summary,
                status, risk, str(goal) if goal else None, str(phase) if phase else None, episode,
                refs or [source], {'type':source['type'],'id':source['id']}, snap, details or {}, metric)
            entries.append(e); return e
        for b in baselines:
            metrics=baseline_metrics(b)
            annual=b.assessment_type in {'BASELINE','ANNUAL'}
            add(b,b.confirmed_at or b.assessed_at,'ANNUAL_BASELINE' if annual else 'HEALTH_ASSESSMENT','HEALTH_STATE','年度健康基线' if annual else '已确认健康评估',b.summary,
                snap=snapshot(b.assessed_at,'ANNUAL_BASELINE',metrics,[ref(b)],b.version),
                details={'state':b.summary,'sources':b.source_references_json})
        episode_refs = {}
        for event in sorted(events,key=lambda e:e.received_at):
            data=event.payload_ref or {}
            if event.event_type=='CARE_EPISODE_LINK':
                if data.get('trigger_id'):
                    for source in source_references(data.get('links')):episode_refs[identity(source)]='change:'+data['trigger_id']
        risk_episodes = {}; agent_episodes = {}
        for event in events:
            if event.event_type!='MEANINGFUL_CHANGE':continue
            data=event.payload_ref or {}; change=data.get('change') or {}; look=data.get('lookback') or {}
            code=change.get('metric'); episode='change:'+str(event.id)
            risk_data=data.get('risk_evaluation') or {}
            risk_id=data.get('risk_event_id') or risk_data.get('risk_event_id')
            if not risk_id and event.goal_id:
                ag=session.get(AgentGoal,event.goal_id)
                if ag and ag.member_id==member_id:risk_id=(ag.context_json or {}).get('risk_event_id')
            risk=next((r for r in risks if str(r.id)==str(risk_id)),None)
            if risk:risk_episodes[str(risk.id)]=episode
            if event.goal_id:agent_episodes[str(event.goal_id)]=episode
            metrics={code:{'value':change.get('today'),'unit':REGISTRY[code].default_unit}} if code in REGISTRY and change.get('today') is not None else {}
            version=int(data.get('summary_version') or 1)
            if data.get('summary_id'):
                summary=session.get(DailyHealthSummary,UUID(data['summary_id']))
                if summary and summary.patient_id==member_id:
                    revision=session.scalar(select(DailySummaryRevision).where(DailySummaryRevision.summary_id==summary.id,DailySummaryRevision.version==version))
                    metrics=(revision.snapshot or {} if revision else {}).get('metrics') or metrics
                    metrics={k:v for k,v in metrics.items() if k==code}
            refs=[ref(event)]
            for oid in data.get('observation_ids') or []:
                if not oid:continue
                obs=session.get(Observation,UUID(str(oid)))
                if obs and obs.patient_id==member_id:refs.append(ref(obs))
            goal_id=data.get('goal_id')
            if goal_id not in goal_map:goal_id=None
            title=METRIC_LABELS.get(code,'健康状态')+'重要变化'
            e=add(event,event.occurred_at,'MEANINGFUL_CHANGE','HEALTH_STATE',title,change.get('reason') or event.description,
                risk=risk.risk_level if risk else None, goal=goal_id, metric=code, episode=episode,refs=refs,
                snap=snapshot(event.occurred_at,'MEANINGFUL_CHANGE',metrics,refs,version,risk=risk.risk_level if risk else None),
                details={'change':change,'lookback':look,'state':change.get('reason') or event.description})
            if risk:e.source_refs.append(ref(risk))
            baseline,_,_=context(event.occurred_at)
            if baseline:
                e.source_refs.append(ref(baseline))
                e.details['baseline_label']=f'{baseline.assessed_at:%Y-%m-%d} · {baseline.title}'
                if code in baseline_metrics(baseline):
                    previous=baseline_metrics(baseline)[code];e.details['baseline_metric']=previous
                    if code in metrics and metrics[code].get('unit')==previous['unit']:
                        metrics[code]={**metrics[code],'baseline':previous['value'],
                            'delta':number(Decimal(str(metrics[code]['value']))-Decimal(previous['value']))}
        for g in goals:
            add(g,g.confirmed_at,'GOAL_CONFIRMED','CARE_ACTION','确认健康目标',g.title,goal=g.id,
                details={'human':f'{g.confirmed_by}确认目标','state':g.description})
            if g.plan_confirmed_at:
                add(g,g.plan_confirmed_at,'PLAN_CONFIRMED','CARE_ACTION','确认管理计划',g.title,goal=g.id,
                    details={'human':f'{g.plan_confirmed_by}确认计划'})
        for p in phases:
            if p.status not in {'ACTIVE','COMPLETED'}:continue
            g=next((g for g in goals if g.program_id==p.program_id),None)
            add(p,at_day(p.start_date),'PHASE_STARTED','CARE_ACTION','进入管理阶段',p.title,
                goal=g.id if g else None,phase=p.id,details={'state':p.goal,'next':p.management_content or ''})
        for r in risks:
            episode=risk_episodes.get(str(r.id)) or 'risk:'+str(r.id)
            if str(r.id) not in risk_episodes:
                add(r,r.created_at,'RISK_CHANGE','HEALTH_STATE','健康风险变化',r.summary,risk=r.risk_level,
                    episode=episode,details={'state':r.summary})
            if r.resolved_at and r.resolved_at>=r.created_at and r.resolved_at<=end:
                add(r,r.resolved_at,'RISK_RESOLVED','HEALTH_STATE','风险事项已关闭','处理流程已关闭；不等同健康指标恢复',
                    episode=episode,details={'outcome':'风险处置已结束；健康结果仍以测量/医生记录为准'})
            risk_episodes[str(r.id)]=episode
        tasks=rows(Task)
        task_episodes={}
        for t in tasks:
            ep=episode_refs.get(identity(ref(t))) or risk_episodes.get(str(t.risk_event_id))
            if not ep and (t.source or '').startswith('agent_goal:'):
                ep=agent_episodes.get(t.source.split(':')[1])
            if ep:task_episodes[str(t.id)]=ep
        logs=rows(ManagementLog)
        for r in logs:
            episode=episode_refs.get(identity(ref(r))) or risk_episodes.get(str(r.related_risk_id)) or task_episodes.get(str(r.related_task_id))
            add(r,r.occurred_at,'CARE_CONTACT','CARE_ACTION',r.category if r.category not in {'电话','日常跟进'} else '健管随访',r.result or r.manager_action,
                episode=episode,details={'human':r.manager_action,'result':r.result,'reason':r.member_issue,'next':r.next_action})
        for t in tasks:
            if str(t.id) in task_episodes and not any(l.related_task_id==t.id for l in logs):
                add(t,t.created_at,'MANAGEMENT_ITEM','CARE_ACTION',t.title,t.instruction,
                    episode=task_episodes[str(t.id)],status=t.status,details={'next':t.instruction})
        doctors=rows(DoctorReview)
        doctor_episodes={}
        for d in doctors:
            if d.status!='CONFIRMED':continue
            episode=episode_refs.get(identity(ref(d))) or risk_episodes.get(str(d.risk_event_id))
            doctor_episodes[d.id]=episode
            risk=next((r for r in risks if r.id==d.risk_event_id),None)
            add(d,d.reviewed_at,'DOCTOR_DECISION','CARE_ACTION','医生判断',d.opinion,
                episode=episode,risk=risk.risk_level if risk else None,
                snap=snapshot(d.reviewed_at,'DOCTOR_DECISION',refs=[ref(d)],risk=risk.risk_level if risk else None),
                details={'reason':d.doctor_brief,'question':d.question_for_doctor,'human':d.doctor_name+'：'+d.opinion})
        for d in rows(ClinicalRecommendation):
            if d.status.lower()!='confirmed':continue
            encounter=session.get(Encounter,d.encounter_id)
            if not encounter or encounter.patient_id!=member_id:continue
            add(d,d.created_at,'DOCTOR_DECISION','CARE_ACTION','医生正式意见',d.content,
                episode=episode_refs.get(identity(ref(d))),snap=snapshot(d.created_at,'DOCTOR_DECISION',refs=[ref(d)]),
                details={'reason':encounter.reason,'human':d.clinician_name+'：'+d.content})
        for r in rows(FollowUp):
            if not r.completed_at or any(l.related_task_id and l.related_task_id==r.task_id for l in logs):continue
            add(r,r.completed_at,'FOLLOWUP','CARE_ACTION','健管随访',r.outcome or '已记录随访',
                episode=episode_refs.get(identity(ref(r))) or task_episodes.get(str(r.task_id)),
                details={'human':r.reviewed_by or '负责人','result':r.outcome or ''})
        rechecks=rows(RecheckPlan)
        for r in rechecks:
            episode=episode_refs.get(identity(ref(r)))
            if not episode and r.doctor_review_id:
                episode=doctor_episodes.get(r.doctor_review_id)
            add(r,r.created_at,'RECHECK','CARE_ACTION','安排复查',r.title,episode=episode,status=r.status,
                details={'reason':r.reason,'result':r.result,'next':f'{r.planned_at:%Y-%m-%d} · {r.owner}'})
        for r in rows(ManagementPlan):
            if r.adjusted_at and r.adjusted_by:
                add(r,r.adjusted_at,'PLAN_ADJUSTMENT','CARE_ACTION','调整管理计划',r.adjustment_reason or r.title,
                    episode=episode_refs.get(identity(ref(r))),details={'human':r.adjusted_by+'：'+r.content,'reason':r.adjustment_reason})
        for r in rows(ServiceRequest):
            if r.status!='COMPLETED' or not r.completed_at:continue
            add(r,r.completed_at,'SERVICE_RESULT','CARE_ACTION','服务完成',r.result_summary or r.reason,
                phase=r.phase_id,episode=episode_refs.get(identity(ref(r))),details={'result':r.result_summary,'next':r.next_action})
        for r in rows(StageReview):
            content=r.content or {}
            add(r,r.reviewed_at,'PHASE_REVIEW','CARE_ACTION','阶段复盘',str(content.get('实际完成') or content.get('summary') or '已记录阶段结果'),
                phase=r.phase_id,episode=episode_refs.get(identity(ref(r))),
                snap=snapshot(r.reviewed_at,'PHASE_REVIEW',refs=[ref(r)]),details={'phase':content,'human':r.owner})
        for r in rows(OutcomeEvaluation):
            label=OUTCOMES.get(r.result,'结果待观察')
            add(r,at_day(r.evaluation_date),'OUTCOME','HEALTH_STATE','观察结果 · '+label,
                f'{r.metric}：{r.baseline_value} → {r.current_value} {r.unit}',
                status=label,episode=episode_refs.get(identity(ref(r))),
                details={'outcome':label+' · '+(r.notes or r.evidence),'result':r.evidence,
                    'change':{'today':r.current_value,'baseline':r.baseline_value,'unit':r.unit}})
        for r in rows(CommunicationRecord):
            if r.confirmed_status!='CONFIRMED' or r.log_id:continue # log is the operational representation
            add(r,r.occurred_at,'COMMUNICATION','CARE_ACTION','健管沟通',r.raw_note,
                goal=r.related_goal_id,episode=episode_refs.get(identity(ref(r))),details={'human':r.raw_note})
        for m in medications:
            if not m.prescriber_name:continue # No inferred doctor attribution.
            add(m,at_day(m.start_date),'MEDICATION_CHANGE','CARE_ACTION','正式用药记录',f'{m.drug_name} {m.dose} {m.dose_unit} · {m.frequency}',
                details={'human':'处方记录医生：'+m.prescriber_name,'state':'记录开始用药日期；不推断未留存的历史剂量变更'})
            if m.end_date and m.end_date<=end.date():
                add(m,at_day(m.end_date),'MEDICATION_END','CARE_ACTION','用药记录结束',m.drug_name+' · 已记录结束日期',
                    details={'human':'正式用药记录，处方人：'+m.prescriber_name})
        # Current state: indexed latest lookups, never load raw measurement history.
        b,g,p=context(now)
        codes=list(dict.fromkeys(([g.metric_code] if g and g.metric_code else [])+list(baseline_metrics(b) if b else {})+['weight','sleep_duration','systolic_bp','diastolic_bp']))[:8]
        metrics={}; refs=[]
        for code in codes:
            obs=session.scalar(usable(select(Observation).where(Observation.patient_id==member_id,
                Observation.metric_code==code,Observation.observed_at<=now)).order_by(Observation.observed_at.desc(),Observation.id).limit(1))
            if obs:
                metrics[code]={'value':str(obs.value_numeric),'unit':obs.unit,'at':obs.observed_at.isoformat()}
                if b and code in baseline_metrics(b):
                    old=baseline_metrics(b)[code]
                    if old['unit']==obs.unit:
                        try:metrics[code]['baseline']=old['value'];metrics[code]['delta']=number(obs.value_numeric-Decimal(old['value']))
                        except InvalidOperation:pass
                refs.append(ref(obs))
        latest_summary=session.scalar(select(DailyHealthSummary).where(DailyHealthSummary.patient_id==member_id,
            DailyHealthSummary.summary_date<=now.date()).order_by(DailyHealthSummary.summary_date.desc()).limit(1))
        active_risk=max((r for r in risks if r.status not in {'CLOSED','DISMISSED_DATA_ISSUE'}),key=lambda r:{'RED':3,'YELLOW':2,'GREEN':1}.get(r.risk_level,0),default=None)
        if latest_summary:refs.append(ref(latest_summary))
        if b:refs.append(ref(b))
        real_records=bool(entries or metrics or latest_summary)
        if real_records:
            current=TimelineEntry('current:'+str(member_id),member_id,now,'CURRENT_STATE','HEALTH_STATE','当前状态',
                (g.title if g else '尚未确认管理目标'),risk_level=active_risk.risk_level if active_risk else None,
                goal_id=str(g.id) if g else None,phase_id=str(p.id) if p else None,source_refs=refs,
                snapshot=snapshot(now,'CURRENT_STATE',metrics,refs,latest_summary.version if latest_summary else 1,
                    latest_summary.completeness if latest_summary else {},active_risk.risk_level if active_risk else None))
            future=sorted((t for t in tasks if t.status not in {'COMPLETED','CANCELLED'} and t.due_at),key=lambda t:t.due_at)
            current.details={'next':f'{future[0].due_at:%Y-%m-%d} · {future[0].title}' if future else '等待后续资料或负责人确认下一步',
                'open_items':sum(t.status not in {'COMPLETED','CANCELLED'} for t in tasks),
                'goal':g.title if g else '尚未确认管理目标',
                'progress':progress(g,metrics.get(g.metric_code,{}).get('value')) if g else {}}
            upcoming=sorted((r for r in rechecks if r.planned_at>=now and r.status not in {'COMPLETED','CANCELLED'}),key=lambda r:r.planned_at)
            if upcoming and (not future or upcoming[0].planned_at<future[0].due_at):
                current.details['next']=f'{upcoming[0].planned_at:%Y-%m-%d} · {upcoming[0].title}'
            week=list(session.scalars(select(DailyHealthSummary).where(DailyHealthSummary.patient_id==member_id,
                DailyHealthSummary.summary_date>=now.date()-timedelta(days=6),DailyHealthSummary.summary_date<=now.date())))
            sleep=[Decimal(s.metrics['sleep_duration']['value']) for s in week if s.metrics.get('sleep_duration',{}).get('unit') in {'min','minutes'}]
            if sleep:current.details['sleep_week']=f'{number((sum(sleep)/len(sleep)/60).quantize(Decimal(".1")))} 小时（有记录的 {len(sleep)} 天）'
            entries.append(current)
        entries=[e for e in entries if e.occurred_at<=end]
        episode_goals={episode:source.split(':',1)[1] for source,episode in episode_refs.items() if source.startswith('ManagementGoal:')}
        for e in entries:
            if e.care_episode_id is None and e.entry_type not in {'GOAL_CONFIRMED','PLAN_CONFIRMED'}:
                e.care_episode_id=episode_refs.get(identity(e.detail_target)) if e.detail_target else None
            if not e.goal_id:
                _,eg,ep=context(e.occurred_at)
                # Goal association requires an explicit episode or relevant metric, not just same member.
                if eg and e.metric==eg.metric_code:e.goal_id=str(eg.id)
                elif e.care_episode_id in episode_goals:e.goal_id=episode_goals[e.care_episode_id]
            if not e.phase_id:
                _,eg,ep=context(e.occurred_at)
                if ep and e.goal_id and eg and e.goal_id==str(eg.id):e.phase_id=str(ep.id)
            if e.goal_id in goal_map:
                eg=goal_map[e.goal_id]; e.details['goal']=eg.title
                if e.snapshot and eg.metric_code in e.snapshot.metric_summary:
                    e.details['progress']=progress(eg,e.snapshot.metric_summary[eg.metric_code].get('value'))
        episodes={}
        for key in {e.care_episode_id for e in entries if e.care_episode_id}:
            connected=sorted((e for e in entries if e.care_episode_id==key),key=lambda e:(e.occurred_at,e.entry_id))
            outcomes=tuple(e.entry_id for e in connected if e.entry_type=='OUTCOME')
            episodes[key]=CareEpisode(key,key.split(':',1)[1],tuple(e.entry_id for e in connected),outcomes,
                next((e.status for e in reversed(connected) if e.entry_type=='OUTCOME'),'结果待观察'))
        has_earlier=any(e.occurred_at<start and e.entry_type!='CURRENT_STATE' for e in entries)
        visible=[e for e in entries if start<=e.occurred_at<=end and
            (filters=='全部' or filters=='健康变化' and e.track=='HEALTH_STATE' or filters=='管理行动' and e.track=='CARE_ACTION'
            or filters=='医疗' and e.entry_type in {'DOCTOR_DECISION','MEDICATION_CHANGE','MEDICATION_END','RECHECK'}
            or filters=='阶段' and e.entry_type in {'PHASE_REVIEW','PHASE_STARTED','OUTCOME','PLAN_CONFIRMED'})]
        visible.sort(key=lambda e:(e.occurred_at,e.entry_id))
        changes=sum(e.entry_type=='MEANINGFUL_CHANGE' for e in visible)
        outcomes=[e for e in visible if e.entry_type=='OUTCOME']
        story=f'本时段记录了 {changes} 次重要健康变化，{sum(e.entry_type=="DOCTOR_DECISION" for e in visible)} 次医生判断。'
        if outcomes:story+='最近观察结果：'+outcomes[-1].summary+'；'+outcomes[-1].status+'。'
        if any(ep.outcome_status=='结果待观察' for ep in episodes.values()):story+='部分管理行动的结果仍待观察。'
        view=TimelineView(member_id,visible,episodes,start,end,story,not real_records,has_earlier,truncated)
        # Related records remain available for detail even when outside the selected display window.
        view._all_entries=entries
        return view

    def details(self, session, view, entry_id):
        e=next((e for e in view.entries if e.entry_id==entry_id),None)
        if e is None:raise ValueError('历程节点不在当前会员视图中。')
        linked=sorted((r for r in view._all_entries if e.care_episode_id and r.care_episode_id==e.care_episode_id),key=lambda r:r.occurred_at)
        sources=[]
        from executive_health_ai.services.care_episodes import MODELS
        models={**MODELS, 'HealthAssessment':HealthAssessment,'MedicationPlan':MedicationPlan,'DailyHealthSummary':DailyHealthSummary,'ProgramPhase':ProgramPhase}
        for source in source_references(e.source_refs):
            model=models.get(source['type'])
            row=session.get(model,UUID(source['id'])) if model else None
            if not row:continue
            if isinstance(row,ProgramPhase):
                program=session.get(HealthProgram,row.program_id)
                if not program or program.patient_id!=view.member_id:continue
            elif row.patient_id!=view.member_id:continue
            if isinstance(row,Observation):
                from executive_health_ai.services.data_provenance import detail
                provenance=detail(session,row)
                raw=session.get(RawData,row.raw_record_id) if row.raw_record_id else None
                payload=(raw.payload_json or {}) if raw and raw.patient_id==view.member_id else {}
                original=payload.get('original_text') or payload.get('original_value') or (payload.get('payload') or {}).get('original_text') or ''
                sources.append({'label':METRIC_LABELS.get(row.metric_code,row.metric_code),'text':f'{row.observed_at:%Y-%m-%d} · {row.evidence_ref or row.source_type or "测量记录"} · {number(row.value_numeric)} {row.unit}',
                    'original':str(original),'corrected':provenance['corrected']})
                for version in provenance['versions'][1:]:
                    sources.append({'label':'保留的修正前记录','text':f"{number(version['value'])} {version['unit']}",'original':'','corrected':True})
            else:
                label={'HealthEvent':'变化记录','HealthAssessment':'年度基线','RiskEvent':'正式风险依据','DoctorReview':'医生意见',
                    'ManagementLog':'管理原始记录','OutcomeEvaluation':'结果评价','DailyHealthSummary':'每日健康摘要'}.get(source['type'],'业务原始记录')
                text=next((getattr(row,k) for k in ('evidence','raw_note','opinion','content','summary','result','description','title') if getattr(row,k,None)),label)
                if isinstance(row,DoctorReview):text=f'{row.doctor_name} · {row.department} · {row.reviewed_at:%Y-%m-%d}：{row.opinion}'
                if isinstance(row,DailyHealthSummary):text=f'{row.summary_date:%Y-%m-%d} · 根据当天有效测量计算的健康摘要'
                if isinstance(text,dict):
                    text='；'.join(str(k)+'：'+str(v) for k,v in text.items() if isinstance(v,(str,int,float)))
                sources.append({'label':label,'text':str(text),'original':'','corrected':False})
        auto=[]
        for source in source_references(e.source_refs):
            if source['type']!='HealthEvent':continue
            event=session.get(HealthEvent,UUID(source['id']))
            if not event or event.member_id!=view.member_id or not event.goal_id:continue
            goal=session.get(AgentGoal,event.goal_id)
            if goal and goal.member_id==view.member_id:
                auto.append('已整理变化依据并进入原管理流程')
                if (event.payload_ref or {}).get('lookback'):auto.append('已回溯相关指标与既往记录')
                if session.scalar(select(AgentRunTrace.id).where(AgentRunTrace.goal_id==goal.id,AgentRunTrace.action=='tool_execution',AgentRunTrace.status=='COMPLETED').limit(1)):
                    auto.append('已执行获准的管理步骤，结果见关联事项')
        later_outcomes=[r for r in linked if r.entry_type=='OUTCOME' and r.occurred_at>=e.occurred_at]
        # A result observed BEFORE a doctor decision cannot be its subsequent outcome.
        outcome=(later_outcomes[-1].status if later_outcomes else '结果待观察') if e.track=='CARE_ACTION' else (
            view.episodes[e.care_episode_id].outcome_status if e.care_episode_id in view.episodes else e.details.get('outcome','结果待观察'))
        return {'entry':e,'related':linked,'sources':sources,'automatic':auto,'outcome':outcome,
            'outcomes':later_outcomes if e.track=='CARE_ACTION' else [r for r in linked if r.entry_type=='OUTCOME']}

    def groups(self, view):
        """Presentation groups over existing entries, never inferred clinical links.

        Episode membership is authoritative. Phase/goal grouping only organizes
        their own records; it does not claim that a phase caused an outcome.
        """
        buckets = {}
        key_types = {'ANNUAL_BASELINE','HEALTH_ASSESSMENT','MEANINGFUL_CHANGE','RISK_CHANGE',
            'DOCTOR_DECISION','PHASE_REVIEW','PHASE_STARTED','CURRENT_STATE','OUTCOME',
            'GOAL_CONFIRMED','PLAN_CONFIRMED','MEDICATION_CHANGE','MEDICATION_END'}
        for e in view.entries:
            if e.care_episode_id:
                key = e.care_episode_id
            elif e.entry_type in {'GOAL_CONFIRMED','PLAN_CONFIRMED'} and e.goal_id:
                key = 'goal:'+e.goal_id
            elif e.entry_type in {'PHASE_STARTED','PHASE_REVIEW'} and e.phase_id:
                key = 'phase:'+e.phase_id
            elif e.entry_type in key_types:
                key = e.entry_id
            else:
                continue  # Ordinary calls/logs remain in episode drill-down.
            buckets.setdefault(key, []).append(e)
        # A legacy member may have only narrative records. Keep them accessible
        # as one archive group rather than inventing a change or an episode.
        if all(e.entry_type=='CURRENT_STATE' for rows in buckets.values() for e in rows):
            legacy=[e for e in view.entries if e.entry_type in {'CARE_CONTACT','FOLLOWUP','COMMUNICATION'}]
            if legacy:buckets['legacy-care']=legacy
        groups = []
        for key, visible in buckets.items():
            members = sorted((e for e in view._all_entries if e.care_episode_id == key),
                key=lambda e:(e.occurred_at,e.entry_id)) if key in view.episodes else visible
            members = sorted(members,key=lambda e:(e.occurred_at,e.entry_id))
            trigger = next((e for e in members if e.entry_type in {'MEANINGFUL_CHANGE','RISK_CHANGE'}), members[0])
            if key.startswith('phase:'):
                trigger=next((e for e in reversed(members) if e.entry_type=='PHASE_REVIEW'),trigger)
            current = next((e for e in members if e.entry_type=='CURRENT_STATE'),None)
            if current:trigger=current
            doctor = any(e.entry_type=='DOCTOR_DECISION' for e in members)
            outcomes = [e for e in members if e.entry_type=='OUTCOME' and e.occurred_at>=trigger.occurred_at]
            title = trigger.title
            if key in view.episodes:
                title = ('睡眠管理事件' if trigger.metric=='sleep_duration' else
                    '复查与医生协同' if doctor else METRIC_LABELS.get(trigger.metric,'健康变化')+'管理事件')
            elif key.startswith('goal:'):title='确认目标与年度计划'
            elif key.startswith('phase:'):
                phase_title=next((e.summary for e in members if e.entry_type=='PHASE_STARTED'),'')
                title='阶段复盘 · '+phase_title if trigger.entry_type=='PHASE_REVIEW' else phase_title
            elif key=='legacy-care':title='历史管理记录'
            human = '需要医生' if doctor else '需要健管' if trigger.risk_level=='YELLOW' else (
                '优先人工处理' if trigger.risk_level=='RED' else '系统自动处理' if trigger.risk_level=='GREEN' else '已有管理记录')
            result = '后续观察到'+outcomes[-1].summary+'（'+outcomes[-1].status+'）' if outcomes else (
                trigger.details.get('next','继续当前管理') if current else '结果待观察')
            if not outcomes and not current:
                result={'ANNUAL_BASELINE':'已确认基线，作为后续比较依据',
                    'GOAL_CONFIRMED':'管理目标已人工确认',
                    'PHASE_REVIEW':'已记录阶段复盘，健康结果以测量和医生记录为准',
                    'PHASE_STARTED':'已进入该阶段，持续记录执行与结果'}.get(trigger.entry_type,result)
            groups.append({'key':key,'entry':trigger,'members':members,'title':title,'human':human,
                'outcome':result,'outcomes':outcomes,'current':bool(current),'doctor':doctor})
        return sorted(groups,key=lambda g:(g['current'],g['entry'].occurred_at,g['key']))

    def overview(self, view):
        """Deterministic counts and comparable, dated facts from this projection."""
        current=next((e for e in view.entries if e.entry_type=='CURRENT_STATE'),None)
        baselines=[e for e in view.entries if e.entry_type=='ANNUAL_BASELINE' and e.snapshot]
        state=[]
        if current and current.snapshot:
            weight=current.snapshot.metric_summary.get('weight')
            baseline=next((e.snapshot.metric_summary['weight'] for e in reversed(baselines)
                if 'weight' in e.snapshot.metric_summary and weight and e.snapshot.metric_summary['weight']['unit']==weight['unit']),None)
            if baseline:state.append('体重：'+number(baseline['value'])+' → '+number(weight['value'])+' '+weight['unit'])
        sleep=[g for g in self.groups(view) if g['entry'].metric=='sleep_duration']
        for g in sleep:
            state.append(f"{g['entry'].occurred_at:%m}月睡眠出现重要变化；"+g['outcome'])
        if not state:state.append(view.story)
        counts={label:sum(e.entry_type in kinds for e in view.entries) for label,kinds in {
            '健管随访':{'CARE_CONTACT','FOLLOWUP'},'医生协同':{'DOCTOR_DECISION'},
            '计划调整':{'PLAN_ADJUSTMENT'},'阶段复盘':{'PHASE_REVIEW'}}.items()}
        counts['健管随访']=sum(e.entry_type=='FOLLOWUP' or e.entry_type=='CARE_CONTACT' and e.title=='健管随访' for e in view.entries)
        # One risk per episode, not one count per risk/action/outcome node.
        attention=sum(g['entry'].risk_level in {'YELLOW','RED'} for g in self.groups(view)
            if g['entry'].entry_type in {'MEANINGFUL_CHANGE','RISK_CHANGE'})
        conclusion=[RISK_LABELS.get(current.risk_level,'尚无正式风险结论') if current else '尚无当前状态记录',
            current.details.get('goal','尚未确认管理目标') if current else '等待更多健康记录']
        return {'state':state,'actions':[f'{n} 次{label}' for label,n in counts.items()],
            'conclusion':conclusion,'attention':attention}

    def group_details(self, session, view, group):
        """Evidence-backed preparation, human responsibility and memory candidate.

        Candidate memory quotes explicitly linked management decisions and outcomes;
        it is neither a confirmed fact nor a persistent/LLM-generated memory.
        """
        from dataclasses import replace
        whole=replace(view,entries=view._all_entries)
        e=group['entry'];base=self.details(session,whole,e.entry_id)
        look=e.details.get('lookback') or {}
        automatic=list(base['automatic'])
        history=look.get('history_30d') or []
        if history:
            automatic.append(f"已回溯 {len(history)} 个有记录日期的相关指标（{history[-1]['date']} 至 {history[0]['date']}）")
        metrics={code for day in history for code in (day.get('metrics') or {})}
        if metrics.intersection({'steps','exercise_minutes'}):automatic.append('已整理同期活动数据，供对照变化')
        if look.get('annual_baseline'):automatic.append('已比较留存的个人年度基线')
        if look.get('goal'):automatic.append('已查看当时目标：'+look['goal']['title'])
        for field,label in [('management_logs','相关管理记录'),('doctor_opinions','相关医生意见')]:
            if field in look:automatic.append(f"已检查{label}：找到 {len(look[field] or [])} 条")
        care=[r for r in group['members'] if r.track=='CARE_ACTION']
        if group['doctor']:
            reason=next((r.details.get('question') for r in care if r.entry_type=='DOCTOR_DECISION' and r.details.get('question')), '医学判断需由医生负责。')
        elif e.risk_level in {'YELLOW','RED'}:
            reason=(e.details.get('change') or {}).get('reason') or e.summary
            reason+='；需要人工核实原因并决定后续安排。'
        elif group['human']=='系统自动处理':reason='已记录为正常管理范围，由系统按获准流程推进。'
        else:reason='此记录未留存单独的人工介入原因，不补推断。'
        sources=[];seen=set()
        for item in group['members']:
            for source in self.details(session,whole,item.entry_id)['sources']:
                key=(source['label'],source['text'],source['original'])
                if key not in seen:sources.append(source);seen.add(key)
        adjustments=[r for r in care if r.entry_type=='PLAN_ADJUSTMENT' and r.details.get('reason')]
        memory={'status':'尚未形成','text':'尚无可追溯的长期管理经验记录。','sources':[], 'time_range':None}
        if adjustments:
            decision=adjustments[-1]
            memory={'status':'候选，待后续验证',
                'text':'可沉淀经验：已记录的执行障碍 / 调整原因「'+decision.details['reason']+'」。'+
                    group['outcome']+'。这些记录尚不能证明干预因果，也不是已确认的长期经验。',
                'sources':decision.source_refs+[s for r in group['outcomes'] for s in r.source_refs],
                'time_range':(e.occurred_at.date().isoformat(),max(r.occurred_at for r in group['members']).date().isoformat())}
        return {**base,'automatic':list(dict.fromkeys(automatic)), 'human_reason':reason,'care':care,
            'memory':memory,'sources':sources,'history':history,'outcomes':group['outcomes']}
