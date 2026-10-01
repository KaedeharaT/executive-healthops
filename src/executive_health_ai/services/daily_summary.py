"""Deterministic daily Observation aggregates and governed change detection.

No raw payload reads, network calls or LLM calls. A queue entry coalesces a
member's measurements for one local day. Historical revisions stay immutable.
"""
import hashlib
import json
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from sqlalchemy import select
from executive_health_ai.models import Observation, HealthAssessment, ManagementRule, Patient
from executive_health_ai.models.goal_data import DailyHealthSummary, DailySummaryRevision, SummaryWorkItem, ManagementGoal, CommunicationRecord
from executive_health_ai.models.goal_data_hooks import SUMMARY_TIMEZONE
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.goal_metrics import usable, requirements, progress

CUMULATIVE={'steps','exercise_minutes','sleep_duration','deep_sleep_duration','light_sleep_duration',
    'rem_sleep_duration','awake_duration','active_calories'}
LATEST={'weight','bmi','waist_circumference'}


def current_goal(session,member_id):
    return session.scalar(select(ManagementGoal).where(ManagementGoal.patient_id==member_id,
        ManagementGoal.status.in_(('CONFIRMED','ACTIVE'))).order_by(ManagementGoal.start_date.desc()).limit(1))


def calculate(session,member_id,day,*,emit=True):
    from executive_health_ai.models.archive_guard import locked_members
    locked_members(session.connection(),{member_id})
    member=session.get(Patient,member_id)
    zone=member.timezone if member else SUMMARY_TIMEZONE
    start=datetime.combine(day,time.min,tzinfo=ZoneInfo(zone)).astimezone(timezone.utc)
    end=datetime.combine(day+timedelta(days=1),time.min,tzinfo=ZoneInfo(zone)).astimezone(timezone.utc)
    rows=session.scalars(usable(select(Observation).where(Observation.patient_id==member_id,
        Observation.observed_at>=start,Observation.observed_at<end)).order_by(Observation.metric_code,
        Observation.observed_at,Observation.id)).yield_per(1000)
    aggregates={}; digest=hashlib.sha256()
    for row in rows:
        digest.update(f'{row.id}:{row.version}:{row.value_numeric}:{row.unit};'.encode())
        item=aggregates.setdefault(row.metric_code,{'sum':Decimal(0),'count':0,'max':row.value_numeric})
        item['sum']+=row.value_numeric;item['count']+=1;item['max']=max(item['max'],row.value_numeric)
        item['latest']=row.value_numeric;item['unit']=row.unit;item['observation_id']=str(row.id)
    if not aggregates:
        prior=session.scalar(select(DailyHealthSummary).where(DailyHealthSummary.patient_id==member_id,DailyHealthSummary.summary_date==day))
        if prior and prior.metrics:
            prior.version+=1;prior.metrics={};prior.changes=[];prior.change_status='INSUFFICIENT_DATA'
            prior.input_hash=hashlib.sha256(b'no-usable-data').hexdigest()
            prior.completeness={'available':0,'expected':prior.completeness.get('expected',0),'percent':None}
            session.add(DailySummaryRevision(summary_id=prior.id,version=prior.version,
                snapshot={'metrics':{},'reason':'来源删除或质量修正后无可用数据'}))
            session.flush()
        return None
    metrics={}
    for code,item in aggregates.items():
        mode='maximum' if code in CUMULATIVE else 'latest' if code in LATEST else 'mean'
        value=item['max'] if mode=='maximum' else item['latest'] if mode=='latest' else item['sum']/item['count']
        metrics[code]={'value':str(value.quantize(Decimal('.001'))),'unit':item['unit'],'count':item['count'],
            'aggregation':mode,'observation_id':item['observation_id']}
    goal=current_goal(session,member_id)
    expected=[r.metric_code for r in requirements(goal.goal_type) if r.importance=='CORE'] if goal else []
    completeness={'available':sum(code in metrics for code in expected),'expected':len(expected),
        'percent':round(100*sum(code in metrics for code in expected)/len(expected)) if expected else None,
        'basis':'当日目标核心指标；无目标时不伪造完整度'}
    digest.update(json.dumps(completeness,sort_keys=True).encode())
    digest.update(str(goal.id if goal else '').encode())
    input_hash=digest.hexdigest()
    summary=session.scalar(select(DailyHealthSummary).where(DailyHealthSummary.patient_id==member_id,
        DailyHealthSummary.summary_date==day))
    if summary and summary.input_hash==input_hash:return summary
    if summary:summary.version+=1
    else:
        summary=DailyHealthSummary(patient_id=member_id,summary_date=day,timezone=zone,version=1)
        session.add(summary)
    summary.input_hash=input_hash;summary.metrics=metrics;summary.completeness=completeness;summary.calculated_at=utc_now()
    session.flush()
    summary.changes=HealthSummaryChangeDetector().detect(session,summary)
    summary.change_status='MEANINGFUL_CHANGE' if summary.changes else 'NO_MEANINGFUL_CHANGE'
    session.add(DailySummaryRevision(summary_id=summary.id,version=summary.version,snapshot={
        'metrics':metrics,'completeness':completeness,'changes':summary.changes,'input_hash':input_hash}))
    session.flush()
    if emit:
        from executive_health_ai.services.health_events import ingest_health_event
        for change in summary.changes:
            context=lookback(session,member_id,change['metric'],day)
            payload={'summary_id':str(summary.id),'summary_version':summary.version,'change':change,
                'goal_id':str(goal.id) if goal else None,'lookback':context,
                'observation_ids':[metrics[change['metric']]['observation_id']]}
            ingest_health_event(session,member_id=member_id,event_type='MEANINGFUL_CHANGE',
                event_category='MEANINGFUL_CHANGE',source_type='SYSTEM',
                source_id=f"summary:{summary.id}:{change['rule_id']}:{day}",payload_ref=payload,dispatch=False)
    return summary


class HealthSummaryChangeDetector:
    def detect(self,session,summary):
        history=list(session.scalars(select(DailyHealthSummary).where(DailyHealthSummary.patient_id==summary.patient_id,
            DailyHealthSummary.summary_date<summary.summary_date,
            DailyHealthSummary.summary_date>=summary.summary_date-timedelta(days=30)).order_by(DailyHealthSummary.summary_date)))
        changes=[]
        from executive_health_ai.services.longitudinal import ManagementRoutingService
        compare=ManagementRoutingService._compare
        for rule in session.scalars(select(ManagementRule).where(ManagementRule.is_active.is_(True),
                ManagementRule.review_status=='APPROVED')):
            code=rule.canonical_code;config=rule.threshold_config or {};window=rule.window_config or {}
            if code not in summary.metrics:continue
            today=summary.metrics[code]
            if config.get('unit') and config['unit'].lower()!=today['unit'].lower():continue
            prior=[r for r in history if code in r.metrics]
            recent=[r for r in prior if r.summary_date>=summary.summary_date-timedelta(days=7)]
            minimum=max(2,int(window.get('summary_minimum_days',3)))
            if len(recent)<minimum:continue
            value=Decimal(today['value']);values=[Decimal(r.metrics[code]['value']) for r in recent]
            mean=sum(values)/len(values);mean30=sum(Decimal(r.metrics[code]['value']) for r in prior)/len(prior)
            try:threshold=Decimal(str(config['value']))
            except (KeyError,ValueError,ArithmeticError):continue
            kind=rule.condition_type.upper();operator=config.get('operator','')
            if kind in {'PERCENTAGE_CHANGE','PERCENTAGE_DECLINE','TREND'}:
                if mean==0:continue
                measured=(value-mean)/mean*100
                # An approved percentage threshold defines significance; equality/noise cannot trigger.
                matched=value!=mean and compare(measured,operator,threshold)
                previous=(values[-1]-mean)/mean*100
                matched=matched and not compare(previous,operator,threshold)
            elif kind in {'THRESHOLD','SINGLE_THRESHOLD','AVERAGE_THRESHOLD','AVERAGE','CONSECUTIVE_DAYS','REPEATED_DAYS'}:
                measured=value
                matched=compare(value,operator,threshold) and not compare(values[-1],operator,threshold)
                if kind in {'CONSECUTIVE_DAYS','REPEATED_DAYS'}:
                    count=max(2,int(window.get('required_matches',2)))
                    sequence=values[-(count-1):]+[value]
                    matched=len(sequence)==count and all(compare(v,operator,threshold) for v in sequence)
                    matched=matched and not all(compare(v,operator,threshold) for v in values[-count:])
            else:continue
            if matched:
                changes.append({'metric':code,'rule_id':str(rule.id),'rule_version':rule.version,
                    'kind':'HEALTH_STATE_CHANGE','today':str(value),'mean_7d':str(mean),
                    'mean_30d':str(mean30),'evaluated_value':str(measured),'window_days':7,
                    'reason':rule.name,'recommended_route':rule.recommended_route})
        # Formal abnormality rules must not depend on a separately configured
        # lifestyle rule. Reuse the engine's actual matcher and scope policy;
        # only a newly matched state becomes a summary change.
        from executive_health_ai.models import RiskRule
        from executive_health_ai.services.risk_triage import RiskEvaluationService, WELLNESS_MANAGEMENT_METRICS
        engine=RiskEvaluationService();member=session.get(Patient,summary.patient_id)
        formal={}
        for rule in session.scalars(select(RiskRule).where(RiskRule.is_active.is_(True),RiskRule.review_status=='APPROVED',
                RiskRule.canonical_code.in_(list(summary.metrics)))):
            if rule.condition_type not in {'THRESHOLD','SYNTHETIC_TEST_THRESHOLD'} or not engine._scope_allows_member(rule,member):continue
            code=rule.canonical_code
            if code in WELLNESS_MANAGEMENT_METRICS and not engine._is_explicit_synthetic_test_rule(rule):continue
            from uuid import UUID
            observation=session.get(Observation,UUID(summary.metrics[code]['observation_id']))
            device_class=engine.classify_provider(observation.source)
            if rule.applicable_device_class not in {'ANY',device_class}:continue
            matched=engine._evaluate_rule(session,observation,rule,device_class)
            if not matched:continue
            previous=next((r.metrics[code] for r in reversed(history) if code in r.metrics),None)
            if previous:
                old=session.get(Observation,UUID(previous['observation_id']))
                if old and engine._evaluate_rule(session,old,rule,engine.classify_provider(old.source)):continue
            elif rule.risk_level=='GREEN':continue
            change={'metric':code,'rule_id':str(rule.id),'rule_version':rule.version,'kind':'HEALTH_STATE_CHANGE',
                'today':summary.metrics[code]['value'],'reason':rule.name,'window_days':1,'risk_rule':True}
            rank={'GREEN':1,'YELLOW':2,'RED':3}.get(rule.risk_level,0)
            if code not in formal or rank>formal[code][0]:formal[code]=(rank,change)
        changed={item['metric'] for item in changes}
        changes.extend(change for code,(_,change) in formal.items() if code not in changed)
        goal=current_goal(session,summary.patient_id)
        if goal and goal.start_date<=summary.summary_date<=goal.target_date and goal.metric_code in summary.metrics and history:
            before=next((r.metrics[goal.metric_code]['value'] for r in reversed(history) if goal.metric_code in r.metrics),None)
            now=progress(goal,summary.metrics[goal.metric_code]['value'])['percent']
            old=progress(goal,before)['percent']
            # Only crossing the explicitly confirmed target; not every 0.1kg movement.
            if now is not None and old is not None and old<100<=now:
                changes.append({'metric':goal.metric_code,'rule_id':'goal-target-'+str(goal.id),
                    'kind':'GOAL_PROGRESS_CHANGE','reason':'已达到已确认目标值','window_days':1})
        return changes


def lookback(session,member_id,metric,day):
    related={'sleep_duration':{'sleep_duration','steps','exercise_minutes','resting_heart_rate'},
        'weight':{'weight','bmi','waist_circumference','steps','exercise_minutes'},
        'systolic_bp':{'systolic_bp','diastolic_bp','heart_rate','weight'},
        'diastolic_bp':{'systolic_bp','diastolic_bp','heart_rate','weight'}}.get(metric,{metric})
    rows=list(session.scalars(select(DailyHealthSummary).where(DailyHealthSummary.patient_id==member_id,
        DailyHealthSummary.summary_date<=day,DailyHealthSummary.summary_date>=day-timedelta(days=30))
        .order_by(DailyHealthSummary.summary_date.desc()).limit(31)))
    history=[{'date':str(r.summary_date),'metrics':{k:v for k,v in r.metrics.items() if k in related}} for r in rows]
    goal=current_goal(session,member_id)
    baseline=session.scalar(select(HealthAssessment).where(HealthAssessment.patient_id==member_id,
        HealthAssessment.cycle_year==day.year,HealthAssessment.status.in_(('CONFIRMED','AMENDED')),
        HealthAssessment.superseded_by_id.is_(None)).order_by(HealthAssessment.version.desc()).limit(1))
    baseline_data=baseline.baseline_json if baseline else {}
    baseline_scope={k:v for k,v in baseline_data.items() if k in related}
    # Annual report baselines use key_metrics, while older manual baselines
    # used direct metric keys. Preserve evidence for both existing contracts.
    baseline_scope.update({row['metric']:row for row in baseline_data.get('key_metrics',[])
        if isinstance(row,dict) and row.get('metric') in related})
    records=list(session.scalars(select(CommunicationRecord).where(CommunicationRecord.patient_id==member_id,
        CommunicationRecord.occurred_at>=datetime.combine(day-timedelta(days=30),time.min,tzinfo=timezone.utc),
        CommunicationRecord.occurred_at<datetime.combine(day+timedelta(days=1),time.min,tzinfo=timezone.utc),
        CommunicationRecord.confirmed_status=='CONFIRMED')
        .order_by(CommunicationRecord.occurred_at.desc()).limit(30)))
    notes=[{'id':str(r.id),'summary':r.structured_summary,'source':r.source} for r in records if related.intersection(r.related_metrics)][:5]
    from sqlalchemy import or_
    from executive_health_ai.models.management_workflow import ManagementLog
    from executive_health_ai.models import DoctorReview
    from executive_health_ai.services.goal_metrics import METRIC_LABELS
    words=[METRIC_LABELS.get(code,code) for code in related]
    since=datetime.combine(day-timedelta(days=30),time.min,tzinfo=timezone.utc)
    until=datetime.combine(day+timedelta(days=1),time.min,tzinfo=timezone.utc)
    logs=list(session.scalars(select(ManagementLog).where(ManagementLog.patient_id==member_id,
        ManagementLog.occurred_at>=since,ManagementLog.occurred_at<until,
        or_(*(ManagementLog.member_issue.contains(word) for word in words)))
        .order_by(ManagementLog.occurred_at.desc()).limit(5)))
    doctors=list(session.scalars(select(DoctorReview).where(DoctorReview.patient_id==member_id,
        DoctorReview.status=='CONFIRMED',DoctorReview.created_at<until,
        or_(*(DoctorReview.question_for_doctor.contains(word) for word in words),
            *(DoctorReview.opinion.contains(word) for word in words)))
        .order_by(DoctorReview.created_at.desc()).limit(3)))
    # Relevance comes from explicit mention in selected evidence, never from
    # an inferred drug indication or a model's guess about pharmacology.
    from executive_health_ai.models import MedicationPlan
    from sqlalchemy import literal
    relevant_text='\n'.join([r.opinion for r in doctors]+[r.raw_note for r in records if related.intersection(r.related_metrics)])
    medications=list(session.scalars(select(MedicationPlan).where(MedicationPlan.patient_id==member_id,
        MedicationPlan.status.in_(('active','ACTIVE')),MedicationPlan.start_date<=day,
        or_(MedicationPlan.end_date.is_(None),MedicationPlan.end_date>=day),MedicationPlan.drug_name!='',
        literal(relevant_text).contains(MedicationPlan.drug_name)).order_by(MedicationPlan.created_at.desc()).limit(10))) if relevant_text else []
    from executive_health_ai.models import ProgramPhase
    phase=session.scalar(select(ProgramPhase).where(ProgramPhase.program_id==goal.program_id,
        ProgramPhase.status=='ACTIVE')) if goal else None
    return {'metric_scope':sorted(related),'history_30d':history,
        'history_7d':[h for h in history if h['date']>=str(day-timedelta(days=7))],
        'annual_baseline':baseline_scope,
        'goal':{'id':str(goal.id),'title':goal.title} if goal and any(r.metric_code==metric for r in requirements(goal.goal_type)) else None,
        'phase':phase.title if phase else None,'relevant_notes':notes,
        'management_logs':[{'id':str(r.id),'result':r.result,'next_action':r.next_action} for r in logs],
        'doctor_opinions':[{'id':str(r.id),'doctor':r.doctor_name,'opinion':r.opinion} for r in doctors],
        'confirmed_medication_plans':[{'id':str(r.id),'drug':r.drug_name,'dose':r.dose,'unit':r.dose_unit,
            'frequency':r.frequency,'prescriber':r.prescriber_name} for r in medications],
        'medication_lifestyle_facts':[r.structured_summary for r in records if related.intersection(r.related_metrics)
            and ('用药' in r.raw_note or '生活方式' in r.raw_note)][:5], 'bounded':True}


def run_daily_batch(session,*,now=None,limit=100):
    now=now or utc_now();today=now.astimezone(ZoneInfo(SUMMARY_TIMEZONE)).date()
    jobs=list(session.scalars(select(SummaryWorkItem).join(Patient,Patient.id==SummaryWorkItem.patient_id)
        .where(SummaryWorkItem.dirty.is_(True),SummaryWorkItem.summary_date<=today,Patient.archived_at.is_(None))
        .order_by(SummaryWorkItem.summary_date,SummaryWorkItem.patient_id).limit(limit)))
    processed=0
    for job in jobs:
        member=session.get(Patient,job.patient_id)
        if job.summary_date>=now.astimezone(ZoneInfo(member.timezone)).date():continue
        calculate(session,job.patient_id,job.summary_date)
        job.dirty=False
        processed+=1
    session.flush()
    return processed
