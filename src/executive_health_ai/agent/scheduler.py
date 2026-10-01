"""Small DB-backed wake-up scheduler; replaceable by a production worker."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
from executive_health_ai.models import AgentGoal, AgentPlanStep
from executive_health_ai.services.event_service import EventService


class AgentSchedulerService:
    def __init__(self, supervisor: HealthOpsAgentSupervisor | None = None) -> None:
        self.supervisor = supervisor or HealthOpsAgentSupervisor()

    def run_due(self, session: Session, *, now: datetime, durable_profile: bool = False) -> int:
        supervisor = self.supervisor
        from executive_health_ai.services.daily_summary import run_daily_batch
        run_daily_batch(session,now=now)
        from executive_health_ai.services.daily_care import schedule_due, advance, reconcile
        reconcile(session,supervisor)
        schedule_due(session,now)
        from executive_health_ai.services.health_events import process_pending
        processed = process_pending(session,supervisor,now=now)
        for goal in list(session.scalars(select(AgentGoal).where(AgentGoal.goal_type=='DAILY_CARE',
                AgentGoal.status=='RUNNING',AgentGoal.automation_paused.is_(False)))):
            advance(session,goal,supervisor)
        # Reconcile migrated identities and changes made before a worker restart.
        from executive_health_ai.models import MemberAgent, Patient
        from executive_health_ai.services.member_agents import synchronize
        for member_id in session.scalars(select(MemberAgent.member_id).join(Patient,Patient.id==MemberAgent.member_id)
                .where(Patient.archived_at.is_(None))):
            synchronize(session,member_id)
        if durable_profile:
            from executive_health_ai.agent.care_result_execution import execute as execute_result
            for goal in list(session.scalars(select(AgentGoal).where(AgentGoal.goal_type=='FOLLOWUP_RESULT',
                    AgentGoal.status.in_(('RUNNING','PROCESSING')),AgentGoal.automation_paused.is_(False)))):
                execute_result(supervisor,session,goal);processed+=1
            from executive_health_ai.agent.post_checkup_execution import execute
            for goal in list(session.scalars(select(AgentGoal).where(AgentGoal.goal_type=='POST_CHECKUP_MANAGEMENT',
                    AgentGoal.status.in_(('RUNNING','PROCESSING')),AgentGoal.automation_paused.is_(False)))):
                if goal.context_json.get('pending_ai'):
                    execute(supervisor,session,goal);processed+=1
        statuses=['RUNNING','PROCESSING'] if durable_profile else ['RUNNING']
        for goal in list(session.scalars(select(AgentGoal).where(AgentGoal.goal_type == "PROFILE_INTAKE", AgentGoal.status.in_(statuses), AgentGoal.automation_paused.is_(False)))):
            supervisor.execute_next_step(session, goal.id, **({'durable_profile':True} if durable_profile else {}))
            processed += 1
        due_goals = list(session.scalars(select(AgentGoal).where(AgentGoal.status == "WAITING", AgentGoal.next_check_at.is_not(None), AgentGoal.next_check_at <= now, AgentGoal.automation_paused.is_(False))))
        for goal in due_goals:
            plan_id = goal.current_plan_id
            retry = session.scalar(select(AgentPlanStep).where(AgentPlanStep.plan_id == plan_id, AgentPlanStep.status == "RETRY_WAIT", AgentPlanStep.next_retry_at <= now).order_by(AgentPlanStep.step_order))
            if retry:
                retry.status = "PENDING"
                goal.status = "ACTIVE"
                supervisor.execute_next_step(session, goal.id)
                processed += 1
                continue
            event, _ = EventService().publish(session, event_type="REVIEW_DUE", member_id=goal.member_id, source_type="agent_goal", source_id=goal.id, payload_summary="Scheduled follow-up review is due", dedup_key=f"REVIEW_DUE:{goal.id}:{goal.next_check_at.isoformat()}")
            supervisor.receive_event(session, event)
            processed += 1
        return processed
