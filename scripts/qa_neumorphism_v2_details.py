"""Real Chromium detail captures and non-submitting control-state checks."""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/images/neumorphism-v2/details'
OUT.mkdir(parents=True,exist_ok=True)
sys.stdout.reconfigure(encoding='utf-8')
checks={}
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':900})
    def settle():
        page.wait_for_timeout(700)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden',timeout=90000)
        page.wait_for_timeout(400)
        assert not page.locator('[data-testid="stException"]').count()
    def button(name):
        page.get_by_role('button',name=name,exact=True).last.click();settle()
    def radio(name):
        page.get_by_role('radio',name=name,exact=True).last.locator('xpath=ancestor::label').click();settle()
    def capture(name,selector):
        page.locator(selector).screenshot(path=str(OUT/(name+'.png')))
    page.goto('http://127.0.0.1:18503',wait_until='networkidle');settle();button('进入 HealthOps 运营后台')
    capture('today-table','.st-key-neu-work')
    radio('会员');field=page.get_by_label('搜索成员',exact=True);field.fill('Demo Executive A');field.press('Enter');settle()
    page.locator('[data-testid="stDataFrame"]').last.click(position={'x':100,'y':55});settle();radio('健康档案')
    capture('archive-grid','.st-key-soft-archive-summary')
    assert page.locator('.neu-archive-grid>div').count()==7
    button('继续填写')
    page.get_by_role('combobox',name='填写步骤',exact=True).click()
    page.get_by_role('option',name='1. 基础资料',exact=True).click();settle()
    capture('assessment-stepper','.st-key-soft-intake-progress')
    capture('assessment-form','[data-testid="stForm"]')
    checks['stepper']=page.locator('.neu-intake-steps').evaluate('e=>({display:getComputedStyle(e).display,columns:getComputedStyle(e).gridTemplateColumns,steps:e.children.length})')
    assert checks['stepper']['display']=='grid' and checks['stepper']['steps']==11
    field=page.get_by_label('姓名 / 称呼',exact=True);field.focus();page.keyboard.press('Tab');page.keyboard.press('Shift+Tab')
    checks['input_focus']=field.evaluate('e=>({style:getComputedStyle(e).outlineStyle,width:getComputedStyle(e).outlineWidth})')
    assert checks['input_focus']=={'style':'solid','width':'3px'}
    button_control=page.get_by_role('button',name='保存草稿并继续',exact=True)
    button_control.scroll_into_view_if_needed();page.mouse.move(310,70)
    checks['button_normal']=button_control.evaluate('e=>getComputedStyle(e).boxShadow')
    button_control.hover();page.wait_for_timeout(180);checks['button_hover']=button_control.evaluate('e=>getComputedStyle(e).boxShadow')
    page.mouse.down();page.wait_for_timeout(180)
    checks['button_pressed']=button_control.evaluate('e=>getComputedStyle(e).boxShadow')
    page.mouse.move(310,70);page.mouse.up();settle()
    assert checks['button_pressed'].count('inset')==2
    assert checks['button_normal']!=checks['button_hover']
    assert checks['button_normal']!=checks['button_pressed']
    page.emulate_media(reduced_motion='reduce')
    checks['reduced_motion']=button_control.evaluate('e=>getComputedStyle(e).transitionDuration')
    assert checks['reduced_motion']=='0s'
    step_select=page.get_by_role('combobox',name='填写步骤',exact=True)
    step_select.fill('确认提交')
    step_select.press('ArrowDown')
    page.get_by_role('option',name='11. 确认提交',exact=True).click();settle()
    disabled=page.get_by_role('button',name='提交初始评估',exact=True)
    assert disabled.is_disabled()
    checks['disabled']=disabled.evaluate('e=>({background:getComputedStyle(e).backgroundColor,color:getComputedStyle(e).color,shadow:getComputedStyle(e).boxShadow})')
    assert checks['disabled']['shadow']=='none'
    page.locator('[data-testid="stMain"]').evaluate('e=>e.scrollTo(0,0)')
    page.get_by_text('切换演示角色',exact=True).click();radio('管理员');page.keyboard.press('Escape');settle()
    page.screenshot(path=str(OUT/'admin.png'))
    checks['admin_no_duplicate_key']=not page.locator('[data-testid="stException"]').count()
    checks['contrast']=page.evaluate((ROOT/'scripts/neumorphism_contrast.js').read_text(encoding='utf-8'))
    assert not checks['contrast']['findings']
    (OUT/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    browser.close()
print(json.dumps(checks,ensure_ascii=False))
