"""Business-state partition, exception compression and durable same-goal resume."""
import json
from datetime import date
import pytest
from sqlalchemy import select
from executive_health_ai.models import Patient,MemberAgent,HealthEvent,AgentRunTrace,AgentGoal
from executive_health_ai.services import intake_exceptions as service
from executive_health_ai.services.intake_requirement_policy import IntakeRequirementPolicy
from tests.test_assessment_import import env,upload,native
from tests.test_intake_exceptions import responses,semantic


def partition(data):
    c=data['counts']
    assert c['total']==sum(c[k] for k in ('auto_filled','pending','conflicts','required_missing','optional_missing','not_applicable'))
    assert c['exceptions']==c['pending']+c['conflicts']+c['required_missing']+c['doctor_required']
    keys=[(f['section'],f['identity'],f['field']) for f in data['fields']]
    assert len(keys)==len(set(keys))
    assert len(data['queue'])==len({q['key'] for q in data['queue']})
    assert all(q['state'] in {'NEEDS_CONFIRMATION','CONFLICT','REQUIRED_MISSING','DOCTOR_REQUIRED'} for q in data['queue'])


def test_optional_missing_not_human_work_required_missing_is(env):
    s,p,row=env
    data=service.project(s,row);partition(data)
    assert next(f for f in data['fields'] if f['field']=='空气污染')['state']=='OPTIONAL_MISSING'
    assert not any(q['section']=='环境与暴露' for q in data['queue'])
    assert next(q for q in data['queue'] if q['field']=='睡眠')['state']=='REQUIRED_MISSING'
    assert not data['answers'].get('过敏史')  # missing never means no allergy


@pytest.mark.parametrize('section,record,field,expected',[
 ('手术 / 住院史',{'名称':'无手术史'},'日期','NOT_APPLICABLE'),
 ('手术 / 住院史',{'名称':'阑尾切除术','持续随访':'否'},'随访内容','NOT_APPLICABLE'),
 ('手术 / 住院史',{'名称':'阑尾切除术','持续随访':'是'},'随访内容','REQUIRED'),
 ('家族健康史',{'具体疾病':'糖尿病'},'患病家属','REQUIRED'),
 ('个人病史',{'疾病或问题':'某疾病','是否存在':'否'},'确诊时间','NOT_APPLICABLE'),
 ('手术 / 住院史',{},'名称','OPTIONAL')])
def test_conditional_requirements(section,record,field,expected):
    assert IntakeRequirementPolicy().requirement(section,field,record)==expected


def test_negative_parent_collapses_details_without_fabricating_answers(env):
    s,p,row=env
    upload(env,[('history.json',native({'手术 / 住院史':[{'名称':'无手术史'}]}))])
    data=service.project(s,row);partition(data)
    assert data['counts']['not_applicable']==5
    assert data['answers']['手术 / 住院史']==[{'名称':'无手术史'}]
    assert not any(q['section']=='手术 / 住院史' for q in data['queue'])


def test_auto_confirm_and_conflict_unique_states(env):
    s,p,row=env
    upload(env,[('a.json',native({'生活方式':{'睡眠':'七小时','烟草':'偶尔吸烟','运动':'每周快走'}})),
                ('b.json',native({'生活方式':{'烟草':'已戒烟'}}))])
    candidate=next(r for g in service.imports.project(s,p.id,row.id)['groups'] if g['field']=='运动' for r in g['rows'])
    candidate.confidence='LOW';s.flush()
    data=service.project(s,row);partition(data)
    states={f['field']:f['state'] for f in data['fields'] if f['section']=='生活方式'}
    assert states['睡眠']=='AUTO_FILLED' and states['运动']=='NEEDS_CONFIRMATION' and states['烟草']=='CONFLICT'
    assert not any(q['field']=='睡眠' for q in data['queue'])
    first=data['queue'][0]
    service.decide(s,row,first['key'],'MODIFY','QA',value='已核对的实际回答')
    after=service.project(s,row);partition(after)
    assert after['counts']['exceptions']==data['counts']['exceptions']-1
    assert first['key'] not in {q['key'] for q in after['queue']}
    assert after['counts']['processed']==1


@pytest.mark.parametrize('dates',[('2026-01-01','2026-01-01'),('2025-01-01','')])
def test_undated_or_same_date_disagreement_remains_conflict(env,dates):
    s,p,row=env
    upload(env,[(f'{i}.json',json.dumps({'source_date':d,'responses':{'生活方式':{'烟草':v}}},ensure_ascii=False).encode())
        for i,(d,v) in enumerate(zip(dates,['偶尔吸烟','已戒烟']))])
    data=service.project(s,row);partition(data)
    assert next(q for q in data['queue'] if q['field']=='烟草')['state']=='CONFLICT'


def test_unknown_evidence_never_auto_filled(env,monkeypatch):
    s,p,row=env
    semantic(monkeypatch,[{'section':'生活方式','field':'运动','value':'每周快走','evidence':'现在每周快走'}])
    upload(env,[('history.txt','现在每周快走'.encode())])
    source=next(r for g in service.imports.project(s,p.id,row.id)['groups'] for r in g['rows'])
    source.evidence_text='不同原文';s.flush()
    data=service.project(s,row);partition(data)
    assert next(q for q in data['queue'] if q['field']=='运动')['state']=='NEEDS_CONFIRMATION'


def test_same_agent_same_goals_resume_through_idempotent_health_event(env):
    from executive_health_ai.services.intake_handoff import assessment_confirmed
    s,p,row=env
    answers=responses();del answers['生活方式']['休假'];del answers['生活方式']['睡眠']
    view,_=upload(env,[('questionnaire.json',native(answers))])
    agent=s.scalar(select(MemberAgent).where(MemberAgent.member_id==p.id));agent_id=agent.id;wakes=agent.wake_count
    goal_ids={g.id for g in view['goals']}
    item=next(q for q in service.project(s,row)['queue'] if q['field']=='睡眠')
    service.decide(s,row,item['key'],'ANSWER','QA',value='每天七小时')
    assert service.project(s,row)['ready']
    service.complete(s,row,'QA',retain_unknown=True);s.flush()
    event=s.scalar(select(HealthEvent).where(HealthEvent.event_type=='INTAKE_ASSESSMENT_CONFIRMED'))
    assert event.status=='PROCESSED' and event.route_action=='RESUME_CURRENT_GOAL' and event.goal_id in goal_ids
    assert {g.id for g in service.imports.goals(s,row)}==goal_ids
    assert all(g.status=='COMPLETED' for g in service.imports.goals(s,row))
    s.refresh(agent)
    assert agent.id==agent_id and agent.wake_count==wakes+1 and agent.status=='IDLE'
    assert s.scalar(select(AgentRunTrace).where(AgentRunTrace.goal_id.in_(goal_ids),AgentRunTrace.action=='intake_confirmation_resume'))
    _,created=assessment_confirmed(s,row,'QA');s.refresh(agent)
    assert not created and agent.wake_count==wakes+1
    with pytest.raises(ValueError):service.complete(s,row,'QA',retain_unknown=True)
    assert '休假' not in row.responses['生活方式']
    assert row.status=='SUBMITTED' and row.review_status=='READY_FOR_REVIEW' # professional gate preserved


def test_forged_confirmation_cannot_resume_draft(env):
    from executive_health_ai.services.health_events import ingest_health_event
    s,p,row=env
    upload(env,[('questionnaire.json',native(responses()))])
    with pytest.raises(ValueError,match='总确认'):
        ingest_health_event(s,member_id=p.id,event_type='INTAKE_ASSESSMENT_CONFIRMED',event_category='NEW_INFORMATION',source_type='SYSTEM',source_id=str(row.id))
    assert row.status=='DRAFT'


def test_current_human_queue_not_full_catalog(env):
    s,p,row=env
    upload(env,[('questionnaire.json',native({'过敏史':[{'名称':'会员不清楚'}],'个人病史':[{'疾病或问题':'无既往病史'}],
        '当前用药 / 营养补充':[{'名称':'无用药'}],'生活方式':{'睡眠':'七小时','饮酒':'不饮酒','烟草':'不吸烟'},'会员重点关注':{'concern':'改善精力'}}))])
    data=service.project(s,row);partition(data)
    assert data['ready'] and data['counts']['optional_missing']>10
    service.complete(s,row,'QA',retain_unknown=True)
    assert row.status=='SUBMITTED'


def test_ignored_identity_does_not_reappear_as_auto_filled(env):
    s,p,row=env
    upload(env,[('questionnaire.json',native({'个人病史':[{'疾病或问题':'疑似胃病'}]}))])
    item=next(q for q in service.project(s,row)['queue'] if q['field']=='疾病或问题')
    service.decide(s,row,item['key'],'IGNORE','QA',note='原文尚未确认，暂不采用。')
    data=service.project(s,row);partition(data)
    assert not data['answers'].get('个人病史')
    assert next(q for q in data['queue'] if q['field']=='疾病或问题')['state']=='REQUIRED_MISSING'


def test_explicit_absence_and_positive_history_not_silently_combined(env):
    s,p,row=env
    upload(env,[('a.json',native({'手术 / 住院史':[{'名称':'无手术史'}]})),
                ('b.json',native({'手术 / 住院史':[{'名称':'阑尾切除术'}]}))])
    data=service.project(s,row);partition(data)
    assert len([q for q in data['queue'] if q['kind']=='CONFLICT'])==2
    assert not data['answers'].get('手术 / 住院史')


def test_unbound_records_have_unique_decisions_and_require_identity(env):
    s,p,row=env
    upload(env,[('a.json',native({'手术 / 住院史':[{'日期':'2020-01-01'}]})),
                ('b.json',native({'手术 / 住院史':[{'日期':'2021-02-02'}]}))])
    data=service.project(s,row);partition(data)
    items=[q for q in data['queue'] if q['section']=='手术 / 住院史']
    assert len(items)==2 and len({q['key'] for q in items})==2
    with pytest.raises(ValueError,match='哪一项记录'):service.decide(s,row,items[0]['key'],'CONFIRM','QA')
    service.decide(s,row,items[0]['key'],'CONFIRM','QA',identity='已核对的阑尾手术')
    after=service.project(s,row);partition(after)
    assert items[1]['key'] in {q['key'] for q in after['queue']}
    assert after['answers']['手术 / 住院史'][0]['名称']=='已核对的阑尾手术'


def test_repeat_after_reload_is_idempotent_but_new_submission_resumes_new_source(env):
    from executive_health_ai.services.intake_handoff import assessment_confirmed
    from executive_health_ai.services.management_workflow import ManagementWorkflowService
    from executive_health_ai.models.management_workflow import IntakeAssessment
    s,p,row=env
    upload(env,[('first.json',native(responses()))])
    service.complete(s,row,'QA');s.commit();row_id=row.id;member_id=p.id
    s.expunge_all();row=s.get(IntakeAssessment,row_id);p=s.get(Patient,member_id)
    _,created=assessment_confirmed(s,row,'QA')
    assert not created
    ManagementWorkflowService().review_intake(s,p.id,row.id,focus='',missing='',tests='',medical_question='',annual_focus='',actor='QA',decision='RETURN')
    view,_=upload((s,p,row),[('new.json',native({'生活方式':{'睡眠':'每天八小时'}}))])
    item=next(q for q in service.project(s,row)['queue'] if q['field']=='睡眠')
    service.decide(s,row,item['key'],'MODIFY','QA',value='每天八小时')
    service.complete(s,row,'QA');s.flush()
    events=list(s.scalars(select(HealthEvent).where(HealthEvent.event_type=='INTAKE_ASSESSMENT_CONFIRMED')))
    assert len(events)==2 and all(e.status=='PROCESSED' for e in events)
    assert all(g.status=='COMPLETED' for g in view['goals'])
    assert row.responses['生活方式']['睡眠']=='每天八小时'
