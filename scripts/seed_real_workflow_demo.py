"""Add one synthetic enrollment; complete its journey through the actual UI.

Never reads source questionnaires, spreadsheets or personal records.
"""
from datetime import date,timedelta
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import Patient
from executive_health_ai.services.management_workflow import ManagementWorkflowService


def seed_workflow_enrollment(session):
    external='synthetic-real-workflow-v1'
    member=session.scalar(select(Patient).where(Patient.external_id==external))
    if member: return member
    program=ManagementWorkflowService().enroll(session,name='Synthetic Workflow Member',start=date.today(),
        end=date.today()+timedelta(days=364),owner='Synthetic Care Manager',goal='完成资料核对并建立持续执行习惯',advisor='Synthetic Advisor')
    member=session.get(Patient,program.patient_id);member.external_id=external
    return member


if __name__=='__main__':
    with SessionLocal() as session:
        seed_workflow_enrollment(session);session.commit()
    print('Synthetic enrollment ready; continue in Member 360.')
