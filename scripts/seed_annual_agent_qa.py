"""Isolated synthetic acceptance data; actual local LLM and governed retrieval calls."""
import json
import os
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.runtime/annual-agent-ai'
OUT.mkdir(parents=True,exist_ok=True)
database = OUT / 'qa.db'
if database.exists():
    raise SystemExit('QA database already exists; reuse its real execution records instead of reseeding.')
with sqlite3.connect(ROOT/'data/portfolio_demo.db') as src, sqlite3.connect(database) as dst:
    src.backup(dst)
os.environ.update(DATABASE_URL='sqlite:///'+database.as_posix(), PORTFOLIO_DEMO='true',
    AGENT_SUPERVISOR_ENABLED='true', LOCAL_LLM_PROVIDER='local', OLLAMA_BASE_URL='http://127.0.0.1:11434',
    LOCAL_LLM_ENABLED='true', LOCAL_LLM_MODEL='qwen2.5:7b', LOCAL_LLM_TIMEOUT_SECONDS='180')
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentGoal, AgentRunTrace, HealthAssessment, Task, Patient
from executive_health_ai.services.management_workflow import ManagementWorkflowService
from executive_health_ai.services.knowledge import KnowledgeService
from executive_health_ai.services.report_parsing import ReportParsingService
from executive_health_ai.services.profile_ingestion import ProfileIngestionService
from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
from executive_health_ai.agent import post_checkup
from executive_health_ai.services.agent_capabilities import load

today = date.today()
manifest = {'database':str(database),'members':{},'goals':{}}
with SessionLocal() as session:
    ks = KnowledgeService()
    for title,term in [('体重记录核对（QA匿名示例）','体重'),('血脂资料核对（QA匿名示例）','低密度脂蛋白胆固醇'),('体检沟通准备（QA匿名示例）','谷丙转氨酶')]:
        doc = ks.create_document(session,title=title,category='PATIENT_EDUCATION',source_type='INTERNAL',
            source_name='QA匿名测试资料（非临床指南）',content_text=term+'资料应由健管核对报告日期、单位与来源。涉及医学判断交由医生。此文仅用于验证检索功能。',version='qa-1')
        ks.approve_document(session,doc,reviewer='QA演示审核员',comment='仅供隔离验收使用')
    workflow = ManagementWorkflowService()
    for index,label in enumerate(['基线','持续','阶段复盘','年度复盘','逾期']):
        end = today + timedelta(days=20 if label == '年度复盘' else 120)
        program = workflow.enroll(session,name='验收会员·'+label,start=today-timedelta(days=60),end=end,
                                   owner='验收健管',goal='记录体重 / 血脂变化，按期核对年度安排')
        manifest['members'][label] = str(program.patient_id)
        if label != '基线':
            session.add(HealthAssessment(patient_id=program.patient_id,assessment_type='BASELINE',version=1,
                cycle_year=today.year,title='QA匿名年度基线',summary='验收用已确认基线',created_by='验收健管',status='CONFIRMED',baseline_json={}))
            phase = workflow.add_phase(session,program.patient_id,program.id,title='持续管理执行',goal='按约定核对资料',
                content='跟踪执行并记录结果',start=program.start_date,
                end=today+timedelta(days=7 if label=='阶段复盘' else 15 if label=='年度复盘' else -2 if label=='逾期' else 60),owner='验收健管')
            phase.status='ACTIVE';program.status='ACTIVE'
            session.add(Task(patient_id=program.patient_id,program_id=program.id,title='核对本阶段记录',instruction='合成验收事项',
                status='PENDING',priority='MEDIUM',assignee='验收健管',responsible_role='health_manager',
                due_at=datetime.now(timezone.utc)+timedelta(days=-2 if label=='逾期' else 5),source='annual-agent-qa'))
        session.flush()
    session.commit()
    parser = ReportParsingService();parser.storage_root=OUT/'reports'
    member = manifest['members']['持续']
    from uuid import UUID
    report,_,_ = parser.upload_and_parse(session,UUID(member),'AI知识调用验收.txt',
        ('体检日期：'+today.isoformat()+'\n低密度脂蛋白胆固醇  3.4 mmol/L\n体重  75 kg\n谷丙转氨酶  24 U/L').encode(),'验收健管')
    goal = session.scalar(select(AgentGoal).where(AgentGoal.source_id==str(report.id)))
    manifest['goals']['care']=str(goal.id)
    session.commit()
    print('Care: '+json.dumps([(a.title,a.status) for a in load(session,goal)[0]],ensure_ascii=True),flush=True)
    ingestion=ProfileIngestionService();ingestion.storage_root=OUT/'profiles'
    native={'responses':{'生活方式':{'睡眠':'每天七小时','烟草':'不吸烟'}}}
    prose='最近我每天睡眠六小时。平时我不吸烟。我希望改善睡眠质量。'
    for label,filename,content in [('structured','结构化问卷.json',json.dumps(native,ensure_ascii=False).encode()),
                                    ('prose','自由文本问卷.txt',prose.encode())]:
        intake,_=ingestion.upload(session,UUID(member),filename,content,'questionnaire',actor='验收健管',role='HEALTH_MANAGER')
        supervisor=HealthOpsAgentSupervisor()
        for _ in range(5):
            if intake.status!='RUNNING':break
            supervisor.execute_next_step(session,intake.id)
        manifest['goals'][label]=str(intake.id)
        session.commit()
        print(label+': '+json.dumps([(a.title,a.status) for a in load(session,intake)[0]],ensure_ascii=True),flush=True)
    # A genuine unavailable request, without overriding successful cases.
    os.environ['LOCAL_LLM_ENABLED']='false'
    report,_,_ = parser.upload_and_parse(session,UUID(manifest['members']['基线']),'AI不可用验收.txt',
        ('体检日期：'+today.isoformat()+'\n体重  72 kg').encode(),'验收健管')
    unavailable=session.scalar(select(AgentGoal).where(AgentGoal.source_id==str(report.id)))
    manifest['goals']['unavailable']=str(unavailable.id)
    session.commit()
    manifest['calls'] = [t.metadata_json['capability'] for t in session.scalars(select(AgentRunTrace).where(
        AgentRunTrace.goal_id.in_([UUID(v) for v in manifest['goals'].values()]),AgentRunTrace.action=='capability_activity'))]
(OUT/'cases.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'manifest.json').write_text(json.dumps({'annual-ai':dict(source=str(ROOT),database=str(database),port=18540)},indent=2),encoding='utf-8')
print('Prepared isolated real-call QA cases.',flush=True)
