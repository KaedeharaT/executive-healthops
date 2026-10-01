"""Versioned goal requirements over the existing canonical registry; no LLM rules."""
from dataclasses import dataclass, asdict
from datetime import timedelta
from decimal import Decimal
from sqlalchemy import select
from executive_health_ai.integrations.codes import REGISTRY
from executive_health_ai.models import Observation
from executive_health_ai.models.base import utc_now

VERSION = 'goal-metrics-1'
GOAL_LABELS = {
    'WEIGHT_MANAGEMENT': '体重管理', 'BLOOD_PRESSURE_MANAGEMENT': '血压管理',
    'GLUCOSE_MANAGEMENT': '血糖管理', 'LIPID_MANAGEMENT': '血脂管理',
    'SLEEP_MANAGEMENT': '睡眠管理', 'ACTIVITY_MANAGEMENT': '活动管理',
    'LIFESTYLE_MANAGEMENT': '生活方式管理', 'FOLLOWUP_MANAGEMENT': '随访管理', 'CUSTOM': '自定义',
}
METRIC_LABELS = {'weight':'体重','bmi':'BMI','waist_circumference':'腰围','steps':'步数',
    'exercise_minutes':'运动时长','sleep_duration':'睡眠时长','systolic_bp':'收缩压',
    'diastolic_bp':'舒张压','heart_rate':'心率','resting_heart_rate':'静息心率',
    'glucose':'血糖','fasting_glucose':'空腹血糖','hba1c':'糖化血红蛋白',
    'ldl_c':'低密度脂蛋白胆固醇','hdl_c':'高密度脂蛋白胆固醇',
    'triglycerides':'甘油三酯','total_cholesterol':'总胆固醇'}


@dataclass(frozen=True)
class MetricRequirement:
    metric_code: str
    importance: str
    source_capability: tuple[str, ...]
    max_age_days: int = 90


MAPPINGS = {
    'WEIGHT_MANAGEMENT': (('weight','bmi'), ('waist_circumference','steps','exercise_minutes','sleep_duration'), ()),
    'BLOOD_PRESSURE_MANAGEMENT': (('systolic_bp','diastolic_bp'), ('heart_rate','weight'), ('steps','sleep_duration')),
    'GLUCOSE_MANAGEMENT': (('glucose',), ('hba1c','fasting_glucose','weight'), ('steps','exercise_minutes')),
    'LIPID_MANAGEMENT': (('ldl_c',), ('hdl_c','triglycerides','total_cholesterol'), ('weight','steps')),
    'SLEEP_MANAGEMENT': (('sleep_duration',), ('steps','resting_heart_rate'), ('exercise_minutes',)),
    'ACTIVITY_MANAGEMENT': (('steps',), ('exercise_minutes',), ('resting_heart_rate','sleep_duration')),
    'LIFESTYLE_MANAGEMENT': (('steps','sleep_duration'), ('exercise_minutes','weight'), ('resting_heart_rate',)),
    'FOLLOWUP_MANAGEMENT': ((), (), ()), 'CUSTOM': ((), (), ()),
}
CONTINUOUS = {'steps','exercise_minutes','sleep_duration','resting_heart_rate','heart_rate'}


def requirements(goal_type):
    if goal_type not in MAPPINGS:
        raise ValueError('不支持此健康管理目标类型。')
    result = []
    for level, codes in zip(('CORE','SUPPORTING','OPTIONAL'), MAPPINGS[goal_type]):
        for code in codes:
            if code not in REGISTRY:
                raise ValueError('目标引用未注册指标：' + code)
            sources = ('MANUAL','MOBILE','DEVICE') if code in CONTINUOUS else ('REPORT','MANUAL','MOBILE','DEVICE')
            result.append(MetricRequirement(code, level, sources, 14 if code in CONTINUOUS else 90))
    return tuple(result)


def snapshot(goal_type):
    return [asdict(item) for item in requirements(goal_type)]


def usable(statement):
    return statement.where(Observation.quality_flag.in_(('valid','manually_corrected')),
        Observation.source_deleted.is_(False), Observation.excluded_from_analysis.is_(False),
        Observation.confirmation_status.in_(('GOVERNED','CONFIRMED')))


def completeness(session, member_id, goal_type, *, now=None, configured=None):
    now = now or utc_now()
    rules = [MetricRequirement(**r) for r in configured] if configured else requirements(goal_type)
    result = {level: {'available':0,'total':0,'missing':[]} for level in ('CORE','SUPPORTING','OPTIONAL')}
    latest = {}
    # Each metric gets its own indexed latest lookup; a high-volume metric must
    # not crowd every other metric out of a global LIMIT.
    for rule in rules:
        row = session.scalar(usable(select(Observation).where(Observation.patient_id==member_id,
            Observation.metric_code==rule.metric_code, Observation.observed_at<=now,
            Observation.observed_at>=now-timedelta(days=rule.max_age_days)))
            .order_by(Observation.observed_at.desc(), Observation.id).limit(1))
        group = result[rule.importance]
        group['total'] += 1
        if row:
            group['available'] += 1
            latest[rule.metric_code] = {'value':str(row.value_numeric),'unit':row.unit,'observation_id':str(row.id)}
        else:
            group['missing'].append(rule.metric_code)
    return {**result, 'latest':latest,
        'suggestions':[{'metric':code,'text':'建议下次随访时补充'+METRIC_LABELS.get(code,code)+'记录',
                        'blocking':False} for level in ('CORE','SUPPORTING') for code in result[level]['missing']]}


def progress(goal, current):
    if goal.target_value is None or goal.baseline_value is None or current is None:
        return {'percent':None,'current':str(current) if current is not None else None,'status':'按阶段和任务记录进展'}
    baseline, target, current = map(Decimal, (str(goal.baseline_value),str(goal.target_value),str(current)))
    if not all(x.is_finite() for x in (baseline,target,current)) or baseline==target:
        return {'percent':None,'current':str(current),'status':'目标无需数值进度计算'}
    percent = max(Decimal(0), min(Decimal(100), (current-baseline)/(target-baseline)*100))
    return {'percent':float(percent.quantize(Decimal('.1'))),'current':str(current),
            'remaining':str(max(Decimal(0), (current-target) if baseline>target else (target-current))),
            'status':'已达到目标值' if percent>=100 else '执行中'}
