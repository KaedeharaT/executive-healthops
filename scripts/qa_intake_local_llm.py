"""Optional real local-model smoke check, synthetic text and in-memory database."""
import json
from pathlib import Path
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from executive_health_ai.config import load_project_environment
from executive_health_ai.models import Patient,AgentRunTrace
from executive_health_ai.models.base import Base
from executive_health_ai.services.management_workflow import ManagementWorkflowService
from executive_health_ai.services.assessment_import import AssessmentImportService
from executive_health_ai.services.profile_ingestion import ProfileIngestionService
from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
from executive_health_ai.llm.local_llm_client import LocalLLMClient

load_project_environment()
client=LocalLLMClient()
if not client.settings.is_local_ollama() or not client.available():
    raise SystemExit('Local Ollama is not available; no remote request will be sent.')
engine=create_engine('sqlite://');Base.metadata.create_all(engine)
ProfileIngestionService.storage_root=Path('.runtime/multi-file-intake/local-model-docs')
with Session(engine,expire_on_commit=False) as session:
    member=Patient(display_name='Synthetic Local Model QA',timezone='Asia/Tokyo');session.add(member);session.flush()
    row=ManagementWorkflowService().start_intake(session,member.id,2026,'QA')
    imports=AssessmentImportService()
    imports.upload_batch(session,member.id,row.id,[('synthetic-free-text.txt','平时每晚只睡六小时，最想改善睡眠质量。'.encode())],actor='QA')
    goal=imports.goals(session,row)[0]
    for _ in range(6):
        if goal.status!='RUNNING':break
        HealthOpsAgentSupervisor().execute_next_step(session,goal.id)
    view=imports.project(session,member.id,row.id)
    traces=list(session.scalars(select(AgentRunTrace).where(AgentRunTrace.goal_id==goal.id,AgentRunTrace.action=='capability_activity')))
    calls=[t.metadata_json['capability'] for t in traces if t.metadata_json.get('capability',{}).get('kind')=='LLM']
    result={'provider':'local Ollama','synthetic_only':True,'goal_status':goal.status,
        'calls':[{'task':c.get('task'),'status':c.get('status'),'request_sent':c.get('request_sent'),'accepted':c.get('accepted'),'result_count':c.get('result_count')} for c in calls],
        'candidate_count':view['files'][0]['count'],'manual_check_required':view['files'][0]['needs_check']}
    Path('docs/multi-file-intake/local-llm.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)
