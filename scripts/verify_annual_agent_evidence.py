"""Read-only acceptance assertions over actual isolated execution records."""
import json
import os
from pathlib import Path
from uuid import UUID

ROOT=Path(__file__).resolve().parents[1]
cases=json.loads((ROOT/'.runtime/annual-agent-ai/cases.json').read_text(encoding='utf-8'))
os.environ['DATABASE_URL']='sqlite:///'+Path(cases['database']).as_posix()
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentGoal, RiskEvent
from executive_health_ai.services.agent_capabilities import load, trace_data

report={}
with SessionLocal() as session:
    for name,identity in cases['goals'].items():
        goal=session.get(AgentGoal,UUID(identity))
        support,traces=load(session,goal)
        calls=[trace_data(t).copy() for t in traces if t.action=='capability_activity']
        for call in calls:
            if 'citations' in call:
                call['citations']=[{k:v for k,v in c.items() if k in {'title','source','version','location'}} for c in call['citations']]
        report[name]={'goal_status':goal.status,'support':[{'activity':a.title,'status':a.status,'used':a.used,'result':a.result} for a in support],
                      'calls':calls,'formal_risks':len(list(session.scalars(select(RiskEvent).where(RiskEvent.patient_id==goal.member_id))))}
    care=report['care']
    assert care['goal_status']=='COMPLETED'
    assert care['formal_risks']==0
    assert {c['task'] for c in care['calls'] if c['kind']=='LLM' and c['request_sent'] and c['accepted']} == {'post_checkup_manager_draft','post_checkup_action_draft'}
    assert any(c['kind']=='KNOWLEDGE' and c['knowledge_hit_count']>0 for c in care['calls'])
    assert not any(c['kind'] in {'LLM','KNOWLEDGE'} for c in report['structured']['calls'])
    assert any(c['kind']=='LLM' and c['request_sent'] and c['accepted'] for c in report['prose']['calls'])
    assert not any(c['kind']=='KNOWLEDGE' for c in report['prose']['calls'])
    assert any(c['kind']=='LLM' and not c['request_sent'] and c['status']=='UNAVAILABLE' for c in report['unavailable']['calls'])
    forbidden={'prompt','system_prompt','user_prompt','chain_of_thought','reasoning_content','response_body'}
    assert all(not forbidden.intersection(c) for row in report.values() for c in row['calls'])
output=ROOT/'docs/annual-agent-ai/execution-evidence.json'
output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Actual execution assertions passed: completed doctor path, native mapping, prose AI, unavailable fallback, no synthetic risk.')
