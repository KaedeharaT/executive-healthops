"""Responsibility is a durable safety boundary, not a model-generated label."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from test_post_checkup_care_v1 import care, send_doctor, judge
from executive_health_ai.agent import post_checkup as flow, care_routing
from executive_health_ai.agent.reflection import HealthOpsReflectionService
from executive_health_ai.models import AgentRunTrace, RiskRule, RiskEvent, Task
from executive_health_ai.services.responsibility import ResponsibilityRouter, REASONS
from executive_health_ai.services.care_board import project


@pytest.mark.parametrize('code,route', [('NON_MEDICAL_PREPARATION','AUTO'),('MANAGER_CONFIRMATION','MANAGER'),
    ('DIAGNOSIS','DOCTOR'),('MEDICATION','DOCTOR'),('TREATMENT','DOCTOR'),('EXAMINATION','DOCTOR'),
    ('REFERRAL','DOCTOR'),('MEDICAL_RISK','DOCTOR'),('DISEASE_CHANGE','DOCTOR'),('MANAGER_REQUEST','DOCTOR'),
    ('RULE_DOCTOR','DOCTOR'),('EMERGENCY_RULE','ESCALATE'),('DATA_CONFLICT','ESCALATE'),('UNREADABLE_REPORT','ESCALATE')])
def test_shared_responsibility_types(code, route):
    decision=ResponsibilityRouter().decide(reason_codes=[code],evidence_refs=['document:synthetic'])
    assert decision.route_type==route and decision.reason_summary==REASONS[code][1]


@pytest.mark.parametrize('original', ['DIAGNOSIS','EMERGENCY_RULE'])
def test_llm_cannot_downgrade_or_erase_original_reasons(original):
    router=ResponsibilityRouter()
    prior=router.decide(reason_codes=[original],rule_refs=['rule:original'],evidence_refs=['report:original'])
    for suggestion in ['AUTO','MANAGER','DOCTOR']:
        decision=router.decide(reason_codes=['NON_MEDICAL_PREPARATION'],previous=prior,
            ai_suggestion=suggestion,evidence_refs=['report:original'])
        assert decision.route_type==prior.route_type
        assert original in decision.reason_codes and 'rule:original' in decision.rule_refs


def test_reason_evidence_actor_persisted_and_idempotent(care):
    s,g,sup=care
    decision=care_routing.route(s,g,codes=['MANAGER_REQUEST'],actor=g.owner)
    count=s.query(AgentRunTrace).filter_by(action='responsibility_routed').count()
    care_routing.route(s,g,codes=['MANAGER_REQUEST'],actor=g.owner)
    s.commit();s.expire_all()
    loaded=care_routing.latest(s,g)
    assert loaded.reason_summary==decision.reason_summary
    assert loaded.evidence_refs==decision.evidence_refs and loaded.confirmed_by==g.owner
    assert s.query(AgentRunTrace).filter_by(action='responsibility_routed').count()==count
    with pytest.raises(ValueError,match='医生'):
        flow.manager_review(sup,s,g,actor=g.owner,role='HEALTH_MANAGER')


def add_risk(s,g,*,emergency=False):
    rule=RiskRule(name='Synthetic explicit safety rule',code=str(uuid4()),applicable_device_class='MANUAL_ENTRY',
        risk_level='RED',condition_type='synthetic',action_type='ESCALATE',source_reference='Synthetic test only')
    s.add(rule);s.flush()
    event=RiskEvent(patient_id=g.member_id,risk_rule_id=rule.id,risk_level='RED',device_class='MANUAL_ENTRY',
        summary='Synthetic existing rule output',requires_doctor_review=True,requires_emergency_action=emergency)
    s.add(event);s.flush();return event


def test_emergency_stops_ordinary_actions_and_cannot_resume_or_replan(care):
    s,g,sup=care
    add_risk(s,g,emergency=True)
    flow.analyze(sup,s,g)
    assert g.status=='ESCALATED' and care_routing.latest(s,g).route_type=='ESCALATE'
    sup.resume_goal(s,g.id,actor=g.owner)
    assert g.status=='ESCALATED'
    with pytest.raises(ValueError):flow.prepare_actions(sup,s,g)
    with pytest.raises(ValueError):HealthOpsReflectionService().replan(s,g.id,reason='DATA_INSUFFICIENT')
    with pytest.raises(ValueError):sup.registry.execute(s,'create_followup_task',g,{})
    assert not s.query(Task).count()


def test_doctor_wait_does_not_get_reanalyzed_past_the_gate(care):
    s,g,sup=care;send_doctor(s,g,sup)
    with pytest.raises(ValueError):flow.analyze(sup,s,g)
    assert g.status=='WAITING_DOCTOR'
    with pytest.raises(ValueError):flow.prepare_actions(sup,s,g)
    with pytest.raises(ValueError):HealthOpsReflectionService().replan(s,g.id,reason='SERVICE_DELAYED')


def test_router_and_board_follow_real_goal_across_all_gates(care):
    s,g,sup=care
    assert project(s,g).route.route_type=='MANAGER'
    send_doctor(s,g,sup)
    waiting=project(s,g)
    assert waiting.route.route_type=='DOCTOR' and '演示医生' in waiting.owner
    assert '健管已申请' in waiting.route.reason_summary
    assert waiting.humans and not waiting.doctor_opinion
    judge(s,g)
    resumed=project(s,g)
    assert resumed.route.route_type=='MANAGER' and resumed.doctor_opinion
    flow.approve_actions(sup,s,g,actions=g.context_json['actions'],actor=g.owner,role='HEALTH_MANAGER')
    done=project(s,g)
    assert done.route.route_type=='AUTO' and g.status=='COMPLETED'
    assert {'AUTO','MANAGER','DOCTOR'} <= {r.route_type for r in done.route_history}
    assert len(g.context_json['created']['tasks'])==3
    assert not done.risks and not s.query(RiskEvent).count()


def test_existing_risk_is_not_claimed_as_new_or_ai_generated(care):
    s,g,_=care
    risk=add_risk(s,g)
    board=project(s,g)
    assert board.route.route_type=='DOCTOR'
    assert len(board.risks)==1 and not board.risks[0]['new_for_report']
    assert board.risks[0]['等级']==risk.risk_level
    assert board.doctor_opinion is None
    assert s.query(RiskEvent).count()==1


def test_running_and_escalated_projection(care):
    s,g,sup=care
    g.current_stage='ANALYZING';g.status='RUNNING'
    board=project(s,g)
    assert board.route.route_type=='AUTO' and board.owner=='健康管理助手'
    g.context_json={**g.context_json,'structured':False}
    flow.analyze(sup,s,g)
    assert project(s,g).route.route_type=='ESCALATE'
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_string("from types import SimpleNamespace\n"
        "from executive_health_ai.ui.pages.manager.post_checkup import stepper\n"
        f"stepper(SimpleNamespace(status={g.status!r}, current_stage={g.current_stage!r}, context_json={{'structured':False}}))").run()
    assert not app.exception
    assert '系统分析<br><small>需人工核对' in app.markdown[0].value


def test_routing_rejects_untrusted_reason_and_unbacked_ai_advice():
    with pytest.raises(ValueError):ResponsibilityRouter().decide(reason_codes=['AI_HIGH_RISK'])
    with pytest.raises(ValueError):ResponsibilityRouter().decide(reason_codes=['NON_MEDICAL_PREPARATION'],ai_suggestion='DOCTOR')


def test_fabricated_doctor_result_cannot_clear_real_review_gate(care):
    s,g,sup=care;send_doctor(s,g,sup)
    g.context_json={**g.context_json,'doctor_result':{'judgement':'untrusted claimed completion'}}
    assert care_routing.evaluate(s,g).route_type=='DOCTOR'
    with pytest.raises(ValueError):flow.prepare_actions(sup,s,g)


def test_new_emergency_at_action_gate_escalates_without_writes(care):
    s,g,sup=care
    flow.manager_review(sup,s,g,actor=g.owner,role='HEALTH_MANAGER')
    add_risk(s,g,emergency=True)
    flow.approve_actions(sup,s,g,actions=g.context_json['actions'],actor=g.owner,role='HEALTH_MANAGER')
    assert g.status=='ESCALATED' and not s.query(Task).count()


def test_manager_cannot_turn_action_editor_into_medical_prescription(care):
    s,g,sup=care
    flow.manager_review(sup,s,g,actor=g.owner,role='HEALTH_MANAGER')
    actions=[dict(a) for a in g.context_json['actions']]
    actions[0]['title']='调整药物剂量'
    with pytest.raises(ValueError,match='医学决定'):
        flow.approve_actions(sup,s,g,actions=actions,actor=g.owner,role='HEALTH_MANAGER')
    assert not s.query(Task).count()


def test_real_safe_human_reassessment_preserves_original_medical_gate(care):
    s,g,sup=care;send_doctor(s,g,sup)
    risk=add_risk(s,g,emergency=True)
    flow.move(sup,s,g,'WAITING_DOCTOR_REVIEW','等待医生')
    assert g.status=='ESCALATED'
    risk.status='CLOSED';s.flush()
    sup.resume_goal(s,g.id,actor=g.owner)
    assert care_routing.latest(s,g).route_type=='DOCTOR'
    assert g.status=='WAITING_DOCTOR'
    # No model or generic replan can create actions just because safety cleared.
    with pytest.raises(ValueError):flow.prepare_actions(sup,s,g)
