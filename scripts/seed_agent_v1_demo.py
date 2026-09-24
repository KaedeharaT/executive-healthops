"""Add one synthetic report to the existing synthetic workbench demo database."""
import os
from datetime import date
from pathlib import Path

if not os.getenv('DATABASE_URL', '').endswith('/.runtime/agent-v1.db'):
    raise SystemExit('Use only the isolated .runtime/agent-v1.db synthetic demo.')

from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import Patient, AgentGoal
from executive_health_ai.services.report_parsing import ReportParsingService

with SessionLocal() as session:
    member = session.scalar(select(Patient).where(Patient.display_name == 'Demo Executive A'))
    if not member:
        raise SystemExit('First prepare the existing synthetic workbench demo.')
    content = f'''合成演示体检报告（非真实个人资料）
体检日期：{date.today().isoformat()}
低密度脂蛋白胆固醇  4.35 mmol/L
谷丙转氨酶  56 U/L
体重  85.8 kg
'''.encode('utf-8')
    parser = ReportParsingService()
    parser.storage_root = Path('.runtime/agent-v1-reports')
    report, run, duplicate = parser.upload_and_parse(session, member.id, '本次体检报告（合成演示）.txt', content, '王健管')
    goal = session.scalar(select(AgentGoal).where(AgentGoal.source_id == str(report.id)))
    session.commit()
    print(f'{member.display_name}: {goal.status}, {len(goal.context_json.get("findings", []))} findings')
    Path('.runtime/agent-v1-goal.txt').write_text(str(goal.id), encoding='utf-8')
