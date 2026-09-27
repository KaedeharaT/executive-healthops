"""Continue the real import journey with member visibility and trend verification."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
OUT=Path('docs/images/profile-intake-agent')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1100})
    def settle():
        page.wait_for_timeout(500)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden',timeout=90000)
        page.wait_for_timeout(800)
        assert not page.locator('[data-testid="stException"]').count(),page.locator('body').inner_text()
    def button(name):page.get_by_role('button',name=name,exact=True).click();settle()
    def radio(name):page.get_by_role('radio',name=name,exact=True).locator('xpath=ancestor::label').click();settle()
    def shot(name):page.screenshot(path=str(OUT/name),full_page=True)
    try:
        page.goto(os.getenv('QA_URL','http://127.0.0.1:8502'),wait_until='networkidle');settle()
        button('进入成员健康中心');radio('健康');radio('健康档案')
        expect(page.get_by_role('heading',name='已确认健康资料',exact=True)).to_be_visible()
        shot('09-member-synced.png')
        radio('健康数据')
        print('COMBOBOXES',page.get_by_role('combobox').evaluate_all('(els)=>els.map(e=>e.getAttribute("aria-label"))'),flush=True)
        print(page.locator('body').inner_text(),flush=True)
        shot('08-health-trend-updated.png')
        radio('体检与检查');shot('14-member-report-synced.png')
        print('MEMBER ARCHIVE + HEALTH DATA + REPORT pages PASS',flush=True)
    except Exception:
        page.screenshot(path='.runtime/profile-sync-failure.png',full_page=True)
        print(page.locator('body').inner_text(),flush=True);raise
    finally:browser.close()
