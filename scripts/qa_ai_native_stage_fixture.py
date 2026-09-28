"""Create a documented synthetic due/stage scenario through existing services."""
import os,json,sys
from pathlib import Path
from uuid import UUID
from datetime import timedelta,datetime,time,timezone
os.environ['DATABASE_URL']='sqlite:///D:/executive_health_ai/.runtime/ai-native-final/browser.db'
sys.stdout.reconfigure(encoding='utf-8')
from sqlalchemy import select,func
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentGoal,MemberAgent,HealthProgram,ProgramPhase,Observation,Task
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.longitudinal import HealthAssessmentService
from executive_health_ai.services.management_workflow import ManagementWorkflowService,task
from executive_health_ai.services.management_action_loop import ManagementActionLoop
from executive_health_ai.services.measurement_ingestion import MeasurementEnvelope,ingest_measurement
from executive_health_ai.services.health_event_measurements import evaluate_window
from executive_health_ai.services.daily_care import schedule_due
from executive_health_ai.services.health_events import ingest_health_event
ids=json.loads(Path('.runtime/ai-native-final/members.json').read_text(encoding='utf-8'));member=UUID(ids['intake'])
with SessionLocal() as s:
    program=s.scalar(select(HealthProgram).where(HealthProgram.patient_id==member));w=ManagementWorkflowService()
    agent=s.scalar(select(MemberAgent).where(MemberAgent.member_id==member));before=agent.wake_count
    count_before=s.scalar(select(func.count(Observation.id)).where(Observation.patient_id==member))
    start=utc_now()-timedelta(minutes=1)
    for i in range(100):
        ingest_measurement(s,MeasurementEnvelope(member_id=member,source_type='DEVICE',source_id='final-device-'+str(i),
            metric='systolic_bp',value=145,unit='mmHg',observed_at=utc_now()))
    s.commit();s.refresh(agent);raw=agent.wake_count-before
    assert raw==0
    end=utc_now()+timedelta(seconds=1)
    for _ in range(3):evaluate_window(s,member_id=member,metric='systolic_bp',threshold=140,minimum_count=3,
        window_start=start,window_end=end,rule_id='final-synthetic-bp')
    s.commit();s.refresh(agent);change=agent.wake_count-before
    assert change==1
    evidence={'member':str(member),'member_agent':str(agent.id),'raw_count':100,'raw_wakes':raw,'meaningful_wakes':change,
        'observations_added':s.scalar(select(func.count(Observation.id)).where(Observation.patient_id==member))-count_before}
    Path('docs/images/ai-native-final/device-evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    # Review the synthetic operational change, preserving the source measurements.
    loop=ManagementActionLoop()
    for item in list(s.scalars(select(Task).where(Task.patient_id==member,Task.status.not_in(['COMPLETED','CANCELLED'])))):
        if item.source.startswith('meaningful') or item.title=='核对健康数据变化':
            loop.process_task(s,member,program.id,item.id,actor=program.owner,result='合成规则验收：已核对数据来源，医学判断仍交医生。',
                outcome='已完成',next_action='无需后续',follow_at=None,request_key='final-change-check-'+str(item.id))
    baseline=HealthAssessmentService();existing=baseline.latest_baseline(s,member,include_draft=True,cycle_year=program.cycle_year)
    if not existing:
        report=s.scalar(select(AgentGoal).where(AgentGoal.member_id==member,AgentGoal.goal_type=='POST_CHECKUP_MANAGEMENT'))
        existing=baseline.create_draft_from_report(s,member,UUID(report.source_id),created_by=program.owner,cycle_year=program.cycle_year)
    if existing.status!='CONFIRMED':baseline.confirm(s,existing.id,program.owner)
    phase=s.scalar(select(ProgramPhase).where(ProgramPhase.program_id==program.id))
    if not phase:phase=w.add_phase(s,member,program.id,title='首阶段资料与随访核对',goal='核对已有资料并记录会员反馈',content='沟通、核对与跟进',
        start=program.start_date,end=program.start_date+timedelta(days=6),owner=program.owner)
    s.flush()
    if program.status=='PLANNED':w.start_program(s,member,program.id,program.owner)
    due=datetime.combine(phase.start_date,time(9),timezone.utc)
    core=task(s,member,program.id,'合成到期随访核对','核对会员资料与后续安排',program.owner,due,'final-due-core')
    s.flush()
    # Explicit synthetic due event; no progress animation or simulated elapsed time.
    event,_=ingest_health_event(s,member_id=member,event_type='TIME_DUE',event_category='TIME_DUE',source_type='SYSTEM',
        source_id='synthetic-due:'+str(core.id),payload_ref={'work_kind':'task','work_id':str(core.id),'due_at':due.isoformat()})
    loop.process_task(s,member,program.id,core.id,actor=program.owner,result='已完成合成到期随访：资料已核对，后续复查安排沿用医生意见。',
        outcome='已完成',next_action='无需后续',follow_at=None,request_key='final-due-completed')
    s.commit();state=loop.project(s,member,program.id)
    print({'phase':phase.title,'ready':state['review_ready'],'open':[i.title for i in state['phase_open']]})
    assert state['review_ready'] and not state['phase_open']
