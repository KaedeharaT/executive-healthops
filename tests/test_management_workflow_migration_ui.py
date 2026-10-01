from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4
import json
import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest
from executive_health_ai.models import Base, Patient
from executive_health_ai.api import create_app
from executive_health_ai.services.management_workflow import ManagementWorkflowService

ROOT=Path(__file__).resolve().parents[1]


def test_migration_upgrades_previous_head_without_losing_existing_member(tmp_path,monkeypatch):
    url='sqlite:///'+(tmp_path/'migration.db').as_posix();monkeypatch.setenv('DATABASE_URL',url)
    cfg=Config(str(ROOT/'alembic.ini'));command.upgrade(cfg,'0026_strengthen_health_baseline')
    engine=create_engine(url)
    with engine.begin() as c:
        c.execute(text("INSERT INTO patients (id,display_name,timezone,created_at,updated_at) VALUES (:id,'Synthetic existing','UTC',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"),{'id':uuid4().hex})
    command.upgrade(cfg,'head')
    tables=set(inspect(engine).get_table_names())
    assert {'management_logs','intake_assessments','consultation_cases','stage_reviews','recheck_plans','family_relations'}<=tables
    assert {'cycle_year','customer_advisor'}<={c['name'] for c in inspect(engine).get_columns('health_programs')}
    assert {'program_id','phase_id','management_task_id'}<={c['name'] for c in inspect(engine).get_columns('service_requests')}
    with engine.connect() as c: assert c.scalar(text('SELECT COUNT(*) FROM patients'))==1
    command.downgrade(cfg,'0026_strengthen_health_baseline')
    with engine.connect() as c: assert c.scalar(text('SELECT COUNT(*) FROM patients'))==1
    command.upgrade(cfg,'head');engine.dispose()


def test_api_commands_use_same_service_and_reject_non_doctor_medical_write():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine);factory=sessionmaker(engine,expire_on_commit=False)
    with factory() as s:
        p=ManagementWorkflowService().enroll(s,name='Synthetic API Member',start=date.today(),end=date.today()+timedelta(days=364),owner='Synthetic Manager',goal='Synthetic goal');s.commit();mid=str(p.patient_id)
    client=TestClient(create_app(factory))
    assert client.get('/management/members/'+mid).json()['owner']=='Synthetic Manager'
    response=client.post('/management/members/'+mid+'/commands',json={'action':'intake_save','actor':'Synthetic Member','actor_role':'member','values':{'year':date.today().year,'step':'会员重点关注','data':{'concern':'睡眠规律'}}})
    assert response.status_code==200,response.text
    assert client.get('/management/members/'+mid).json()['member_concern']=='睡眠规律'
    denied=client.post('/management/members/'+mid+'/commands',json={'action':'consultation_opinion','actor':'Synthetic Member','actor_role':'member','values':{}})
    assert denied.status_code==403
    invalid=client.post('/management/members/'+mid+'/commands',json={'action':'recheck_create','actor':'Synthetic Manager','actor_role':'health_manager','values':{'planned_at':'2026-01-01T10:00:00'}})
    assert invalid.status_code==422
    engine.dispose()


@pytest.mark.parametrize('mode',['管理日志','年度方案与阶段','检查复查','阶段评估','关联服务','计划调整与随访'])
def test_management_modes_render_with_short_default_sections(monkeypatch,mode):
    from executive_health_ai.ui.pages.manager import workflow
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine);factory=sessionmaker(engine,expire_on_commit=False)
    with factory() as s:
        p=ManagementWorkflowService().enroll(s,name='Synthetic UI Member',start=date.today(),end=date.today()+timedelta(days=364),owner='Synthetic Manager',goal='Synthetic goal');s.commit();member=s.get(Patient,p.patient_id)
        from tests.goal_loop_support import approved_program
        approved_program(s,p);s.commit()
    monkeypatch.setattr(workflow,'SessionLocal',factory)
    from executive_health_ai.ui.pages.manager import goal_loop
    monkeypatch.setattr(goal_loop,'SessionLocal',factory)
    # Existing legacy plan surface is covered separately; this renderer test
    # verifies the new workflow dispatch without connecting to a real database.
    from executive_health_ai.ui.pages.manager import experience
    monkeypatch.setattr(experience,'management',lambda app,patient,action=None:None)
    def page(mid,mode):
        import streamlit as st
        from types import SimpleNamespace
        from executive_health_ai.ui.pages.manager import workflow
        from executive_health_ai.models import Patient
        from uuid import UUID
        with workflow.SessionLocal() as s: member=s.get(Patient,UUID(mid))
        st.session_state[f'workflow-mode-{member.id}']=mode
        workflow.management(SimpleNamespace(render_member_service_management=lambda _:None),member)
    app=AppTest.from_function(page,args=(str(member.id),mode)).run(timeout=30)
    assert not app.exception
    assert any(x.label=='← 返回当前阶段' for x in app.button)
    assert any(x.value==mode for x in app.subheader)
    engine.dispose()


def test_staff_navigation_and_frozen_element_functions_preserved():
    import ast
    source=(ROOT/'streamlit_app.py').read_text(encoding='utf8')
    assert '["今日", "成员", "年度管理", "服务运营", "医疗协同", "专项管理"]' in source
    rows=json.loads((ROOT/'docs/ux_v3_implementation/elements.json').read_text(encoding='utf8'))
    assert len(rows)==121
    for row in rows:
        functions={n.name for n in ast.walk(ast.parse((ROOT/row['source']).read_text(encoding='utf8'))) if isinstance(n,ast.FunctionDef)}
        assert row['renderer'] in functions and row['preserved']


def test_member_intake_resumes_first_unsaved_step(monkeypatch):
    from executive_health_ai.ui.pages.manager import workflow
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine);factory=sessionmaker(engine,expire_on_commit=False)
    with factory() as s:
        service=ManagementWorkflowService()
        program=service.enroll(s,name='Synthetic Resume Member',start=date.today(),end=date.today()+timedelta(days=364),owner='Synthetic Manager',goal='Synthetic goal')
        service.save_intake(s,program.patient_id,program.cycle_year,'基础资料',{'display_name':'Synthetic Resume Member'},'Synthetic Member')
        s.commit();mid=str(program.patient_id)
    monkeypatch.setattr(workflow,'SessionLocal',factory)
    def page(mid):
        from uuid import UUID
        from executive_health_ai.models import Patient
        from executive_health_ai.ui.pages.manager import workflow
        with workflow.SessionLocal() as s:member=s.get(Patient,UUID(mid))
        workflow.intake(None,member,member=True)
    app=AppTest.from_function(page,args=(mid,)).run(timeout=30)
    assert not app.exception and app.selectbox[0].value==1
    next(b for b in app.button if b.label=='保存草稿并继续').click().run()
    assert not app.exception and app.selectbox[0].value==2
    engine.dispose()
