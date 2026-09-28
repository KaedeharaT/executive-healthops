"""Real Chromium acceptance through ordinary controls; no injected UI state.

Run prepare_agent_visibility_regression.py and start its scenario manifest first.
Reads the isolated DB only to verify the opened instance and genuine transitions.
"""
import json
import re
import sqlite3
from datetime import date
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'.runtime/agent-visibility-regression'
OUT=ROOT/'docs/images/agent-visibility-regression'
OUT.mkdir(parents=True,exist_ok=True)
FORBIDDEN=re.compile(r'AgentGoal|AgentRun|ToolCall|Trace|Prompt|Token|JSON|UUID|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b',re.I)

def record():
    with sqlite3.connect(WORK/'scenario.db') as db:
        rows=db.execute('select id,status,current_stage from agent_goals').fetchall()
        assert len(rows)==1,rows
        return rows[0]

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1600,'height':1100})
    page.set_default_timeout(30000)
    errors=[];checks=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    def settle():
        page.wait_for_timeout(650)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden',timeout=240000)
        assert not page.locator('[data-testid="stException"]').count(),page.locator('body').inner_text()
    def button(label):
        page.get_by_role('button',name=label,exact=True).click();settle()
    def radio(label):
        page.get_by_role('radio',name=label,exact=True).locator('xpath=ancestor::label').click();settle()
    def shot(filename,anchor=None):
        if anchor:page.get_by_text(anchor,exact=True).first.scroll_into_view_if_needed()
        content=page.locator('body').inner_text()
        assert not FORBIDDEN.findall(content),FORBIDDEN.findall(content)
        page.screenshot(path=str(OUT/filename))
        (OUT/filename.replace('.png','.txt')).write_text(content,encoding='utf-8')
        print(filename,flush=True)
    def today_visible():
        expect(page.get_by_role('heading',name='健康管理助手',exact=True)).to_be_visible()
        assert all(t in page.locator('.st-key-soft-assistant-status').inner_text() for t in ('正在运行','等待我确认','等待医生','最近完成'))
    def member():
        radio('会员')
        if page.get_by_role('button',name='← 返回会员',exact=True).count():button('← 返回会员')
        field=page.get_by_label('搜索成员',exact=True);field.fill('Demo Executive A');field.press('Enter');settle()
        page.locator('[data-testid="stDataFrame"]').last.click(position={'x':100,'y':55});settle()
        button('查看会员 / 进入Member360')
    def board():
        expect(page.get_by_role('heading',name='健康管理助手 · 运行看板',exact=True)).to_be_visible()
        content=page.locator('body').inner_text()
        assert all(label in content for label in ('报告接收','系统分析','责任分流','专业确认','行动建立','完成',
            '助手现在在做什么','AI与知识支持','当前责任分流','系统发现','正式风险规则','人工参与','接下来会发生什么'))
        # A visible table widget is bound to the actual instance, not the title.
        assert page.locator(f'[class*="st-key-care-evidence-{identity}-"]').count()==1
        assert record()[0].replace('-','')==identity.replace('-','')
    try:
        page.goto('http://127.0.0.1:18581');settle();button('进入 HealthOps 运营后台')
        with sqlite3.connect(WORK/'scenario.db') as db:
            fresh=db.execute('select count(*) from agent_goals').fetchone()[0]==0
        if fresh:
            today_visible();expect(page.get_by_text('当前没有需要您处理的自动流程。',exact=True)).to_be_visible()
            shot('05-no-active-agent-empty-state.png','健康管理助手');checks.append('no_goals_empty_state')
            # Reproduce the previous stale selection through real row selection.
            page.get_by_role('heading',name='工作事项',exact=True).scroll_into_view_if_needed()
            page.locator('[data-testid="stDataFrame"]').last.click(position={'x':100,'y':55});settle()
            expect(page.get_by_role('button',name='← 返回今日工作',exact=True)).to_be_visible()
            radio('会员');radio('今日工作');today_visible();checks.append('sidebar_clears_work_selection')
            member();expect(page.get_by_role('heading',name='自动跟进',exact=True)).to_be_visible()
            expect(page.get_by_role('button',name='查看运行看板',exact=True)).to_be_disabled()
            shot('06-member-no-agent-empty-state.png','自动跟进')
            radio('医疗');radio('医疗记录');radio('检查')
            page.locator('input[type="file"]').set_input_files({'name':'自动跟进回归验收.txt','mimeType':'text/plain',
                'buffer':('体检日期：'+date.today().isoformat()+'\n低密度脂蛋白胆固醇  4.15 mmol/L\n谷丙转氨酶  56 U/L\n体重  85.8 kg').encode()})
            settle();button('开始解析报告');radio('今日工作')
        raw_id,state,stage=record();identity=str(__import__('uuid').UUID(raw_id))
        if state=='WAITING_MANAGER' and stage=='WAITING_MANAGER_REVIEW':
            today_visible();shot('01-today-assistant-visible.png','健康管理助手');checks.append('waiting_manager_visible')
            button('查看运行看板');board();shot('03-agent-dashboard.png','健康管理助手 · 运行看板')
            shot('07-ai-knowledge-panel.png','AI与知识支持')
            button('← 返回今日工作');member()
            expect(page.get_by_role('heading',name='自动跟进',exact=True)).to_be_visible()
            shot('02-member360-auto-followup.png','自动跟进');button('查看运行看板');board()
            button('← 返回会员360');radio('管理')
            expect(page.get_by_role('heading',name='自动跟进',exact=True)).to_be_visible()
            button('查看运行看板');board();checks.append('today_member_management_same_instance')
            if page.get_by_text('修改整理结果 / 提交医生判断',exact=True).count():
                page.get_by_text('修改整理结果 / 提交医生判断',exact=True).click()
            page.get_by_label('责任医生',exact=True).fill('演示医生')
            page.get_by_label('需要医生判断的问题',exact=True).fill('可视化回归验收：请核对合成报告后续安排。')
            button('确认并提交医生' if page.get_by_role('button',name='确认并提交医生',exact=True).count() else '提交医生判断')
            assert record()[1]=='WAITING_DOCTOR'
            radio('会员');radio('今日工作');today_visible()
            shot('08-waiting-doctor-visible.png','健康管理助手');checks.append('waiting_doctor_visible')
            button('查看运行看板');board()
        if record()[1]=='WAITING_DOCTOR':
            if not page.get_by_role('heading',name='健康管理助手 · 运行看板',exact=True).count():
                today_visible();shot('08-waiting-doctor-visible.png','健康管理助手')
                button('查看运行看板');board()
            manager=page
            page=browser.new_page(viewport={'width':1600,'height':1100});page.set_default_timeout(30000)
            page.goto('http://127.0.0.1:18581');settle();button('进入 HealthOps 运营后台')
            page.get_by_role('button',name='切换演示角色').click();radio('医生')
            page.get_by_role('button',name='切换演示角色').click();settle()
            field=page.get_by_label('搜索记录',exact=True);field.fill('可视化回归验收');field.press('Enter');settle()
            page.locator('[data-testid="stDataFrame"]').last.click(position={'x':100,'y':55});settle()
            page.get_by_label('医学判断',exact=True).fill('合成验收：已核对资料，建议按期复核。')
            page.get_by_label('建议',exact=True).fill('了解饮酒情况并随访生活方式执行情况。')
            radio('需要');page.get_by_label('复查项目',exact=True).fill('肝功能复查')
            button('提交判断')
            page=manager;page.get_by_role('button',name='确认并创建后续安排',exact=True).wait_for(timeout=65000);settle()
        if record()[2]=='WAITING_ACTION_APPROVAL':
            if not page.get_by_role('heading',name='健康管理助手 · 运行看板',exact=True).count():
                button('查看运行看板');board()
            button('确认并创建后续安排');assert record()[1]=='COMPLETED';board()
        if record()[1]=='COMPLETED':
            if not page.get_by_role('heading',name='健康管理助手 · 运行看板',exact=True).count():
                button('查看最近运行');board()
            shot('09-completed-dashboard.png','本次自动管理已完成')
            button('返回会员360');expect(page.get_by_text('当前：本次管理已完成',exact=True)).to_be_visible()
            shot('10-member-completed.png','自动跟进');button('查看运行看板');board()
            radio('会员');radio('今日工作');today_visible()
            expect(page.get_by_text('当前没有需要您处理的自动流程。',exact=True)).to_be_visible()
            shot('04-completed-agent-visible.png','健康管理助手')
            button('查看最近运行');board();checks.extend(['completed_history_visible','completed_member_visible','no_active_with_history','same_instance_after_completion'])
        assert not errors,errors
        with sqlite3.connect(WORK/'scenario.db') as db:
            calls=[json.loads(row[0])['capability'] for row in db.execute("select metadata_json from agent_run_traces where action='capability_activity'")]
        previous=json.loads((OUT/'browser-results.json').read_text(encoding='utf-8')) if (OUT/'browser-results.json').exists() else {}
        checks=list(dict.fromkeys(previous.get('checks',[])+checks)) if previous.get('goal_id')==identity else checks
        (OUT/'browser-results.json').write_text(json.dumps({'browser':'Chromium '+browser.version,'checks':checks,
            'goal_id':identity,'final_status':record()[1],'calls':calls,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
        print('Agent visibility Chromium acceptance passed',flush=True)
    except Exception:
        page.screenshot(path=str(OUT/'failure.png'))
        (OUT/'failure.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
        raise
    finally:browser.close()
