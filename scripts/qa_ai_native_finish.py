"""Complete the existing synthetic member's human decisions in Chromium."""
import json,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
sys.stdout.reconfigure(encoding='utf-8')
OUT=Path('docs/images/ai-native-final')
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':900})
    def settle():
        page.wait_for_timeout(700)
        expect(page.locator('[data-testid=stApp]')).to_have_attribute('data-test-script-state','notRunning',timeout=90000)
        assert not page.locator('[data-testid=stException]').count()
    def button(name):page.get_by_role('button',name=name,exact=True).click();settle()
    def radio(name):page.get_by_role('radio',name=name,exact=True).locator('xpath=ancestor::label').click();settle()
    def shot(name):
        page.locator('[data-testid=stMain]').evaluate('(e)=>e.scrollTo(0,0)');page.screenshot(path=str(OUT/(name+'.png')))
        (OUT/(name+'.txt')).write_text(page.locator('body').inner_text(),encoding='utf-8');print(name,flush=True)
    def today(search):
        radio('今日工作')
        if page.get_by_role('button',name='← 返回今日工作',exact=True).count():button('← 返回今日工作')
        field=page.get_by_label('查找待办',exact=True);field.fill(search);field.press('Enter');settle()
        page.locator('[data-testid=stDataFrame]').first.click(position={'x':150,'y':55});settle()
    try:
        page.goto('http://127.0.0.1:18701');expect(page.get_by_role('button',name='进入 HealthOps 运营后台',exact=True)).to_be_visible(timeout=90000)
        button('进入 HealthOps 运营后台')
        if '--review' in sys.argv:
            today('初始健康评估已提交')
            page.get_by_role('textbox',name='专业管理重点',exact=True).fill('根据本人资料与沟通结果，持续跟进睡眠和生活方式执行情况。')
            page.get_by_role('textbox',name='初步年度管理重点',exact=True).fill('规律记录、电话随访和医生已确认复查安排。')
            page.get_by_label('初评决定',exact=True).click();page.get_by_role('option',name='确认初评 / 交医生确认',exact=True).click()
            button('保存健管初评');shot('intake-professional-review')
        if '--actions' in sys.argv:
            today('医生意见已返回');shot('doctor-actions-before')
            button('确认并创建后续安排');shot('doctor-actions-completed')
        if '--member' in sys.argv or '--stage' in sys.argv:
            radio('会员');field=page.get_by_label('搜索成员',exact=True);field.fill('张三');field.press('Enter');settle()
            page.locator('[data-testid=stDataFrame]').last.click(position={'x':150,'y':55});settle();shot('02-member360')
            radio('健康档案')
            upload=page.get_by_text('上传健康资料',exact=True).first
            if not page.locator('input[type=file]').is_visible():upload.click();settle()
            upload.evaluate("(e)=>e.scrollIntoView({block:'start'})");page.screenshot(path=str(OUT/'03-health-record-input.png'))
            (OUT/'03-health-record-input.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
            radio('管理');shot('08-management')
            if '--stage' in sys.argv:
                button('进行阶段复盘');shot('11-stage-review')
                page.get_by_role('checkbox',name='我已核对阶段结果，确认本次复盘',exact=True).locator('xpath=ancestor::label').click()
                button('确认并进入下一阶段');shot('12-next-phase')
    except Exception:shot('finish-failure');raise
    finally:browser.close()
