"""Prepare a disposable UI-only audit fixture from the synthetic portfolio seed."""
from pathlib import Path
import os,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
story='--management-story' in sys.argv
work=ROOT/('.runtime/ui-dedup-management' if story else '.runtime/ui-dedup');work.mkdir(parents=True,exist_ok=True)
db=work/'qa.db'
if db.exists():raise SystemExit('Reuse existing isolated QA database')
if not story:
 with sqlite3.connect(ROOT/'data/portfolio_demo.db') as src,sqlite3.connect(db) as dst:src.backup(dst)
os.environ.update(DATABASE_URL='sqlite:///'+db.as_posix(),LOCAL_LLM_ENABLED='false',PORTFOLIO_DEMO='true',AGENT_SUPERVISOR_ENABLED='true')
from executive_health_ai.database import SessionLocal,engine
from executive_health_ai.models import Base,Patient
Base.metadata.create_all(engine)
from scripts.seed_management_action_loop import seed
from executive_health_ai.services.management_workflow import ManagementWorkflowService
from executive_health_ai.services.assessment_import import AssessmentImportService
from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
from executive_health_ai.models import AgentGoal
from uuid import UUID
with SessionLocal() as s:
 member,_=seed(s)
 p=Patient(display_name='UI Audit Intake',timezone='Asia/Tokyo');s.add(p);s.flush()
 intake=ManagementWorkflowService().start_intake(s,p.id,2026,'演示健管')
 data={'responses':{'基础资料':{'display_name':'UI Audit Intake','birth_date':'1980-01-01','sex':'male'},'生活方式':{'睡眠':'七小时'},'家族健康史':[{'关系':'母亲','具体疾病':'会员表示暂不清楚'}]}}
 results=AssessmentImportService().upload_batch(s,p.id,intake.id,[('合成问卷.json',json.dumps(data,ensure_ascii=False).encode())],actor='演示健管')
 for result in results:
  goal=s.get(AgentGoal,UUID(result['goal_id']))
  for _ in range(4):HealthOpsAgentSupervisor().execute_next_step(s,goal.id)
 s.commit()
(work/'manifest.json').write_text(json.dumps({'dedup':{'source':str(ROOT),'database':str(db),'port':18586 if story else 18585}}),encoding='utf-8')
print('Isolated synthetic QA database prepared')
