"""Real persistence and human gates for the document intake policy."""
import json
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from executive_health_ai.models import Patient, Observation, AgentGoal, AgentApprovalRequest, AgentRunTrace, RiskEvent, MedicationPlan, HealthProblem, DoctorReview
from executive_health_ai.models.base import Base
from executive_health_ai.models.management_workflow import IntakeAssessment
from executive_health_ai.services.profile_ingestion import ProfileIngestionService, candidates, confirmed_profile
from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
from executive_health_ai.agent import profile_intake as flow
from executive_health_ai.services.product_projection import ProductProjectionService


@pytest.fixture
def env(tmp_path,monkeypatch):
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    monkeypatch.setattr(ProfileIngestionService,'storage_root',tmp_path)
    monkeypatch.setenv('LOCAL_LLM_ENABLED','false')
    with Session(engine,expire_on_commit=False) as s:
        p=Patient(display_name='Synthetic Import Member',timezone='Asia/Tokyo');s.add(p);s.flush()
        yield s,p,HealthOpsAgentSupervisor()


def upload(env,dtype='questionnaire',responses=None,at='2026-09-25'):
    s,p,supervisor=env
    payload={'source_date':at,'responses':responses or {'生活方式':{'烟草':'无','睡眠':'每天七小时'},'过敏史':[{'名称':'花粉','来源':'会员自述'}]}}
    goal,_=ProfileIngestionService().upload(s,p.id,'问卷.json',json.dumps(payload,ensure_ascii=False).encode(),dtype,actor='王健管',role='HEALTH_MANAGER')
    return goal


def run(env,goal):
    for _ in range(5):
        if goal.status!='RUNNING':break
        env[2].execute_next_step(env[0],goal.id)
    assert goal.status=='WAITING_MANAGER',goal.next_action


def approve(env,goal,choice='采用新资料'):
    return flow.confirm(env[2],env[0],goal,{str(r.id):choice for r in candidates(env[0],goal)},actor='王健管',role='HEALTH_MANAGER')


def test_questionnaire_draft_approval_shared_archive_and_today(env):
    s,p,_=env;goal=upload(env);run(env,goal)
    assert goal.context_json['source_date']=='2026-09-25'
    assert s.scalar(select(AgentRunTrace).where(AgentRunTrace.goal_id==goal.id,AgentRunTrace.tool_name=='parse_profile_document'))
    assert not confirmed_profile(s,p.id)
    intake=s.scalar(select(IntakeAssessment));assert intake.status=='DRAFT' and intake.responses['生活方式']['烟草']=='无'
    assert len(s.scalars(select(AgentApprovalRequest)).all())==1
    assert any(i.source_id==goal.id for i in ProductProjectionService().manager(s,datetime.now(timezone.utc)).items)
    approve(env,goal)
    assert goal.status=='COMPLETED' and len(confirmed_profile(s,p.id))==4
    assert s.scalar(select(func.count(RiskEvent.id)))==0
    assert s.scalar(select(func.count(HealthProblem.id)))==0
    assert s.scalar(select(func.count(MedicationPlan.id)))==0
    assert all(r.reviewed_by=='王健管' and r.structured_data_json['source_document_id'] for r in candidates(s,goal))
    assert not any(i.source_id==goal.id for i in ProductProjectionService().manager(s,datetime.now(timezone.utc)).items)


def test_duplicate_file_and_approval_idempotent(env):
    s,p,_=env;goal=upload(env);same=upload(env);assert same.id==goal.id
    run(env,goal);approve(env,goal);approve(env,goal)
    assert s.scalar(select(func.count(AgentGoal.id)))==1
    assert len(confirmed_profile(s,p.id))==4


def test_history_keeps_medication_as_reported_not_prescribed(env):
    s,p,_=env;goal=upload(env,'history',{'个人病史':[{'疾病或问题':'既往脂肪肝'}],
        '当前用药 / 营养补充':[{'名称':'既往记录药物','剂量':'5','单位':'mg'}],
        '手术 / 住院史':[{'名称':'既往手术记录','日期':'2020-01-02','类型':'手术'}]})
    run(env,goal)
    assert s.scalar(select(func.count(HealthProblem.id)))==0
    approve(env,goal)
    assert s.scalar(select(func.count(HealthProblem.id)))==1
    assert s.scalar(select(func.count(MedicationPlan.id)))==0
    assert any(x['已确认内容']=='既往记录药物' for x in confirmed_profile(s,p.id))


def test_conflict_is_not_overwritten_and_temporal_change(env):
    s,p,_=env;first=upload(env,responses={'生活方式':{'烟草':'无'}});run(env,first);approve(env,first)
    second=upload(env,responses={'生活方式':{'烟草':'偶尔'}});run(env,second)
    assert next(iter(second.context_json['comparison'].values()))[0]=='冲突'
    approve(env,second,'暂不确认')
    assert s.scalar(select(IntakeAssessment)).responses['生活方式']['烟草']=='无'
    assert second.context_json['output']['deferred']==1
    third=upload(env,responses={'生活方式':{'烟草':'已戒烟'}},at='2026-09-26');run(env,third)
    assert next(iter(third.context_json['comparison'].values()))[0]=='更新'
    approve(env,third)
    assert s.scalar(select(IntakeAssessment)).responses['生活方式']['烟草']=='已戒烟'


def test_report_observation_and_no_automatic_diagnosis(env):
    s,p,supervisor=env
    content='体检日期：2026-09-25\n体重 85.8 kg\nLDL-C 3.8 mmol/L\n'
    goal,_=ProfileIngestionService().upload(s,p.id,'体检.txt',content.encode(),'report',actor='王健管',role='HEALTH_MANAGER')
    run(env,goal)
    assert s.scalar(select(func.count(Observation.id)))==0
    approve(env,goal)
    assert s.scalar(select(func.count(Observation.id)))>=1
    assert s.scalar(select(func.count(HealthProblem.id)))==0
    assert goal.context_json['output']['measurements']>=1


def test_doctor_gate_resume_original_goal(env):
    s,p,supervisor=env;goal=upload(env);run(env,goal)
    review=flow.request_doctor(s,goal,question='历史用药是否需要进一步核对？',actor='王健管',role='HEALTH_MANAGER')
    assert goal.status=='WAITING_DOCTOR'
    with pytest.raises(ValueError):approve(env,goal)
    review.status='CONFIRMED';review.opinion='仅核对历史资料';s.flush()
    supervisor.publish_and_receive(s,event_type='DOCTOR_REVIEW_COMPLETED',member_id=p.id,source_type='doctor_review',source_id=review.id)
    assert goal.status=='WAITING_MANAGER'
    approve(env,goal);assert goal.status=='COMPLETED'
    assert s.scalar(select(func.count(AgentGoal.id)))==1


def test_unavailable_and_parse_failure_preserve_file(env):
    s,p,sup=env
    goal,_=ProfileIngestionService().upload(s,p.id,'外部档案.txt','不能确定字段的自由文本。'.encode(),'history',actor='王健管',role='HEALTH_MANAGER')
    for _ in range(3):sup.execute_next_step(s,goal.id)
    assert goal.status=='ESCALATED' and '智能整理暂不可用' in goal.next_action
    assert s.scalar(select(func.count(Observation.id)))==0
    with pytest.raises(ValueError):sup.complete_goal(s,goal.id)
    with pytest.raises(ValueError):sup.resume_goal(s,goal.id)
    broken,_=ProfileIngestionService().upload(s,p.id,'损坏.pdf',b'%PDF-1.4\nbroken document','report',actor='王健管',role='HEALTH_MANAGER')
    for _ in range(3):sup.execute_next_step(s,broken.id)
    assert broken.status=='ESCALATED' and '原文件已保存' in broken.next_action
    assert not candidates(s,broken)
    assert s.scalar(select(AgentRunTrace).where(AgentRunTrace.goal_id==broken.id,AgentRunTrace.action=='profile_exception')).status=='FAILED'
    for invalid in ([],{'responses':[]}):
        malformed,_=ProfileIngestionService().upload(s,p.id,'格式不符.json',json.dumps(invalid).encode(),'questionnaire',actor='王健管',role='HEALTH_MANAGER')
        for _ in range(3):sup.execute_next_step(s,malformed.id)
        assert malformed.status=='ESCALATED' and not candidates(s,malformed)


def test_permission_boundary(env):
    s,p,sup=env;goal=upload(env);run(env,goal)
    with pytest.raises(PermissionError):flow.confirm(sup,s,goal,{},actor='member',role='MEMBER')
    with pytest.raises(PermissionError):sup.registry.execute(s,'approve_profile_document',goal,{},approved_role='HEALTH_MANAGER')
    with pytest.raises(PermissionError):sup.registry.execute(s,'evaluate_confirmed_observations',goal)


def test_llm_must_quote_exact_source(env):
    s,p,_=env
    goal,_=ProfileIngestionService().upload(s,p.id,'外部问卷.txt','本人说：每天睡眠七小时。'.encode(),'questionnaire',actor='王健管',role='HEALTH_MANAGER')
    class Client:
        def generate_structured(self,**kw):
            return {'document_type':'questionnaire','facts':[{'section':'生活方式','field':'睡眠','value':'每天睡眠七小时','evidence':'本人说：每天睡眠七小时。'}]}
    assert ProfileIngestionService().parse(s,goal,Client())['count']==1
    bad=upload(env,responses={'生活方式':{'运动':'走路'}})
    # Native mappings do not consult an LLM and preserve self-report source.
    ProfileIngestionService().parse(s,bad)
    assert candidates(s,bad)[0].structured_data_json['source_type']=='会员自述'


def test_fabricated_llm_fact_rejected(env):
    s,p,_=env
    goal,_=ProfileIngestionService().upload(s,p.id,'记录.txt','只有睡眠描述，无任何诊断。'.encode(),'history',actor='王健管',role='HEALTH_MANAGER')
    class Client:
        def generate_structured(self,**kw):
            return {'document_type':'history','facts':[{'section':'个人病史','field':'疾病或问题','value':'高脂血症','evidence':'只有睡眠描述，无任何诊断。'}]}
    with pytest.raises(ValueError,match='逐字核实'):ProfileIngestionService().parse(s,goal,Client())
    assert s.scalar(select(func.count(HealthProblem.id)))==0


def test_image_failure_and_retry_never_guesses(env):
    s,p,sup=env
    image=b'\x89PNG\r\n\x1a\n'+b'\0'*50
    goal,_=ProfileIngestionService().upload(s,p.id,'扫描.png',image,'report',actor='王健管',role='HEALTH_MANAGER')
    for _ in range(3):sup.execute_next_step(s,goal.id)
    assert goal.status=='ESCALATED'
    assert not candidates(s,goal)
    flow.retry(s,goal,actor='王健管',role='HEALTH_MANAGER')
    assert goal.status=='RUNNING'


@pytest.mark.parametrize('line',['体重：85.7','体重：85.7 unknown','体重：85.7 kg'])
def test_missing_date_or_unit_cannot_be_confirmed(env,line):
    s,p,sup=env
    goal,_=ProfileIngestionService().upload(s,p.id,'缺少日期.txt',line.encode(),'report',actor='王健管',role='HEALTH_MANAGER')
    run(env,goal)
    assert all(v[0]=='无法确认' for v in goal.context_json['comparison'].values())
    with pytest.raises(ValueError):approve(env,goal)
    assert s.scalar(select(func.count(Observation.id)))==0


def test_new_document_same_measurement_is_not_written_twice(env):
    s,p,sup=env
    for title,extra in [('一.txt',''),('二.txt','\n机构：合成医院')]:
        goal,_=ProfileIngestionService().upload(s,p.id,title,('体检日期：2026-09-27\n体重：85.7 kg'+extra).encode(),'report',actor='王健管',role='HEALTH_MANAGER')
        run(env,goal);approve(env,goal)
    assert s.scalar(select(func.count(Observation.id)))==1
    assert s.scalar(select(func.count(AgentGoal.id)).where(AgentGoal.goal_type=='PROFILE_INTAKE'))==2
    # The first confirmed report now hands off to the existing post-checkup
    # policy. Duplicate measurements still produce neither a second fact nor
    # another post-checkup goal.
    assert s.scalar(select(func.count(AgentGoal.id)).where(AgentGoal.goal_type=='POST_CHECKUP_MANAGEMENT'))==1


def test_real_doctor_command_resumes_without_extra_workflow(env):
    from executive_health_ai.services.care_commands import complete_review
    s,p,sup=env;goal=upload(env);run(env,goal)
    review=flow.request_doctor(s,goal,question='核对历史医疗资料含义',actor='王健管',role='HEALTH_MANAGER')
    complete_review(s,review,'合成医生','全科','已核对原始记录','仅记录既往情况',datetime.now(timezone.utc))
    assert goal.status=='WAITING_MANAGER' and review.status=='CONFIRMED'
    approve(env,goal)
    assert goal.status=='COMPLETED'


def test_preserve_current_conflict_and_audited_routes(env):
    s,p,sup=env;first=upload(env,responses={'生活方式':{'烟草':'无'}});run(env,first);approve(env,first)
    second=upload(env,responses={'生活方式':{'烟草':'偶尔吸烟'}});run(env,second);approve(env,second,'保留当前记录')
    assert confirmed_profile(s,p.id)[0]['已确认内容']=='无'
    routes=s.scalars(select(AgentRunTrace).where(AgentRunTrace.goal_id==second.id,AgentRunTrace.action=='responsibility_routed')).all()
    assert routes and all(r.metadata_json['responsibility']['evidence_refs'] for r in routes)


def test_updated_observation_reaches_existing_trend_projection(env):
    from executive_health_ai.services.health_visualization import HealthVisualizationService
    s,p,sup=env
    for at,value in [('2026-09-20','85.9'),('2026-09-27','85.7')]:
        goal,_=ProfileIngestionService().upload(s,p.id,at+'.txt',f'体检日期：{at}\n体重：{value} kg'.encode(),'report',actor='王健管',role='HEALTH_MANAGER')
        run(env,goal);approve(env,goal)
    health=HealthVisualizationService().build(s,p.id)
    assert any(len(x.points)==2 for x in health)


def test_negative_allergy_requires_choice_and_preserves_prior_evidence(env):
    s,p,sup=env;first=upload(env,responses={'过敏史':[{'名称':'青霉素'}]});run(env,first);approve(env,first)
    second=upload(env,responses={'过敏史':[{'名称':'无'}]});run(env,second)
    assert next(iter(second.context_json['comparison'].values()))[0]=='冲突'
    approve(env,second)
    current=s.scalar(select(IntakeAssessment)).responses['过敏史']
    assert current==[{'名称':'无'}]
    assert candidates(s,second)[0].structured_data_json['previous_record']==[{'名称':'青霉素'}]
    assert candidates(s,first)[0].status=='CONFIRMED'


def test_same_dose_for_different_medications_is_not_wrongly_deduplicated(env):
    s,p,sup=env
    for name in ('历史药品甲','历史药品乙'):
        goal=upload(env,'history',{'当前用药 / 营养补充':[{'名称':name,'剂量':'5','单位':'mg'}]})
        run(env,goal);approve(env,goal)
    current=s.scalar(select(IntakeAssessment)).responses['当前用药 / 营养补充']
    assert len(current)==2 and all(r['剂量']=='5' and r['单位']=='mg' for r in current)


def test_foreign_extraction_record_is_rejected(env):
    s,p,sup=env;goal=upload(env)
    other=Patient(display_name='Different Synthetic Member',timezone='Asia/Tokyo');s.add(other);s.flush()
    foreign=upload((s,other,sup))
    goal.context_json={**goal.context_json,'run_id':foreign.context_json['run_id']}
    with pytest.raises(ValueError,match='不属于'):candidates(s,goal)
