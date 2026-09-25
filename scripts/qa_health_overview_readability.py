"""Read-only real browser verification from the member homepage."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT=Path('docs/images/health-overview-readability')
OUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':900})
    errors=[];results={}
    page.on('pageerror',lambda error:errors.append(str(error)))
    def settle():
        page.wait_for_timeout(800)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden',timeout=90000)
        page.wait_for_timeout(400)
        assert not page.locator('[data-testid="stException"]').count(),page.locator('body').inner_text()
        assert not errors,errors
    def top():
        page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTo(0,0)')
        page.wait_for_timeout(150)
    def button(label):
        page.get_by_role('button',name=label,exact=True).click();settle()
    def radio(label):
        page.get_by_role('radio',name=label,exact=True).last.locator('xpath=ancestor::label').click();settle()
    def choose(label,value):
        field=page.get_by_label(label,exact=True)
        field.scroll_into_view_if_needed();field.click();field.fill(value)
        page.get_by_role('option',name=value,exact=True).click();settle()
    try:
        page.goto(os.getenv('HEALTHOPS_QA_URL','http://127.0.0.1:18520'),wait_until='networkidle');settle()
        button('进入成员健康中心');radio('健康')
        sections=['overview-heading','overview-trend','overview-focus','overview-domain-coverage']
        domain_count=page.locator('.overview-domain-list tbody tr').count()
        coverage_count=page.locator('.overview-coverage>div').count()
        assert domain_count==8 and coverage_count==6
        assert page.locator('.overview-focus-list article').count()==4
        for size in [(1366,768),(1440,900),(1920,1080)]:
            page.set_viewport_size({'width':size[0],'height':size[1]});settle();top()
            boxes=[page.locator('.st-key-'+key).bounding_box() for key in sections]
            gaps=[round(boxes[i+1]['y']-boxes[i]['y']-boxes[i]['height'],1) for i in range(3)]
            assert all(24<=gap<=40 for gap in gaps),gaps
            assert page.locator('.st-key-overview-heading .overview-stages').count()==1
            for selector in ['[data-testid="stMain"]','.st-key-overview-trend','.overview-focus-list','.overview-domain-list','.overview-coverage']:
                bounds=page.locator(selector).evaluate('(e)=>({width:e.clientWidth,scroll:e.scrollWidth})')
                assert bounds['scroll']<=bounds['width']+2,(size,selector,bounds)
            left=page.locator('.st-key-overview-health-domains').bounding_box()
            right=page.locator('.st-key-overview-data-completeness').bounding_box()
            assert abs(left['y']-right['y'])<3 and left['x']+left['width']<right['x']
            page.screenshot(path=str(OUT/f'viewport-{size[0]}x{size[1]}.png'))
            for selector in ['.st-key-overview-trend','.st-key-overview-focus','.st-key-overview-domain-coverage']:
                page.locator(selector).scroll_into_view_if_needed()
                page.screenshot(path=str(OUT/f'viewport-{size[0]}x{size[1]}-{selector.split("overview-")[-1]}.png'))
            results[f'{size[0]}x{size[1]}']={'section_gaps':gaps,'horizontal_overflow':False,'bottom_columns':'side by side'}
        page.set_viewport_size({'width':1440,'height':900});settle()
        for name,key in [('02-baseline-section','overview-heading'),('03-trend-section','overview-trend'),('04-focus-section','overview-focus')]:
            page.locator('.st-key-'+key).screenshot(path=str(OUT/(name+'.png')))
        page.locator('.st-key-overview-domain-coverage [data-testid="stHorizontalBlock"]').first.screenshot(path=str(OUT/'05-health-summary-data-completeness.png'))
        top()
        height=page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollHeight')
        page.set_viewport_size({'width':1440,'height':height+100});settle();top()
        page.screenshot(path=str(OUT/'01-full-page.png'),full_page=True)
        page.set_viewport_size({'width':1440,'height':900});settle()
        chart=page.locator('[data-testid="stVegaLiteChart"]').first
        chart.scroll_into_view_if_needed()
        assert all(t in chart.inner_text() for t in ['时间','kg','年度基线','当前'])
        chart.locator('svg .mark-symbol.role-mark path').last.hover();page.wait_for_timeout(400)
        assert page.locator('#vg-tooltip-element').is_visible()
        results['tooltip']=page.locator('#vg-tooltip-element').inner_text()
        page.mouse.move(5,5)
        choose('选择指标','血压（收缩压 / 舒张压）')
        assert all(t in chart.inner_text() for t in ['mmHg','收缩压','舒张压'])
        choose('时间范围','7天')
        assert '保留年度基线作为起点' in page.locator('body').inner_text()
        choose('时间范围','当前管理周期');choose('选择指标','体重')
        button('查看依据');assert page.get_by_text('原文',exact=False).count();page.keyboard.press('Escape')
        button('持续关注事项 · 3项');assert '长期睡眠不足' in page.locator('body').inner_text();page.keyboard.press('Escape')
        page.get_by_text('所有指标与当前对比',exact=True).click();settle()
        assert page.locator('[data-testid="stDataFrame"]').first.is_visible()
        page.get_by_text('年度基线完整资料',exact=True).click();settle()
        button('查看年度健康基线');assert '关键指标基线' in page.locator('body').inner_text()
        button('返回健康概览')
        button('查看历次记录');assert page.get_by_role('radio',name='历程',exact=True).last.is_checked()
        radio('健康');radio('健康数据');radio('体检与检查');radio('健康档案');radio('健康概览')
        button('补充健康资料');assert page.locator('[data-testid="stFileUploader"]').count()
        results.update(actual_browser='Chromium',domains=domain_count,coverage_items=coverage_count,focus_items=4,
            retained_controls=['metric','time_window','baseline','current','delta','chart','evidence','focus_details','history','all_metrics','full_baseline','archive','reports','supplement'],errors=errors)
        (OUT/'browser-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Three viewports, all four sections and retained interactions: PASS',flush=True)
    except Exception:
        page.screenshot(path=str(OUT/'failure.png'),full_page=True)
        (OUT/'failure.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
        raise
    finally:browser.close()
