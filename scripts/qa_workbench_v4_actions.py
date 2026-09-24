"""Real browser save/follow-up/selection checks on the isolated V4 fixture only."""
import json,sqlite3
from datetime import date,timedelta
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright

db=Path('.runtime/workbench-v4.db').resolve()
assert db.parent.name=='.runtime' and db.name=='workbench-v4.db'
out=Path('docs/images/workbench-v2')
marker='浏览器验收-'+uuid4().hex[:6]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1600,'height':1100})
    def settle():
        page.wait_for_timeout(700)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden',timeout=60000)
        page.wait_for_timeout(800)
        assert not page.locator('[data-testid="stException"]').count(),page.locator('body').inner_text()
    def radio(label):page.get_by_role('radio',name=label,exact=True).last.locator('xpath=ancestor::label').click();settle()
    def button(label):page.get_by_role('button',name=label,exact=True).last.click();settle()
    def fill(label,value):page.get_by_label(label,exact=True).fill(value)
    def select(label,value):
        box=page.get_by_label(label,exact=True)
        box.click();box.press('ArrowDown')
        try: page.get_by_role('option',name=value,exact=True).click(timeout=10000)
        except Exception:
            Path('.runtime/v4-actions-debug.txt').write_text(page.locator('body').inner_text(),encoding='utf8')
            page.screenshot(path='.runtime/v4-actions-debug.png')
            raise
        settle()
    page.goto('http://127.0.0.1:18514',wait_until='networkidle');settle()
    radio('会员');fill('搜索成员','张先生');page.get_by_label('搜索成员',exact=True).press('Enter');settle()
    page.locator('[data-testid="stDataFrame"]').first.click(position={'x':80,'y':55});settle();radio('管理');button('新增管理记录')
    fill('发生了什么',marker+'已与会员确认复查时间')
    fill('我做了什么','核对医生既有安排，联系会员确认')
    fill('本次结果','已确认')
    fill('下一步',marker+'确认复查预约')
    follow_date=page.locator('[data-testid="stDateInput"]').filter(has_text='下次跟进日期').locator('input')
    follow_date.fill((date.today()+timedelta(days=3)).strftime('%Y/%m/%d'))
    follow_date.press('Tab')
    page.get_by_role('button',name='保存并创建下一步',exact=True).scroll_into_view_if_needed()
    page.screenshot(path=str(out/'management-log-create.png'))
    button('保存并创建下一步')
    assert '记录已保存' in page.locator('body').inner_text()
    select('管理工作','管理事项');fill('搜索记录',marker);page.get_by_label('搜索记录',exact=True).press('Enter');settle()
    grid=page.locator('[data-testid="stDataFrame"]').first
    grid.click(position={'x':17,'y':55});settle()
    assert marker+'确认复查预约' in page.locator('body').inner_text()
    page.screenshot(path=str(out/'log-created-next-work.png'))
    with sqlite3.connect(db) as conn:
        rows=conn.execute('select l.follow_up_task_id,t.title,t.patient_id=l.patient_id,t.program_id=l.program_id from management_logs l join tasks t on t.id=l.follow_up_task_id where l.member_issue like ?',(marker+'%',)).fetchall()
        assert len(rows)==1 and rows[0][2:]==(1,1),rows
    button('关闭')
    assert not page.get_by_role('button',name='关闭',exact=True).count()
    # Switching selected member must not retain another member's follow-up.
    button('← 返回成员列表');fill('搜索成员','Demo Executive A');page.get_by_label('搜索成员',exact=True).press('Enter');settle()
    page.locator('[data-testid="stDataFrame"]').first.click(position={'x':80,'y':55});settle();radio('管理')
    assert marker not in page.locator('body').inner_text()
    (out/'action-results.json').write_text(json.dumps({'actual_browser':True,'log_saved':True,'next_task_created_once':True,'member_and_program_match':True,'drawer_closed':True,'member_switch_isolated':True},indent=2),encoding='utf8')
    browser.close()
