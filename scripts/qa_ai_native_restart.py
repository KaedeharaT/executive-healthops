"""Persisted wait/restart acceptance on the isolated synthetic database."""
import os,json,sys
from pathlib import Path
from uuid import UUID
from datetime import timedelta
os.environ['DATABASE_URL']='sqlite:///D:/executive_health_ai/.runtime/ai-native-final/browser.db'
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentGoal,MemberAgent,HealthProgram
from executive_health_ai.models.base import utc_now
from executive_health_ai.services import care_runtime
from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
ids=json.loads(Path('.runtime/ai-native-final/members.json').read_text(encoding='utf-8'));member=UUID(ids['intake'])
path=Path('docs/images/ai-native-final/restart-evidence.json')
with SessionLocal() as s:
    agent=s.scalar(select(MemberAgent).where(MemberAgent.member_id==member))
    if '--prepare' in sys.argv:
        p=s.scalar(select(HealthProgram).where(HealthProgram.patient_id==member));goals={}
        for state in ['RUNNING','WAITING_MANAGER','WAITING_DOCTOR','WAITING_TIME','WAITING_MEMBER','WAITING_INPUT']:
            goal=care_runtime.start(s,HealthOpsAgentSupervisor(),member_id=member,kind='DAILY_CARE',source_id='restart-check:'+state,
                title='合成重启验收',context={'program_id':str(p.id),'trigger_reason':'合成进程恢复验收'},owner=p.owner)
            if state!='RUNNING':care_runtime.wait(s,goal,state,next_action='等待合成验收返回',
                due=utc_now()+timedelta(days=1) if state=='WAITING_TIME' else None,expected_event='TIME_DUE' if state=='WAITING_TIME' else 'SYNTHETIC_RETURN',expected_source=str(goal.id))
            goals[state]=str(goal.id)
        s.commit();path.write_text(json.dumps({'member_agent':str(agent.id),'before':goals},indent=2),encoding='utf-8')
    else:
        data=json.loads(path.read_text(encoding='utf-8'));assert data['member_agent']==str(agent.id)
        after={state:s.get(AgentGoal,UUID(identity)).status for state,identity in data['before'].items()}
        assert after['RUNNING']=='COMPLETED',after
        assert all(value==state for state,value in after.items() if state!='RUNNING'),after
        data['after']=after;data['same_member_agent']=True;path.write_text(json.dumps(data,indent=2),encoding='utf-8');print('Restart PASS',after)
        # End only the synthetic restart checks; real business waits are untouched.
        for state,identity in data['before'].items():
            goal=s.get(AgentGoal,UUID(identity))
            if goal.status!='COMPLETED':
                goal.context_json={**goal.context_json,'no_action_reason':'合成重启验收结束，无真实业务事项'}
                care_runtime.finish(s,goal)
        s.commit()
