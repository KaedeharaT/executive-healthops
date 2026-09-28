"""Real commands, ownership, evidence and handoff on existing domain objects."""
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from sqlalchemy import select
from executive_health_ai.models import Task, ServiceCatalogItem, OutcomeEvaluation, DoctorReview
from executive_health_ai.models.management_workflow import ManagementLog
from executive_health_ai.services.member_services import MemberServiceOperations
from executive_health_ai.services.service_operations_projection import service_stage, special_programs, stage_evidence
from tests.test_management_action_loop import env, task, complete, loop, workflow


def request(env):
    s,p,phase=env
    item=ServiceCatalogItem(code=str(uuid4()),name='合成沟通',category='连续管理',description='合成服务')
    s.add(item);s.flush()
    return MemberServiceOperations().request(s,p.patient_id,item.id,'核对当前阶段反馈')


def finish(env,row):
    s,p,_=env;ops=MemberServiceOperations()
    ops.approve(s,row.id,p.owner)
    ops.schedule(s,row.id,datetime.now(timezone.utc),p.owner,'合成团队')
    ops.start(s,row.id,p.owner)
    ops.complete(s,row.id,'已完成沟通',p.owner,completion_evidence='合成会员确认',next_action='复核结果')
    return s.scalar(select(Task).where(Task.source==f'service_result:{row.id}'))


def test_member_manager_and_plan_to_service_task(env):
    s,p,phase=env;r=request(env)
    assert (r.assigned_manager,r.program_id,r.phase_id)==(p.owner,p.id,phase.id)
    follow=finish(env,r)
    assert follow.program_id==p.id and follow.assignee==p.owner
    assert follow in loop.project(s,p.patient_id,p.id)['planned']


def test_service_result_writes_log_once_and_keeps_confirmation_open(env):
    s,p,_=env;r=request(env);follow=finish(env,r)
    MemberServiceOperations().complete(s,r.id,'duplicate',p.owner)
    logs=list(s.scalars(select(ManagementLog).where(ManagementLog.related_service_id==r.id)))
    assert len(logs)==1 and logs[0].result=='已完成沟通' and logs[0].evidence=='合成会员确认'
    assert follow.status=='PENDING' and not loop.project(s,p.patient_id,p.id)['review_ready']
    assert service_stage(r,[follow])=='待结果确认'


def test_followup_next_action_and_service_lifecycle(env):
    s,p,_=env;r=request(env)
    assert service_stage(r,[])=='待安排'
    follow=finish(env,r)
    log=complete(env,follow,next_action='继续随访',follow_at=datetime.now(timezone.utc)+timedelta(days=1))
    tasks=list(s.scalars(select(Task)));logs=list(s.scalars(select(ManagementLog)))
    assert service_stage(r,tasks,logs)=='待回访'
    complete(env,s.get(Task,log.follow_up_task_id))
    assert service_stage(r,tasks,logs)=='已完成'


@pytest.mark.parametrize('status,expected',[('SCHEDULED','已预约'),('IN_SERVICE','执行中'),('CANCELLED','已取消')])
def test_service_statuses_are_real(env,status,expected):
    r=request(env);r.status=status
    assert service_stage(r,[])==expected


def test_completed_service_cannot_be_rescheduled(env):
    s,p,_=env;r=request(env);finish(env,r)
    with pytest.raises(ValueError,match='安排时间'):
        MemberServiceOperations().schedule(s,r.id,datetime.now(timezone.utc),p.owner)
    assert r.status=='COMPLETED'


def outcome(env,current='85.8',target=None):
    s,p,_=env
    row=OutcomeEvaluation(patient_id=p.patient_id,program_id=p.id,metric='weight',baseline_value='90',
        current_value=current,target_value=target,unit='kg',direction='OBSERVED',evaluation_date=date.today(),
        evaluator=p.owner,evidence='合成秤记录；仅观察差异',result='STABLE')
    s.add(row);s.flush();return row


def test_special_progress_uses_latest_evidence_and_never_invents_target(env):
    s,p,_=env;prior=outcome(env,'87','83');prior.evaluation_date=date.today()-timedelta(days=1);latest=outcome(env)
    row=task(env);complete(env,row)
    result=special_programs(s)
    assert len(result)==1 and result[0]['outcome'].id==latest.id
    assert result[0]['outcome'].target_value is None
    assert result[0]['completed']==result[0]['total']==1


def test_stage_summary_contains_real_service_and_metric_evidence(env):
    s,p,phase=env;r=request(env);follow=finish(env,r);complete(env,follow);outcome(env)
    state=loop.project(s,p.patient_id,p.id);summary=loop.stage_summary(state)
    assert '90 → 85.8' in summary['关键指标变化'] and '合成秤记录' in summary['关键指标变化']
    assert '已完成沟通' in summary['服务完成']
    assert state['review_ready']
    review=loop.review_stage(s,p.patient_id,p.id,phase_id=phase.id,content=summary,actor=p.owner)
    assert review.content==summary


def test_no_outcome_is_missing_not_health_improvement(env):
    s,p,phase=env
    assert '资料不足' in stage_evidence(s,p.patient_id,p.id,phase)['关键指标变化']
    assert special_programs(s)==[]


def test_special_route_reuses_member360_with_program_context(monkeypatch):
    from executive_health_ai.ui.pages.manager import service_progress
    state={};monkeypatch.setattr(service_progress.st,'session_state',state)
    p=SimpleNamespace(id=uuid4(),patient_id=uuid4());app=Mock()
    service_progress.open_special(app,{'program':p})
    app._open_member_management.assert_called_once_with(p.patient_id)
    assert state[f'annual-program-{p.patient_id}']==str(p.id)
    assert state['member-return-origin']=='专项管理'


def test_service_and_log_do_not_create_risk_or_doctor_decisions(env):
    from executive_health_ai.models import RiskEvent, AgentGoal
    s,p,_=env;r=request(env);follow=finish(env,r);complete(env,follow)
    assert list(s.scalars(select(RiskEvent)))==[]
    assert list(s.scalars(select(DoctorReview)))==[]
    assert list(s.scalars(select(AgentGoal)))==[]


def test_followup_chain_remains_visible_until_last_followup_done(env):
    s,p,_=env;r=request(env);follow=finish(env,r)
    first=complete(env,follow,next_action='继续随访',follow_at=datetime.now(timezone.utc)+timedelta(days=1))
    second=complete(env,s.get(Task,first.follow_up_task_id),next_action='继续随访',follow_at=datetime.now(timezone.utc)+timedelta(days=2))
    tasks=list(s.scalars(select(Task)));logs=list(s.scalars(select(ManagementLog)))
    assert service_stage(r,tasks,logs)=='待回访'
    complete(env,s.get(Task,second.follow_up_task_id))
    assert service_stage(r,tasks,logs)=='已完成'


def test_outcome_next_action_keeps_named_manager(env):
    from executive_health_ai.services.chronic_care import apply_outcome_decision
    s,p,_=env;row=outcome(env)
    follow=apply_outcome_decision(s,row,'CONTINUE',p.owner,'继续核对')
    assert follow.assignee==p.owner and follow.program_id==p.id


def test_new_enrollment_appears_in_today_with_owner(env):
    from executive_health_ai.services.member_management_projection import management_work_items
    s,p,_=env
    rows=management_work_items(s,datetime.now(timezone.utc))
    item=next(r for r in rows if r.source_type=='intake_review')
    assert item.owner==p.owner and item.member_id==p.patient_id


@pytest.mark.parametrize('state,target',[('资料收集中','资料'),('待健管初评','初评'),('待建立基线','基线'),('待制定方案','方案')])
def test_onboarding_next_is_explicit_without_second_detail(state,target):
    from executive_health_ai.services.member_management_projection import onboarding_next
    view=SimpleNamespace(program=SimpleNamespace(status='PLANNED'),current_phase=None,onboarding=state)
    assert onboarding_next(view)[1]==target
    view.program.status='ACTIVE'
    assert onboarding_next(view) is None


def test_doctor_return_is_processed_before_phase_handoff(env):
    from executive_health_ai.services import care_commands
    s,p,phase=env;complete(env,task(env));state=loop.project(s,p.patient_id,p.id)
    loop.review_stage(s,p.patient_id,p.id,phase_id=phase.id,content=loop.stage_summary(state),actor=p.owner,medical=True)
    review=s.scalar(select(DoctorReview))
    _,follow=care_commands.complete_review(s,review,'合成医生','全科','已人工核对合成资料','落实已确认管理安排',datetime.now(timezone.utc)+timedelta(days=1))
    state=loop.project(s,p.patient_id,p.id)
    assert state['next'].record.id==follow.id and state['next'].kind!='STAGE_REVIEW'
    assert follow.assignee==p.owner
    complete(env,follow)
    state=loop.project(s,p.patient_id,p.id)
    assert not state['phase_open']
    draft=loop.next_phase_draft(state)
    following=loop.enter_next_phase(s,p.patient_id,p.id,phase.id,actor=p.owner,title=draft['title'],goal=draft['goal'],content=draft['content'],start=draft['start'],end=draft['end'],action='继续下阶段安排')
    assert following.status=='ACTIVE' and phase.status=='COMPLETED'


def test_finished_core_work_enters_today_before_planned_phase_end(env):
    from executive_health_ai.services.member_management_projection import management_work_items
    s,p,phase=env;row=task(env)
    assert phase.end_date>date.today()
    assert not any(i.source_type=='stage_review' for i in management_work_items(s,datetime.now(timezone.utc)))
    complete(env,row)
    items=management_work_items(s,datetime.now(timezone.utc))
    assert any(i.source_type=='stage_review' and i.source_id==phase.id and i.owner==p.owner for i in items)
