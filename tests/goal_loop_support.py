"""Explicit human-approved prerequisites for post-onboarding UI fixtures."""
from sqlalchemy import select
from executive_health_ai.models import HealthProgram, HealthAssessment, Patient
from executive_health_ai.models.management_workflow import IntakeAssessment
from executive_health_ai.models.goal_data import ManagementGoal
from executive_health_ai.models.base import utc_now


def approved_program(session,program):
    year=program.cycle_year or program.start_date.year
    intake=session.scalar(select(IntakeAssessment).where(IntakeAssessment.patient_id==program.patient_id,IntakeAssessment.cycle_year==year))
    if not intake:
        intake=IntakeAssessment(patient_id=program.patient_id,cycle_year=year)
        session.add(intake)
    intake.status=intake.review_status='CONFIRMED';intake.reviewed_by='synthetic fixture manager'
    if not session.scalar(select(HealthAssessment).where(HealthAssessment.patient_id==program.patient_id,
            HealthAssessment.cycle_year==year,HealthAssessment.status=='CONFIRMED')):
        from sqlalchemy import func
        version=(session.scalar(select(func.max(HealthAssessment.version)).where(HealthAssessment.patient_id==program.patient_id)) or 0)+1
        session.add(HealthAssessment(patient_id=program.patient_id,cycle_year=year,version=version,
            title='合成已确认基线',summary='用于正式管理界面的前置条件',created_by='synthetic fixture manager',
            reviewed_by='synthetic fixture manager',confirmed_at=utc_now(),status='CONFIRMED'))
    goal=session.scalar(select(ManagementGoal).where(ManagementGoal.program_id==program.id))
    if not goal:
        goal=ManagementGoal(patient_id=program.patient_id,program_id=program.id,goal_type='CUSTOM',
            title=program.main_goal,description='既有人已批准的合成测试方案',start_date=program.start_date,
            target_date=program.end_date or program.start_date,owner_id=program.owner or '测试健管',status='ACTIVE',
            source='EXISTING_APPROVED_PLAN',confirmed_by='synthetic fixture manager',confirmed_at=utc_now(),
            plan_confirmed_by='synthetic fixture manager',plan_confirmed_at=utc_now())
        session.add(goal)
    goal.status='ACTIVE';goal.confirmed_by=goal.plan_confirmed_by='synthetic fixture manager'
    goal.confirmed_at=goal.plan_confirmed_at=utc_now()
    if goal.agent_goal_id:
        from executive_health_ai.models import AgentGoal
        agent=session.get(AgentGoal,goal.agent_goal_id)
        agent.status='COMPLETED';agent.completed_at=utc_now()
    session.flush()


def approved_demo():
    from executive_health_ai.database import SessionLocal
    with SessionLocal() as session:
        member=session.scalar(select(Patient))
        for program in session.scalars(select(HealthProgram).where(HealthProgram.patient_id==member.id)):
            approved_program(session,program)
        session.commit()
        return member.id
