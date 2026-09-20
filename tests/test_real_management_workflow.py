"""Synthetic workflow contracts, isolation, human gates and due projections."""
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from executive_health_ai.models import Base, Patient, Task, HealthProblem, HealthAssessment, RiskEvent, MedicationPlan, ProgramPhase, Document, ServiceRequest, ServiceCatalogItem, DoctorReview
from executive_health_ai.models.management_workflow import IntakeAssessment, ManagementLog, StageReview
from executive_health_ai.services.management_workflow import ManagementWorkflowService, STEPS, TABLE_FIELDS, PROFILE_FIELDS
from executive_health_ai.services.member_management_projection import MemberManagementProjection, management_work_items
from executive_health_ai.services.operational_worklist import OperationalWorklistService
from executive_health_ai.services.longitudinal import HealthTimelineService
from executive_health_ai.services import care_commands

NOW=datetime.now(timezone.utc)
DAY=NOW.date()
S=ManagementWorkflowService()


@pytest.fixture
def db():
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with sessionmaker(engine,expire_on_commit=False)() as session:
        yield session
    engine.dispose()


def enrolled(db):
    return S.enroll(db,name='Synthetic Workflow Member',start=DAY-timedelta(days=30),end=DAY+timedelta(days=334),owner='Synthetic Manager',goal='合成年度执行目标')


def submitted(db,program):
    for step in STEPS[:-1]:
        data=({'display_name':'Synthetic Workflow Member','sex':'male','birth_date':'1980-01-01'} if step=='基础资料' else
            [] if step in TABLE_FIELDS else {k:'未提供' for k in PROFILE_FIELDS[step]} if step in PROFILE_FIELDS else {'concern':'希望规律记录睡眠'})
        S.save_intake(db,program.patient_id,program.cycle_year,step,data,'Synthetic Member')
    row=db.scalar(select(IntakeAssessment).where(IntakeAssessment.patient_id==program.patient_id))
    return S.submit_intake(db,program.patient_id,row.id,'Synthetic Member')


def initial_review(db,p,row,medical=''):
    return S.review_intake(db,p.patient_id,row.id,focus='核对资料完整度',missing='报告',tests='',medical_question=medical,annual_focus='建立持续执行习惯',actor='Synthetic Manager',decision='CONFIRM')


def phases(db,p):
    first=S.add_phase(db,p.patient_id,p.id,title='资料整合',goal='核对完成',content='人工核对',start=p.start_date,end=DAY,owner=p.owner)
    second=S.add_phase(db,p.patient_id,p.id,title='持续执行',goal='落实计划',content='持续跟进',start=DAY+timedelta(days=1),end=DAY+timedelta(days=30),owner=p.owner)
    return first,second


def baseline(db,p):
    db.add(HealthAssessment(patient_id=p.patient_id,assessment_type='INITIAL',cycle_year=p.cycle_year,version=1,title='Synthetic confirmed baseline',summary='Synthetic facts',baseline_json={},source_references_json={},created_by='Synthetic Clinician',status='CONFIRMED',confirmed_at=NOW))
    db.flush()


def test_enrollment_reuses_program_and_profile_no_duplicate_year(db):
    p=enrolled(db)
    assert p.program_type=='ANNUAL' and p.status=='PLANNED'
    with pytest.raises(ValueError):S.enroll(db,name='unused',member_id=p.patient_id,start=p.start_date,end=p.end_date,owner=p.owner,goal='goal')
    assert db.scalar(select(func.count(Patient.id)))==1


def test_draft_resume_submit_does_not_create_diagnosis_or_risk(db):
    p=enrolled(db)
    row=submitted(db,p)
    assert row.review_status=='READY_FOR_REVIEW' and row.version=='healthops-intake-v1'
    assert db.scalar(select(func.count(HealthProblem.id)))==0
    assert db.scalar(select(func.count(RiskEvent.id)))==0
    assert db.scalar(select(func.count(MedicationPlan.id)))==0
    assert db.get(Patient,p.patient_id).birth_date==date(1980,1,1)
    assert row.responses['基础资料']=={'profile_confirmed':True}
    assert any(i.source_type=='intake_review' for i in management_work_items(db,NOW))


@pytest.mark.parametrize('step,data',[
 ('家族健康史',[{'疾病类别':'合成类别','具体疾病':'自述待核对','患病家属':'长辈','备注':'未知'}]),
 ('个人病史',[{'疾病或问题':'自述事项','是否存在':'未知','确诊来源':'待核对','持续管理':'未知'}]),
 ('手术 / 住院史',[{'类型':'住院','名称':'合成记录','日期':'2020-01-01','持续随访':'未知'}]),
 ('过敏史',[{'类别':'其他','名称':'未确认','过敏反应':'自述反应','来源':'本人'}]),
 ('专项症状评估',[{'症状':'合成症状','原始回答':'偶尔','频率或严重度':'频率','原始分数':'2'}]),
])
def test_structured_self_reports_are_retained_without_promotion(db,step,data):
    p=enrolled(db);row=S.save_intake(db,p.patient_id,p.cycle_year,step,data,'Synthetic Member')
    assert row.responses[step]==data
    assert db.scalar(select(func.count(HealthProblem.id)))==0


def test_missing_steps_and_invalid_scores_rejected(db):
    p=enrolled(db);row=db.scalar(select(IntakeAssessment))
    with pytest.raises(ValueError):S.submit_intake(db,p.patient_id,row.id,'member')
    with pytest.raises(ValueError):S.save_intake(db,p.patient_id,p.cycle_year,'专项症状评估',[{'原始分数':'5'}],'member')


def test_member_concern_is_distinct_and_medical_confirmation_blocks_initial_review(db):
    p=enrolled(db);row=submitted(db,p);initial_review(db,p,row,'请核对自述问题与补充检查必要性')
    assert row.member_concern!=row.professional_focus
    assert row.review_status=='WAITING_MEDICAL_REVIEW'
    review=db.get(DoctorReview,row.doctor_review_id)
    assert review.status=='PENDING'
    care_commands.complete_review(db,review,'Synthetic Doctor','Synthetic General','已核对资料','健管继续资料整理',NOW)
    initial_review(db,p,row,'请核对自述问题与补充检查必要性')
    assert row.review_status=='CONFIRMED'
    assert db.get(HealthProblem,review.health_problem_id).status=='CLOSED'
    assert any(i.source_type=='task' and i.member_id==p.patient_id for i in OperationalWorklistService().list_items(db,NOW))


def test_medication_requires_doctor_and_formal_source(db):
    p=enrolled(db)
    S.save_intake(db,p.patient_id,p.cycle_year,'当前用药 / 营养补充',[{'名称':'Synthetic medication','剂量':'1','单位':'unit','频次':'核对处方','途径':'核对处方','开始日期':DAY.isoformat(),'处方来源':'Synthetic record'}],'member')
    row=db.scalar(select(IntakeAssessment));row.status='SUBMITTED'
    with pytest.raises(ValueError):S.confirm_medication(db,p.patient_id,row.id,0,actor='manager',role='health_manager',evidence='record')
    with pytest.raises(ValueError):S.confirm_medication(db,p.patient_id,row.id,0,actor='doctor',role='doctor',evidence='')
    med=S.confirm_medication(db,p.patient_id,row.id,0,actor='Synthetic Doctor',role='doctor',evidence='Synthetic signed record')
    assert S.confirm_medication(db,p.patient_id,row.id,0,actor='Synthetic Doctor',role='doctor',evidence='Synthetic signed record').id==med.id
    assert db.scalar(select(func.count(MedicationPlan.id)))==1


def test_cycle_start_requires_confirmed_intake_baseline_and_phase(db):
    p=enrolled(db);first,second=phases(db,p)
    with pytest.raises(ValueError):S.start_program(db,p.patient_id,p.id,p.owner)
    row=submitted(db,p);initial_review(db,p,row);baseline(db,p)
    S.start_program(db,p.patient_id,p.id,p.owner)
    assert first.status=='ACTIVE' and second.status=='PLANNED'
    assert MemberManagementProjection().member(db,p.patient_id).onboarding=='持续管理中'
    assert any(i.source_type=='stage_review' for i in management_work_items(db,NOW))


def test_phase_dates_overlap_and_outside_cycle_rejected(db):
    p=enrolled(db);phases(db,p)
    with pytest.raises(ValueError):S.add_phase(db,p.patient_id,p.id,title='overlap',goal='goal',content='content',start=DAY,end=DAY+timedelta(days=1),owner=p.owner)


def test_log_creates_exactly_one_followup_and_does_not_pollute_timeline(db):
    p=enrolled(db);key=str(uuid4())
    data=dict(actor=p.owner,request_key=key,create_followup=True,occurred_at=NOW,category='电话',member_issue='确认复查安排',manager_action='联系会员核对日期',result='已收到回复',next_action='确认复查预约',follow_up_at=NOW,owner=p.owner)
    log=S.record_log(db,p.patient_id,p.id,**data);again=S.record_log(db,p.patient_id,p.id,**data)
    assert log.id==again.id and log.follow_up_task_id
    assert db.scalar(select(func.count(Task.id)))==1
    assert any(i.source_id==log.follow_up_task_id for i in OperationalWorklistService().list_items(db,NOW))
    assert not any(e.source=='management_log' for e in HealthTimelineService().get_timeline(db,p.patient_id))


def test_log_validation_cross_member_and_followup_missing_date(db):
    p=enrolled(db)
    with pytest.raises(ValueError):S.record_log(db,p.patient_id,p.id,actor=p.owner,request_key=str(uuid4()),create_followup=True,occurred_at=NOW,category='电话',member_issue='issue',manager_action='action',owner=p.owner)
    other=Patient(display_name='Synthetic Other',timezone='UTC');db.add(other);db.flush()
    with pytest.raises(ValueError):S.record_log(db,other.id,p.id,actor='other',request_key=str(uuid4()))


def test_recheck_due_enters_queue_report_required_and_next_followup(db):
    p=enrolled(db)
    with pytest.raises(ValueError):S.create_recheck(db,p.patient_id,p.id,title='复查',reason='核对',planned_at=NOW,owner=p.owner)
    row=S.create_recheck(db,p.patient_id,p.id,title='合成复查',reason='已有建议',planned_at=NOW,owner=p.owner,evidence='Synthetic medical record')
    assert any(i.source_id==row.id for i in OperationalWorklistService().list_items(db,NOW))
    for state in ['TO_BOOK','BOOKED','TO_EXECUTE','COMPLETED','WAITING_REPORT']:S.advance_recheck(db,p.patient_id,row.id,status=state,actor=p.owner)
    with pytest.raises(ValueError):S.advance_recheck(db,p.patient_id,row.id,status='WAITING_REVIEW',actor=p.owner)
    doc=Document(patient_id=p.patient_id,document_type='report',title='Synthetic report',storage_reference='synthetic://report',source='synthetic');db.add(doc);db.flush()
    S.advance_recheck(db,p.patient_id,row.id,status='WAITING_REVIEW',actor=p.owner,document_id=doc.id)
    S.advance_recheck(db,p.patient_id,row.id,status='CLOSED',actor=p.owner,result='人工核对完成',next_recheck_at=NOW+timedelta(days=30))
    assert db.scalar(select(Task).where(Task.source==f'recheck_next:{row.id}'))


def test_consultation_requires_all_opinions_then_manager_confirms_actions(db):
    p=enrolled(db)
    case=S.create_consultation(db,p.patient_id,program_id=p.id,reason='Synthetic discussion',scheduled_at=NOW,location='线上',participants=[{'doctor':'Doctor A','department':'General'},{'doctor':'Doctor B','department':'Review'}],evidence='Synthetic evidence',owner=p.owner)
    S.schedule_consultation(db,p.patient_id,case.id,p.owner)
    S.consultation_opinion(db,p.patient_id,case.id,actor='Doctor A',department='General',content='需要进一步核对资料',role='doctor')
    with pytest.raises(ValueError):S.conclude_consultation(db,p.patient_id,case.id,actor='Doctor A',role='doctor',conclusion='not yet')
    S.consultation_opinion(db,p.patient_id,case.id,actor='Doctor B',department='Review',content='已提供本科意见',role='doctor')
    S.conclude_consultation(db,p.patient_id,case.id,actor='Doctor A',role='doctor',conclusion='健管协调后续已确认安排')
    actions=[{'category':'复查事项','title':'协调既有检查建议','owner':p.owner,'due':DAY.isoformat()}]
    S.confirm_actions(db,p.patient_id,case.id,actions=actions,actor=p.owner)
    assert db.scalar(select(func.count(Task.id)))==0
    assert any(i.source_id==case.id and i.title=='会诊方案拆解' for i in management_work_items(db,NOW))
    S.confirm_actions(db,p.patient_id,case.id,actions=actions,actor=p.owner,confirm=True)
    S.confirm_actions(db,p.patient_id,case.id,actions=actions,actor=p.owner,confirm=True)
    assert db.scalar(select(func.count(Task.id)))==1
    assert any(e.source=='consultation' for e in HealthTimelineService().get_timeline(db,p.patient_id))


def test_stage_review_advances_next_phase_and_is_recorded(db):
    p=enrolled(db);first,second=phases(db,p);first.status='ACTIVE';p.current_phase=first.phase_code
    review=S.review_stage(db,p.patient_id,first.id,content={'实际完成':'完成资料核对','未解决问题':'暂无新问题','下一阶段建议':'继续人工跟进','关键指标变化':'仅记录观察变化'},decision='NEXT_PHASE',actor=p.owner)
    assert first.status=='COMPLETED' and second.status=='ACTIVE' and p.current_phase==second.phase_code
    assert first.completed_at and first.result_feedback
    assert any(e.source=='stage_review' for e in HealthTimelineService().get_timeline(db,p.patient_id))
    assert not any(i.source_id==first.id for i in management_work_items(db,NOW))


def test_service_and_family_use_member_context(db):
    p=enrolled(db);first,_=phases(db,p)
    catalog=ServiceCatalogItem(code='SYNTHETIC',name='Synthetic service',category='care',description='Synthetic service');db.add(catalog);db.flush()
    request=ServiceRequest(patient_id=p.patient_id,service_item_id=catalog.id,requested_by=p.owner);db.add(request);db.flush()
    S.link_service(db,p.patient_id,request.id,p.id,first.id)
    assert request.program_id==p.id and request.phase_id==first.id
    relation=S.family(db,p.patient_id,relationship='家属',contact_name='Synthetic Contact',emergency=True,actor=p.owner)
    assert relation.emergency and MemberManagementProjection().member(db,p.patient_id).family


def test_shared_projection_owner_phase_and_services(db):
    p=enrolled(db);first,_=phases(db,p);first.status='ACTIVE';db.flush()
    a=MemberManagementProjection().member(db,p.patient_id)
    b=next(v for m,v in MemberManagementProjection().annual(db) if m.id==p.patient_id)
    assert a.owner==b.owner==p.owner
    assert a.current_phase.id==b.current_phase.id==first.id
    assert a.services==b.services and a.rechecks==b.rechecks


def test_changed_medical_question_requires_fresh_confirmation(db):
    p=enrolled(db);row=submitted(db,p);initial_review(db,p,row,'第一个待核对问题')
    original=row.doctor_review_id
    care_commands.complete_review(db,db.get(DoctorReview,original),'Synthetic Doctor','Synthetic General','已核对','继续跟进',NOW)
    initial_review(db,p,row,'第一个待核对问题')
    assert row.status=='CONFIRMED'
    initial_review(db,p,row,'不同的待核对问题')
    assert row.doctor_review_id!=original
    assert row.status=='SUBMITTED' and row.review_status=='WAITING_MEDICAL_REVIEW'


def test_continue_review_requires_explicit_later_phase_handoff(db):
    p=enrolled(db);first,second=phases(db,p);first.status='ACTIVE';p.status='ACTIVE';p.current_phase=first.phase_code
    S.review_stage(db,p.patient_id,first.id,content={'实际完成':'部分完成','未解决问题':'资料尚待补齐','下一阶段建议':'继续整理后人工交接'},decision='CONTINUE',actor=p.owner)
    assert first.status=='ACTIVE' and second.status=='PLANNED'
    S.advance_phase(db,p.patient_id,first.id,p.owner)
    assert first.status=='COMPLETED' and second.status=='ACTIVE'
    with pytest.raises(ValueError):S.start_program(db,p.patient_id,p.id,p.owner)


def test_unlinked_service_and_intake_review_remain_discoverable(db):
    p=enrolled(db);row=submitted(db,p);initial_review(db,p,row,'核对资料')
    catalog=ServiceCatalogItem(code='SYNTHETIC_UNLINKED',name='Synthetic service',category='care',description='Synthetic')
    db.add(catalog);db.flush()
    service=ServiceRequest(patient_id=p.patient_id,service_item_id=catalog.id,requested_by=p.owner)
    db.add(service);db.flush()
    view=MemberManagementProjection().member(db,p.patient_id)
    assert service.id in {s.id for s in view.services}
    assert row.doctor_review_id in {r.id for r in view.doctor_reviews}
