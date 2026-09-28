"""Exercise real UI writes only on the disposable, synthetic dedup fixture."""
import json,re,sqlite3
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/images/ui-dedup-audit'
DB=ROOT/'.runtime/ui-dedup/qa.db'
with sqlite3.connect(DB) as db:
    goal_count=db.execute('select count(*) from agent_goals').fetchone()[0]

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1050});page.set_default_timeout(45000)
    results={'browser':browser.version}
    def settle():
        page.wait_for_timeout(700)
        expect(page.locator('[data-testid="stApp"]')).to_have_attribute('data-test-script-state','notRunning',timeout=90000)
        page.wait_for_function('!document.querySelector(\'[data-stale="true"]\')')
        assert not page.locator('[data-testid="stException"]').count()
    def button(label):page.get_by_role('button',name=label,exact=True).click();settle()
    def radio(label):page.get_by_role('radio',name=label,exact=True).locator('xpath=ancestor::label').click();settle()
    def search(label,text):page.get_by_label(label,exact=True).fill(text);page.get_by_label(label,exact=True).press('Enter');settle()
    def row():page.locator('[data-testid="stDataFrame"]').last.click(position={'x':160,'y':55});settle()
    def role(label):
        page.get_by_text('切换演示角色',exact=True).click();radio(label)
        page.get_by_text('切换演示角色',exact=True).click();settle()
    def shot(name,anchor):
        page.get_by_text(anchor,exact=True).first.scroll_into_view_if_needed()
        page.screenshot(path=str(OUT/(name+'.png')))
    try:
        page.goto('http://127.0.0.1:18585',wait_until='networkidle');settle();button('进入 HealthOps 运营后台')
        # Two distinct reports remain distinct. The doctor's report is the latest
        # member summary, so compare its source and launch time from both contexts.
        page.get_by_role('button',name='查看运行看板',exact=True).last.click();settle()
        today=page.locator('body').inner_text()
        assert '等待医生判断' in today
        button('← 返回今日工作');radio('会员');search('搜索成员','Demo Executive A');row()
        button('查看运行看板');member=page.locator('body').inner_text()
        assert '等待医生判断' in member
        for line in today.splitlines():
            if line.startswith('开始原因：') or line=='Demo Executive A · 体检后健康管理':assert line in member
        with sqlite3.connect(DB) as db:assert db.execute('select count(*) from agent_goals').fetchone()[0]==goal_count
        results['same_agent_today_member_no_creation']=True
        button('← 返回会员360');button('← 返回会员')
        search('搜索成员','UI Audit Intake');row();radio('健康档案')
        expect(page.locator('[data-testid="stFileUploader"]')).to_have_count(1)
        payload=json.dumps({'responses':{'生活方式':{'饮酒':'会员自述每月一次'}}},ensure_ascii=False).encode()
        page.locator('input[type="file"]').set_input_files({'name':'合成去重验收问卷.json','mimeType':'application/json','buffer':payload})
        settle();button('上传并整理资料')
        expect(page.get_by_role('button',name=re.compile('^处理剩余'))).to_be_visible(timeout=90000)
        settle();shot('35-upload-to-exceptions','需要你处理')
        assert not page.get_by_role('button',name='继续完成初始评估',exact=True).count()
        page.get_by_role('button',name=re.compile('^处理剩余')).click();settle()
        before=page.locator('.st-key-intake-exception-workspace').inner_text()
        page.get_by_label('填写会员实际回答',exact=True).fill('暂不清楚（合成会员本人回答）')
        button('保存答案并处理下一项')
        after=page.locator('.st-key-intake-exception-workspace').inner_text()
        assert before!=after
        results['single_upload_to_live_agent_to_exception_save']=True
        # Doctor decision is submitted through the existing service, not through
        # an injected UI state or API; no real patient or medical decision.
        role('医生');search('搜索记录','肝功能');row()
        page.get_by_label('医学判断',exact=True).fill('合成验收：资料仍需核对，保留人工复核。')
        page.get_by_label('建议',exact=True).fill('合成验收：由责任医生核对原文件后继续处理。')
        button('提交判断')
        expect(page.get_by_text('医学判断已提交，健康管理师将确认后续安排。',exact=True)).to_be_visible()
        assert not page.get_by_role('button',name='提交判断',exact=True).count()
        shot('36-doctor-submitted','医学判断已提交，健康管理师将确认后续安排。')
        button('← 返回待我判断');radio('历史')
        results['doctor_pending_decision_submit_history']=True
        results['errors']=[]
        (OUT/'story-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Dedup core stories passed')
    except Exception:
        page.screenshot(path=str(OUT/'story-failure.png'))
        (OUT/'story-failure.txt').write_text(page.locator('body').inner_text(),encoding='utf-8');raise
    finally:browser.close()
