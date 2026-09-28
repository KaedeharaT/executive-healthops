"""Care workflow regressions; browser screenshots are captured separately."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace as Row
from pathlib import Path
from streamlit.testing.v1 import AppTest
from tests.ui_selection import open_member, select_table_row
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import Patient
from executive_health_ai.models.management_workflow import IntakeAssessment
from executive_health_ai.services.management_workflow import ManagementWorkflowService, STEPS
from executive_health_ai.services.member_management_projection import MemberManagementProjection
from executive_health_ai.services.health_visualization import HealthSeries, HealthPoint
from executive_health_ai.ui.charts.health import metric_trend_chart

APP=Path(__file__).resolve().parents[1]/'streamlit_app.py'


def test_today_drawer_requires_selection_and_close_resets_only_selection():
    app=AppTest.from_file(APP).run(timeout=45)
    assert not app.exception
    assert not any(b.label=='← 返回今日工作' for b in app.button)
    select_table_row(app).run(timeout=45)
    assert not app.exception and any(b.label=='← 返回今日工作' for b in app.button)
    next(b for b in app.button if b.label=='← 返回今日工作').click().run(timeout=45)
    assert not app.exception and not any(b.label=='← 返回今日工作' for b in app.button)
    assert app.dataframe


def test_header_keeps_member_concern_distinct_from_professional_focus():
    def page():
        from executive_health_ai.ui.components import member_header
        member_header('合成会员',cycle='2026',owner='王健管',phase='第二阶段',concern='睡眠',focus='血压',next_action='确认预约 · 王健管 · 9/27',updated='9/24')
    app=AppTest.from_function(page).run()
    value=app.markdown[0].value
    assert '睡眠' not in value and '血压' not in value
    from executive_health_ai.ui.pages.manager import experience
    import inspect
    overview=inspect.getsource(experience.member_detail)
    assert '会员关注：' in overview and '当前管理重点' in overview
    assert '确认预约' in value and '9/27' in value and '责任健管' in value


def test_phase_selection_uses_actual_status_and_can_inspect_completed_phase():
    def page():
        import streamlit as st
        from types import SimpleNamespace
        from executive_health_ai.ui.components import stage_stepper
        rows=[SimpleNamespace(id='a',title='建档',status='COMPLETED'),SimpleNamespace(id='b',title='随访',status='ACTIVE')]
        selected=stage_stepper(rows,key='phases',current_id='b')
        st.caption(selected.id)
    app=AppTest.from_function(page).run()
    assert app.caption[-1].value=='b'
    app.button[0].click().run()
    assert app.caption[-1].value=='a'
    assert '已完成' in app.button[0].label and '当前' in app.button[1].label


def test_phase_task_table_cannot_inherit_another_year_or_undated_task():
    def page():
        from datetime import date,datetime,timezone
        from types import SimpleNamespace as R
        from executive_health_ai.ui.pages.manager.workflow import phase_detail
        def task(name,program,day):
            return R(id=name,title=name,program_id=program,due_at=datetime(2026,9,day,tzinfo=timezone.utc) if day else None,instruction='执行目标',assignee='王健管',status='PENDING',completed_at=None)
        view=R(program=R(id='this-year'),owner='王健管',tasks=[task('阶段内','this-year',10),task('别的年度','past',10),task('阶段外','this-year',25),task('未排期','this-year',None)])
        phase=R(id='phase',start_date=date(2026,9,1),end_date=date(2026,9,20),goal='阶段目标',owner='王健管',management_content='核对安排',result_feedback='')
        phase_detail(view,phase,key='phase-test')
    app=AppTest.from_function(page).run()
    assert not app.exception
    assert app.dataframe[0].value['事项'].tolist()==['阶段内']


def test_eleven_step_wizard_keeps_both_medication_sections_and_draft_resume():
    svc=ManagementWorkflowService()
    with SessionLocal() as s:
        program=svc.enroll(s,name='V4 Wizard Synthetic',start=date.today(),end=date.today()+timedelta(days=364),owner='V4 Care',goal='合成问卷验收')
        s.commit();member_id=program.patient_id
    def page(member_key):
        from uuid import UUID
        from executive_health_ai.database import SessionLocal
        from executive_health_ai.models import Patient
        from executive_health_ai.ui.pages.manager.workflow import intake
        with SessionLocal() as s:patient=s.get(Patient,UUID(member_key))
        intake(None,patient,member=True)
    app=AppTest.from_function(page,args=(str(member_id),)).run()
    assert not app.exception and len(app.selectbox[0].options)==11
    next(b for b in app.button if b.label=='保存草稿').click().run()
    assert app.selectbox[0].value==0
    for _ in range(10):
        concern=next((x for x in app.text_area if x.label=='会员自己最想改善什么'),None)
        if concern: concern.set_value('改善睡眠与规律活动')
        next(b for b in app.button if b.label=='保存草稿并继续').click().run()
        assert not app.exception
    with SessionLocal() as s:
        row=MemberManagementProjection().member(s,member_id).intake
        assert set(STEPS[:-1])<=set(row.responses)
        assert row.status=='DRAFT'
        assert row.responses['当前用药 / 营养补充']==row.responses['最近用药']==[]
    next(c for c in app.checkbox if '逐项核对' in c.label).check().run()
    next(b for b in app.button if b.label=='提交初始评估').click().run()
    assert not app.exception
    with SessionLocal() as s:
        row=MemberManagementProjection().member(s,member_id).intake
        assert row.status=='SUBMITTED'


def test_baseline_reference_matches_metric_and_unit_without_relabeling_first_point():
    series=(HealthSeries('weight','体重','kg',(HealthPoint(datetime(2026,9,1,tzinfo=timezone.utc),Decimal('88'),'合成记录'),HealthPoint(datetime(2026,9,20,tzinfo=timezone.utc),Decimal('85'),'合成记录'))),)
    baseline=Row(code='weight',label='体重',unit='kg',value=Decimal('90'))
    wrong=Row(code='weight',label='体重',unit='lb',value=Decimal('210'))
    spec=metric_trend_chart(series,baseline_metrics=[baseline,wrong]).to_dict()
    assert len(spec['layer'])==2
    reference=spec['datasets'][spec['layer'][1]['data']['name']]
    assert reference==[{'年度基线':90.0,'指标':'体重','单位':'kg'}]
    assert series[0].points[0].value==Decimal('88')
    assert 'layer' not in metric_trend_chart(series,baseline_metrics=[wrong]).to_dict()
