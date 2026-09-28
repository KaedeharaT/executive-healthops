"""Same synthetic member: report preparation → physician → original goal."""
import json,os,time
from pathlib import Path
from uuid import UUID
os.environ['DATABASE_URL']='sqlite:///D:/executive_health_ai/.runtime/ai-native-final/browser.db'
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentGoal,MemberAgent
from playwright.sync_api import sync_playwright,expect
OUT=Path('docs/images/ai-native-final');ids=json.loads(Path('.runtime/ai-native-final/members.json').read_text(encoding='utf-8'))
def snapshot():
    with SessionLocal() as s:
        goal=s.scalar(select(AgentGoal).where(AgentGoal.member_id==UUID(ids['intake']),AgentGoal.goal_type=='POST_CHECKUP_MANAGEMENT'))
        agent=s.scalar(select(MemberAgent).where(MemberAgent.member_id==goal.member_id))
        return {'goal':str(goal.id),'agent':str(agent.id),'status':goal.status,'stage':goal.current_stage,
            'count':len(list(s.scalars(select(AgentGoal).where(AgentGoal.member_id==goal.member_id,AgentGoal.goal_type==goal.goal_type))))}
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':900})
    def settle():
        page.wait_for_timeout(650)
        expect(page.locator('[data-testid=stApp]')).to_have_attribute('data-test-script-state','notRunning',timeout=90000)
        assert not page.locator('[data-testid=stException]').count(),page.locator('body').inner_text()
    def radio(name):page.get_by_role('radio',name=name,exact=True).locator('xpath=ancestor::label').click();settle()
    def button(name):page.get_by_role('button',name=name,exact=True).click();settle()
    def role(name):page.get_by_text('切换演示角色',exact=True).click();radio(name);page.get_by_text('切换演示角色',exact=True).click();settle()
    def shot(name):
        page.locator('[data-testid=stMain]').evaluate('(e)=>e.scrollTo(0,0)');page.screenshot(path=str(OUT/(name+'.png')))
        (OUT/(name+'.txt')).write_text(page.locator('body').inner_text(),encoding='utf-8');print(name,flush=True)
    def row(target):
        for x in (150,90,15):
            page.locator('[data-testid=stDataFrame]').last.click(position={'x':x,'y':55});settle()
            if page.get_by_role('textbox',name=target,exact=True).count() or page.get_by_role('button',name=target,exact=True).count():break
    try:
        page.goto('http://127.0.0.1:18701')
        expect(page.get_by_role('button',name='进入 HealthOps 运营后台',exact=True)).to_be_visible(timeout=90000)
        button('进入 HealthOps 运营后台')
        before=snapshot()
        if before['stage']=='WAITING_MANAGER_REVIEW':
            page.get_by_label('查找待办',exact=True).fill('新体检报告待确认');page.get_by_label('查找待办',exact=True).press('Enter');settle()
            row('确认并继续')
            page.get_by_text('修改整理结果 / 提交医生判断',exact=True).click();settle()
            page.get_by_role('textbox',name='责任医生',exact=True).fill('演示医生')
            page.get_by_role('textbox',name='需要医生判断的问题',exact=True).fill('合成验收：请核对既有复查安排，是否需要医学确认？')
            button('提交医生判断');shot('09-doctor-wait')
        if snapshot()['status']=='WAITING_DOCTOR':
            role('医生');row('医学判断')
            page.get_by_role('textbox',name='医学判断',exact=True).fill('合成演示资料需结合原始医疗记录核对，本次不新增诊断。')
            page.get_by_role('textbox',name='建议',exact=True).fill('合成演示：建议复查血脂，并由健管安排一次电话随访核对结果。')
            radio('需要')
            page.get_by_role('textbox',name='复查项目',exact=True).fill('血脂')
            button('提交判断')
        deadline=time.monotonic()+660
        while snapshot()['status'] in {'RUNNING','PROCESSING'} and time.monotonic()<deadline:page.wait_for_timeout(800)
        after=snapshot()
        assert after['goal']==before['goal'] and after['agent']==before['agent'] and after['count']==1
        assert after['status']=='WAITING_MANAGER',after
        role('健康管理师');radio('今日工作')
        if page.get_by_role('button',name='← 返回今日工作',exact=True).count():button('← 返回今日工作')
        page.get_by_label('查找待办',exact=True).fill('张三');page.get_by_label('查找待办',exact=True).press('Enter');settle()
        shot('10-doctor-return-resume')
        (OUT/'same-member-doctor.json').write_text(json.dumps({'before':before,'after':after,'chromium':browser.version},indent=2),encoding='utf-8')
    except Exception:shot('doctor-failure');raise
    finally:browser.close()
