"""Read-only final administrator verification in actual Chromium."""
import json,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
sys.stdout.reconfigure(encoding='utf-8');OUT=Path('docs/images/ai-native-final')
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':900})
    def settle():
        page.wait_for_timeout(700);expect(page.locator('[data-testid=stApp]')).to_have_attribute('data-test-script-state','notRunning',timeout=90000)
        assert not page.locator('[data-testid=stException]').count()
    def button(n):page.get_by_role('button',name=n,exact=True).click();settle()
    def radio(n):page.get_by_role('radio',name=n,exact=True).locator('xpath=ancestor::label').click();settle()
    def shot(n):
        page.locator('[data-testid=stMain]').evaluate('(e)=>e.scrollTo(0,0)');page.screenshot(path=str(OUT/(n+'.png')))
        (OUT/(n+'.txt')).write_text(page.locator('body').inner_text(),encoding='utf-8')
    page.goto('http://127.0.0.1:18701');expect(page.get_by_role('button',name='进入 HealthOps 运营后台',exact=True)).to_be_visible(timeout=90000);button('进入 HealthOps 运营后台')
    page.get_by_text('切换演示角色',exact=True).click();radio('管理员');page.get_by_text('切换演示角色',exact=True).click();settle()
    radio('自动化运行');radio('管理工具');shot('14-admin-tool-registry')
    radio('运行记录');page.locator('[data-testid=stDataFrame]').last.click(position={'x':180,'y':55});settle()
    expect(page.get_by_text('持久化执行记录',exact=True)).to_be_visible();shot('13-admin-agent-trace')
    print('Actual Chromium '+browser.version+'; registry and persistent trace PASS');browser.close()
