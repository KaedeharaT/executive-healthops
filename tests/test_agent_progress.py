"""Business progress, frozen during model calls and stopped at human boundaries."""
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace as NS
from uuid import UUID
import pytest
from streamlit.testing.v1 import AppTest
from executive_health_ai.services.agent_progress import project,load,batch,PROFILE_STEPS
from executive_health_ai.models import AgentGoal
from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
from executive_health_ai.services import intake_workspace as workspace
from tests.test_assessment_import import env,native

NOW=datetime(2026,9,28,12,tzinfo=timezone.utc)


def goal(status='PROCESSING',stage='PARSING',**context):
    return NS(goal_type='PROFILE_INTAKE',status=status,current_stage=stage,context_json=context,
              started_at=NOW-timedelta(seconds=42),completed_at=NOW if status=='COMPLETED' else None,automation_paused=False)


def steps(*completed):
    return [NS(step_type=s,status='COMPLETED' if s in completed else 'PENDING',started_at=NOW-timedelta(seconds=37))
            for s in ('RECEIVED','PARSING','NORMALIZING','MATCHING','REVIEW','WRITING')]


def events():return {'CONTENT_READ':(NOW-timedelta(seconds=38)).isoformat(),'AI_REQUEST_STARTED':(NOW-timedelta(seconds=37)).isoformat()}


def test_progress_derived_from_real_steps_and_no_timer_growth():
    g=goal(progress_events=events())
    a=project(g,steps('RECEIVED'),now=NOW)
    b=project(g,steps('RECEIVED'),now=NOW+timedelta(seconds=100))
    assert a.labels==PROFILE_STEPS and a.completed_steps==2 and a.current_step==3
    assert a.progress_percent==b.progress_percent==29
    assert a.elapsed_seconds==42 and b.elapsed_seconds==142
    assert a.ai_running and a.ai_elapsed_seconds==37
    assert '仍在处理中' in a.wait_message and '处理时间较长' in b.wait_message


@pytest.mark.parametrize('status',['WAITING_MANAGER','WAITING_DOCTOR','FAILED','ESCALATED','CANCELLED','COMPLETED'])
def test_human_and_terminal_states_stop_spinner(status):
    g=goal(status,progress_events=events())
    p=project(g,steps('RECEIVED','PARSING','NORMALIZING','MATCHING'),now=NOW)
    assert not p.running and not p.ai_running
    assert p.progress_percent==(100 if status=='COMPLETED' else 71)


def test_llm_finished_stops_ai_spinner_without_advancing_business_steps():
    g=goal(progress_events={**events(),'AI_REQUEST_FINISHED':NOW.isoformat()})
    p=project(g,steps('RECEIVED'),now=NOW+timedelta(seconds=10))
    assert not p.ai_running and p.progress_percent==29 and p.ai_elapsed_seconds==37


def test_timeout_preserves_failed_position_and_actual_duration():
    g=goal('ESCALATED',progress_events={**events(),'AI_REQUEST_TIMEOUT':NOW.isoformat()})
    p=project(g,steps('RECEIVED'),now=NOW+timedelta(seconds=100))
    assert p.timeout and not p.ai_running and not p.running
    assert p.progress_percent==29 and p.ai_elapsed_seconds==37


def test_post_checkup_uses_six_business_steps():
    from executive_health_ai.agent.post_checkup import VERSION
    g=goal('WAITING_DOCTOR','WAITING_DOCTOR_REVIEW',version=VERSION);g.goal_type='POST_CHECKUP_MANAGEMENT'
    records=[NS(step_type=s,status='COMPLETED',started_at=NOW) for s in ('REPORT_RECEIVED','ANALYZING','WAITING_MANAGER_REVIEW')]
    p=project(g,records,[NS(action='responsibility_routed')],now=NOW)
    assert p.total_steps==6 and p.current_step==4 and p.progress_percent==50
    assert not p.running and not p.ai_running


def test_file_subprogress_does_not_inflate_overall_steps():
    completed=project(goal('WAITING_MANAGER','REVIEW'),steps('RECEIVED','PARSING','NORMALIZING','MATCHING'),now=NOW)
    running=project(goal(progress_events=events()),steps('RECEIVED'),now=NOW)
    files=[dict(progress=p,document=NS(title=name)) for p,name in [(completed,'问卷.json'),(completed,'体检.txt'),(running,'历史.docx')]]
    p=batch(files)
    assert (p.file_completed,p.file_total,p.current_file)==(2,3,'历史.docx')
    assert p.progress_percent==29 and p.ai_running


def test_real_profile_intake_plan_transitions(env):
    s,patient,row=env
    result=workspace.upload(s,patient,NS(intake=row,owner='QA'),[('问卷.json',native({'生活方式':{'睡眠':'七小时'}}))])[0]
    g=s.get(AgentGoal,UUID(result['goal_id']))
    values=[load(s,g).progress_percent]
    for _ in range(4):
        HealthOpsAgentSupervisor().execute_next_step(s,g.id)
        values.append(load(s,g).progress_percent)
    assert values==[0,14,43,43,71]
    assert g.status=='WAITING_MANAGER' and not load(s,g).running


def draw(p):
    from executive_health_ai.ui.agent_progress import render,ai_timing
    render(p);ai_timing(p)


@pytest.mark.parametrize('status',['PROCESSING','WAITING_MANAGER','WAITING_DOCTOR','ESCALATED','COMPLETED'])
def test_rendered_bar_has_accessible_percent_and_correct_spinner(status):
    p=project(goal(status,progress_events=events()),steps('RECEIVED'),now=NOW)
    app=AppTest.from_function(draw,args=(p,)).run()
    assert not app.exception
    html='\n'.join(w.value for w in app.markdown)
    assert f'aria-valuenow="{p.progress_percent}"' in html
    assert ('aria-label="正在整理资料"' in html)==(status=='PROCESSING')
    assert '知识检索' not in html


def test_real_timeout_callback_stops_spinner():
    import requests
    from executive_health_ai.llm.activity import collect_calls,observe_call,observe_progress,request_started
    recorded=[]
    with collect_calls() as calls,observe_progress(recorded.append):
        with pytest.raises(requests.exceptions.ReadTimeout):
            with observe_call('parse_health_intake','local'):
                request_started();raise requests.exceptions.ReadTimeout('synthetic timeout')
    assert recorded==['AI_REQUEST_STARTED','AI_REQUEST_TIMEOUT']
    assert calls[0]['failure_reason']=='TIMEOUT' and calls[0]['status']=='UNAVAILABLE'


def test_retry_does_not_show_old_timeout_as_current_request_failure():
    g=goal(progress_events={**events(),'PARSING_STARTED':(NOW-timedelta(seconds=40)).isoformat()})
    old=NS(action='capability_activity',started_at=NOW-timedelta(minutes=3),completed_at=NOW-timedelta(minutes=2),
           metadata_json={'capability':{'kind':'LLM','request_sent':True,'status':'UNAVAILABLE','failure_reason':'TIMEOUT'}})
    p=project(g,steps('RECEIVED'),[old],now=NOW)
    assert p.ai_running and not p.timeout and p.ai_status=='RUNNING'


def test_current_file_action_is_distinct_from_batch_bottleneck(env):
    from tests.test_intake_workspace_v2 import board,text
    s,patient,row=env
    results=workspace.upload(s,patient,NS(intake=row,owner='QA'),[
        ('a.json',native({'生活方式':{'睡眠':'七小时'}})),('b.json',native({'生活方式':{'烟草':'不吸烟'}}))])
    g=s.get(AgentGoal,UUID(results[0]['goal_id']))
    for _ in range(3):HealthOpsAgentSupervisor().execute_next_step(s,g.id)
    data=workspace.project(s,patient.id,row)
    assert data['progress'].progress_percent==0  # Second file not yet processed.
    app=AppTest.from_function(board,args=(data,)).run()
    assert not app.exception and '正在档案匹配' in text(app)
