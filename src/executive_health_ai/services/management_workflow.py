"""Shared UI/API commands for human-owned annual care; callers own transactions."""
from datetime import date, datetime, time, timezone
from uuid import UUID
from sqlalchemy import select
from executive_health_ai.models import (Patient, HealthProgram, HealthJourney, AnnualHealthAccount,
    ProgramPhase, Task, DoctorReview, HealthProblem, Document, RiskEvent, ServiceRequest,
    HealthAssessment, Encounter, ClinicalRecommendation, MedicationPlan, AuditLog)
from executive_health_ai.models.base import utc_now
from executive_health_ai.models.management_workflow import (IntakeAssessment, ManagementLog,
    RecheckPlan, ConsultationCase, FamilyRelation, StageReview)
from executive_health_ai.services import chronic_care as care

STEPS = ['基础资料','家族健康史','个人病史','手术 / 住院史','过敏史','当前用药 / 营养补充','最近用药','生活方式','环境与暴露','会员重点关注','专项症状评估','确认提交']
TABLE_FIELDS = {
 '家族健康史':['疾病类别','具体疾病','患病家属','备注'],
 '个人病史':['疾病或问题','是否存在','确诊来源','确诊时间','持续管理','备注'],
 '手术 / 住院史':['类型','名称','日期','机构','持续随访','随访内容'],
 '过敏史':['类别','名称','过敏反应','来源'],
 '当前用药 / 营养补充':['名称','剂量','单位','频次','途径','开始日期','处方来源'],
 '最近用药':['名称','使用时间','原因','来源'],
 '专项症状评估':['症状','原始回答','频率或严重度','原始分数'],
}
PROFILE_FIELDS = {'生活方式':['睡眠','运动','饮食','烟草','饮酒','工作压力','休假','生活规律'],
 '环境与暴露':['空气污染','工业暴露','噪音','宠物','香氛','油烟 / 二手烟','潮湿 / 霉菌','装修','食品暴露','个人用品暴露']}
LOG_CATEGORIES = ['日常跟进','电话','微信','上门','健康宣教','用药提醒','数据跟进','检查提醒','复查','检查协调','陪诊','代问诊','会诊','设备','报告沟通','生活方式','服务执行','其他']
RECHECK_STATES = {'PENDING_CONFIRMATION':'待确认','TO_BOOK':'待预约','BOOKED':'已预约','TO_EXECUTE':'待执行','COMPLETED':'已完成','WAITING_REPORT':'待报告','WAITING_REVIEW':'待复核','CLOSED':'已关闭'}
CASE_STATES = {'PREPARING':'待准备','SCHEDULED':'待举行','WAITING_RESULT':'待整理结果','WAITING_ACTIONS':'待方案拆解','COMPLETED':'已完成'}


def required(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'请填写{label}。')
    return value.strip()


def owned(session, model, key, member_id):
    row = session.get(model, UUID(str(key))) if key else None
    if row is None or row.patient_id != member_id:
        raise ValueError('关联记录不存在或不属于此会员。')
    return row


def audit(session, member_id, actor, action, obj, role='health_manager'):
    session.flush()
    care._audit(session, member_id, required(actor, '记录人'), role, action, obj)


def task(session, member_id, program_id, title, instruction, owner, due, source):
    existing = session.scalar(select(Task).where(Task.patient_id == member_id, Task.source == source))
    if existing:
        return existing
    row = Task(patient_id=member_id, program_id=program_id, title=required(title,'下一步'),
        instruction=required(instruction,'执行内容'), assignee=required(owner,'负责人'),
        due_at=due, source=source, responsible_role='health_manager', status='PENDING')
    session.add(row); session.flush()
    return row


class ManagementWorkflowService:
    def start_intake(self, session, member_id, year, actor):
        """Open the existing member/year questionnaire, including legacy members."""
        if not session.get(Patient, member_id):
            raise ValueError('会员不存在。')
        if not isinstance(year, int) or not 1900 <= year <= 2200:
            raise ValueError('评估年度无效。')
        row = session.scalar(select(IntakeAssessment).where(
            IntakeAssessment.patient_id == member_id, IntakeAssessment.cycle_year == year))
        if row is None:
            row = IntakeAssessment(patient_id=member_id, cycle_year=year)
            session.add(row)
            audit(session, member_id, actor, 'intake_started', row)
        return row

    def enroll(self, session, *, name, start, end, owner, goal, advisor='', member_id=None):
        if end < start:
            raise ValueError('服务结束日期不能早于开始日期。')
        member = session.get(Patient, member_id) if member_id else None
        if member_id and not member:
            raise ValueError('会员不存在。')
        if member is None:
            member = Patient(display_name=required(name,'会员称呼'), timezone='Asia/Tokyo')
            session.add(member); session.flush()
        existing = session.scalar(select(HealthProgram).where(HealthProgram.patient_id == member.id,
            HealthProgram.cycle_year == start.year))
        if existing:
            raise ValueError('此会员本年度已入组，请从会员详情继续。')
        journey = session.scalar(select(HealthJourney).where(HealthJourney.patient_id == member.id))
        if not journey:
            journey = care.create_assessment(session, member.id, '入组待人工初评', required(goal,'年度目标'),
                'NEEDS_MEDICAL_EVALUATION', [], {}, required(owner,'责任健管'))
        program = care.create_program(session, journey, 'ANNUAL', f'{start.year}年度健康管理', goal, [], start, owner, end_date=end)
        program.status, program.current_phase = 'PLANNED', 'ONBOARDING'
        program.cycle_year, program.customer_advisor = start.year, advisor
        if not session.scalar(select(AnnualHealthAccount).where(AnnualHealthAccount.patient_id==member.id, AnnualHealthAccount.year==start.year)):
            care.create_annual_account(session, journey, start.year, goal, owner)
        session.add(IntakeAssessment(patient_id=member.id, cycle_year=start.year))
        audit(session, member.id, owner, 'member_enrolled', program)
        return program

    def save_intake(self, session, member_id, year, step, data, actor):
        row = session.scalar(select(IntakeAssessment).where(IntakeAssessment.patient_id==member_id, IntakeAssessment.cycle_year==year))
        if not row or row.status != 'DRAFT' or step not in STEPS[:-1]:
            raise ValueError('问卷不可编辑，请由健管退回补充后继续。')
        responses = dict(row.responses)
        if step == '基础资料':
            member = session.get(Patient, member_id)
            member.display_name = required(data.get('display_name'), '会员称呼')
            member.birth_date = date.fromisoformat(data['birth_date']) if data.get('birth_date') else None
            member.sex = data.get('sex') or None
            responses[step] = {'profile_confirmed':True}  # never duplicate profile facts
        elif step in TABLE_FIELDS:
            if not isinstance(data, list):
                raise ValueError('请按结构化行填写。')
            clean = []
            for item in data:
                if not isinstance(item, dict) or set(item) - set(TABLE_FIELDS[step]):
                    raise ValueError('问卷字段不匹配。')
                item = {k:str(v or '').strip() for k,v in item.items()}
                if step == '专项症状评估' and item.get('原始分数','') not in {'','0','1','2','3','4'}:
                    raise ValueError('原始分数须为0至4；原资料未提供时留空，不推算分数。')
                clean.append(item)
            responses[step] = clean
        elif step in PROFILE_FIELDS:
            if not isinstance(data, dict) or set(data) - set(PROFILE_FIELDS[step]):
                raise ValueError('画像字段不匹配。')
            responses[step] = {k:str(v).strip() for k,v in data.items()}
        else:
            row.member_concern = required(data.get('concern'), '会员自己希望改善的问题')
            responses[step] = {'concern':row.member_concern}
        row.responses = responses
        audit(session, member_id, actor, 'intake_draft_saved', row, 'member')
        return row

    def submit_intake(self, session, member_id, assessment_id, actor):
        row = owned(session, IntakeAssessment, assessment_id, member_id)
        missing = [s for s in STEPS[:-1] if s not in row.responses]
        if row.status != 'DRAFT' or missing:
            raise ValueError('请逐步确认问卷（无已知情况可保存空表）：' + '、'.join(missing))
        from executive_health_ai.services.assessment_import import AssessmentImportService
        imports = AssessmentImportService()
        imports.validate_submit(session, row)
        row.status, row.submitted_at, row.review_status = 'SUBMITTED', utc_now(), 'READY_FOR_REVIEW'
        row.review = {**row.review, 'member_statement':row.member_concern, 'lifestyle':row.responses.get('生活方式',{}),
            'history':row.responses.get('个人病史',[]), 'missing':['报告及自述资料均需人工核对'], 'confirmation':['问卷不是诊断，核对病史与用药来源']}
        if row.review.get('exception_intake',{}).get('completed_at'):
            from executive_health_ai.services.intake_handoff import assessment_confirmed
            assessment_confirmed(session,row,actor)
        else:
            imports.finish(session, row, actor)
        audit(session, member_id, actor, 'intake_submitted', row, 'member')
        return row

    def review_intake(self, session, member_id, assessment_id, *, focus, missing, tests, medical_question, annual_focus, actor, decision):
        row = owned(session, IntakeAssessment, assessment_id, member_id)
        if row.status not in {'SUBMITTED','CONFIRMED'}:
            raise ValueError('先提交问卷。')
        if decision == 'RETURN':
            row.status, row.review_status = 'DRAFT','DRAFT'
        elif decision in {'DRAFT','CONFIRM'}:
            row.status, row.review_status = 'SUBMITTED', 'DRAFT'
            prior_medical=(row.review.get('medical_question',''),row.review.get('supplementary_tests',''))
            if row.doctor_review_id and prior_medical!=(medical_question,tests):
                # A confirmation for a different question cannot approve a new one.
                row.doctor_review_id=None
            row.professional_focus = required(focus,'专业管理重点')
            row.review = {**row.review, 'missing':missing, 'supplementary_tests':tests,
                'medical_question':medical_question, 'annual_focus':required(annual_focus,'初步年度管理重点')}
            row.reviewed_by = required(actor,'初评人')
            if medical_question.strip() or tests.strip():
                if not row.doctor_review_id:
                    problem = HealthProblem(patient_id=member_id,title='入组资料待医学确认',description=medical_question or tests,source='intake_review',owner=actor)
                    session.add(problem); session.flush()
                    from executive_health_ai.services.member_management_projection import intake_program
                    program = intake_program(session,row)
                    review = DoctorReview(patient_id=member_id, program_id=program.id if program else None, health_problem_id=problem.id, doctor_name='待分配医生',
                        department='待确认',doctor_brief='会员自述与健管初评，尚非正式医学结论',
                        question_for_doctor=medical_question or tests,opinion='',status='PENDING')
                    session.add(review); session.flush(); row.doctor_review_id=review.id
                review = session.get(DoctorReview,row.doctor_review_id)
                if review.status != 'CONFIRMED':
                    row.review_status='WAITING_MEDICAL_REVIEW'
                elif decision=='CONFIRM':
                    row.review_status='CONFIRMED'; row.status='CONFIRMED'
            elif decision=='CONFIRM':
                row.review_status='CONFIRMED'; row.status='CONFIRMED'
            else:
                row.review_status='DRAFT'
        else:
            raise ValueError('不支持的初评决定。')
        if row.review_status=='CONFIRMED' and row.doctor_review_id:
            reviewed=session.get(DoctorReview,row.doctor_review_id)
            problem=session.get(HealthProblem,reviewed.health_problem_id) if reviewed else None
            # Close only the administrative intake-confirmation placeholder,
            # never an underlying diagnosis, risk or other health problem.
            if reviewed and reviewed.status=='CONFIRMED' and problem and problem.source=='intake_review':
                problem.status='CLOSED'
        if row.review_status == 'CONFIRMED':
            row.review = {**row.review, 'confirmed_at': utc_now().isoformat()}
        audit(session,member_id,actor,'intake_manager_reviewed',row)
        return row

    def confirm_medication(self, session, member_id, assessment_id, index, *, actor, role, evidence):
        if role != 'doctor':
            raise ValueError('用药事实须由医生核对正式来源后确认。')
        row = owned(session,IntakeAssessment,assessment_id,member_id)
        candidates = row.responses.get('当前用药 / 营养补充',[])
        if row.status not in {'SUBMITTED','CONFIRMED'} or index < 0 or index >= len(candidates):
            raise ValueError('未找到已提交用药候选。')
        key=f'medication:{index}'
        if row.review.get(key):
            return session.get(MedicationPlan,UUID(row.review[key]))
        data=candidates[index]
        required(evidence,'正式医疗记录依据')
        med=MedicationPlan(patient_id=member_id, drug_name=required(data.get('名称'),'药品名称'),
            dose=required(data.get('剂量'),'已核对剂量'),dose_unit=required(data.get('单位'),'单位'),
            frequency=required(data.get('频次'),'频次'),route=required(data.get('途径'),'途径'),
            start_date=date.fromisoformat(required(data.get('开始日期'),'开始日期')), prescriber_name=actor)
        session.add(med);session.flush()
        row.review={**row.review,key:str(med.id),key+':evidence':evidence}
        audit(session,member_id,actor,'intake_medication_confirmed',med,'doctor')
        return med

    def add_phase(self, session, member_id, program_id, *, title, goal, content, start, end, owner):
        program=owned(session,HealthProgram,program_id,member_id)
        phases=list(session.scalars(select(ProgramPhase).where(ProgramPhase.program_id==program.id).order_by(ProgramPhase.sequence)))
        if start<program.start_date or end<start or (program.end_date and end>program.end_date) or any(start<=p.end_date and end>=p.start_date for p in phases):
            raise ValueError('阶段日期须在服务周期内，且不能与其他阶段重叠。')
        sequence=max([p.sequence for p in phases],default=0)+1
        phase=ProgramPhase(program_id=program.id,phase_code=f'PHASE_{sequence}',title=required(title,'阶段名称'),
            goal=required(goal,'阶段目标'),management_content=required(content,'管理内容'),owner=required(owner,'负责人'),
            start_date=start,end_date=end,sequence=sequence,status='PLANNED')
        session.add(phase);audit(session,member_id,owner,'phase_added',phase)
        return phase

    def start_program(self,session,member_id,program_id,actor):
        program=owned(session,HealthProgram,program_id,member_id)
        if program.status != 'PLANNED':
            raise ValueError('年度方案已启动，不能重新覆盖当前阶段。')
        intake=session.scalar(select(IntakeAssessment).where(IntakeAssessment.patient_id==member_id,IntakeAssessment.cycle_year==program.cycle_year))
        baseline=session.scalar(select(HealthAssessment).where(HealthAssessment.patient_id==member_id,HealthAssessment.cycle_year==program.cycle_year,HealthAssessment.status=='CONFIRMED'))
        phase=session.scalar(select(ProgramPhase).where(ProgramPhase.program_id==program.id).order_by(ProgramPhase.sequence))
        if not intake or intake.review_status!='CONFIRMED' or not baseline or not phase:
            raise ValueError('需完成健管初评、当年已确认基线并建立阶段后启动。')
        program.status='ACTIVE';program.current_phase=phase.phase_code;phase.status='ACTIVE'
        audit(session,member_id,actor,'annual_program_started',program)
        return program

    def record_log(self,session,member_id,program_id,*,actor,request_key,create_followup=False,**data):
        program=owned(session,HealthProgram,program_id,member_id)
        prior=session.scalar(select(ManagementLog).where(ManagementLog.request_key==request_key))
        if prior:
            if prior.patient_id!=member_id: raise ValueError('重复请求不属于此会员。')
            return prior
        for field,label in [('member_issue','发生了什么'),('manager_action','我做了什么'),('owner','负责人')]:
            required(data.get(field),label)
        if data.get('category') not in LOG_CATEGORIES: raise ValueError('请选择记录类型。')
        for field,model in [('related_task_id',Task),('related_risk_id',RiskEvent),('related_doctor_review_id',DoctorReview),('related_service_id',ServiceRequest),('related_document_id',Document)]:
            if data.get(field): owned(session,model,data[field],member_id)
        if create_followup and (not data.get('follow_up_at') or not data.get('next_action','').strip()):
            raise ValueError('创建下一步需要填写行动和跟进日期。')
        log=ManagementLog(patient_id=member_id,program_id=program.id,created_by=actor,request_key=request_key,**data)
        session.add(log);session.flush()
        if create_followup:
            follow=task(session,member_id,program.id,log.next_action,log.next_action,log.owner,log.follow_up_at,f'management_log:{log.id}')
            log.follow_up_task_id=follow.id
        audit(session,member_id,actor,'management_log_recorded',log)
        return log

    def create_recheck(self,session,member_id,program_id,*,title,reason,planned_at,owner,provider='',doctor_review_id=None,evidence=''):
        program=owned(session,HealthProgram,program_id,member_id)
        if doctor_review_id:
            review=owned(session,DoctorReview,doctor_review_id,member_id)
            if review.status!='CONFIRMED': raise ValueError('检查依据的医生意见尚未确认。')
        elif not evidence.strip():
            raise ValueError('请记录已有正式医疗建议依据，健管不自行开检查。')
        row=RecheckPlan(patient_id=member_id,program_id=program.id,title=required(title,'检查项目'),reason=required(reason,'检查原因'),
            planned_at=planned_at,owner=required(owner,'负责人'),provider=provider,doctor_review_id=doctor_review_id,evidence=evidence)
        session.add(row);audit(session,member_id,owner,'recheck_created',row)
        return row

    def advance_recheck(self,session,member_id,recheck_id,*,status,actor,result='',document_id=None,next_recheck_at=None):
        row=owned(session,RecheckPlan,recheck_id,member_id)
        states=list(RECHECK_STATES)
        if status not in states or states.index(status)!=states.index(row.status)+1:
            raise ValueError('请按预约、执行、报告与复核顺序推进。')
        if document_id: owned(session,Document,document_id,member_id)
        if status in {'WAITING_REVIEW','CLOSED'} and not (document_id or row.document_id):
            raise ValueError('先关联正式报告，再交付复核。')
        if status=='CLOSED' and not result.strip(): raise ValueError('请记录已人工复核的结果。')
        row.status=status;row.result=result or row.result;row.document_id=document_id or row.document_id
        row.next_recheck_at=next_recheck_at or row.next_recheck_at
        if status=='CLOSED' and row.next_recheck_at:
            task(session,member_id,row.program_id,'确认下一次复查：'+row.title,'核对医生意见后安排下一次复查',row.owner,row.next_recheck_at,f'recheck_next:{row.id}')
        audit(session,member_id,actor,'recheck_progressed',row)
        return row

    def create_consultation(self,session,member_id,*,reason,scheduled_at,location,participants,evidence,owner,program_id=None):
        if program_id: owned(session,HealthProgram,program_id,member_id)
        if not participants or any(not p.get('doctor') or not p.get('department') for p in participants):
            raise ValueError('至少填写一位参加医生和科室。')
        enc=Encounter(patient_id=member_id,encounter_at=scheduled_at,encounter_type='case_conference',department='多学科',
            clinician_name='待会诊',reason=required(reason,'会诊原因'),status='scheduled')
        session.add(enc);session.flush()
        row=ConsultationCase(patient_id=member_id,program_id=program_id,encounter_id=enc.id,scheduled_at=scheduled_at,
            location=required(location,'地点或方式'),participants=participants,evidence=required(evidence,'关键资料'),owner=required(owner,'负责人'))
        session.add(row);audit(session,member_id,owner,'consultation_requested',row)
        return row

    def schedule_consultation(self,session,member_id,case_id,actor):
        case=owned(session,ConsultationCase,case_id,member_id)
        if case.status!='PREPARING': raise ValueError('此会诊已安排。')
        case.status='SCHEDULED';audit(session,member_id,actor,'consultation_scheduled',case)
        return case

    def consultation_opinion(self,session,member_id,case_id,*,actor,department,content,role):
        if role!='doctor': raise ValueError('仅医生能提交医学意见。')
        case=owned(session,ConsultationCase,case_id,member_id)
        if case.status not in {'SCHEDULED','WAITING_RESULT'}: raise ValueError('会诊尚未进入意见整理阶段。')
        if not any(p['doctor']==actor and p['department']==department for p in case.participants):
            raise ValueError('请使用本次会诊参加医生身份提交。')
        opinion=ClinicalRecommendation(encounter_id=case.encounter_id,patient_id=member_id,department=department,
            clinician_name=actor,recommendation_type='case_conference',content=required(content,'医生意见'))
        session.add(opinion);case.status='WAITING_RESULT';audit(session,member_id,actor,'consultation_opinion_recorded',opinion,'doctor')
        return opinion

    def conclude_consultation(self,session,member_id,case_id,*,actor,role,conclusion):
        if role!='doctor': raise ValueError('综合医学结论须由参加医生确认。')
        case=owned(session,ConsultationCase,case_id,member_id)
        opinions=list(session.scalars(select(ClinicalRecommendation).where(ClinicalRecommendation.encounter_id==case.encounter_id)))
        if case.status!='WAITING_RESULT' or actor not in {p['doctor'] for p in case.participants} or any(not any(o.clinician_name==p['doctor'] and o.department==p['department'] for o in opinions) for p in case.participants):
            raise ValueError('请先收齐各参加医生的意见。')
        case.conclusion=required(conclusion,'综合结论');case.concluded_by=actor;case.status='WAITING_ACTIONS'
        encounter=session.get(Encounter,case.encounter_id);encounter.summary=case.conclusion;encounter.status='completed';encounter.clinician_name=actor
        audit(session,member_id,actor,'consultation_concluded',case,'doctor')
        return case

    def confirm_actions(self,session,member_id,case_id,*,actions,actor,confirm=False):
        case=owned(session,ConsultationCase,case_id,member_id)
        if case.status=='COMPLETED': return case
        if case.status!='WAITING_ACTIONS' or not actions: raise ValueError('先完成会诊结论，再保存方案拆解。')
        clean=[]
        for a in actions:
            if a.get('category') not in {'复查事项','用药管理事项','生活方式事项','服务事项','医生复核'}: raise ValueError('请选择行动类型。')
            clean.append({'category':a['category'],'title':required(a.get('title'),'行动'),
                'owner':required(a.get('owner'),'负责人'),'due':date.fromisoformat(a['due']).isoformat()})
        case.action_drafts=clean
        if confirm:
            for i,a in enumerate(clean):
                task(session,member_id,case.program_id,a['title'],'依据已确认会诊意见落实：'+a['category']+'；不授权自行改变医疗方案。',a['owner'],datetime.combine(date.fromisoformat(a['due']),time(9),timezone.utc),f'consultation:{case.id}:{i}')
            case.status='COMPLETED';case.confirmed_by=actor;case.confirmed_at=utc_now()
        audit(session,member_id,actor,'consultation_actions_confirmed' if confirm else 'consultation_actions_drafted',case)
        return case

    def review_stage(self,session,member_id,phase_id,*,content,decision,actor):
        phase=session.get(ProgramPhase,UUID(str(phase_id)))
        if not phase: raise ValueError('阶段不存在。')
        program=owned(session,HealthProgram,phase.program_id,member_id)
        prior=session.scalar(select(StageReview).where(StageReview.phase_id==phase.id))
        if prior: raise ValueError('此阶段已复盘，请查看记录。')
        if phase.status!='ACTIVE' or decision not in {'CONTINUE','ADJUST','DOCTOR_REVIEW','STABILIZE','NEXT_PHASE'}:
            raise ValueError('请对当前执行阶段选择管理决定。')
        for key in ['实际完成','未解决问题','下一阶段建议']: required(content.get(key),key)
        next_phase=session.scalar(select(ProgramPhase).where(ProgramPhase.program_id==program.id,ProgramPhase.sequence>phase.sequence).order_by(ProgramPhase.sequence))
        if decision=='NEXT_PHASE' and not next_phase: raise ValueError('请先建立下一阶段。')
        row=StageReview(patient_id=member_id,program_id=program.id,phase_id=phase.id,content=content,decision=decision,owner=actor)
        session.add(row);session.flush();phase.result_feedback=content['实际完成']
        if decision=='NEXT_PHASE':
            phase.status='COMPLETED';phase.completed_at=utc_now();next_phase.status='ACTIVE';program.current_phase=next_phase.phase_code
        else:
            program.next_decision=decision
            task(session,member_id,program.id,'落实阶段复盘：'+phase.title,content['下一阶段建议'],program.owner,utc_now(),f'stage_result:{row.id}')
        if decision=='DOCTOR_REVIEW':
            problem=HealthProblem(patient_id=member_id,program_id=program.id,title='阶段复盘需医生判断',description=content['未解决问题'],source='stage_review',owner=actor)
            session.add(problem);session.flush()
            session.add(DoctorReview(patient_id=member_id,program_id=program.id,health_problem_id=problem.id,doctor_name='待分配医生',department='待确认',doctor_brief=content['实际完成'],question_for_doctor=content['未解决问题'],opinion='',status='PENDING'))
        audit(session,member_id,actor,'stage_review_recorded',row)
        return row

    def advance_phase(self,session,member_id,phase_id,actor):
        phase=session.get(ProgramPhase,UUID(str(phase_id)))
        if not phase:raise ValueError('阶段不存在。')
        program=owned(session,HealthProgram,phase.program_id,member_id)
        reviewed=session.scalar(select(StageReview).where(StageReview.phase_id==phase.id))
        next_phase=session.scalar(select(ProgramPhase).where(ProgramPhase.program_id==program.id,ProgramPhase.sequence>phase.sequence).order_by(ProgramPhase.sequence))
        pending=session.scalar(select(DoctorReview).where(DoctorReview.program_id==program.id,DoctorReview.status=='PENDING'))
        if phase.status!='ACTIVE' or not reviewed or not next_phase or pending:
            raise ValueError('需要当前阶段已复盘、后续阶段已建立，且医学复核已完成。')
        phase.status='COMPLETED';phase.completed_at=utc_now();next_phase.status='ACTIVE';program.current_phase=next_phase.phase_code
        audit(session,member_id,actor,'reviewed_phase_advanced',phase)
        return next_phase

    def link_service(self,session,member_id,service_id,program_id,phase_id=None,task_id=None):
        service=owned(session,ServiceRequest,service_id,member_id)
        program=owned(session,HealthProgram,program_id,member_id)
        if phase_id:
            phase=session.get(ProgramPhase,phase_id)
            if not phase or phase.program_id!=program.id: raise ValueError('阶段不属于当前周期。')
        if task_id: owned(session,Task,task_id,member_id)
        service.program_id=program.id;service.phase_id=phase_id;service.management_task_id=task_id
        audit(session,member_id,program.owner,'service_cycle_linked',service)
        return service

    def family(self,session,member_id,*,relationship,contact_name,contact='',emergency=False,shared_entitlement=False,related_patient_id=None,actor):
        if related_patient_id and (related_patient_id==member_id or not session.get(Patient,related_patient_id)):
            raise ValueError('关联会员无效。')
        row=FamilyRelation(patient_id=member_id,relationship=required(relationship,'关系'),contact_name=required(contact_name,'联系人'),contact=contact,
            emergency=emergency,shared_entitlement=shared_entitlement,related_patient_id=related_patient_id)
        session.add(row);audit(session,member_id,actor,'family_relation_added',row)
        return row
