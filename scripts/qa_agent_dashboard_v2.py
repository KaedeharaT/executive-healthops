"""Real browser stories from role homepages. No internal routes or state injection."""
import json
import os
import re
from datetime import date, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT=Path('docs/images/agent-dashboard-v2');OUT.mkdir(parents=True,exist_ok=True)
FORBIDDEN=re.compile(r'AgentGoal|AgentRun|PlanStep|ToolCall|Trace|\bRaw\b|Debug|UUID|Internal|Legacy|canonical_code|provider_code|WAITING_MANAGER|WAITING_DOCTOR|键盘选择|下拉选择|备用选择|完整标题|Agent模式|st\.rerun|no-op')

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1600,'height':1100})
    errors=[];results=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    def settle():
        page.wait_for_timeout(500)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden',timeout=90000)
        page.wait_for_timeout(500)
        assert not page.locator('[data-testid="stException"]').count(),page.locator('body').inner_text()
        assert not errors,errors
    def top():
        page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTo(0,0)');page.wait_for_timeout(150)
    def button(text):page.get_by_role('button',name=text,exact=True).last.click();settle()
    def radio(text):page.get_by_role('radio',name=text,exact=True).last.locator('xpath=ancestor::label').click();settle()
    def role(text):
        top();page.get_by_text('切换演示角色',exact=True).click();radio(text)
        page.get_by_text('切换演示角色',exact=True).click();settle()
    def search(label,text):
        field=page.get_by_label(label,exact=True);field.fill(text);field.press('Enter');settle()
    def row(index=-1):
        page.locator('[data-testid="stDataFrame"]:visible').nth(index).click(position={'x':120,'y':53});settle()
    def choose(label,value):
        field=page.get_by_label(label,exact=True);field.click();field.fill(value)
        page.get_by_role('option',name=value,exact=True).click();settle()
    def shot(name,admin=False,keep_scroll=False,section=None):
        if not keep_scroll:top()
        text=page.locator('body').inner_text()
        assert admin or not FORBIDDEN.findall(text),(name,FORBIDDEN.findall(text))
        nested=page.locator('[data-testid="stExpander"] [data-testid="stExpander"]').count()
        assert nested==0,(name,'nested expanders',nested)
        (page.locator(section) if section else page).screenshot(path=str(OUT/(name+'.png')))
        results.append({'page':name,'technical_terms':0 if not admin else 'admin only','nested_expanders':nested,'page_errors':0})
        print(name,flush=True)
    try:
        page.goto(os.getenv('HEALTHOPS_QA_URL','http://127.0.0.1:18521'),wait_until='networkidle');settle()
        if page.get_by_role('button',name='进入 HealthOps 运营后台',exact=True).count():button('进入 HealthOps 运营后台')
        assert page.locator('[class*="st-key-assistant-card-"]').count() >= 2
        shot('01-manager-assistant-summary')
        page.get_by_role('button',name='查看运行看板',exact=True).first.click();settle()
        assert page.get_by_role('heading',name='健康管理助手 · 运行看板',exact=True).count()
        assert page.locator('.care-history').count()==2
        shot('03-agent-dashboard-manager')
        shot('05-agent-routing-reasons',section='.st-key-board-routing')
        shot('06-agent-findings-risk',section='.st-key-board-clinical')
        shot('07-agent-human-timeline',section='.st-key-board-history')
        page.get_by_text('核对或修正原报告资料',exact=True).click()
        page.get_by_role('button',name='刷新已修改资料',exact=True).click()
        page.get_by_text('● 当前正在：重新读取报告、核对基线与历史资料并整理确认内容',exact=True).wait_for(timeout=90000)
        shot('02-agent-dashboard-running')
        page.get_by_text('● 当前正在：重新读取报告、核对基线与历史资料并整理确认内容',exact=True).wait_for(state='hidden',timeout=300000)
        settle()
        page.get_by_label('责任医生',exact=True).fill('演示医生')
        page.get_by_label('需要医生判断的问题',exact=True).fill('运行看板验收：本次肝功能变化如何安排后续管理？')
        button('确认并提交医生')
        assert '当前无需健管操作' in page.locator('body').inner_text()
        shot('04-agent-dashboard-doctor')
        waiting_page=page
        page=browser.new_page(viewport={'width':1600,'height':1100})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(os.getenv('HEALTHOPS_QA_URL','http://127.0.0.1:18521'),wait_until='networkidle');settle()
        if page.get_by_role('button',name='进入 HealthOps 运营后台',exact=True).count():button('进入 HealthOps 运营后台')
        role('医生');search('搜索记录','运行看板验收');row()
        assert '当前责任分流' not in page.locator('body').inner_text()
        shot('11-doctor-focused-review')
        page.get_by_label('医学判断',exact=True).fill('合成演示：已核对肝功能变化，建议按期复查。')
        page.get_by_label('建议',exact=True).fill('了解饮酒情况并确认生活方式执行情况，按建议时间复查肝功能。')
        radio('需要');page.get_by_label('复查项目',exact=True).fill('肝功能复查')
        page.get_by_role('button',name='提交判断',exact=True).click()
        page.get_by_text('医学判断已提交，健康管理师将确认后续安排。',exact=True).wait_for(timeout=300000)
        settle()
        page=waiting_page
        page.get_by_role('button',name='确认并创建后续安排',exact=True).wait_for(timeout=65000)
        settle()
        assert '已收到医生判断，原流程自动继续' in page.locator('body').inner_text()
        shot('08-agent-resumed')
        shot('12-human-history-after-doctor',section='.st-key-board-history')
        button('确认并创建后续安排')
        page.get_by_role('heading',name='本次自动管理已完成',exact=True).wait_for(timeout=90000);settle()
        shot('09-agent-completed',section='.st-key-board-exit')
        shot('13-completed-header')
        button('返回会员360')
        page.get_by_text('自动跟进 · 体检后健康管理',exact=True).scroll_into_view_if_needed()
        assert '当前：本次管理已完成' in page.locator('body').inner_text()
        shot('14-member360-automatic-followup',keep_scroll=True)
        button('查看运行看板')
        assert page.get_by_role('button',name='← 返回会员360',exact=True).count()
        button('← 返回会员360')
        role('管理员');radio('自动化运行');row()
        page.get_by_text('技术详情',exact=True).click()
        shot('10-admin-technical-detail',admin=True,section='[data-testid="stExpander"]:has-text("技术详情")')
        role('健康管理师');radio('会员')
        if page.get_by_role('button',name='← 返回会员',exact=True).count():button('← 返回会员')
        search('搜索成员','Demo Executive A');row()
        radio('医疗');radio('医疗记录');radio('检查')
        page.locator('input[type="file"]').set_input_files({'name':'synthetic-unreadable-dashboard-v2.txt',
            'mimeType':'text/plain','buffer':b'no extractable health evidence'})
        settle();button('开始解析报告')
        radio('今日工作')
        page.get_by_role('button',name='查看运行看板',exact=True).first.click();settle()
        assert '需要优先人工处理' in page.locator('body').inner_text()
        assert '报告无法可靠整理' in page.locator('body').inner_text()
        shot('15-agent-escalated')
        button('重新读取已补充资料')
        assert '需要优先人工处理' in page.locator('body').inner_text()
        assert not page.get_by_role('button',name='确认并创建后续安排',exact=True).count()
        (OUT/'browser-results.json').write_text(json.dumps({'actual_browser':'Chromium','states':{
            'running':'real report reread command, no simulated delay','waiting_manager':'PASS','waiting_doctor':'PASS',
            'doctor_resume':'original open manager board refreshed automatically after real doctor submission',
            'action_approval':'PASS','completed':'PASS','member360':'same board, return context preserved',
            'admin':'same board with technical expander','escalated':'real unreadable report uploaded through member medical records; retry remains stopped'},'pages':results,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
    except Exception:
        page.screenshot(path=str(OUT/'failure.png'),full_page=True)
        (OUT/'failure.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
        raise
    finally:browser.close()
