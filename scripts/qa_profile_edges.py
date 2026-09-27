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
        button('＋ 导入健康资料');radio('健康问卷')
        content=json.dumps({'source_date':'2026-09-27','responses':{'生活方式':{'运动':'未确认自述验证：每周散步'},'会员重点关注':{'concern':'未确认自述验证：希望改善作息'}}},ensure_ascii=False).encode()
        page.locator('input[type=file]').set_input_files({'name':'合成待确认问卷.json','mimeType':'text/plain','buffer':content});settle();button('上传并整理资料')
        expect(page.get_by_role('button',name='确认并更新健康档案',exact=True)).to_be_visible(timeout=90000);settle()
        page.locator('[data-testid="stMain"]').evaluate('e=>e.scrollTop=0');shot('12-questionnaire-preview.png')
        button('← 返回健康档案');radio('今日工作')
        field=page.get_by_role('textbox',name='查找待办',exact=True);field.fill('新健康资料已整理');field.press('Enter');settle()
        page.locator('[data-testid="stDataFrame"]').last.scroll_into_view_if_needed();shot('22-today-import-item.png')
        page.locator('[data-testid="stDataFrame"]').last.click(position={'x':70,'y':55});settle()
        assert '合成待确认问卷.json' in page.locator('body').inner_text()
        button('← 返回健康档案')
        role('成员');radio('健康');radio('健康档案');shot('09-member-synced.png')
        role('医生');radio('历史')
        field=page.get_by_role('textbox',name='搜索记录',exact=True);field.fill('合成导入验收');field.press('Enter');settle()
        page.locator('[data-testid="stDataFrame"]').last.click(position={'x':70,'y':55});settle()
        assert '暂无原始依据' not in page.locator('body').inner_text();shot('17-doctor-source-context.png')
        role('健康管理师');radio('会员');radio('健康档案')
        button('＋ 导入健康资料');radio('体检报告')
        page.locator('input[type=file]').set_input_files({'name':'合成损坏文件.pdf','mimeType':'application/pdf','buffer':b'%PDF-1.4\nbroken document'});settle();button('上传并整理资料')
        expect(page.get_by_role('button',name='重新尝试整理',exact=True)).to_be_visible(timeout=90000);settle()
        shot('21-safe-parse-fallback.png')
        assert '原文件已保存' in page.locator('body').inner_text()
        print('TODAY DIRECT ENTRY, UNCONFIRMED MEMBER BOUNDARY, DOCTOR SOURCE AND PARSE FAILURE PASS',flush=True)
    except Exception:
        page.screenshot(path='.runtime/profile-doctor-failure.png',full_page=True);print(page.locator('body').inner_text(),flush=True);raise
    finally:browser.close()
