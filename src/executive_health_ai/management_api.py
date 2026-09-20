"""Portfolio workflow API. Role is asserted, not a replacement for production identity."""
from datetime import date, datetime
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from executive_health_ai.models import Patient
from executive_health_ai.services.management_workflow import ManagementWorkflowService
from executive_health_ai.services.member_management_projection import MemberManagementProjection


class WorkflowCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action: Literal['enroll','intake_save','intake_submit','intake_review','medication_confirm','phase_add','phase_advance','program_start','log_create','recheck_create','recheck_advance','consultation_create','consultation_schedule','consultation_opinion','consultation_conclude','action_plan','stage_review','service_link','family_add']
    actor: str=Field(min_length=1,max_length=128)
    actor_role: Literal['member','health_manager','doctor']
    values: dict=Field(default_factory=dict)


def register_management_api(app,get_session):
    router=APIRouter(prefix='/management',tags=['会员全周期管理'])
    service=ManagementWorkflowService()
    @router.get('/members/{member_id}')
    def member_workspace(member_id:UUID,session=Depends(get_session)):
        if not session.get(Patient,member_id):raise HTTPException(404,'会员不存在')
        view=MemberManagementProjection().member(session,member_id)
        return {'onboarding':view.onboarding,'owner':view.owner,'program_id':str(view.program.id) if view.program else None,
            'current_phase':view.current_phase.title if view.current_phase else None,
            'member_concern':view.intake.member_concern if view.intake else '',
            'professional_focus':view.intake.professional_focus if view.intake else '',
            'log_count':len(view.logs),'recheck_count':len(view.rechecks),'milestones':view.milestones}

    @router.post('/members/{member_id}/commands')
    def command(member_id:UUID,payload:WorkflowCommand,session=Depends(get_session)):
        if not session.get(Patient,member_id):raise HTTPException(404,'会员不存在')
        medical={'medication_confirm','consultation_opinion','consultation_conclude'}
        self_report={'intake_save','intake_submit'}
        if (payload.action in medical and payload.actor_role!='doctor') or (payload.action not in medical|self_report and payload.actor_role!='health_manager'):
            raise HTTPException(403,'此角色不能执行该业务动作')
        v=dict(payload.values);actor=payload.actor
        try:
            for key in ['program_id','assessment_id','case_id','phase_id','recheck_id','service_id','task_id','doctor_review_id','document_id','related_patient_id','related_task_id','related_risk_id','related_doctor_review_id','related_service_id','related_document_id']:
                if v.get(key):v[key]=UUID(v[key])
            for key in ['start','end']:
                if v.get(key):v[key]=date.fromisoformat(v[key])
            for key in ['occurred_at','planned_at','scheduled_at','follow_up_at','next_recheck_at']:
                if v.get(key):
                    v[key]=datetime.fromisoformat(v[key])
                    if v[key].tzinfo is None:raise ValueError('时间必须包含时区。')
            actions={
                'enroll':lambda:service.enroll(session,member_id=member_id,**v),
                'intake_save':lambda:service.save_intake(session,member_id,actor=actor,**v),
                'intake_submit':lambda:service.submit_intake(session,member_id,actor=actor,**v),
                'intake_review':lambda:service.review_intake(session,member_id,actor=actor,**v),
                'medication_confirm':lambda:service.confirm_medication(session,member_id,actor=actor,role=payload.actor_role,**v),
                'phase_add':lambda:service.add_phase(session,member_id,**v),
                'phase_advance':lambda:service.advance_phase(session,member_id,actor=actor,**v),
                'program_start':lambda:service.start_program(session,member_id,actor=actor,**v),
                'log_create':lambda:service.record_log(session,member_id,actor=actor,**v),
                'recheck_create':lambda:service.create_recheck(session,member_id,**v),
                'recheck_advance':lambda:service.advance_recheck(session,member_id,actor=actor,**v),
                'consultation_create':lambda:service.create_consultation(session,member_id,**v),
                'consultation_schedule':lambda:service.schedule_consultation(session,member_id,actor=actor,**v),
                'consultation_opinion':lambda:service.consultation_opinion(session,member_id,actor=actor,role=payload.actor_role,**v),
                'consultation_conclude':lambda:service.conclude_consultation(session,member_id,actor=actor,role=payload.actor_role,**v),
                'action_plan':lambda:service.confirm_actions(session,member_id,actor=actor,**v),
                'stage_review':lambda:service.review_stage(session,member_id,actor=actor,**v),
                'service_link':lambda:service.link_service(session,member_id,**v),
                'family_add':lambda:service.family(session,member_id,actor=actor,**v),
            }
            row=actions[payload.action]();session.commit()
            return {'id':str(row.id),'status':getattr(row,'status','saved')}
        except (ValueError,TypeError,KeyError) as error:
            session.rollback();raise HTTPException(422,'参数或业务状态不允许此操作：'+str(error)) from error
    app.include_router(router)
