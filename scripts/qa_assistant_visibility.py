"""Real browser stories from role homepages. No internal routes or state injection."""
import json
import os
import re
from datetime import date, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT=Path('docs/images/assistant-visibility');OUT.mkdir(parents=True,exist_ok=True)
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
    def shot(name,admin=False,keep_scroll=False):
        if not keep_scroll:top()
        text=page.locator('body').inner_text()
        assert admin or not FORBIDDEN.findall(text),(name,FORBIDDEN.findall(text))
        nested=page.locator('[data-testid="stExpander"] [data-testid="stExpander"]').count()
        assert nested==0,(name,'nested expanders',nested)
        page.screenshot(path=str(OUT/(name+'.png')))
        results.append({'page':name,'technical_terms':0 if not admin else 'admin only','nested_expanders':nested,'page_errors':0})
        print(name,flush=True)
    try:
        page.goto(os.getenv('HEALTHOPS_QA_URL','http://127.0.0.1:18518'),wait_until='networkidle');settle()
        if page.get_by_role('button',name='进入 HealthOps 运营后台',exact=True).count():button('进入 HealthOps 运营后台')
        assert page.locator('[class*="st-key-assistant-card-"]').count() >= 2
        assert '已完成' in page.locator('body').inner_text()
        shot('01-today-assistant-cards')
        button('继续处理')
        assert '本次自动管理' in page.locator('body').inner_text()
        assert page.locator('.care-history').count()==1
        shot('02-manager-confirmation')
        page.get_by_text('核对或修正原报告资料',exact=True).click()
        page.get_by_role('button',name='刷新已修改资料',exact=True).click()
        page.get_by_text('● 当前正在：重新读取报告、核对基线与历史资料并整理确认内容',exact=True).wait_for(timeout=90000)
        assert '当前：等待您的确认' not in page.locator('body').inner_text()
        shot('03-assistant-running')
        page.get_by_text('● 当前正在：重新读取报告、核对基线与历史资料并整理确认内容',exact=True).wait_for(state='hidden',timeout=300000)
        settle()
        page.get_by_text('修改整理结果 / 提交医生判断',exact=True).click()
        button('提交医生判断')
        page.get_by_text('请填写责任医生；资料将保留在待健管确认。',exact=True).wait_for(timeout=30000)
        assert page.get_by_role('button',name='确认并继续',exact=True).is_visible()
        assert page.locator('.care-history .current').is_visible()
        shot('10-validation-keeps-work-visible')
        page.get_by_label('责任医生',exact=True).fill('演示医生')
        page.get_by_label('需要医生判断的问题',exact=True).fill('助手可见性验收：本次肝功能变化如何安排后续管理？')
        button('提交医生判断')
        assert '当前无需健管操作' in page.locator('body').inner_text()
        shot('04-waiting-doctor')
        button('← 返回今日工作')
        radio('会员');search('搜索成员','Demo Executive A');row()
        assert '医生提交后自动继续' in page.locator('body').inner_text()
        page.get_by_text('自动跟进 · 体检后健康管理',exact=True).scroll_into_view_if_needed()
        shot('05-member360-waiting',keep_scroll=True)
        role('医生');search('搜索记录','助手可见性验收');row()
        page.get_by_label('医学判断',exact=True).fill('合成演示：已核对肝功能变化，建议按期复查。')
        page.get_by_label('建议',exact=True).fill('了解饮酒情况并确认生活方式执行情况，按建议时间复查肝功能。')
        radio('需要');page.get_by_label('复查项目',exact=True).fill('肝功能复查')
        page.get_by_role('button',name='提交判断',exact=True).click()
        page.get_by_text('● 当前正在：保存医生判断，并将医生意见整理为后续行动',exact=True).wait_for(timeout=90000)
        page.get_by_text('健康管理助手继续工作',exact=True).scroll_into_view_if_needed()
        shot('06-doctor-return-processing',keep_scroll=True)
        page.get_by_text('医学判断已提交，健康管理师将确认后续安排。',exact=True).wait_for(timeout=300000)
        settle();button('← 返回待我判断');role('健康管理师');radio('今日工作')
        button('继续处理');assert '确认并创建后续安排' in page.locator('body').inner_text()
        assert '已收到医生判断，原流程自动继续' in page.locator('body').inner_text()
        shot('07-action-approval');button('确认并创建后续安排')
        page.get_by_role('heading',name='本次自动管理已完成',exact=True).wait_for(timeout=90000);settle()
        assert '本次自动管理已完成' in page.locator('body').inner_text()
        assert '最终产出' in page.locator('body').inner_text()
        shot('08-completed-output');button('返回会员360')
        page.get_by_text('自动跟进 · 体检后健康管理',exact=True).scroll_into_view_if_needed()
        assert '当前：本次管理已完成' in page.locator('body').inner_text()
        shot('09-member360-completed',keep_scroll=True)
        (OUT/'browser-results.json').write_text(json.dumps({'actual_browser':'Chromium','states':{
            'running':'real report reread command','waiting_manager':'PASS','waiting_doctor':'PASS',
            'doctor_resume':'real doctor submission command','action_approval':'PASS','completed':'PASS','member360':'PASS'},
            'pages':results,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
    except Exception:
        page.screenshot(path=str(OUT/'failure.png'),full_page=True)
        (OUT/'failure.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
        raise
    finally:browser.close()
