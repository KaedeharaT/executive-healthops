"""Real Chromium acceptance against a prepared, isolated synthetic instance.

Prepare browser.db / members.json under .runtime/ai-native-final; never points
at the formal Demo database. Captures UI and checks persisted event identities.
"""
import json
import os
import sys
import time
from pathlib import Path
from uuid import UUID

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / '.runtime/ai-native-final'
OUT = ROOT / 'docs/images/ai-native-final'
OUT.mkdir(parents=True, exist_ok=True)
os.environ['DATABASE_URL'] = 'sqlite:///' + (DATA / 'browser.db').as_posix()
if '--prepare' in sys.argv:
    os.environ['LOCAL_LLM_ENABLED']='false'
sys.stdout.reconfigure(encoding='utf-8')

from sqlalchemy import select, func
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import MemberAgent, HealthEvent, AgentGoal


def prepare():
    """Create synthetic fixtures once; never reset an existing database."""
    from datetime import date,timedelta
    from executive_health_ai.database import engine
    from executive_health_ai.models import Base
    from executive_health_ai.services.management_workflow import ManagementWorkflowService
    from executive_health_ai.services.report_parsing import ReportParsingService
    from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
    from executive_health_ai.agent import post_checkup
    if (DATA/'browser.db').exists():raise SystemExit('QA database already exists; preserve it.')
    DATA.mkdir(parents=True,exist_ok=True)
    Base.metadata.create_all(engine)
    ids={}
    with SessionLocal() as session:
        for key,name in [('intake','张三（AI Native合成）'),('doctor','李四（医生流程合成）'),('device','设备合成会员')]:
            program=ManagementWorkflowService().enroll(session,name=name,start=date.today(),end=date.today()+timedelta(days=364),
                owner='王健管',goal='年度连续健康管理')
            ids[key]=str(program.patient_id)
            if key=='doctor':
                parser=ReportParsingService();parser.storage_root=DATA/'reports'
                report,_,_=parser.upload_and_parse(session,program.patient_id,'合成体检.txt',
                    ('体检日期：'+date.today().isoformat()+'\n低密度脂蛋白胆固醇  4.15 mmol/L\n谷丙转氨酶  56 U/L\n体重  85.8 kg').encode(),'王健管')
                goal=session.scalar(select(AgentGoal).where(AgentGoal.source_id==str(report.id)))
                post_checkup.manager_review(HealthOpsAgentSupervisor(),session,goal,actor='王健管',role='HEALTH_MANAGER',
                    doctor='演示医生',question='请结合原始资料判断是否需要进一步医学评估。')
                assert goal.status=='WAITING_DOCTOR'
                ids['doctor_goal']=str(goal.id)
        session.commit()
    (DATA/'members.json').write_text(json.dumps(ids,ensure_ascii=False,indent=2),encoding='utf-8')


if '--prepare' in sys.argv:
    prepare();raise SystemExit(0)

members = json.loads((DATA / 'members.json').read_text(encoding='utf-8'))


def snapshot(key):
    with SessionLocal() as session:
        member_id = UUID(members[key])
        agent = session.scalar(select(MemberAgent).where(MemberAgent.member_id == member_id))
        goals = list(session.scalars(select(AgentGoal).where(AgentGoal.member_id == member_id)))
        events = list(session.scalars(select(HealthEvent).where(HealthEvent.member_id == member_id,
            HealthEvent.event_category.is_not(None)).order_by(HealthEvent.received_at)))
        return {'member_agent': str(agent.id), 'status': agent.status, 'wake_count': agent.wake_count,
            'goals': [{'id': str(g.id), 'status': g.status, 'stage': g.current_stage} for g in goals],
            'events': [{'type': e.event_type, 'source': e.source_type, 'action': e.route_action,
                'goal': str(e.goal_id), 'status': e.status} for e in events]}


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    evidence = (json.loads((OUT/'browser-evidence.json').read_text(encoding='utf-8')) if '--doctor-only' in sys.argv else
        {'browser': browser.version, 'before_intake': snapshot('intake'), 'before_doctor': snapshot('doctor')})

    def settle():
        page.wait_for_timeout(500)  # Observe Streamlit rendering, never drives business progress.
        expect(page.locator('[data-testid="stApp"]')).to_have_attribute('data-test-script-state', 'notRunning', timeout=90000)
        page.wait_for_function('!document.querySelector(\'[data-stale="true"]\')')
        assert not page.locator('[data-testid="stException"]').count(), page.locator('body').inner_text()

    def button(label):
        page.get_by_role('button', name=label, exact=True).click(); settle()

    def radio(label):
        page.get_by_role('radio', name=label, exact=True).locator('xpath=ancestor::label').click(); settle()

    def shot(name):
        page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTo(0,0)')
        page.screenshot(path=str(OUT / (name+'.png')))
        (OUT / (name+'.txt')).write_text(page.locator('body').inner_text(), encoding='utf-8')
        print(name, flush=True)

    try:
        page.goto('http://127.0.0.1:18701', wait_until='networkidle'); settle()
        if page.get_by_role('button', name='进入 HealthOps 运营后台', exact=True).count():
            button('进入 HealthOps 运营后台')
        if '--doctor-only' not in sys.argv:
            radio('会员')
            page.get_by_label('搜索成员', exact=True).fill('张三'); page.get_by_label('搜索成员', exact=True).press('Enter'); settle()
            page.locator('[data-testid="stDataFrame"]').last.click(position={'x':160, 'y':55}); settle()
            radio('健康档案'); shot('01-before-upload')
            page.get_by_text('上传健康资料', exact=True).first.click(); settle()
            payload = json.dumps({'responses': {'家族健康史': [{'患病家属':'父亲', '具体疾病':'会员明确回答暂不清楚'}],
                '生活方式': {'睡眠':'七小时', '烟草':'不吸烟', '运动':'每周快走三次'}}}, ensure_ascii=False).encode()
            page.locator('input[type=file]').set_input_files({'name':'AI Native合成问卷.json','mimeType':'application/json','buffer':payload})
            button('上传并整理资料')
            evidence['after_upload'] = snapshot('intake'); shot('02-document-trigger')
            expect(page.get_by_text('触发原因：收到新的健康资料 · 来源：人工上传 / 录入', exact=True)).to_be_visible(timeout=90000)
            deadline = time.monotonic()+180
            while snapshot('intake')['status']=='RUNNING' and time.monotonic()<deadline:
                page.wait_for_timeout(1000)
            settle(); evidence['after_intake'] = snapshot('intake')
            assert evidence['after_intake']['status']=='WAITING_MANAGER'
            assert evidence['after_intake']['member_agent']==evidence['before_intake']['member_agent']
            assert evidence['after_intake']['wake_count']==1
            expect(page.get_by_role('progressbar',name='整体业务进度')).to_have_attribute('aria-valuenow','71',timeout=20000)
            expect(page.locator('.agent-action-spinner')).to_have_count(0)
            shot('03-intake-waiting-manager')
            radio('今日工作')
            page.get_by_label('查找待办', exact=True).fill('张三'); page.get_by_label('查找待办', exact=True).press('Enter'); settle()
            shot('04-today-human-work')
        page.get_by_text('切换演示角色', exact=True).click(); radio('医生')
        page.get_by_text('切换演示角色', exact=True).click(); settle()
        for x in (140,80,15):
            page.locator('[data-testid="stDataFrame"]').last.click(position={'x':x,'y':55}); settle()
            if page.get_by_role('textbox',name='医学判断',exact=True).count():break
        shot('05-doctor-original-goal')
        page.get_by_role('textbox', name='医学判断', exact=True).fill('合成验收：现有资料不足以作医学结论，请继续核对会员记录。')
        page.get_by_role('textbox', name='建议', exact=True).fill('合成验收：核对生活方式记录，安排一次随访。')
        button('提交判断'); shot('06-doctor-submitted')
        deadline=time.monotonic()+360
        while snapshot('doctor')['status']=='RUNNING' and time.monotonic()<deadline:
            page.wait_for_timeout(1000)
        evidence['after_doctor']=snapshot('doctor')
        assert evidence['after_doctor']['member_agent']==evidence['before_doctor']['member_agent']
        assert evidence['after_doctor']['goals'][0]['id']==members['doctor_goal']
        assert len(evidence['after_doctor']['goals'])==1
        assert evidence['after_doctor']['status']=='WAITING_MANAGER'
        assert evidence['after_doctor']['wake_count']==2
        assert evidence['after_doctor']['events'][-1]['action']=='RESUME_CURRENT_GOAL'
        page.get_by_text('切换演示角色', exact=True).click(); radio('健康管理师')
        page.get_by_text('切换演示角色', exact=True).click(); settle()
        radio('今日工作')
        page.get_by_label('查找待办', exact=True).fill('李四'); page.get_by_label('查找待办', exact=True).press('Enter'); settle()
        shot('07-doctor-returned-today')
        evidence['passed']=True
    except Exception:
        shot('failure'); raise
    finally:
        (OUT/'browser-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
        browser.close()
