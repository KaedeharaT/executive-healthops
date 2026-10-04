from pathlib import Path
import pytest
from executive_health_ai.services.change_review import review_summary
from executive_health_ai.ui.pages.manager.longitudinal_timeline import public_text
from tests.test_autonomy_policy import db, change


def evidence():
    return {'change':{'metric':'sleep_duration'},'lookback':{
        'history_30d':[
            {'date':'2026-08-10','metrics':{'sleep_duration':{'value':'324','unit':'min'},'steps':{'value':'7000'}}},
            {'date':'2026-08-08','metrics':{'sleep_duration':{'value':'390','unit':'min'}}},
            {'date':'2026-08-07','metrics':{'weight':{'value':'83'}}}],
        'annual_baseline':{'sleep_duration':{'value':'384'}},
        'goal':{'title':'改善睡眠规律'},'management_logs':[],
        'doctor_opinions':[{'opinion':'按计划监测'}]}}


def test_checks_are_dated_and_metric_specific():
    result=review_summary(evidence(),'YELLOW')
    assert result['dates']==['2026-08-08','2026-08-10']
    assert '2 个记录日期' in result['checked'][0]
    assert '14天' not in str(result)
    assert '同期活动记录' in result['checked']
    assert '个人年度基线' in result['checked']
    assert '当时的管理目标：改善睡眠规律' in result['checked']
    assert '近期管理记录：未找到相关记录' in result['checked']
    assert '相关医生意见：1 条' in result['checked']


@pytest.mark.parametrize('payload',[None,{}, {'lookback':{}}, {'lookback':{'history_30d':[]}}])
def test_old_records_do_not_invent_checks(payload):
    result=review_summary(payload,'YELLOW')
    assert not result['available'] and result['checked']==[]
    assert '尚未留存' in result['message']


@pytest.mark.parametrize('level,route,expected',[
    ('GREEN','AUTO','无需新增人工待办'),('YELLOW','MANAGER','健管联系会员'),
    ('YELLOW','DOCTOR','需要医生判断'),
    ('RED','DOCTOR','需要医生判断'),('RED','ESCALATE','需要人工接手'),
    (None,None,'尚未留存明确的处理结论')])
def test_responsibility_is_separate_from_checked_data(level,route,expected):
    result=review_summary(evidence(),level,{'responsibility':{'route_type':route}})
    assert result['available'] and expected in result['decision']


def test_goal_progress_no_action_requires_recorded_decision():
    payload=evidence();payload['change']['kind']='GOAL_PROGRESS_CHANGE'
    assert '无需新增' not in review_summary(payload)['decision']
    assert '无需新增人工待办' in review_summary(payload,context={'no_action_reason':'目标进展已记录'})['decision']


@pytest.mark.parametrize('term',['Meaningful Change','Context Assembly','Lookback','Query','Retrieval'])
def test_retrieval_terms_not_exposed(term):
    assert term not in public_text(term)


def test_collapsed_episode_shows_checks_before_decision():
    component=Path('src/executive_health_ai/ui/pages/manager/timeline_component/index.html').read_text(encoding='utf-8')
    assert component.index('e.review.checked.forEach') < component.index("'当时核对后的处理：'")
    assert "evidence=disclosure(key+'-evidence','查看依据')" in component
    assert 'disclosureState.has(key)' in component
    assert "evidence.append(table)" in component and "evidence.append(sources)" in component
    assert "evidence.append(trend)" in component


def test_preparation_payload_does_not_mutate_evidence():
    import copy
    payload=evidence();before=copy.deepcopy(payload)
    review_summary(payload,'RED')
    assert payload==before


@pytest.mark.parametrize('level,route,expected',[
    ('GREEN','HEALTH_MANAGER','无需新增人工待办'),
    ('YELLOW','HEALTH_MANAGER','健管联系会员'),('RED','DOCTOR','需要医生判断')])
def test_work_page_reads_actual_goal_and_event(db,monkeypatch,level,route,expected):
    from contextlib import nullcontext
    from uuid import UUID
    from executive_health_ai.models import RiskEvent
    from executive_health_ai.ui import change_review as ui
    session,program=db
    event,goal=change(session,program,level,route)
    event.payload_ref={**event.payload_ref,'lookback':evidence()['lookback']}
    event.payload_ref={**event.payload_ref,'change':{'metric':'sleep_duration'}}
    session.flush()
    risk=session.get(RiskEvent,UUID(goal.context_json['risk_event_id']))
    messages=[]
    monkeypatch.setattr(ui,'SessionLocal',lambda:nullcontext(session))
    monkeypatch.setattr(ui.st,'write',messages.append)
    monkeypatch.setattr(ui.st,'caption',messages.append)
    ui.render_for_risk(program.patient_id,risk)
    assert any('已进一步核对' in t for t in messages)
    assert any('个人年度基线' in t for t in messages)
    assert expected in messages[-1]
