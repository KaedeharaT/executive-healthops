"""Read-only Chromium screenshots for the member health overview only.

Run against an isolated Portfolio Demo server on 18511. No data is written.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path('docs/images/member-health-overview')
ROOT.mkdir(parents=True, exist_ok=True)
results = {}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1500, 'height': 1100})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    def settle():
        page.wait_for_timeout(600)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden', timeout=60000)
        page.wait_for_timeout(450)
        assert not page.locator('[data-testid="stException"]').count()
        assert not errors
    def top():
        page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTop=0')
        page.wait_for_timeout(250)
    page.goto('http://127.0.0.1:18511', wait_until='networkidle'); settle()
    page.get_by_role('button', name='进入成员健康中心', exact=True).click(); settle()
    page.get_by_role('radio', name='健康', exact=True).last.locator('xpath=ancestor::label').click(); settle()
    stage_boxes = page.locator('.overview-stages > [role="listitem"]').evaluate_all('(els)=>els.map(e=>({x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y}))')
    assert len(stage_boxes) == 3 and max(b['y'] for b in stage_boxes) - min(b['y'] for b in stage_boxes) < 2
    assert stage_boxes[0]['x'] < stage_boxes[1]['x'] < stage_boxes[2]['x']
    top(); page.screenshot(path=str(ROOT/'after-desktop.png'))
    page.set_viewport_size({'width':1500,'height':2200}); page.wait_for_timeout(500)
    top(); page.screenshot(path=str(ROOT/'after-desktop-full.png'))
    body = page.locator('body').inner_text()
    Path('.runtime/overview-after.txt').write_text(body, encoding='utf8')
    assert '当前基线中暂无该领域' not in body
    assert '资料不足' not in body
    assert body.index('重点关注') < body.index('从基线到现在') < body.index('资料待补充') < body.index('详细资料')
    assert '这是资料完整度，不代表健康评分' in body
    page.set_viewport_size({'width':1500,'height':1100}); page.wait_for_timeout(300)
    chart = page.locator('[data-testid="stVegaLiteChart"]').first
    chart.scroll_into_view_if_needed(); page.screenshot(path=str(ROOT/'after-desktop-chart.png'))
    svg_text = chart.inner_text()
    assert all(t in svg_text for t in ['时间', 'kg', '年度基线', '当前'])
    point = chart.locator('svg .mark-symbol.role-mark path').last
    point.hover(); page.wait_for_timeout(500)
    tip = page.locator('#vg-tooltip-element')
    assert tip.is_visible() and 'kg' in tip.inner_text()
    results['tooltip'] = tip.inner_text()
    page.mouse.move(5,5)
    page.get_by_label('选择指标', exact=True).click()
    page.get_by_role('option', name='血压（收缩压 / 舒张压）', exact=True).click(); settle()
    chart = page.locator('[data-testid="stVegaLiteChart"]').first
    assert all(t in chart.inner_text() for t in ['mmHg', '收缩压', '舒张压'])
    chart.scroll_into_view_if_needed(); page.screenshot(path=str(ROOT/'after-blood-pressure.png'))
    page.get_by_label('选择指标', exact=True).click()
    page.get_by_role('option', name='体重', exact=True).click(); settle()
    page.get_by_role('button', name='查看依据', exact=True).click(); settle()
    assert page.get_by_text('原文', exact=False).count()
    page.keyboard.press('Escape')
    page.get_by_role('button', name='持续关注事项 · 3项', exact=True).click(); settle()
    assert '长期睡眠不足' in page.locator('body').inner_text()
    page.keyboard.press('Escape')
    page.get_by_text('所有指标与当前对比', exact=True).click(); settle()
    assert page.locator('[data-testid="stDataFrame"]').first.is_visible()
    page.get_by_text('所有指标与当前对比', exact=True).click(); settle()
    page.get_by_text('年度基线完整资料', exact=True).click(); settle()
    page.get_by_role('button', name='查看年度健康基线', exact=True).click(); settle()
    assert '关键指标基线' in page.locator('body').inner_text()
    page.get_by_role('button', name='返回健康概览', exact=True).click(); settle()
    page.set_viewport_size({'width':640,'height':1100}); page.wait_for_timeout(500)
    collapse = page.locator('[data-testid="stSidebarCollapseButton"] button')
    if collapse.count() and collapse.is_visible():
        collapse.click(); page.wait_for_timeout(300)
    top(); page.screenshot(path=str(ROOT/'after-640.png'))
    stage_y = page.locator('.overview-stages > [role="listitem"]').evaluate_all('(els)=>els.map(e=>e.getBoundingClientRect().y)')
    assert max(stage_y)-min(stage_y) < 2
    chart = page.locator('[data-testid="stVegaLiteChart"]').first
    chart.scroll_into_view_if_needed()
    page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTop+=100'); page.wait_for_timeout(250)
    page.screenshot(path=str(ROOT/'after-640-chart.png'))
    missing = page.get_by_role('heading', name='资料待补充', exact=True)
    missing.evaluate('(el)=>el.scrollIntoView({block:"center"})'); page.wait_for_timeout(300)
    page.screenshot(path=str(ROOT/'after-640-coverage.png'))
    columns = page.locator('.st-key-overview-domain-coverage > div [data-testid="stColumn"]')
    results['narrow'] = page.locator('[data-testid="stMain"]').evaluate('(e)=>({width:e.clientWidth,scrollWidth:e.scrollWidth})')
    assert results['narrow']['scrollWidth'] <= results['narrow']['width'] + 1
    health_box = page.get_by_role('heading', name='健康概览', exact=True).bounding_box()
    missing_box = missing.bounding_box()
    assert health_box['y'] < missing_box['y']
    page.get_by_label('选择指标', exact=True).click()
    page.get_by_label('选择指标', exact=True).press('ArrowDown')
    page.get_by_role('option', name='糖化血红蛋白', exact=True).click(); settle()
    chart = page.locator('[data-testid="stVegaLiteChart"]').first
    chart.scroll_into_view_if_needed()
    page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTop+=100'); page.wait_for_timeout(250)
    page.screenshot(path=str(ROOT/'after-640-hba1c.png'))
    table = page.locator('.st-key-overview-trend .v3-comparison').evaluate('(e)=>({width:e.clientWidth,scrollWidth:e.scrollWidth})')
    assert table['scrollWidth'] <= table['width'] + 1
    page.get_by_role('button', name='补充健康资料', exact=True).click(); settle()
    assert page.locator('[data-testid="stFileUploader"]').count()
    results.update(desktop=True, narrow_stacked=True, narrow_hba1c=True, comparison_accessible=True, baseline_details_accessible=True, supplement_route=True, exceptions=0)
    Path('.runtime/member-overview-qa.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf8')
    browser.close()
