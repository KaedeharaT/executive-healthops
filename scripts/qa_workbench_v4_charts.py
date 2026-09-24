"""Verify real chart hover, metric switching and retained admin entry in Chromium."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path('docs/images/workbench-v2')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1600,'height':1100})
    def settle():
        page.wait_for_timeout(700)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden',timeout=60000)
        page.wait_for_timeout(800)
        assert not page.locator('[data-testid="stException"]').count()
    def radio(label):page.get_by_role('radio',name=label,exact=True).last.locator('xpath=ancestor::label').click();settle()
    def role(label):
        page.get_by_text('切换演示角色',exact=True).click();radio(label)
        page.get_by_text('切换演示角色',exact=True).click();settle()
    page.goto('http://127.0.0.1:18514',wait_until='networkidle');settle()
    role('成员');radio('健康');radio('健康数据')
    box=page.get_by_label('选择健康指标',exact=True)
    box.click();box.press('ArrowDown')
    labels=page.get_by_role('option').all_text_contents()
    page.keyboard.press('Escape')
    checked=[]
    for label in labels:
        box.click();box.press('ArrowDown');page.get_by_role('option',name=label,exact=True).click();settle()
        assert page.locator('[data-testid="stVegaLiteChart"]').count()>=1,label
        checked.append(label)
    # Last chart still uses the shared grammar; inspect the rendered axes and hover.
    chart=page.locator('[data-testid="stVegaLiteChart"]').first
    chart.scroll_into_view_if_needed()
    points=chart.locator('svg .mark-symbol path')
    svg_axes=chart.locator('svg').text_content() if chart.locator('svg').count() else ''
    tooltip=False
    for point in points.all():
        point.hover(force=True);page.wait_for_timeout(150)
        tip=page.locator('#vg-tooltip-element')
        tooltip=tip.count()>0 and tip.is_visible()
        if tooltip:break
    page.screenshot(path=str(out/'health-chart-tooltip.png'))
    assert tooltip,'Rendered chart tooltip must be visible on hover'
    assert '时间' in svg_axes,'The rendered time axis must be present'
    role('管理员');page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTop=0')
    page.screenshot(path=str(out/'admin-preservation.png'))
    text=page.locator('body').inner_text()
    assert '系统状态' in text and '自动化运营' in text
    (out/'chart-results.json').write_text(json.dumps({'actual_browser':True,'metrics_checked':checked,'hover_tooltip':tooltip,'visible_time_axis':True,'admin_available':True},ensure_ascii=False,indent=2),encoding='utf8')
    browser.close()
