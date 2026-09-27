"""Real Chromium journey against an isolated copy of the synthetic demo database."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

OUT = Path('docs/images/intake-assessment-entry')
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1100})
    def settle():
        page.wait_for_timeout(400)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden',timeout=90000)
        page.wait_for_timeout(900)
        assert not page.locator('[data-testid="stException"]').count(), page.locator('body').inner_text()
    def radio(name):
        page.get_by_role('radio',name=name,exact=True).locator('xpath=ancestor::label').click();settle()
    def button(name):
        target=page.get_by_role('button',name=name,exact=True)
        expect(target).to_have_count(1,timeout=15000)
        target.click();settle()
    def shot(name):
        page.locator('[data-testid="stMain"]').evaluate('e=>e.scrollTop=0')
        page.screenshot(path=str(OUT/name),full_page=True)
    def member():
        radio('会员')
        field=page.get_by_role('textbox',name='搜索成员',exact=True)
        if field.count():
            field.fill('Demo Executive A');field.press('Enter');settle()
            page.locator('[data-testid="stDataFrame"]').first.click(position={'x':65,'y':55});settle()
        radio('健康档案')
        if page.get_by_role('button',name='← 返回健康档案',exact=True).count():
            button('← 返回健康档案')
    try:
        page.goto(os.getenv('QA_URL','http://127.0.0.1:8502'),wait_until='networkidle');settle()
        button('进入 HealthOps 运营后台')
        member()
        if page.get_by_role('button',name='开始评估',exact=True).count():
            shot('01-health-record-entry-empty.png');button('开始评估');shot('02-intake-wizard.png')
            button('保存草稿并继续');button('← 返回健康档案');shot('03-intake-draft.png')
        if page.get_by_role('button',name='继续填写',exact=True).count():
            button('继续填写')
            field=page.get_by_role('combobox',name='填写步骤',exact=True)
            field.click();field.fill('家族健康史')
            page.get_by_role('option',name='2. 家族健康史',exact=True).click();settle()
            # Use the visible wizard, preserving the existing table editor and validation.
            for _ in range(10):
                text=page.locator('body').inner_text()
                if page.get_by_role('button',name='提交初始评估',exact=True).count(): break
                if '第2步 /' in text:
                    grid=page.locator('[data-testid="stDataFrame"]').first
                    grid.dblclick(position={'x':120,'y':55})
                    page.locator('textarea').last.fill('合成自述家族史，待核对')
                    page.locator('textarea').last.press('Tab')
                    page.wait_for_timeout(800)
                    page.get_by_text('第2步 / 11步 · 可保存草稿后继续填写',exact=True).click()
                    page.wait_for_timeout(500)
                if '第7步 /' in text:
                    page.get_by_role('textbox',name='睡眠',exact=True).fill('合成自述：希望改善睡眠规律')
                    page.get_by_role('textbox',name='运动',exact=True).fill('每周步行，待进一步核对')
                    page.get_by_role('textbox',name='饮食',exact=True).fill('希望规律三餐')
                if '第9步 /' in text:
                    page.get_by_role('textbox',name='会员自己最想改善什么',exact=True).fill('睡眠、体重；合成验收资料')
                button('保存草稿并继续')
            page.get_by_role('checkbox',name='我确认已逐项核对；未知项由健康管理团队继续确认').locator('xpath=ancestor::label').click()
            button('提交初始评估')
        # Submitted records must become ordinary Today work without another member selector.
        radio('今日工作')
        field=page.get_by_role('textbox',name='查找待办',exact=True)
        field.fill('初始健康评估已提交');field.press('Enter');settle()
        shot('06-today-review-item.png')
        page.locator('[data-testid="stDataFrame"]').last.click(position={'x':75,'y':55});settle()
        assert '会员自述关注：睡眠、体重' in page.locator('body').inner_text()
        shot('04-manager-review.png')
        page.get_by_role('textbox',name='专业管理重点',exact=True).fill('核对自述资料；规律作息与持续随访')
        page.get_by_role('textbox',name='初步年度管理重点',exact=True).fill('建立健康资料，持续记录生活方式')
        page.get_by_role('combobox',name='初评决定',exact=True).click()
        page.get_by_role('option',name='确认初评 / 交医生确认',exact=True).click()
        button('保存健管初评')
        assert '本次处理已完成' in page.locator('body').inner_text()
        button('← 返回今日工作')
        field=page.get_by_role('textbox',name='查找待办',exact=True)
        field.fill('初始健康评估已提交');field.press('Enter');settle()
        assert '当前没有需要处理的工作' in page.locator('body').inner_text()
        member();shot('05-health-record-completed.png')
        assert '健管确认：已完成' in page.locator('body').inner_text()
        button('查看评估')
        assert '睡眠、体重；合成验收资料' in page.locator('body').inner_text()
        assert page.locator('[data-testid="stDataFrame"]').count() >= 3
        shot('07-assessment-completed-detail.png')
        print('PASS: empty entry, eleven-step wizard, saved draft, Today review, confirmation, archive sync and completed detail')
    except Exception:
        page.screenshot(path=str(OUT/'failure.png'),full_page=True)
        print(page.locator('body').inner_text())
        raise
    finally:
        browser.close()

