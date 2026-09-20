"""Enrollment/intake Chromium smoke for an isolated synthetic database.

This helper covers the beginning of the story only. The full browser acceptance
record (including reports, two doctors, services and stage transition) is in
 docs/REAL_WORKFLOW_BROWSER_QA.md. Never point it at a real member database.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT=Path('docs/images/real-workflow-v1');OUT.mkdir(parents=True,exist_ok=True)
STATE=Path('.runtime/real-workflow-browser.json')

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1500,'height':1150})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    def settle():
        page.wait_for_timeout(700)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden',timeout=60000)
        page.wait_for_timeout(1100)
        exc=page.locator('[data-testid="stException"]')
        assert not exc.count(),exc.inner_text() if exc.count() else ''
        assert not errors,errors
    def button(label):page.get_by_role('button',name=label,exact=True).last.click();settle()
    def radio(label):page.get_by_role('radio',name=label,exact=True).last.locator('xpath=ancestor::label').click();settle()
    def select(label,value):
        box=page.get_by_label(label,exact=True);box.click();box.press('ArrowDown');page.get_by_role('option',name=value,exact=True).click();settle()
    def fill(label,value):page.get_by_label(label,exact=True).fill(value)
    def expand(label):page.get_by_text(label,exact=True).click();settle()
    def shot(name):
        page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTop=0');page.wait_for_timeout(200)
        page.screenshot(path=str(OUT/(name+'.png')))
    page.goto('http://127.0.0.1:18512',wait_until='networkidle');settle()
    button('进入 HealthOps 运营后台');shot('manager-today')
    radio('年度管理')
    if 'Synthetic Workflow B' not in page.locator('body').inner_text():
        expand('会员入组 · 新建年度服务周期')
        fill('会员称呼','Synthetic Workflow B');fill('年度目标','建立可持续的资料核对与日常管理习惯')
        button('确认入组')
    page.get_by_role('button',name='进入年度管理',exact=True).last.click();settle()
    shot('member-360-overview')
    radio('健康档案');radio('初始评估');shot('member-intake')
    if page.get_by_role('button',name='保存草稿并继续',exact=True).count():
        for i in range(11):
            if i==9:fill('会员自己最想改善什么','希望规律记录睡眠与活动')
            button('保存草稿并继续')
        page.get_by_text('我确认已逐项核对；未知项由健康管理团队继续确认',exact=True).click();settle()
        button('提交初始评估')
    fill('专业管理重点','建立健康资料与复查安排')
    fill('需要补充资料','年度体检报告')
    fill('初步年度管理重点','按阶段核对资料和执行计划')
    select('初评决定','确认初评 / 交医生确认');button('保存健管初评')
    shot('member-health-record')
    STATE.write_text(json.dumps({'enrollment':True,'intake':True,'manager_review':True,'errors':errors}),encoding='utf8')
    browser.close()
