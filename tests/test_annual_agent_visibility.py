import json
from datetime import date, timedelta
from types import SimpleNamespace as R
from uuid import UUID, uuid4
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from test_post_checkup_care_v1 import care, send_doctor, judge
from test_profile_intake import env, upload, run
from executive_health_ai.agent import post_checkup as flow
from executive_health_ai.llm.local_llm_client import LocalLLMClient, LocalLLMSettings
from executive_health_ai.llm.activity import collect_calls
from executive_health_ai.models import AgentRunTrace, RiskEvent, HealthAssessment, Patient, Task
from executive_health_ai.services import annual_portfolio as annual
from executive_health_ai.services.agent_capabilities import project, load, technical_rows, capabilities
from executive_health_ai.services.profile_ingestion import ProfileIngestionService
from executive_health_ai.services.knowledge import KnowledgeService
from executive_health_ai.services.management_workflow import ManagementWorkflowService
from executive_health_ai.services.product_projection import ProductProjectionService


def client(payload, enabled=True):
    settings=LocalLLMSettings(enabled,'local','http://127.0.0.1:11434','unit-test',1,3000)
    response=R(raise_for_status=lambda:None,json=lambda:{'message':{'content':json.dumps(payload,ensure_ascii=False)}})
    return LocalLLMClient(settings,http_post=Mock(return_value=response))


def test_context_alone_never_invents_ai_or_knowledge():
    goal=R(context_json={'llm_status':'AVAILABLE','knowledge':[{'title':'invented'}], 'summary':'invented'},status='WAITING_MANAGER')
    assert all(a.status == 'PENDING' and not a.used and not a.citations for a in project(goal))


def test_zero_knowledge_hits_are_successful_empty_retrieval(care):
    session,goal,_=care
    support,_=load(session,goal)
    activity=next(a for a in support if a.key=='knowledge')
    assert activity.status=='SUCCESS' and not activity.citations and '暂无匹配' in activity.result


def test_disabled_llm_has_no_fake_network_or_success(care):
    session,goal,_=care
    support,traces=load(session,goal)
    activity=next(a for a in support if a.key=='summary')
    assert activity.status=='UNAVAILABLE' and not activity.used and '规则' in activity.result
    assert dict(capabilities(goal,support,traces))['AI']=='unused'
    assert any(row['请求已发出'] is False for row in technical_rows(traces) if row['类型']=='LLM')


def test_real_retrieval_contains_only_approved_exact_sources(care):
    session,goal,supervisor=care
    ks=KnowledgeService()
    for approved,title in [(True,'体重资料核对规范'),(False,'体重未审核资料')]:
        document=ks.create_document(session,title=title,category='PATIENT_EDUCATION',source_type='INTERNAL',
            source_name='Synthetic test source',content_text='体重记录核对原始资料与单位。',version='v-test')
        if approved:ks.approve_document(session,document,'Test reviewer')
    flow.analyze(supervisor,session,goal)
    activity=next(a for a in load(session,goal)[0] if a.key=='knowledge')
    assert activity.status=='SUCCESS'
    assert [c['title'] for c in activity.citations]==['体重资料核对规范']
    assert activity.citations[0]['version']=='v-test'


def test_llm_success_audited_without_prompts_or_reasoning_or_medical_risk(care,monkeypatch):
    session,goal,supervisor=care
    actual=client({'summary':'请健管核对本次报告资料与变化。','risk':'RED','chain_of_thought':'SECRET_THINKING','prompt':'SECRET_PROMPT'})
    monkeypatch.setattr(flow,'LocalLLMClient',lambda:actual)
    flow.analyze(supervisor,session,goal)
    support,traces=load(session,goal)
    assert next(a for a in support if a.key=='summary').status=='SUCCESS'
    payload=json.dumps([t.metadata_json for t in traces],ensure_ascii=False)
    assert 'SECRET_' not in payload and 'chain_of_thought' not in payload
    assert 'SECRET_' not in json.dumps(goal.context_json,ensure_ascii=False)
    assert not session.query(RiskEvent).count()
    assert actual._http_post.call_count==1
    assert any(r['请求已发出'] is True and isinstance(r['耗时 ms'],int) for r in technical_rows(traces) if r['类型']=='LLM')


def test_rejected_ai_summary_is_not_completed(care,monkeypatch):
    session,goal,supervisor=care
    monkeypatch.setattr(flow,'LocalLLMClient',lambda:client({'summary':'诊断为某疾病，需要处方'}))
    flow.analyze(supervisor,session,goal)
    activity=next(a for a in load(session,goal)[0] if a.key=='summary')
    assert activity.status=='UNUSABLE' and activity.mark!='✓'
    assert not session.query(RiskEvent).count()


def test_reasoning_embedded_in_summary_is_not_exposed(care,monkeypatch):
    session,goal,supervisor=care
    monkeypatch.setattr(flow,'LocalLLMClient',lambda:client({'summary':'<think>PRIVATE_THOUGHT</think>摘要'}))
    flow.analyze(supervisor,session,goal)
    assert next(a for a in load(session,goal)[0] if a.key=='summary').status=='UNUSABLE'
    assert 'PRIVATE_THOUGHT' not in json.dumps(goal.context_json,ensure_ascii=False)
    assert 'PRIVATE_THOUGHT' not in json.dumps([t.result_summary for t in load(session,goal)[1]])


def test_original_ai_draft_remains_distinct_from_manager_edit(care,monkeypatch):
    session,goal,supervisor=care
    monkeypatch.setattr(flow,'LocalLLMClient',lambda:client({'summary':'核对本次体重资料。'}))
    flow.analyze(supervisor,session,goal)
    flow.manager_review(supervisor,session,goal,actor='王健管',role='HEALTH_MANAGER',summary='人工核对后补充记录。')
    assert goal.context_json['summary']=='人工核对后补充记录。'
    assert goal.context_json['ai_summary_draft']=='核对本次体重资料。'


def test_doctor_return_llm_reflects_actual_quote_only(care,monkeypatch):
    session,goal,supervisor=care
    assert next(a for a in load(session,goal)[0] if a.key=='doctor').status=='PENDING'
    send_doctor(session,goal,supervisor)
    actual=client({'quote':'了解饮酒情况','kind':'PRESCRIPTION','date':'1900-01-01'})
    monkeypatch.setattr(flow,'LocalLLMClient',lambda:actual)
    judge(session,goal)
    activity=next(a for a in load(session,goal)[0] if a.key=='doctor')
    assert activity.status=='SUCCESS' and actual._http_post.call_count==1
    follow=goal.context_json['actions'][1]
    assert follow['title']=='随访：了解饮酒情况' and follow['kind']=='FOLLOWUP'
    assert follow['due']==(date.today()+timedelta(days=30)).isoformat()
    assert goal.status=='WAITING_MANAGER' and not session.query(Task).count()
    assert not session.query(RiskEvent).count()


def test_doctor_failed_llm_not_marked_complete(care):
    session,goal,supervisor=care
    send_doctor(session,goal,supervisor);judge(session,goal)
    activity=next(a for a in load(session,goal)[0] if a.key=='doctor')
    assert activity.status=='UNAVAILABLE' and activity.mark=='△'
    assert goal.context_json['actions'][1]['title']=='跟进医生建议执行情况'


def test_structured_questionnaire_does_not_call_llm_or_knowledge(env,monkeypatch):
    monkeypatch.setattr(LocalLLMClient,'generate_structured',Mock(side_effect=AssertionError('Must not call model')))
    goal=upload(env);run(env,goal)
    support,traces=load(env[0],goal)
    assert next(a for a in support if a.key=='semantic').status=='NOT_USED'
    assert next(a for a in support if a.key=='knowledge').status=='NOT_USED'
    assert not any(r['类型'] in {'LLM','KNOWLEDGE'} for r in technical_rows(traces))


def test_free_text_semantic_call_is_real_and_safe(env):
    session,member,_=env
    prose='最近我每天睡眠六小时，希望改善白天精力。'
    goal,_=ProfileIngestionService().upload(session,member.id,'prose.txt',prose.encode(),'questionnaire',actor='王健管',role='HEALTH_MANAGER')
    actual=client({'document_type':'questionnaire','facts':[{'section':'生活方式','field':'睡眠','value':'六小时','evidence':prose}]})
    ProfileIngestionService().parse(session,goal,client=actual)
    support,traces=load(session,goal)
    activity=next(a for a in support if a.key=='semantic')
    assert activity.status=='SUCCESS' and activity.used and '1 项' in activity.result
    assert next(a for a in support if a.key=='knowledge').status=='NOT_USED'
    assert actual._http_post.call_count==1
    assert prose not in json.dumps([t.metadata_json for t in traces],ensure_ascii=False)


def test_free_text_disabled_call_goes_to_manual_not_success(env):
    session,member,supervisor=env
    goal,_=ProfileIngestionService().upload(session,member.id,'prose.txt','最近我每天睡眠六小时，希望改善白天精力。'.encode(),'questionnaire',actor='王健管',role='HEALTH_MANAGER')
    supervisor.execute_next_step(session,goal.id)
    supervisor.execute_next_step(session,goal.id)
    assert goal.status=='ESCALATED'
    assert next(a for a in load(session,goal)[0] if a.key=='semantic').status=='UNAVAILABLE'


def test_unrelated_llm_calls_are_not_captured():
    actual=client({'value':1})
    with collect_calls() as calls:
        pass
    actual.generate_structured(task='other',system_prompt='PRIVATE',user_prompt='PRIVATE',document_id='test',page=0)
    assert calls==[]


def test_multi_section_report_records_each_validated_result_without_double_counting(care,monkeypatch):
    from executive_health_ai.llm.local_llm_client import LocalLLMHealth
    from executive_health_ai.services.report_parsing import ReportSemanticFallback, ExtractedPage
    from executive_health_ai.agent.activity_audit import llm_calls
    session,goal,_=care
    actual=client({'exam_name':'胸部CT','findings':[{'summary':'左肺小结节','body_system':'肺','reported_change':'小结节',
        'reported_severity':'','evidence':'左肺见小结节'}],'recommendations':[]})
    monkeypatch.setattr(actual,'health_check',lambda:LocalLLMHealth(True,True,'local','unit-test','http://127.0.0.1:11434'))
    with collect_calls() as calls:
        result=ReportSemanticFallback(actual).extract(document_id=uuid4(),existing=[],pages=[
            ExtractedPage(1,'胸部CT影像描述：左肺见小结节，双肺未见其他明显异常。建议一年后复查胸部CT，以便持续观察。'),
            ExtractedPage(2,'腹部彩超检查结论：肝脏回声增粗，胆囊及胰腺未见明显异常。请保留原报告供医生核对。')])
    assert len(calls)==2 and [c['result_count'] for c in calls]==[1,0]
    assert len(result.drafts)==1
    llm_calls(session,goal,calls,accepted=True,sources=['本次上传资料原文'],operation_id='latest-parse')
    traces=load(session,goal)[1]
    profile=R(goal_type='PROFILE_INTAKE',context_json={},status='WAITING_MANAGER')
    run=R(status='COMPLETED',candidate_count=1,llm_status='USED',metadata_json={'semantic_candidate_count':1})
    activity=next(a for a in project(profile,traces,run) if a.key=='semantic')
    assert activity.status=='SUCCESS' and '1 项' in activity.result and '另有 1 次' in activity.result
    actual_rows=[r for r in technical_rows(traces) if r['任务']=='report_semantic_fallback']
    assert [r['状态'] for r in actual_rows]==['SUCCESS','UNUSABLE']


def annual_view(**changes):
    today=date.today()
    program=R(id=uuid4(),cycle_year=today.year,start_date=today-timedelta(days=20),end_date=today+timedelta(days=100),
              status='ACTIVE',main_goal='年度目标')
    phase=R(id=uuid4(),sequence=1,start_date=program.start_date,end_date=today+timedelta(days=40),status='ACTIVE')
    values=dict(program=program,current_phase=phase,milestones=(('健康基线',True),),reviews=(),tasks=(),rechecks=(),services=(),doctor_reviews=(),consultations=(),phases=(),owner='王健管')
    values.update(changes)
    return R(**values)


def test_annual_portfolio_tracks_recorded_progress_not_elapsed_time():
    view=annual_view()
    view.tasks=tuple(R(program_id=view.program.id,status=state,due_at=R(date=lambda:date.today())) for state in ['COMPLETED','PENDING','PENDING','PENDING'])
    row=annual.project(R(id=uuid4()),view)
    assert row.stage=='持续管理' and row.progress=='25% · 事项 1/4' and row.open_count==3


def test_annual_filters_use_year_phase_owner_due_doctor_review():
    view=annual_view()
    view.current_phase.end_date=date.today()-timedelta(days=1)
    view.doctor_reviews=(R(status='PENDING'),)
    row=annual.project(R(id=uuid4(),display_name='合成会员'),view)
    assert row.stage=='阶段复盘' and row.overdue and row.waiting=='等待医生'
    assert annual.filter_rows([row],year=str(date.today().year),stage='阶段复盘',owner='王健管',overdue='是',doctor='是',review='是')==[row]
    assert annual.filter_rows([row],doctor='否')==[]
    assert dict(annual.summary([row]))['逾期 / 异常']==1


def test_annual_baseline_and_annual_review_are_distinct():
    member=R(id=uuid4())
    baseline=annual.project(member,annual_view(milestones=(('健康基线',False),)))
    view=annual_view();view.program.end_date=date.today()+timedelta(days=7)
    final=annual.project(member,view)
    assert baseline.stage=='建立基线' and final.stage=='年度复盘'
    assert baseline.progress=='0% · 入组 0/1'
    no_phase=annual.project(member,annual_view(current_phase=None,milestones=(('健康基线',False),)))
    assert no_phase.phase_end is None  # A cycle end date is not a configured phase deadline.


def test_annual_click_management_and_member_click_overview(monkeypatch):
    import streamlit as st
    from executive_health_ai.ui.pages.manager.annual import open_member
    from executive_health_ai.ui.pages.manager.workbench import open_directory_member
    state={};monkeypatch.setattr(st,'session_state',state)
    app=Mock();member=R(id=uuid4());row=R(member=member,id=uuid4())
    open_member(app,row)
    app._open_member_management.assert_called_once_with(member.id)
    assert state['member-return-origin']=='年度管理'
    assert state[f'annual-program-{member.id}']==str(row.id)
    open_directory_member(app,member)
    app.request_navigation.assert_called_once_with(ops_page='成员',member_id=member.id,member_section='概览',rerun=False)
    assert state['member-return-origin']=='会员'


def test_annual_history_drills_into_same_member360_cycle(care):
    session,goal,_=care
    last_year=date.today().year-1
    program=ManagementWorkflowService().enroll(session,name='Existing member',member_id=goal.member_id,
        start=date(last_year,1,1),end=date(last_year,12,31),owner='历史健管',goal='历史年度目标')
    session.flush()
    row=next(r for r in annual.load(session) if r.id==program.id)
    assert row.year==last_year
    view=ProductProjectionService().member(session,goal.member_id,program_id=row.id)
    assert view.program.id==program.id and view.cycle.startswith(str(last_year))
    stranger=Patient(display_name='Other',timezone='UTC');session.add(stranger);session.flush()
    with pytest.raises(ValueError,match='不属于'):
        ProductProjectionService().member(session,stranger.id,program_id=row.id)
