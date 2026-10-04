"""Synthetic 12-month story. CLI only creates a NEW database under .runtime.

Never calls the formal demo builder or opens the configured application DB.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
import argparse
import hashlib
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from executive_health_ai.models import (Base, Patient, HealthJourney, HealthProgram, HealthAssessment,
    ProgramPhase, Observation, RawData, HealthEvent, HealthProblem, DoctorReview, RiskRule,
    RiskEvent, ManagementPlan, Task, AgentGoal)
from executive_health_ai.models.goal_data import ManagementGoal
from executive_health_ai.models.management_workflow import ManagementLog, RecheckPlan, StageReview, IntakeAssessment
from executive_health_ai.services.daily_summary import calculate
from executive_health_ai.services.care_episodes import link_care_episode
from executive_health_ai.services.chronic_care import record_outcome_evaluation
from executive_health_ai.services.goal_metrics import REGISTRY, snapshot


def seed_story(session, *, year=2026):
    def at(month,day=1,yr=None):return datetime(yr or year,month,day,4,tzinfo=timezone.utc)
    def save(row):session.add(row);session.flush();return row
    member=save(Patient(display_name='纵向历程验收会员',external_id='synthetic-timeline-'+str(uuid4()),timezone='Asia/Shanghai'))
    empty=save(Patient(display_name='历程空状态验收会员',external_id='synthetic-empty-'+str(uuid4()),timezone='Asia/Shanghai'))
    journey=save(HealthJourney(patient_id=member.id,assessment_summary='合成资料已核对',main_focus='体重与生活方式',owner='林健管',started_at=at(10,1,year-1)))
    program=save(HealthProgram(patient_id=member.id,journey_id=journey.id,program_type='ANNUAL',title='年度体重与生活方式管理',
        main_goal='逐步改善体重并跟踪睡眠',owner='林健管',cycle_year=year,status='ACTIVE',current_phase='EXECUTION',
        start_date=at(1).date(),end_date=at(12,31).date(),created_at=at(1)))
    prior=save(HealthAssessment(patient_id=member.id,cycle_year=year-1,assessment_type='ANNUAL',version=1,title='上一年度健康基线',summary='体重87kg；睡眠7小时。合成资料。',
        created_by='林健管',status='CONFIRMED',confirmed_at=at(10,1,year-1),assessed_at=at(10,1,year-1),baseline_json={'weight':87,'sleep_duration':420}))
    base=save(HealthAssessment(patient_id=member.id,cycle_year=year,assessment_type='ANNUAL',version=1,title='年度健康基线',summary='体重86kg；睡眠6.8小时。以体重和生活方式管理为重点。',
        created_by='林健管',status='CONFIRMED',confirmed_at=at(1,5),assessed_at=at(1,5),baseline_json={'weight':86,'bmi':28.1,'sleep_duration':408},
        source_references_json={'说明':'隔离QA年度体检报告（合成）'}))
    save(IntakeAssessment(patient_id=member.id,cycle_year=year,status='CONFIRMED',review_status='CONFIRMED',member_concern='想减重并保持睡眠'))
    goal=save(ManagementGoal(patient_id=member.id,program_id=program.id,goal_type='WEIGHT_MANAGEMENT',title='年度减重5kg，先完成3个月生活方式调整',
        description='会员希望改善体重；由健管确认分阶段推进。',metric_code='weight',baseline_value=86,target_value=81,target_unit='kg',
        start_date=at(3).date(),target_date=at(12,31).date(),owner_id='林健管',status='ACTIVE',source='MEMBER',
        confirmed_by='林健管',confirmed_at=at(3),plan_confirmed_by='林健管',plan_confirmed_at=at(3,2),requirements_json=snapshot('WEIGHT_MANAGEMENT')))
    phase=save(ProgramPhase(program_id=program.id,phase_code='EXECUTION',title='阶段2 · 稳定执行',sequence=2,start_date=at(6).date(),end_date=at(12,31).date(),
        goal='稳定执行体重与睡眠监测',status='ACTIVE'))
    problem=save(HealthProblem(patient_id=member.id,program_id=program.id,title='睡眠持续下降',description='会员近期夜班增多',source='synthetic-qa',opened_at=at(8,12)))
    rule=save(RiskRule(name='QA睡眠关注依据（仅合成验证）',code='timeline-qa-'+str(uuid4()),applicable_device_class='WELLNESS',canonical_code='sleep_duration',
        risk_level='YELLOW',condition_type='THRESHOLD',threshold_config={'operator':'<','value':330,'unit':'minutes'},action_type='MANAGER_REVIEW',
        source_reference='隔离QA合成规则，不作医学标准',scope='TEST',review_status='APPROVED',reviewed_by='QA',is_active=False))
    risk=save(RiskEvent(patient_id=member.id,risk_rule_id=rule.id,risk_level='YELLOW',device_class='WELLNESS',canonical_code='sleep_duration',
        summary='睡眠持续低于个人近期水平，需要核实生活方式',requires_manager_review=True,status='FOLLOW_UP',created_at=at(8,12)))
    def observation(code,value,when):
        text=f'{value} {REGISTRY[code].default_unit} · 隔离QA合成设备记录'
        raw=save(RawData(patient_id=member.id,source='QA_DEVICE',record_type='measurement',recorded_at=when,
            payload_json={'original_text':text,'original_value':str(value),'original_unit':REGISTRY[code].default_unit},
            checksum=hashlib.sha256((code+when.isoformat()+text).encode()).hexdigest()))
        return save(Observation(patient_id=member.id,metric_code=code,value_numeric=Decimal(str(value)),unit=REGISTRY[code].default_unit,
            observed_at=when,source='QA_DEVICE',source_type='DEVICE',quality_flag='valid',raw_record_id=raw.id,evidence_ref='隔离QA合成设备记录'))
    observation('weight',86,at(1,5));observation('weight',83.6,at(5,10))
    for day in range(4,13):
        observation('sleep_duration',408 if day<10 else 324,at(8,day));calculate(session,member.id,at(8,day).date(),emit=False)
    sleep_obs=observation('sleep_duration',324,at(8,13));daily=calculate(session,member.id,at(8,13).date(),emit=False)
    change=save(HealthEvent(member_id=member.id,event_type='MEANINGFUL_CHANGE',event_category='MEANINGFUL_CHANGE',occurred_at=at(8,13),
        source='QA summary',source_type='SYSTEM',source_id='timeline-sleep-'+str(uuid4()),description='睡眠从近7日均值6.2小时下降至5.4小时',status='PROCESSED',
        payload_ref={'summary_id':str(daily.id),'summary_version':daily.version,'goal_id':str(goal.id),'risk_event_id':str(risk.id),'observation_ids':[str(sleep_obs.id)],
            'change':{'metric':'sleep_duration','today':'324','mean_7d':'372','mean_30d':'380','window_days':7,'reason':'QA合成场景：持续睡眠下降，需健管核实'},
            'lookback':{'metrics':['sleep_duration','steps'],'baseline_id':str(base.id)}}))
    agent_goal=save(AgentGoal(member_id=member.id,goal_type='HEALTH_CHANGE',title='睡眠变化跟进（隔离QA）',status='WAITING_MANAGER',
        source_type='HealthEvent',source_id=str(change.id),owner='林健管',context_json={'risk_event_id':str(risk.id)},started_at=at(8,13)))
    change.goal_id=agent_goal.id
    log=save(ManagementLog(patient_id=member.id,program_id=program.id,occurred_at=at(8,14),category='健管随访',channel='电话',
        member_issue='近期连续夜班，睡前仍饮用咖啡',manager_action='核实排班与饮食情况，商定可执行的休息安排',result='会员确认夜班影响睡眠',
        next_action='两周后复核睡眠记录',owner='林健管',evidence='合成电话记录，会员确认',related_risk_id=risk.id,created_by='林健管',request_key=str(uuid4())))
    plan=save(ManagementPlan(patient_id=member.id,health_problem_id=problem.id,title='睡眠生活方式调整',content='会员同意减少晚间咖啡，按排班调整休息时间。',
        source='MANAGER',status='ACTIVE',owner='林健管',start_date=at(8,15).date(),adjusted_at=at(8,15),adjusted_by='林健管',adjustment_reason='会员反馈连续夜班，原计划难以执行'))
    doctor=save(DoctorReview(patient_id=member.id,program_id=program.id,health_problem_id=problem.id,risk_event_id=risk.id,doctor_name='王医生',department='全科',
        doctor_brief='生活方式调整后睡眠有所恢复，会员希望确认后续监测安排',question_for_doctor='是否继续家庭监测，何时复查？',
        opinion='暂不调整用药，继续家庭血压监测两周，下次复查时再判断。',status='CONFIRMED',reviewed_at=at(9,15)))
    recheck=save(RecheckPlan(patient_id=member.id,program_id=program.id,title='家庭监测复查',reason='采用医生正式意见',planned_at=at(10,15),owner='林健管',
        status='CONFIRMED',doctor_review_id=doctor.id,created_at=at(9,15),evidence='王医生确认的监测建议'))
    stage=save(StageReview(patient_id=member.id,program_id=program.id,phase_id=phase.id,reviewed_at=at(9,30),owner='林健管',decision='CONTINUE',
        content={'阶段目标':'保持体重管理和稳定睡眠','实际完成':'随访、计划调整与两周睡眠观察已完成','会员反馈':'减少晚间咖啡可执行，仍有夜班',
                 '指标变化':'睡眠记录由5.4小时至6.2小时','未解决问题':'夜班仍需持续跟踪','下一阶段':'继续生活方式计划与家庭监测'}))
    observation('sleep_duration',372,at(9,1))
    outcome=record_outcome_evaluation(session,program,'睡眠时长','5.4','6.2','小时','UP','林健管',
        '隔离QA：8月13日与9月1日设备记录，会员随访核对。','IMPROVED',evaluation_date=at(9,1).date(),care_trigger_id=change.id)
    weight=record_outcome_evaluation(session,program,'体重','86','83.6','kg','DOWN','林健管','1月基线与5月测量记录','IMPROVED',evaluation_date=at(5,10).date())
    for day in range(28,31):observation('sleep_duration',372,at(9,day));calculate(session,member.id,at(9,day).date(),emit=False)
    for day in range(1,5):observation('sleep_duration',372,at(10,day));calculate(session,member.id,at(10,day).date(),emit=False)
    observation('weight',81.2,at(10,4))
    calculate(session,member.id,at(10,4).date(),emit=False)
    link=link_care_episode(session,member.id,change.id,links=[{'type':type(r).__name__,'id':str(r.id)} for r in (log,plan,doctor,recheck,stage,goal)],actor='林健管',role='HEALTH_MANAGER')
    # Explicit recorded relationship time, not the machine's seed execution date.
    link.occurred_at=at(10,4)
    return {'member':member,'empty':empty,'program':program,'goal':goal,'baseline':base,'prior':prior,'change':change,
        'risk':risk,'log':log,'doctor':doctor,'recheck':recheck,'stage':stage,'outcome':outcome,'observation':sleep_obs,'now':at(10,4)+timedelta(hours=10)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--database',required=True);args=parser.parse_args()
    root=Path(__file__).resolve().parents[1];path=Path(args.database).resolve();runtime=(root/'.runtime').resolve()
    if runtime not in path.parents or path.exists() or path.suffix!='.db':
        raise SystemExit('仅允许在本项目 .runtime 下创建不存在的 QA .db 文件；禁止正式库和覆盖。')
    path.parent.mkdir(parents=True,exist_ok=True)
    engine=create_engine('sqlite:///'+path.as_posix());Base.metadata.create_all(engine)
    with Session(engine) as session:
        records=seed_story(session);session.commit();print('Created isolated QA story:',path,records['member'].id)
    engine.dispose()


if __name__=='__main__':main()
