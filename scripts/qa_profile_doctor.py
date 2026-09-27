"""Browser verification of Today discovery, doctor handoff and original-run resume."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
OUT=Path('docs/images/profile-intake-agent')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1100})
    def settle():
        page.wait_for_timeout(450);page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden',timeout=90000);page.wait_for_timeout(750)
        assert not page.locator('[data-testid="stException"]').count(),page.locator('body').inner_text()
    def button(name):page.get_by_role('button',name=name,exact=True).click();settle()
    def radio(name):page.get_by_role('radio',name=name,exact=True).locator('xpath=ancestor::label').click();settle()
    def role(name):page.get_by_role('button',name='切换演示角色').click();settle();radio(name);page.get_by_text('HealthOps',exact=True).first.click();settle()
    def shot(name):page.screenshot(path=str(OUT/name),full_page=True)
    try:
        page.goto(os.getenv('QA_URL','http://127.0.0.1:8502'),wait_until='networkidle');settle()
        button('进入 HealthOps 运营后台');radio('会员')
        field=page.get_by_role('textbox',name='搜索成员',exact=True);field.fill('Demo Executive A');field.press('Enter');settle()
        page.locator('[data-testid="stDataFrame"]').first.click(position={'x':65,'y':55});settle();radio('健康档案')
        page.get_by_role('heading',name='资料导入记录',exact=True).scroll_into_view_if_needed();shot('10-import-history.png')
        button('＋ 导入健康资料');radio('历史健康档案')
        content=json.dumps({'source_date':'2026-09-28','responses':{'环境与暴露':{'噪音':'合成待核对资料：工作场所噪音'}}},ensure_ascii=False).encode()
        page.locator('input[type=file]').set_input_files({'name':'合成验收医生核对.json','mimeType':'text/plain','buffer':content});settle();button('上传并整理资料')
        expect(page.get_by_role('button',name='确认并更新健康档案',exact=True)).to_be_visible(timeout=90000);settle()
        page.locator('[data-testid="stMain"]').evaluate('e=>e.scrollTop=0');shot('15-review-action-visible.png')
        page.get_by_text('需要医学判断时提交医生',exact=True).click();settle()
        page.get_by_role('textbox',name='需要医生判断的问题',exact=True).fill('合成导入验收：历史暴露资料是否需要医学随访？')
        button('提交医生判断');assert '等待医生判断' in page.locator('body').inner_text();shot('16-waiting-doctor.png')
        role('医生')
        field=page.get_by_role('textbox',name='搜索记录',exact=True);field.fill('合成导入验收');field.press('Enter');settle()
        page.locator('[data-testid="stDataFrame"]').last.click(position={'x':65,'y':55});settle()
        shot('17-doctor-source-context.png')
        page.get_by_role('textbox',name='医学判断',exact=True).fill('合成验收：先核对暴露来源，本次不作新诊断。')
        page.get_by_role('textbox',name='建议',exact=True).fill('保留原始来源，完成档案核对。')
        button('提交判断');role('健康管理师')
        expect(page.get_by_role('button',name='确认并更新健康档案',exact=True)).to_be_visible(timeout=40000)
        shot('18-resumed-same-import.png');button('确认并更新健康档案')
        expect(page.get_by_text('本次健康资料已整理完成',exact=True)).to_be_visible();shot('19-doctor-route-completed.png')
        print('DOCTOR SUBMIT -> ORIGINAL IMPORT RESUMED -> CONFIRMED PASS',flush=True)
    except Exception:
        page.screenshot(path='.runtime/profile-doctor-failure.png',full_page=True);print(page.locator('body').inner_text(),flush=True);raise
    finally:browser.close()
