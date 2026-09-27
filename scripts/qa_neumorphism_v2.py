"""Same public navigation, data and top scroll position for each version."""
import argparse
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('version', choices=['original', 'previous', 'revised'])
parser.add_argument('--skip-responsive', action='store_true')
parser.add_argument('--sync-run', help='Shared fresh capture id; synchronize all three versions at each screenshot')
args = parser.parse_args()
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/images/neumorphism-v2' / args.version
OUT.mkdir(parents=True, exist_ok=True)
port = {'original':18501, 'previous':18502, 'revised':18503}[args.version]
results = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width':1440, 'height':900}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    def settle():
        page.wait_for_timeout(650)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden',timeout=90000)
        page.wait_for_timeout(400)
        assert page.locator('[data-testid="stException"]').count() == 0
    def button(name):
        page.get_by_role('button',name=name,exact=True).last.click(); settle()
    def radio(name):
        page.get_by_role('radio',name=name,exact=True).last.locator('xpath=ancestor::label').click(); settle()
    def shot(name, scroll=0):
        if args.sync_run:
            barrier=ROOT/'.runtime/neumorphism-v2/capture-sync'/args.sync_run/name
            barrier.mkdir(parents=True,exist_ok=True)
            maximum=page.locator('[data-testid="stMain"]').evaluate('e=>e.scrollHeight-e.clientHeight')
            (barrier/args.version).write_text(str(maximum),encoding='utf-8')
            deadline=time.monotonic()+120
            while not all((barrier/v).exists() for v in ['original','previous','revised']):
                assert time.monotonic()<deadline, ('capture synchronization timeout',name)
                time.sleep(.2)
            scroll=min(scroll,*[int((barrier/v).read_text(encoding='utf-8')) for v in ['original','previous','revised']])
        page.locator('[data-testid="stMain"]').evaluate('(e,y)=>e.scrollTo(0,y)',scroll)
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / (name+'.png')))
        text = page.locator('body').inner_text()
        (OUT / (name+'.txt')).write_text(text,encoding='utf-8')
        controls=page.locator('button,input,textarea,[role="tab"],[role="combobox"]').evaluate_all('''es=>es.map(e=>({tag:e.tagName,role:e.getAttribute('role'),type:e.getAttribute('type'),label:e.getAttribute('aria-label')||e.innerText||e.getAttribute('placeholder')||'',disabled:e.disabled||false})).filter(e=>e.type!=='hidden')''')
        result={'page':name,'viewport':[1440,900],'scroll':page.locator('[data-testid="stMain"]').evaluate('e=>[e.scrollLeft,e.scrollTop]'), 'controls':controls,
            'tables':page.locator('[data-testid="stDataFrame"]').count(),'charts':page.locator('[data-testid="stVegaLiteChart"]').count()}
        assert result['scroll']==[0,scroll], (name, result['scroll'], scroll)
        if args.version=='revised':
            result['contrast']=page.evaluate((ROOT/'scripts/neumorphism_contrast.js').read_text(encoding='utf-8'))
            for width,height in ([] if args.skip_responsive or scroll else [(1366,768),(1920,1080),(390,844)]):
                page.set_viewport_size({'width':width,'height':height}); settle()
                bounds=page.locator('[data-testid="stMain"]').evaluate('e=>[e.clientWidth,e.scrollWidth]')
                assert bounds[1]<=bounds[0]+2,(name,width,bounds)
                page.locator('[data-testid="stMain"]').evaluate('e=>e.scrollTo(0,0)')
                page.screenshot(path=str(OUT/f'{name}-{width}.png'))
            page.set_viewport_size({'width':1440,'height':900});settle()
        results.append(result)
        (OUT/'results.json').write_text(json.dumps({'browser':browser.version,'errors':errors,'pages':results},ensure_ascii=False,indent=2),encoding='utf-8')
        print(name,flush=True)
    def role(name):
        page.locator('[data-testid="stMain"]').evaluate('e=>e.scrollTo(0,0)')
        page.get_by_text('切换演示角色',exact=True).click();radio(name);page.keyboard.press('Escape');settle()
    try:
        page.goto(f'http://127.0.0.1:{port}',wait_until='networkidle');settle()
        button('进入 HealthOps 运营后台');shot('01-today');shot('01-today-work',600)
        page.get_by_role('button',name='查看运行看板',exact=True).first.click();settle();shot('02-agent');shot('02-agent-panels',700)
        radio('会员')
        field=page.get_by_label('搜索成员',exact=True);field.fill('Demo Executive A');field.press('Enter');settle()
        page.locator('[data-testid="stDataFrame"]').last.click(position={'x':100,'y':55});settle();shot('03-member360')
        radio('健康档案');shot('04-archive');shot('04-archive-details',700)
        for name in ['开始评估','继续填写','查看评估']:
            if page.get_by_role('button',name=name,exact=True).count():button(name);break
        page.get_by_role('combobox',name='填写步骤',exact=True).click()
        page.get_by_role('option',name='1. 基础资料',exact=True).click();settle()
        shot('05-assessment');shot('05-assessment-form',400)
        role('医生');shot('07-doctor')
        field=page.get_by_label('搜索记录',exact=True);field.fill('Demo Executive A');field.press('Enter');settle()
        page.locator('[data-testid="stDataFrame"]').last.click(position={'x':120,'y':55});settle()
        page.get_by_role('button',name='提交判断',exact=True).wait_for(state='visible');shot('07-doctor-review')
        role('成员');radio('首页');shot('08-member-home')
        radio('健康');radio('健康数据');shot('06-trends');shot('06-trends-chart',450)
        assert not errors, errors
    except Exception:
        page.screenshot(path=str(OUT/'failure.png'))
        raise
    finally:
        browser.close()
