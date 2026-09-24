"""Keyboard-only member row activation after normal homepage navigation."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1600,'height':1100})
    page.goto('http://127.0.0.1:18517',wait_until='networkidle')
    page.get_by_role('button',name='进入 HealthOps 运营后台',exact=True).click()
    page.get_by_role('heading',name='今日工作',exact=True).wait_for()
    page.get_by_role('radio',name='会员',exact=True).locator('xpath=ancestor::label').click()
    field=page.get_by_label('搜索成员',exact=True)
    field.fill('Demo Executive A');field.press('Enter')
    page.wait_for_timeout(1500)
    field.focus()
    reached=False
    for _ in range(30):
        page.keyboard.press('Tab')
        if page.locator(':focus').evaluate('(e)=>e.tagName')=='CANVAS':
            reached=True;break
    assert reached,'Member grid must be reachable by Tab without a selector mode switch'
    page.keyboard.press('ArrowDown');page.wait_for_timeout(1000)
    if not page.get_by_role('button',name='← 返回会员',exact=True).count():
        page.keyboard.press('Enter')
    page.get_by_role('button',name='← 返回会员',exact=True).wait_for(timeout=60000)
    assert '会员本人关注' in page.locator('body').inner_text()
    assert not page.locator('[data-testid="stException"]').count()
    Path('docs/images/product-logic-v5/keyboard-results.json').write_text(json.dumps({
        'browser':'Chromium','path':'homepage → member directory → search → Tab → ArrowDown / Enter → Member360',
        'keyboard_accessibility':'PASS','selector_mode_switches':0},ensure_ascii=False,indent=2),encoding='utf-8')
    browser.close()
