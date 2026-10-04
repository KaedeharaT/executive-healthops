"""Exception-first intake retains real sources and the established medical gates."""
from types import SimpleNamespace
from uuid import UUID
import json
import pytest
from executive_health_ai.models import AgentGoal, Patient
from executive_health_ai.services import intake_exceptions as service
from executive_health_ai.services import intake_workspace as workspace
from executive_health_ai.services.management_workflow import TABLE_FIELDS
from executive_health_ai.ui.pages.manager.intake_workspace import execution_mark
from tests.test_assessment_import import env, upload, native


def responses(name='Synthetic Intake'):
    result={}
    for section,fields in service.CATALOG.items():
        data={field:'原资料明确回答' for field in fields}
        result[section]=[data] if section in TABLE_FIELDS else data
    result['基础资料']={'display_name':name,'birth_date':'1980-01-01','sex':'male'}
    result['专项症状评估'][0]['原始分数']='1'
    return result


def semantic(monkeypatch,facts):
    class Client:
        def generate_structured(self,**kwargs):
            assert kwargs['task']=='parse_health_intake'
            return {'facts':facts}
    monkeypatch.setattr('executive_health_ai.services.intake_extraction.LocalLLMClient',Client)


def test_structured_input_no_unnecessary_llm(env,monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('structured data must not request AI')
    monkeypatch.setattr('executive_health_ai.services.intake_extraction.LocalLLMClient',forbidden)
    view,_=upload(env,[('questionnaire.json',native(responses()))])
    s,p,row=env;data=service.project(s,row)
    assert data['ready'] and not data['queue'] and data['counts']['total']==57
    assert data['counts']['auto_filled']==57
    assert all(not f['run'].llm_used for f in view['files'])
    assert row.responses=={}  # Draft proposals do not silently become confirmed facts.


def test_llm_only_used_for_residual_text_and_source_binding(env,monkeypatch):
    semantic(monkeypatch,[{'section':'生活方式','field':'运动','value':'每周快走三次','evidence':'现在每周快走三次'}])
    view,_=upload(env,[('history.txt','睡眠：七小时\n现在每周快走三次'.encode())])
    rows=[r for g in view['groups'] for r in g['rows']]
    assert {r.extraction_method for r in rows}=={'LLM','FIELD_MAPPING'}
    llm=next(r for r in rows if r.extraction_method=='LLM')
    assert set(('section','field','value','source_document','source_location','source_excerpt','source_date','confidence','status'))<=llm.structured_data_json.keys()
    assert llm.structured_data_json['source_excerpt']=='现在每周快走三次'
    s,p,row=env
    data=service.project(s,row)
    assert not any(q['field']=='运动' for q in data['queue'])
    field=next(f for f in data['fields'] if f['section']=='生活方式' and f['field']=='运动')
    assert field['state']=='AUTO_FILLED' and field['sources']==[llm]
    assert data['answers']['生活方式']['运动']=='每周快走三次'


def test_llm_output_requires_literal_source_evidence(env,monkeypatch):
    semantic(monkeypatch,[{'section':'个人病史','field':'疾病或问题','value':'高血压','evidence':'并不存在的原文'}])
    view,_=upload(env,[('history.txt','睡眠：七小时\n会员正在服用一种药物。'.encode())])
    assert not any(g['section']=='个人病史' for g in view['groups'])
    assert view['files'][0]['warnings']


def test_missing_remains_missing_and_answers_map_to_correct_section(env):
    s,p,row=env
    data=service.project(s,row)
    item=next(q for q in data['queue'] if q['section']=='过敏史')
    assert data['answers'].get('过敏史') is None
    service.decide(s,row,item['key'],'ANSWER','QA',value='暂不清楚')
    updated=service.project(s,row)
    assert updated['answers']['过敏史']==[{'名称':'暂不清楚'}]
    assert updated['counts']['manual_fields']==1
    assert updated['answers'].get('个人病史') is None


def test_historical_change_resolves_latest_dated_source_without_overwriting(env):
    s,p,row=env
    files=[(name,json.dumps({'source_date':date,'responses':{'生活方式':{'烟草':value}}},ensure_ascii=False).encode())
           for name,date,value in [('old.json','2025-01-01','偶尔吸烟'),('new.json','2026-01-01','已戒烟')]]
    upload(env,files)
    data=service.project(s,row)
    assert row.responses=={}
    assert data['answers']['生活方式']['烟草']=='已戒烟'
    assert not any(q['kind']=='CONFLICT' for q in data['queue'])
    assert next(f for f in data['fields'] if f['field']=='烟草')['historical_change']


def test_no_need_to_traverse_11_steps_and_existing_submission_used(env):
    s,p,row=env;data=responses();del data['生活方式']['睡眠'];del data['会员重点关注']['concern']
    upload(env,[('questionnaire.json',native(data))])
    projected=service.project(s,row)
    assert projected['counts']['auto_filled']==55 and projected['counts']['exceptions']==2
    for item in projected['queue']:
        service.decide(s,row,item['key'],'ANSWER','QA',value='七小时' if item['field']=='睡眠' else '改善精力')
    service.complete(s,row,'QA')
    assert row.status=='SUBMITTED' and row.review_status=='READY_FOR_REVIEW'
    assert row.responses['生活方式']['睡眠']=='七小时'
    assert row.responses['会员重点关注']['concern']=='改善精力'
    assert service.state(row)['completion']['manual_fields']==2
    assert all(g.status=='COMPLETED' for g in service.imports.goals(s,row))


def test_optional_unknown_requires_explicit_consent_not_fake_absence(env):
    s,p,row=env;data=responses();del data['生活方式']['休假']
    upload(env,[('questionnaire.json',native(data))])
    assert service.project(s,row)['ready']
    with pytest.raises(ValueError,match='未知'):service.complete(s,row,'QA')
    service.complete(s,row,'QA',retain_unknown=True)
    assert '休假' not in row.responses['生活方式']


@pytest.mark.parametrize('status,visible',[('RUNNING',True),('WAITING_MANAGER',False),('COMPLETED',False),('WAITING_DOCTOR',False),('ESCALATED',False)])
def test_spinner_only_during_real_running(status,visible):
    goal=SimpleNamespace(status=status)
    data=dict(current={'goal':goal} if status=='RUNNING' else None,files=[{'goal':goal}],finished=status=='COMPLETED')
    assert ('intake-spinner' in execution_mark(data)) is visible


def test_no_fake_knowledge_retrieval(env):
    s,p,row=env;view,_=upload(env,[('questionnaire.json',native(responses()))])
    from executive_health_ai.services.agent_capabilities import load
    assert all(not next(a for a in load(s,g)[0] if a.key=='knowledge').used for g in view['goals'])


def test_unresolved_exceptions_or_doctor_gate_block_completion(env):
    s,p,row=env
    with pytest.raises(ValueError):service.complete(s,row,'QA')
    view,_=upload(env,[('questionnaire.json',native(responses()))])
    view['goals'][0].status='WAITING_DOCTOR'
    with pytest.raises(ValueError):service.complete(s,row,'QA')


def test_new_source_invalidates_previous_confirmation(env):
    s,p,row=env
    upload(env,[('a.json',native({'生活方式':{'烟草':'偶尔吸烟'}})),('b.json',native({'生活方式':{'烟草':'已戒烟'}}))])
    item=next(q for q in service.project(s,row)['queue'] if q['kind']=='CONFLICT')
    service.decide(s,row,item['key'],'MODIFY','QA',value='已戒烟',expected_signature=item['signature'])
    upload(env,[('c.json',native({'生活方式':{'烟草':'目前吸烟'}}))])
    assert any(q['kind']=='CONFLICT' for q in service.project(s,row)['queue'])
    with pytest.raises(ValueError,match='来源已变化'):
        service.decide(s,row,item['key'],'CONFIRM','QA',expected_signature=item['signature'])


def test_upload_enables_same_assessment_exception_workspace(env):
    s,p,row=env
    result=workspace.upload(s,p,SimpleNamespace(intake=row,owner='QA'),[('questionnaire.json',native(responses()))])[0]
    goal=s.get(AgentGoal,UUID(result['goal_id']))
    assert goal.context_json['intake_id']==str(row.id)
    assert service.state(row)['enabled']


def test_missing_answer_visible_in_existing_editor(env):
    s,p,row=env;service.enable(row)
    item=next(q for q in service.project(s,row)['queue'] if q['section']=='生活方式' and q['field']=='睡眠')
    service.decide(s,row,item['key'],'ANSWER','QA',value='七小时')
    assert service.imports.form_data(service.imports.project(s,p.id,row.id),'生活方式')['睡眠']=='七小时'


def test_spinner_stops_on_ai_result_and_failure():
    data=dict(current={'goal':SimpleNamespace(status='RUNNING')},files=[],finished=False)
    assert execution_mark(data,'AI_RESULT_CHECKED')=='✓ '
    assert execution_mark(data,'AI_UNAVAILABLE')=='! '


def test_formal_measurement_confirmation_retains_doctor_and_date_gates(env):
    s,p,row=env
    view,_=upload(env,[('report.txt','体检日期：2026-09-28\n体重 78 kg\n'.encode())])
    file=view['files'][0];goal=file['goal']
    goal.status='WAITING_DOCTOR'
    with pytest.raises(ValueError,match='医生'):service.confirm_measurements(s,row,goal.id,'QA',file['signature'])
    goal.status='WAITING_MANAGER'
    assert service.confirm_measurements(s,row,goal.id,'QA',file['signature'])==1
    with pytest.raises(ValueError):service.confirm_measurements(s,row,goal.id,'QA',file['signature'])


def test_measurement_without_date_not_promoted(env):
    s,p,row=env;view,_=upload(env,[('report.txt','体重 78 kg\n'.encode())]);file=view['files'][0]
    with pytest.raises(ValueError):service.confirm_measurements(s,row,file['goal'].id,'QA',file['signature'])


def test_upload_from_detached_member360_projection_persists_mode(env):
    from executive_health_ai.models.management_workflow import IntakeAssessment
    s,p,row=env;row_id=row.id;s.expunge(row)
    workspace.upload(s,p,SimpleNamespace(intake=row,owner='QA'),[('questionnaire.json',native(responses()))])
    s.flush()
    assert s.get(IntakeAssessment,row_id).review['exception_intake']['enabled']


def test_existing_multi_file_draft_uses_queue_without_reupload(env):
    s,p,row=env;upload(env,[('questionnaire.json',native(responses()))])
    assert 'exception_intake' not in row.review
    assert service.state(row)['enabled']
    assert workspace.project(s,p.id,row)['exceptions']['ready']


def test_member360_exception_queue_answers_and_submits_without_wizard(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from executive_health_ai.database import SessionLocal
    from executive_health_ai.models.management_workflow import IntakeAssessment
    from executive_health_ai.services.management_workflow import ManagementWorkflowService
    from executive_health_ai.services.profile_ingestion import ProfileIngestionService
    from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
    from tests.test_intake_entry import member,archive_page,button
    monkeypatch.setattr(ProfileIngestionService,'storage_root',tmp_path)
    member_id=member()
    with SessionLocal() as session:
        patient=session.get(Patient,member_id)
        row=ManagementWorkflowService().start_intake(session,member_id,2026,'QA')
        data=responses(patient.display_name);data['会员重点关注']={}
        result=workspace.upload(session,patient,SimpleNamespace(intake=row,owner='QA'),[('questionnaire.json',native(data))])[0]
        goal=session.get(AgentGoal,UUID(result['goal_id']))
        for _ in range(6):
            if goal.status!='RUNNING':break
            HealthOpsAgentSupervisor().execute_next_step(session,goal.id)
        session.commit();row_id=row.id
    app=AppTest.from_function(archive_page,args=(str(member_id),)).run()
    assert not app.exception
    button(app,'处理剩余事项（1项）').click().run()
    next(w for w in app.text_input if w.label=='填写会员实际回答').set_value('改善睡眠')
    button(app,'保存答案并处理下一项').click().run()
    assert not app.exception
    assert not any(w.label=='填写步骤' for w in app.selectbox)
    next(w for w in app.checkbox if w.label=='确认整理结果及已处理例外；可暂缺资料继续保持未知').check().run()
    button(app,'确认完成初始健康评估').click().run()
    assert not app.exception
    with SessionLocal() as session:
        row=session.get(IntakeAssessment,row_id)
        assert row.status=='SUBMITTED' and row.responses['会员重点关注']['concern']=='改善睡眠'
