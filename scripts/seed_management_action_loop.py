"""Add an idempotent, entirely synthetic story to the identified Demo Executive A."""
from datetime import date,datetime,time,timedelta,timezone
from sqlalchemy import select
from executive_health_ai.models import Patient,HealthJourney,HealthProgram,ServiceCatalogItem,ServiceRequest
from executive_health_ai.services import chronic_care,care_commands
from executive_health_ai.services.management_workflow import ManagementWorkflowService
from executive_health_ai.services.member_services import MemberServiceOperations

TITLE='管理操作闭环演示（合成）'

def seed(session):
    member=session.scalar(select(Patient).where(Patient.external_id=='demo-management-action-loop-a',Patient.archived_at.is_(None)))
    if not member:member=session.scalar(select(Patient).where(Patient.external_id.in_(['demo-executive-001','portfolio-demo-executive-a']),Patient.archived_at.is_(None)))
    if not member:
        member=Patient(external_id='demo-management-action-loop-a',display_name='Demo Executive A',timezone='Asia/Tokyo')
        session.add(member);session.flush()
    existing=session.scalar(select(HealthProgram).where(HealthProgram.patient_id==member.id,HealthProgram.title==TITLE))
    if existing:return member,existing
    journey=session.scalar(select(HealthJourney).where(HealthJourney.patient_id==member.id))
    if not journey:
        journey=chronic_care.create_assessment(session,member.id,'纯合成操作链演示；医学资料尚待人工评估','体验管理执行与阶段复盘','NEEDS_MEDICAL_EVALUATION',[],{},'演示健康管理师')
    today=date.today();owner='演示健康管理师'
    program=chronic_care.create_program(session,journey,'ANNUAL',TITLE,'完成沟通、随访与健康服务后进行阶段复盘',[],today-timedelta(days=2),owner,end_date=today+timedelta(days=90))
    program.cycle_year=today.year
    workflow=ManagementWorkflowService()
    phase=workflow.add_phase(session,member.id,program.id,title='资料核对与执行跟进（合成）',goal='完成三项已约定管理工作',content='核对生活方式记录、电话随访、健康沟通服务',start=program.start_date,end=today+timedelta(days=8),owner=owner)
    phase.status='ACTIVE';program.current_phase=phase.phase_code
    workflow.add_phase(session,member.id,program.id,title='下一阶段持续管理（合成）',goal='持续记录与定期随访',content='落实健管确认的随访安排；医疗事项仍遵循医生意见',start=phase.end_date+timedelta(days=1),end=today+timedelta(days=38),owner=owner)
    first=care_commands.schedule_followup(session,program,title='核对本周生活方式记录（合成）',instruction='核对成员提交的睡眠与活动记录，记录事实和执行困难；不作医学判断。',due_at=datetime.combine(today,time(7),timezone.utc),owner=owner)
    first.priority='HIGH';first.source='management_loop_demo:management'
    follow=care_commands.schedule_followup(session,program,title='电话随访执行情况（合成）',instruction='记录本人反馈与执行情况，需要时安排下一次随访。',due_at=datetime.combine(today,time(8),timezone.utc),owner=owner)
    follow.source='followup:management_loop_demo'
    catalog=session.scalar(select(ServiceCatalogItem).where(ServiceCatalogItem.code=='SYNTHETIC_ACTION_LOOP'))
    if not catalog:
        catalog=ServiceCatalogItem(code='SYNTHETIC_ACTION_LOOP',name='健康沟通服务（合成）',category='健康管理',description='纯合成演示；无收费、无对外预约');session.add(catalog);session.flush()
    request=MemberServiceOperations().request(session,member.id,catalog.id,'阶段健康沟通服务（合成）',owner)
    workflow.link_service(session,member.id,request.id,program.id,phase.id)
    request.sla_due_at=datetime.combine(today,time(9),timezone.utc)
    return member,program

if __name__=='__main__':
    from executive_health_ai.database import SessionLocal
    with SessionLocal() as session:
        member,program=seed(session);session.commit()
        print('Synthetic story prepared; existing records retained:',member.id,program.id)
