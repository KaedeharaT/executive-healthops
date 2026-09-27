"""Create one active care story only in the isolated synthetic visual QA copy."""
import os
from pathlib import Path
from datetime import date

if os.getenv('DATABASE_URL') != 'sqlite:///D:/executive_health_ai/.runtime/neumorphism_qa.db':
    raise SystemExit('Only the isolated neumorphism QA database is supported.')

from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import Patient, AgentGoal
from executive_health_ai.services.report_parsing import ReportParsingService
from executive_health_ai.agent.scheduler import AgentSchedulerService
from executive_health_ai.models.base import utc_now

with SessionLocal() as session:
    member=session.scalar(select(Patient).where(Patient.display_name=='Demo Executive A'))
    assert member and member.external_id
    parser=ReportParsingService()
    parser.storage_root=Path('.runtime/neumorphism-reports')
    content=f'合成演示资料，非真实个人信息\n体检日期：{date.today().isoformat()}\n低密度脂蛋白胆固醇 4.35 mmol/L\n谷丙转氨酶 56 U/L\n体重 85.8 kg\n'.encode('utf-8')
    report,run,_=parser.upload_and_parse(session,member.id,'视觉验收体检报告（合成）.txt',content,'演示健康管理师')
    session.commit()
    AgentSchedulerService().run_due(session,now=utc_now())
    session.commit()
    goal=session.scalar(select(AgentGoal).where(AgentGoal.source_id==str(report.id)))
    print(goal.status,goal.current_stage)
