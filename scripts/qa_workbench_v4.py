"""Real Chromium acceptance against an isolated synthetic Streamlit server.

Run: python scripts/qa_workbench_v4.py --url http://127.0.0.1:18514
Requires the optional Playwright browser tooling. Never points at a member database.
"""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:18514');args=parser.parse_args()
out=Path('docs/images/workbench-v2');out.mkdir(parents=True,exist_ok=True)
runtime=Path('.runtime');results=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1600,'height':1100},device_scale_factor=1)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    def settle():
        page.wait_for_timeout(800)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden',timeout=60000)
        page.wait_for_timeout(1000)
        exc=page.locator('[data-testid="stException"]')
        assert not exc.count(),exc.inner_text() if exc.count() else ''
        assert not errors,errors
    def radio(label):
        page.get_by_role('radio',name=label,exact=True).last.locator('xpath=ancestor::label').click();settle()
    def button(label):page.get_by_role('button',name=label,exact=True).last.click();settle()
    def expand(label):page.get_by_text(label,exact=True).last.click();settle()
    def select(label,value):
        page.get_by_label(label,exact=True).click()
        page.get_by_role('option',name=value,exact=True).click();settle()
    def shot(name):
        page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTop=0')
        page.wait_for_timeout(350)
        page.screenshot(path=str(out/(name+'.png')))
        (runtime/(name+'-v4.txt')).write_text(page.locator('body').inner_text(),encoding='utf8')
        counts=page.evaluate('''()=>{const visible=s=>[...document.querySelectorAll(s)].filter(e=>{
            const r=e.getBoundingClientRect(); if(!r.height||!e.checkVisibility({checkVisibilityCSS:true}))return false;
            if(e.closest('details:not([open])'))return false;
            for(let a=e.parentElement;a;a=a.parentElement){const ar=a.getBoundingClientRect();
                if(['hidden','clip'].includes(getComputedStyle(a).overflowY)&&(r.top>=ar.bottom||r.bottom<=ar.top))return false;}
            return true;}).length;
            return {tables:visible('[data-testid="stDataFrame"]'),charts:visible('[data-testid="stVegaLiteChart"]'),
            timelines:visible('.v2-timeline'),steppers:visible('.v2-workflow,[class*="st-key-care-stage-selector-"],.overview-stages'),drawers:visible('[class*="st-key-care-drawer-"]')};}''')
        results.append({'page':name,**counts});print(name,flush=True)
        (out/'browser-results.json').write_text(json.dumps({'pages':results,'errors':errors},ensure_ascii=False,indent=2),encoding='utf8')
    def grid_row(index=0,grid=0):
        box=page.locator('[data-testid="stDataFrame"]').nth(grid)
        box.scroll_into_view_if_needed();box.click(position={'x':17,'y':55+36*index});settle()
    page.goto(args.url,wait_until='networkidle');settle()
    page.get_by_label('查找待办',exact=True).wait_for(state='visible',timeout=60000)
    shot('manager-today')
    grid_row();shot('manager-today-detail');button('关闭')
    page.get_by_label('查找待办',exact=True).fill('不存在的会员__');page.get_by_label('查找待办',exact=True).press('Enter');settle()
    assert '当前筛选下暂无事项' in page.locator('body').inner_text()
    page.get_by_label('查找待办',exact=True).fill('');page.get_by_label('查找待办',exact=True).press('Enter');settle()
    radio('会员');shot('member-list')
    page.get_by_label('搜索成员',exact=True).fill('张先生');page.get_by_label('搜索成员',exact=True).press('Enter');settle()
    grid_row();shot('member-360')
    radio('健康档案');shot('member-health-record')
    radio('管理');shot('member-management')
    select('管理工作','管理日志');shot('management-log')
    radio('表格');shot('management-log-table');radio('时间轴')
    select('管理工作','检查复查');shot('recheck');grid_row();shot('recheck-detail')
    select('管理工作','年度方案与阶段');shot('annual-stage-detail')
    select('管理工作','阶段评估');shot('stage-review')
    radio('年度管理');shot('annual-management');grid_row(2);shot('annual-selected')
    radio('医疗协同');shot('medical-collaboration');grid_row();shot('doctor-review-detail');button('关闭')
    radio('正式会诊');shot('consultation');grid_row();shot('consultation-detail')
    radio('服务');shot('service');grid_row();shot('service-detail');button('关闭')
    page.get_by_text('切换演示角色',exact=True).click();settle();radio('成员')
    page.get_by_text('切换演示角色',exact=True).click();settle()
    select('当前成员','Demo Executive A') if page.get_by_label('当前成员',exact=True).count() else None
    radio('健康');shot('member-health')
    radio('计划');shot('member-plan')
    radio('首页');shot('member-home')
    browser.close()
