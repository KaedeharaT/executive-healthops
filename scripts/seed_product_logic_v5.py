"""Prepare synthetic human gates through the existing report and care services."""
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from sqlalchemy import select
from executive_health_ai.models import Patient, AgentGoal, HealthProgram, ProgramPhase
from executive_health_ai.models.management_workflow import RecheckPlan, ManagementLog
from executive_health_ai.services.report_parsing import ReportParsingService
from executive_health_ai.services.product_projection import current_program
from executive_health_ai.services.management_workflow import ManagementWorkflowService
from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
from executive_health_ai.agent.post_checkup import manager_review


def seed_product_logic(session):
    member=session.scalar(select(Patient).where(Patient.external_id=='portfolio-demo-executive-a'))
    if not member:
        raise ValueError('V5 demo requires the existing isolated synthetic portfolio member.')
    program=current_program(list(session.scalars(select(HealthProgram).where(HealthProgram.patient_id==member.id))))
    parser=ReportParsingService();parser.storage_root=Path('data/portfolio_reports')
    for label,ldl,alt in [('待健管确认',4.25,52),('待医生判断',4.35,56)]:
        exam_date=date.today() if label=='待健管确认' else date.today()-timedelta(days=2)
        content=f'合成演示资料，非真实个人信息。\n体检日期：{exam_date}\n本次用途：{label}\n低密度脂蛋白胆固醇  {ldl} mmol/L\n谷丙转氨酶  {alt} U/L\n体重  85.8 kg\n'.encode('utf-8')
        report,_,_=parser.upload_and_parse(session,member.id,f'体检报告 · {label}（合成演示）.txt',content,program.owner)
        goal=session.scalar(select(AgentGoal).where(AgentGoal.source_id==str(report.id)))
        if label=='待医生判断' and goal.current_stage=='WAITING_MANAGER_REVIEW':
            manager_review(HealthOpsAgentSupervisor(),session,goal,actor=program.owner,role='HEALTH_MANAGER',
                summary='已核对合成报告，肝功能变化请医生判断。',doctor='演示医生',question='肝功能变化是否需要进一步医学处理？')
    workflow=ManagementWorkflowService()
    if not session.scalar(select(RecheckPlan).where(RecheckPlan.patient_id==member.id,RecheckPlan.title=='确认肝功能复查预约')):
        workflow.create_recheck(session,member.id,program.id,title='确认肝功能复查预约',reason='按既有合成医疗记录安排复查',
            planned_at=datetime.combine(date.today(),time(16),timezone.utc),owner=program.owner,provider='合成演示医院',evidence='已核对演示医生复查建议，仅供合成演示。')
    if not session.scalar(select(ManagementLog).where(ManagementLog.patient_id==member.id,ManagementLog.request_key=='product-logic-v5-demo-log')):
        workflow.record_log(session,member.id,program.id,actor=program.owner,request_key='product-logic-v5-demo-log',
            occurred_at=datetime.now(timezone.utc)-timedelta(days=1),category='电话',channel='电话',member_issue='已确认本月复查意向',
            manager_action='解释复查安排并核对可预约时间',result='会员同意继续安排',next_action='确认复查预约',owner=program.owner,create_followup=False)
    if not session.scalar(select(ProgramPhase).where(ProgramPhase.program_id==program.id)):
        first_end=program.start_date+timedelta(days=29)
        last_start=program.end_date-timedelta(days=29)
        for title,start,end,status in [('建档与基线',program.start_date,first_end,'COMPLETED'),
            ('持续管理',first_end+timedelta(days=1),last_start-timedelta(days=1),'ACTIVE'),
            ('年度复盘',last_start,program.end_date,'PLANNED')]:
            phase=workflow.add_phase(session,member.id,program.id,title=title,goal=program.main_goal,
                content='完成复查、随访与结果复盘',start=start,end=end,owner=program.owner)
            # Persisted synthetic demonstration progress; no production state is edited.
            phase.status=status
    session.flush()
