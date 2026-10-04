"""Intake entry, persistence and the shared archive/work-queue contract."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, func
from streamlit.testing.v1 import AppTest

from executive_health_ai.database import SessionLocal
from executive_health_ai.models import Patient, HealthProblem, RiskEvent, MedicationPlan
from executive_health_ai.models.management_workflow import IntakeAssessment
from executive_health_ai.services.management_workflow import ManagementWorkflowService, STEPS, TABLE_FIELDS, PROFILE_FIELDS
from executive_health_ai.services.member_management_projection import MemberManagementProjection, management_work_items

SERVICE = ManagementWorkflowService()


def member():
    with SessionLocal() as s:
        patient = Patient(display_name='Synthetic Intake Entry '+str(uuid4())[:6], timezone='Asia/Tokyo')
        s.add(patient); s.commit()
        return patient.id


def archive_page(member_id):
    from uuid import UUID
    from executive_health_ai.database import SessionLocal
    from executive_health_ai.models import Patient
    from executive_health_ai.services.member_management_projection import MemberManagementProjection
    from executive_health_ai.ui.pages.manager.workbench import archive
    with SessionLocal() as s:
        patient = s.get(Patient, UUID(member_id))
        view = MemberManagementProjection().member(s, patient.id)
    archive(None, patient, view)


def button(app, label):
    return next(b for b in app.button if b.label == label)


def fill(member_id):
    with SessionLocal() as s:
        row = SERVICE.start_intake(s, member_id, datetime.now().year, 'Synthetic Manager')
        for step in STEPS[:-1]:
            data = {'display_name':s.get(Patient, member_id).display_name} if step == '基础资料' else [] if step in TABLE_FIELDS else {} if step in PROFILE_FIELDS else {'concern':'睡眠、体重'}
            if step == '个人病史': data = [{'疾病或问题':'自述待核对事项'}]*3
            if step == '当前用药 / 营养补充': data = [{'名称':'自述药物，未确认'}]*2
            if step == '过敏史': data = [{'名称':'自述花粉过敏'}]
            if step == '家族健康史': data = [{'患病家属':'父亲'},{'患病家属':'母亲'}]
            SERVICE.save_intake(s, member_id, row.cycle_year, step, data, 'Synthetic Member')
        s.commit()
        return row.id


def test_no_assessment_entry_starts_same_member_without_member_selector():
    mid = member()
    app = AppTest.from_function(archive_page, args=(str(mid),)).run()
    assert not app.exception
    assert app.subheader[0].value == '资料整理进度'
    button(app, '继续完成初始评估').click().run()
    assert not app.exception
    assert len(app.selectbox[0].options) == 11
    assert all(x.label not in {'选择会员','会员档案','选择问卷'} for x in app.selectbox)
    button(app, '保存草稿并继续').click().run()
    button(app, '← 返回健康档案').click().run()
    assert button(app, '继续完成初始评估')
    assert any('10%' in m.value for m in app.caption)
    button(app, '查看已填写内容').click().run()
    assert not app.exception
    button(app, '继续填写').click().run()
    assert app.selectbox[0].value == 1
    with SessionLocal() as s:
        assert s.scalar(select(func.count(IntakeAssessment.id)).where(IntakeAssessment.patient_id==mid)) == 1


def test_submit_review_archive_sync_view_and_amend_do_not_promote_medical_facts():
    mid = member(); iid = fill(mid)
    app = AppTest.from_function(archive_page,args=(str(mid),)).run()
    button(app,'确认并提交初始健康评估').click().run()
    assert app.selectbox[0].value == 10
    next(c for c in app.checkbox if '逐项核对' in c.label).check().run()
    button(app,'提交初始评估').click().run()
    with SessionLocal() as s:
        row = s.get(IntakeAssessment,iid)
        assert row.status == 'SUBMITTED'
        queue = [i for i in management_work_items(s,datetime.now(timezone.utc)) if i.member_id==mid]
        assert len(queue)==1 and queue[0].source_id==iid and queue[0].next_action=='完成健管确认'
    button(app,'← 返回健康档案').click().run()
    button(app,'开始健管确认').click().run()
    next(f for f in app.text_area if f.label=='专业管理重点').set_value('核对资料与规律随访')
    next(f for f in app.text_area if f.label=='初步年度管理重点').set_value('持续管理与资料核对')
    next(f for f in app.selectbox if f.label=='初评决定').select('CONFIRM')
    button(app,'保存健管初评').click().run()
    assert not app.exception
    button(app,'← 返回健康档案').click().run()
    assert button(app,'查看评估') and button(app,'补充/修正')
    button(app,'查看完整健康档案').click().run()
    rows = app.dataframe[0].value.set_index('资料')['摘要']
    button(app,'← 返回健康档案主页').click().run()
    assert rows['既往史']=='3 项记录' and rows['用药']=='2 项记录' and rows['过敏']=='1 项记录'
    with SessionLocal() as s:
        view = MemberManagementProjection().member(s,mid)
        assert view.intake.id==iid and view.intake.status=='CONFIRMED'
        assert view.intake.review['confirmed_at'] and view.intake.member_concern=='睡眠、体重'
        assert not any(i.member_id==mid for i in management_work_items(s,datetime.now(timezone.utc)))
        for model in (HealthProblem,RiskEvent,MedicationPlan):
            assert s.scalar(select(func.count(model.id)).where(model.patient_id==mid))==0
    button(app,'查看评估').click().run()
    assert not app.exception and any('专业管理重点' in m.value for m in app.markdown)
    button(app,'补充/修正').click().run()
    assert not app.exception and any(x.label=='填写步骤' for x in app.selectbox)
    with SessionLocal() as s:
        assert s.get(IntakeAssessment,iid).status=='DRAFT'
        assert s.scalar(select(func.count(IntakeAssessment.id)).where(IntakeAssessment.patient_id==mid))==1


def test_start_is_idempotent_and_empty_archive_prompt_is_actionable():
    mid = member()
    with SessionLocal() as s:
        a = SERVICE.start_intake(s,mid,datetime.now().year,'Synthetic Manager')
        b = SERVICE.start_intake(s,mid,datetime.now().year,'Synthetic Manager')
        assert a.id==b.id
        s.commit()
    app=AppTest.from_function(archive_page,args=(str(mid),)).run()
    next(b for b in app.button if b.label.startswith('个人病史\n')).click().run()
    assert not app.exception and app.selectbox[0].value==2


def test_today_review_opens_the_exact_assessment_not_current_year():
    mid=member()
    with SessionLocal() as s:
        old=SERVICE.start_intake(s,mid,2025,'Synthetic Manager')
        old.status='SUBMITTED'; old.review_status='READY_FOR_REVIEW'; old.member_concern='往年自述'
        SERVICE.start_intake(s,mid,2026,'Synthetic Manager')
        s.commit(); iid=old.id
    def page(member_key,assessment_key):
        from uuid import UUID
        from executive_health_ai.database import SessionLocal
        from executive_health_ai.models import Patient
        from executive_health_ai.ui.pages.manager.workflow import intake
        with SessionLocal() as s: patient=s.get(Patient,UUID(member_key))
        intake(None,patient,assessment_id=UUID(assessment_key))
    app=AppTest.from_function(page,args=(str(mid),str(iid))).run()
    assert not app.exception and any('往年自述' in m.value for m in app.markdown)
    assert any('2025' in m.value for m in app.markdown)


def test_legacy_annual_program_owner_is_used_in_today_queue():
    from datetime import date,timedelta
    from executive_health_ai.services.member_management_projection import intake_program
    mid=member()
    with SessionLocal() as s:
        program=SERVICE.enroll(s,name='ignored',member_id=mid,start=date.today(),end=date.today()+timedelta(days=364),
                               owner='Legacy Care Manager',goal='资料核对')
        program.cycle_year=None
        row=s.scalar(select(IntakeAssessment).where(IntakeAssessment.patient_id==mid))
        row.status='SUBMITTED';row.review_status='READY_FOR_REVIEW';s.flush()
        assert intake_program(s,row).id==program.id
        queue=[i for i in management_work_items(s,datetime.now(timezone.utc)) if i.member_id==mid]
        assert len(queue)==1 and queue[0].owner=='Legacy Care Manager'
        s.rollback()


