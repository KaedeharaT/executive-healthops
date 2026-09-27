"""Read-only Chromium journeys, matched screenshots, responsive and preservation QA.

Uses only the isolated synthetic QA server; no live database or internal UI state injection.
"""
import argparse
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

sys.stdout.reconfigure(encoding='utf-8')

parser=argparse.ArgumentParser()
parser.add_argument('phase',choices=['before','after'])
parser.add_argument('--url',default='http://127.0.0.1:18530')
parser.add_argument('--skip-responsive',action='store_true')
args=parser.parse_args()
OUT=Path('docs/images/neumorphism-v1')/args.phase
OUT.mkdir(parents=True,exist_ok=True)
results=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':900},device_scale_factor=1)
    page.set_default_timeout(20000)
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    def settle():
        page.wait_for_timeout(650)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden',timeout=90000)
        page.wait_for_timeout(400)
        assert not page.locator('[data-testid="stException"]').count(),page.locator('body').inner_text()
        assert not errors,errors
    def button(name):
        page.get_by_role('button',name=name,exact=True).last.click();settle()
    def radio(name):
        print('navigate: '+name,flush=True)
        page.get_by_role('radio',name=name,exact=True).last.locator('xpath=ancestor::label').click();settle()
    def search(name,value):
        field=page.get_by_label(name,exact=True);field.fill(value);field.press('Enter');settle()
    def top():
        page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTo(0,0)')
    def role(name):
        top();page.get_by_text('切换演示角色',exact=True).click();radio(name)
        page.keyboard.press('Escape');settle()
    def shot(name,section=None):
        if section:
            height=int(page.locator(section).bounding_box()['height'])+180
            page.set_viewport_size({'width':1440,'height':max(900,height)});settle()
        top();page.wait_for_timeout(200)
        (page.locator(section) if section else page).screenshot(path=str(OUT/f'{name}.png'))
        if section:
            page.set_viewport_size({'width':1440,'height':900});settle()
        text=page.locator('body').inner_text()
        (OUT/f'{name}.txt').write_text(text,encoding='utf-8')
        controls=page.locator('button, input, textarea, [role="tab"], [role="combobox"]').evaluate_all('''els=>els.map(e=>({tag:e.tagName,role:e.getAttribute('role'),type:e.getAttribute('type'),label:e.getAttribute('aria-label')||e.innerText||e.getAttribute('placeholder')||'',disabled:e.disabled||false})).filter(e=>e.type!=='hidden')''')
        contrast=page.evaluate(Path('scripts/neumorphism_contrast.js').read_text(encoding='utf-8')) if args.phase=='after' else None
        results.append({'page':name,'controls':controls,'tables':page.locator('[data-testid="stDataFrame"]').count(),
            'charts':page.locator('[data-testid="stVegaLiteChart"]').count(),'errors':list(errors),'contrast':contrast})
        (OUT/'browser-results.json').write_text(json.dumps({'browser':browser.version,'pages':results,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
        print(name,flush=True)
        if args.phase=='after' and not section and not args.skip_responsive:
            for width,height in [(1366,768),(1920,1080),(390,844)]:
                page.set_viewport_size({'width':width,'height':height});settle();top()
                bounds=page.locator('[data-testid="stMain"]').evaluate('(e)=>({width:e.clientWidth,scroll:e.scrollWidth})')
                assert bounds['scroll']<=bounds['width']+2,(name,width,bounds)
                page.screenshot(path=str(OUT/f'{name}-{width}x{height}.png'),timeout=15000)
            page.set_viewport_size({'width':1440,'height':900});settle()
    def row():
        page.locator('[data-testid="stDataFrame"]').last.click(position={'x':100,'y':55});settle()
    try:
        page.goto(args.url,wait_until='networkidle');settle()
        if page.get_by_role('button',name='进入 HealthOps 运营后台',exact=True).count():button('进入 HealthOps 运营后台')
        shot('01-today')
        if page.get_by_role('button',name='查看运行看板',exact=True).count():
            page.get_by_role('button',name='查看运行看板',exact=True).first.click();settle();shot('02-agent-board')
            radio('今日工作')
        radio('会员');shot('03-member-list')
        search('搜索成员','Demo Executive A');row();shot('04-member360')
        radio('健康档案');shot('05-health-archive')
        shot('05-health-archive-summary',section='[data-testid="stMainBlockContainer"]')
        for label in ['开始评估','继续填写','查看评估']:
            if page.get_by_role('button',name=label,exact=True).count():button(label);break
        shot('06-initial-assessment')
        shot('06-initial-assessment-form',section='[data-testid="stForm"]')
        button('← 返回健康档案')
        button('＋ 导入健康资料');shot('07-import');button('取消上传')
        radio('管理');shot('08-management')
        radio('医疗');shot('09-medical')
        radio('历程');shot('10-timeline')
        radio('年度管理');shot('11-annual')
        radio('服务');shot('12-services')
        role('医生');shot('13-doctor')
        search('搜索记录','Demo Executive A');row()
        expect(page.get_by_role('button',name='提交判断',exact=True)).to_be_visible(timeout=30000)
        settle()
        shot('13-doctor-review')
        role('管理员');shot('14-admin')
        role('成员');radio('首页');shot('15-member-home')
        radio('健康');shot('16-health-trend')
        shot('16-health-trend-panel',section='.st-key-overview-trend')
        radio('健康数据');shot('17-health-data')
        shot('17-health-data-panel',section='.st-key-health-trend-panel')
        if args.phase=='after':
            field=page.get_by_label('选择健康指标',exact=True)
            field.focus();page.keyboard.press('ArrowDown');page.keyboard.press('Escape')
            focus=field.evaluate('''e=>{let s=getComputedStyle(e);return {tag:e.tagName,outline:s.outlineStyle,width:s.outlineWidth}}''')
            assert focus['outline']=='solid' and float(focus['width'].replace('px',''))>=3,focus
            page.keyboard.press('Tab')
            page.emulate_media(reduced_motion='reduce')
            motion=page.get_by_role('radio',name='健康数据',exact=True).evaluate('e=>getComputedStyle(e).transitionDuration')
            assert motion=='0s',motion
            results.append({'keyboard_focus':focus,'reduced_motion':motion})
        (OUT/'browser-results.json').write_text(json.dumps({'browser':browser.version,'pages':results,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
    except Exception:
        page.screenshot(path=str(OUT/'failure.png'))
        (OUT/'failure.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
        raise
    finally:browser.close()
