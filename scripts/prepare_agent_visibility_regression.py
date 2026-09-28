"""Isolated synthetic member; real services create all workflow records.

No goal state is overwritten and the user's runtime databases are not modified.
The browser uploads the report and performs manager / doctor confirmations.
"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.runtime/agent-visibility-regression'
WORK.mkdir(parents=True, exist_ok=True)
database = WORK / 'scenario.db'
if database.exists():
    raise SystemExit('Scenario already exists; reuse it or choose a new isolated directory.')
os.environ['DATABASE_URL'] = 'sqlite:///' + database.as_posix()
from executive_health_ai.database import engine, SessionLocal
from executive_health_ai.models import Base
from executive_health_ai.services.knowledge import KnowledgeService
from seed_management_action_loop import seed

Base.metadata.create_all(engine)
with SessionLocal() as session:
    member, program = seed(session)
    knowledge = KnowledgeService()
    doc = knowledge.create_document(session, title='合成验收：体重资料核对', category='PATIENT_EDUCATION',
        source_type='INTERNAL', source_name='合成验收资料，非临床指南',
        content_text='体重记录须核对日期、单位与报告来源；医学判断交由医生。本条仅用于隔离验收。', version='qa-1')
    knowledge.approve_document(session, doc, reviewer='验收审核员', comment='仅供合成演示验收')
    session.commit()
    (WORK / 'case.json').write_text(json.dumps({'member':str(member.id),'program':str(program.id)}), encoding='utf-8')
(WORK / 'scenario-manifest.json').write_text(json.dumps({'scenario': {
    'source':str(ROOT), 'database':str(database), 'port':18581}}), encoding='utf-8')
print('Prepared synthetic management loop and reviewed knowledge; zero Agent instances.')
