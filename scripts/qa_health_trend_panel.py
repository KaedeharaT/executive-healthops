"""Ordinary member navigation, all fifteen real demo options and empty windows."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path('docs/images/health-trend-ui'); OUT.mkdir(parents=True, exist_ok=True)
METRICS = ['体重', 'BMI', '血压（收缩压 / 舒张压）', '心率', '血糖', '糖化血红蛋白', 'LDL-C', 'ALT',
           '步数', '运动时间', '活动消耗', '睡眠时长', '深度睡眠', '快速眼动睡眠时长', '清醒时间']
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1500, 'height': 1200})
    errors = []; results = []
    page.on('pageerror', lambda e: errors.append(str(e)))

    def settle():
        page.wait_for_timeout(400)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden', timeout=90000)
        page.wait_for_timeout(400)
        assert not page.locator('[data-testid="stException"]').count(), page.locator('body').inner_text()
        assert not errors, errors

    def radio(name):
        page.get_by_role('radio', name=name, exact=True).last.locator('xpath=ancestor::label').click(); settle()

    def choose(name):
        field = page.get_by_label('选择健康指标', exact=True)
        field.click(); field.fill(name)
        page.get_by_role('option', name=name, exact=True).click(); settle()

    def period(name):
        page.locator('.st-key-health-trend-filters').get_by_text(name, exact=True).click(); settle()

    page.goto('http://127.0.0.1:8501', wait_until='networkidle'); settle()
    enter = page.get_by_role('button', name='进入成员健康中心', exact=True)
    if enter.count(): enter.click(); settle()
    else:
        page.get_by_text('切换演示角色', exact=True).click(); radio('成员')
        page.get_by_text('切换演示角色', exact=True).click(); settle()
    radio('健康'); radio('健康数据')
    panel = page.locator('.st-key-health-trend-panel')
    assert panel.get_by_text('当前可查看 15 项健康指标', exact=True).count() == 1
    expected_counts = [6, 3, 7, 60, 1344, 2, 4, 2, 30, 30, 30, 30, 30, 30, 30]
    for index, (metric, count) in enumerate(zip(METRICS, expected_counts)):
        choose(metric); period('全部')
        summary = page.locator('.st-key-health-trend-summary').inner_text()
        metadata = page.locator('.st-key-health-trend-metadata').inner_text()
        chart = panel.locator('[data-testid="stVegaLiteChart"]')
        assert chart.count() == 1
        assert ('7 组（14 个数值）' if metric.startswith('血压') else f'{count} 点') in metadata
        chart_text = chart.inner_text()
        assert ('收缩压' if metric.startswith('血压') else metric) in chart_text
        assert '时间' in chart_text and '最近测量' in summary
        if metric in ['糖化血红蛋白', 'ALT']:
            assert '历史比较' in page.locator('.st-key-health-trend-chart').inner_text()
            assert '两次结果比较' in panel.inner_text()
        if metric in ['ALT', '睡眠时长', '步数']:
            assert '暂无年度基线' in summary
        if metric.startswith('血压'):
            assert '126 / 80 mmHg' in summary and '132 / 86 mmHg' in summary and '↓6 / ↓6 mmHg' in summary
        panel.screenshot(path=str(OUT / f'{index+1:02}-{metric.split("（")[0]}.png'))
        results.append({'metric': metric, 'all_time_points': count, 'summary': summary, 'metadata': metadata, 'chart': True})
    choose('BMI'); period('30天')
    assert panel.locator('[data-testid="stVegaLiteChart"]').count() == 0
    assert '1 点' in page.locator('.st-key-health-trend-metadata').inner_text()
    assert '27.9' in page.locator('.st-key-health-trend-summary').inner_text()
    panel.screenshot(path=str(OUT / '16-single-point.png'))
    panel.get_by_role('button', name='查看全部时间', exact=True).click(); settle()
    assert panel.locator('[data-testid="stVegaLiteChart"]').count() == 1
    choose('血糖'); period('7天')
    assert panel.locator('[data-testid="stVegaLiteChart"]').count() == 0
    assert '0 点' in page.locator('.st-key-health-trend-metadata').inner_text()
    assert '所选范围无记录' in page.locator('.st-key-health-trend-summary').inner_text()
    assert '范围外最近有效记录' in panel.inner_text()
    panel.screenshot(path=str(OUT / '17-empty-window.png'))
    panel.get_by_role('button', name='查看全部时间', exact=True).click(); settle()
    assert '1344 点' in page.locator('.st-key-health-trend-metadata').inner_text()
    choose('血压（收缩压 / 舒张压）')
    for width, height in [(1366, 768), (1920, 1080)]:
        page.set_viewport_size({'width': width, 'height': height}); settle()
        page.locator('.st-key-health-trend-filters').scroll_into_view_if_needed()
        page.screenshot(path=str(OUT / f'18-filters-{width}.png'))
        panel.locator('[data-testid="stVegaLiteChart"]').scroll_into_view_if_needed()
        page.screenshot(path=str(OUT / f'19-chart-{width}.png'))
        assert page.locator('[data-testid="stMain"]').evaluate('e=>e.scrollWidth<=e.clientWidth+1')
    (OUT / 'browser-results.json').write_text(json.dumps({'metrics': results, 'single_point': True, 'empty_window': True,
        'show_all_time': True, 'errors': errors}, ensure_ascii=False, indent=2), encoding='utf-8')
    browser.close(); print('PASS: 15 metrics, summary/chart/metadata, empty/single point and responsive layout')
