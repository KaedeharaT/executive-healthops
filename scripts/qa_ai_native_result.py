"""Real result-input story; isolated synthetic data only, root navigation only."""
import json,time,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
OUT=Path('docs/images/ai-native-final');OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':900})
    def settle():
        page.wait_for_timeout(600)
        expect(page.locator('[data-testid=stApp]')).to_have_attribute('data-test-script-state','notRunning',timeout=90000)
        assert not page.locator('[data-testid=stException]').count(),page.locator('body').inner_text()
    def shot(name):
        page.locator('[data-testid=stMain]').evaluate('(e)=>e.scrollTo(0,0)')
        page.screenshot(path=str(OUT/(name+'.png')))
        (OUT/(name+'.txt')).write_text(page.locator('body').inner_text(),encoding='utf-8')
        print(name,flush=True)
    try:
        page.goto('http://127.0.0.1:18701')
        expect(page.get_by_role('button',name='进入 HealthOps 运营后台',exact=True)).to_be_visible(timeout=90000)
        page.get_by_role('button',name='进入 HealthOps 运营后台',exact=True).click();settle()
        page.get_by_label('查找待办',exact=True).fill('复查候选去重验收' if '--dedup' in sys.argv else '医生返回后电话随访' if '--after-doctor' in sys.argv else '连续管理电话随访')
        page.get_by_label('查找待办',exact=True).press('Enter');settle();shot('01-today')
        for x in (150,90,15):
            page.locator('[data-testid=stDataFrame]').first.click(position={'x':x,'y':55});settle()
            if page.get_by_role('textbox',name='记录处理结果',exact=True).count() or page.get_by_role('checkbox',name='我已核对本次结果与后续安排',exact=True).count():break
        if page.get_by_role('textbox',name='记录处理结果',exact=True).count():
            page.get_by_role('textbox',name='记录处理结果',exact=True).fill('会员说睡眠每天6小时，准备10月22日复查血脂。' if '--dedup' in sys.argv else '会员最近已经不喝酒了，睡眠每天6个小时左右，准备10月15日去复查血脂。')
            shot('07-natural-language-result')
            page.get_by_role('button',name='整理本次结果',exact=True).click();settle();shot('result-running')
        expect(page.get_by_role('checkbox',name='我已核对本次结果与后续安排',exact=True)).to_be_visible(timeout=660000)
        assert page.locator('.agent-action-spinner').count()==0
        shot('result-waiting-confirmation')
        page.get_by_role('checkbox',name='我已核对本次结果与后续安排',exact=True).locator('xpath=ancestor::label').click()
        page.get_by_role('button',name='确认并保存本次结果',exact=True).click();settle()
        expect(page.get_by_text('本次已完成',exact=True)).to_be_visible();shot('result-completed')
        (OUT/'result-browser.json').write_text(json.dumps({'chromium':browser.version,'input_count':1,'same_item':True,'completed':True},indent=2),encoding='utf-8')
    except Exception:
        shot('result-failure');raise
    finally:browser.close()
