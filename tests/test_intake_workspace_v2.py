"""Foreground intake UI, real projections and preserved confirmation boundaries."""
from types import SimpleNamespace
from uuid import UUID
import pytest
from streamlit.testing.v1 import AppTest
from executive_health_ai.models import AgentGoal, AgentRunTrace
from executive_health_ai.services import intake_workspace as workspace
from executive_health_ai.services.management_workflow import ManagementWorkflowService
from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
from tests.test_assessment_import import env, native
from tests.test_intake_entry import archive_page, member, fill, button


def process(env):
    s,p,row=env
    results=workspace.upload(s,p,SimpleNamespace(intake=row,owner='QA'),[
        ('questionnaire.json',native({'家族健康史':[{'患病家属':'父亲','具体疾病':'高血压'}]})),
        ('medication.json',native({'当前用药 / 营养补充':[{'名称':'维生素D'}]})),
        ('history.txt','睡眠：七小时'.encode())])
    for result in results:
        goal=s.get(AgentGoal,UUID(result['goal_id']))
        for _ in range(6):
            if goal.status!='RUNNING':break
            HealthOpsAgentSupervisor().execute_next_step(s,goal.id)
    return workspace.project(s,p.id,row)


def board(data,event=None):
    from executive_health_ai.ui.pages.manager.intake_workspace import draw
    draw(data,event)


def text(app):return '\n'.join(x.value for kind in (app.markdown,app.caption,app.subheader) for x in kind)


def test_single_upload_entry_only():
    app=AppTest.from_function(archive_page,args=(str(member()),)).run()
    assert not app.exception
    assert len(app.get('file_uploader'))==1
    assert sum(b.label=='上传并整理资料' for b in app.button)==1


def test_no_purpose_selector():
    app=AppTest.from_function(archive_page,args=(str(member()),)).run()
    assert not app.radio
    assert all(x not in text(app) for x in ('资料用途','辅助填写初始健康评估','更新正式健康档案（原有逐份确认流程）'))


def test_agent_board_always_visible(env):
    s,p,row=env
    app=AppTest.from_function(board,args=(workspace.project(s,p.id,row),)).run()
    assert not app.exception
    assert app.subheader[0].value=='资料整理进度'
    assert '暂无正在处理的健康资料' in text(app)


def test_agent_running_stage_visible(env):
    s,p,row=env
    workspace.upload(s,p,SimpleNamespace(intake=row,owner='QA'),[('history.txt','睡眠：七小时'.encode())])
    app=AppTest.from_function(board,args=(workspace.project(s,p.id,row),)).run()
    assert not app.exception
    assert app.subheader[0].value=='系统助手正在整理资料'
    assert all(phase in text(app) for phase in workspace.project(s,p.id,row)['progress'].labels)
    assert 'history.txt' in text(app) and '整理进度' in text(app)


def test_agent_completion_summary_visible(env):
    data=process(env)
    app=AppTest.from_function(board,args=(data,)).run()
    assert not app.exception and data['ready'] and not data['finished']
    assert app.subheader[0].value=='资料整理进度'
    assert '需要确认' in text(app) and '健康档案更新' in text(app)
    details=next(e for e in app.expander if e.label=='处理记录与来源')
    assert not details.proto.expanded
    assert '资料整理依据' in text(app)  # retained inside the collapsed disclosure
    assert data['stats']['prefilled']>0 and data['exceptions']['counts']['exceptions']>0
    assert all(f['goal'].status=='WAITING_MANAGER' for f in data['files'])


@pytest.mark.parametrize('index,label',list(enumerate(workspace.LABELS)))
def test_category_card_clickable_and_direct_step(index,label):
    mid=member();app=AppTest.from_function(archive_page,args=(str(mid),)).run()
    assert sum(b.key.startswith('intake-category-') for b in app.button if b.key)==10
    next(b for b in app.button if b.label.startswith(label+'\n')).click().run()
    assert not app.exception
    assert next(w for w in app.selectbox if w.label=='填写步骤').value==index


def test_family_and_medication_override_previous_step_selection():
    mid=member();app=AppTest.from_function(archive_page,args=(str(mid),)).run()
    next(b for b in app.button if b.label.startswith('家族史\n')).click().run()
    app.selectbox[0].select(8).run()
    button(app,'← 返回健康档案').click().run()
    next(b for b in app.button if b.label.startswith('用药\n')).click().run()
    assert app.selectbox[0].value==5
    button(app,'← 返回健康档案').click().run()
    next(b for b in app.button if b.label.startswith('家族史\n')).click().run()
    assert app.selectbox[0].value==1


def test_first_incomplete_step_routing(env):
    s,p,row=env
    ManagementWorkflowService().save_intake(s,p.id,2026,'基础资料',{'display_name':p.display_name},'QA')
    assert workspace.first_incomplete(s,p.id,row)=='家族健康史'
    data=process(env)
    assert next(x for x in data['sections'] if x['label']=='家族史')['status']=='待确认'
    # Uploading introduces a new source review gate, including saved sections.
    assert workspace.first_incomplete(s,p.id,row)=='基础资料'
    workspace.imports.record_review(s,row,'基础资料','QA')
    assert workspace.first_incomplete(s,p.id,row)=='家族健康史'


def test_all_complete_routes_to_submit():
    mid=member();fill(mid)
    app=AppTest.from_function(archive_page,args=(str(mid),)).run()
    button(app,'确认并提交初始健康评估').click().run()
    assert not app.exception and app.selectbox[0].value==10


def test_no_duplicate_archive_summary_table_and_full_archive_accessible():
    app=AppTest.from_function(archive_page,args=(str(member()),)).run()
    assert not app.dataframe
    button(app,'查看完整健康档案').click().run()
    assert not app.exception
    assert len(app.dataframe[0].value)==16
    assert list(app.dataframe[0].value.columns)==['资料','摘要']
    button(app,'← 返回健康档案主页').click().run()
    assert not app.dataframe


def test_ai_activity_reflects_real_calls_only(env):
    from executive_health_ai.llm.activity import observe_progress,collect_calls,observe_call,request_started
    events=[]
    with observe_progress(events.append),collect_calls():
        with observe_call('parse_health_intake','local'):pass
        assert events==[]
        with observe_call('parse_health_intake','local'):request_started()
    assert events==['AI_REQUEST_STARTED','AI_REQUEST_FINISHED']
    data=process(env)
    app=AppTest.from_function(board,args=(data,)).run()
    assert '内容整理' in text(app) and '本次未使用' in text(app)
    app=AppTest.from_function(board,args=(data,'AI_REQUEST_STARTED')).run()
    assert '● 正在进行' in text(app)


def test_knowledge_activity_reflects_real_calls(env):
    from executive_health_ai.services.agent_capabilities import project
    from datetime import datetime,timezone
    data=process(env);goal=data['files'][0]['goal']
    assert next(a for a in project(goal) if a.key=='knowledge').used is False
    now=datetime.now(timezone.utc)
    trace=SimpleNamespace(action='capability_activity',metadata_json={'capability':{'task':'retrieve_knowledge','status':'SUCCESS','knowledge_hit_count':2}},started_at=now,completed_at=now,tool_name='',status='COMPLETED')
    actual=next(a for a in project(goal,[trace]) if a.key=='knowledge')
    assert actual.used and actual.status=='SUCCESS' and '2 条' in actual.result


def test_matching_prepares_formal_update_drafts_without_promoting(env):
    from sqlalchemy import select,func
    from executive_health_ai.models import Observation,RiskEvent,MedicationPlan
    data=process(env);s,_,row=env
    assert all(f['goal'].context_json['comparison'] for f in data['files'])
    assert row.responses=={}
    for model in (Observation,RiskEvent,MedicationPlan):assert s.scalar(select(func.count(model.id)))==0


def test_submitted_intake_is_not_reopened_and_auto_upload_still_parses(env):
    s,p,row=env;row.status='SUBMITTED'
    result=workspace.upload(s,p,SimpleNamespace(intake=row,owner='QA'),[('new.txt','睡眠：七小时'.encode())])[0]
    goal=s.get(AgentGoal,UUID(result['goal_id']))
    assert row.status=='SUBMITTED' and not goal.context_json.get('intake_id')
    for _ in range(6):
        if goal.status!='RUNNING':break
        HealthOpsAgentSupervisor().execute_next_step(s,goal.id)
    assert goal.status=='WAITING_MANAGER'
    assert workspace.project(s,p.id,row)['count']>0


def test_new_upload_keeps_previous_processing_visible_and_history_uses_same_instance(env):
    s,p,row=env
    view=SimpleNamespace(intake=row,owner='QA')
    first=workspace.upload(s,p,view,[('one.txt','睡眠：七小时'.encode())])[0]['goal_id']
    second=workspace.upload(s,p,view,[('two.txt','运动：步行'.encode())])[0]['goal_id']
    assert {str(f['goal'].id) for f in workspace.project(s,p.id,row)['files']}=={first,second}
    assert [str(f['goal'].id) for f in workspace.project(s,p.id,row,first)['files']]==[first]


def test_live_redraw_uses_one_board_without_duplicate_element_keys(env):
    data=process(env)
    def live_page(data):
        import streamlit as st
        from executive_health_ai.ui.pages.manager.intake_workspace import draw
        with st.container(key='intake-agent-board'):placeholder=st.empty()
        for event in (None,'CONTENT_READ','AI_REQUEST_STARTED','PREFILL_READY'):
            with placeholder.container():draw(data,event)
    app=AppTest.from_function(live_page,args=(data,)).run()
    assert not app.exception


def test_waiting_doctor_is_explicit_on_foreground_board(env):
    data=process(env)
    data['files'][0]['goal'].status='WAITING_DOCTOR'
    env[0].flush()
    data=workspace.project(env[0],env[1].id,env[2])
    app=AppTest.from_function(board,args=(data,)).run()
    assert '等待医生判断' in text(app)


def test_auto_questionnaire_confirmation_preserves_medical_boundary(env):
    from sqlalchemy import select,func
    from executive_health_ai.models import HealthProblem,MedicationPlan,RiskEvent
    from executive_health_ai.services.profile_ingestion import candidates
    from executive_health_ai.agent.profile_intake import confirm
    s,p,row=env;row.status='SUBMITTED'
    result=workspace.upload(s,p,SimpleNamespace(intake=row,owner='QA'),[
        ('self-report.json',native({'个人病史':[{'疾病或问题':'会员自述，待核对'}]}))])[0]
    goal=s.get(AgentGoal,UUID(result['goal_id']));supervisor=HealthOpsAgentSupervisor()
    for _ in range(6):
        if goal.status!='RUNNING':break
        supervisor.execute_next_step(s,goal.id)
    confirm(supervisor,s,goal,{str(r.id):'采用新资料' for r in candidates(s,goal)},actor='QA',role='HEALTH_MANAGER')
    assert goal.status=='COMPLETED' and row.status=='SUBMITTED'
    assert row.responses['个人病史'][0]['疾病或问题']=='会员自述，待核对'
    for model in (HealthProblem,MedicationPlan,RiskEvent):assert s.scalar(select(func.count(model.id)))==0


def test_existing_formal_archive_confirmation_is_accessible_in_workspace(tmp_path,monkeypatch):
    from executive_health_ai.database import SessionLocal
    from executive_health_ai.models import Patient
    from executive_health_ai.models.management_workflow import IntakeAssessment
    from executive_health_ai.services.member_management_projection import MemberManagementProjection
    from executive_health_ai.services.profile_ingestion import ProfileIngestionService
    monkeypatch.setattr(ProfileIngestionService,'storage_root',tmp_path)
    mid=member();iid=fill(mid)
    with SessionLocal() as session:
        row=session.get(IntakeAssessment,iid);row.status='SUBMITTED'
        patient=session.get(Patient,mid);view=MemberManagementProjection().member(session,mid)
        result=workspace.upload(session,patient,view,[('new.txt','睡眠：七小时'.encode())])[0]
        goal=session.get(AgentGoal,UUID(result['goal_id']))
        for _ in range(6):
            if goal.status!='RUNNING':break
            HealthOpsAgentSupervisor().execute_next_step(session,goal.id)
        session.commit();gid=goal.id
    app=AppTest.from_function(archive_page,args=(str(mid),)).run()
    assert not app.exception
    assert len([b for b in app.button if b.proto.type=='primary'])==1
    button(app,'确认并更新健康档案').click().run()
    assert not app.exception
    assert len([b for b in app.button if b.proto.type=='primary'])==1
    with SessionLocal() as session:
        assert session.get(AgentGoal,gid).status=='COMPLETED'
        assert session.get(IntakeAssessment,iid).status=='SUBMITTED'


def test_auto_upload_keeps_existing_measurement_detection_and_confirmation(env):
    from sqlalchemy import select,func
    from executive_health_ai.models import Observation
    from executive_health_ai.services.profile_ingestion import candidates
    from executive_health_ai.agent.profile_intake import confirm
    s,p,row=env;row.status='SUBMITTED'
    result=workspace.upload(s,p,SimpleNamespace(intake=row,owner='QA'),[
        ('report.txt','体检日期：2026-09-28\n体重 78 kg\nLDL-C 3.8 mmol/L\n'.encode())])[0]
    goal=s.get(AgentGoal,UUID(result['goal_id']));supervisor=HealthOpsAgentSupervisor()
    for _ in range(6):
        if goal.status!='RUNNING':break
        supervisor.execute_next_step(s,goal.id)
    rows=candidates(s,goal)
    assert len(rows)==2 and all(r.candidate_type=='OBSERVATION' for r in rows)
    assert all(r.structured_data_json['source_date']=='2026-09-28' for r in rows)
    assert s.scalar(select(func.count(Observation.id)))==0
    confirm(supervisor,s,goal,{str(r.id):'采用新资料' for r in rows},actor='QA',role='HEALTH_MANAGER')
    assert s.scalar(select(func.count(Observation.id)))==2
