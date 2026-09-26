"""Read-only browser verification of the live completed history and its board links."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path('docs/images/completed-history'); OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1600, 'height': 1000})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))

    def settle():
        page.wait_for_timeout(500)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden', timeout=90000)
        page.wait_for_timeout(500)
        assert not page.locator('[data-testid="stException"]').count()
        assert not errors, errors

    page.goto('http://127.0.0.1:8501', wait_until='networkidle'); settle()
    enter = page.get_by_role('button', name='进入 HealthOps 运营后台', exact=True)
    if enter.count(): enter.click(); settle()
    history = page.locator('.st-key-assistant-recent')
    rows = history.locator('[class*="st-key-completed-row-"]')
    assert rows.count() == 2
    assert history.locator('[class*="st-key-assistant-card-"]').count() == 0
    assert ['2026-09-23' in rows.nth(0).inner_text(), '2026-09-25' in rows.nth(1).inner_text()] == [True, True]
    assert history.get_by_role('button', name='查看', exact=True).count() == 2
    assert '核对行动负责人' not in history.inner_text()
    links = []
    for index in range(2):
        row = rows.nth(index)
        identity = row.evaluate("e => [...e.classList].find(c=>c.startsWith('st-key-completed-row-')).replace('st-key-completed-row-', '')")
        report_date = '2026-09-23' if index == 0 else '2026-09-25'
        row.get_by_role('button', name='查看', exact=True).click(); settle()
        page.get_by_role('heading', name='本次自动管理已完成', exact=True).wait_for(timeout=90000)
        settle()
        assert page.locator(f'[class*="st-key-care-report-{identity}-"]').count() == 1, (identity, page.locator('[class*="st-key-"]').evaluate_all('es=>es.map(e=>e.className)'))
        links.append({'report_date': report_date, 'instance': identity, 'correct_board': True})
        page.get_by_role('button', name='← 返回今日工作', exact=True).click(); settle()
    assert links[0]['instance'] != links[1]['instance']
    page.get_by_role('button', name='查看全部历史', exact=True).click(); settle()
    assert rows.count() == 2
    page.get_by_role('button', name='收起历史', exact=True).click(); settle()
    for width, height in [(1600, 1000), (1366, 768)]:
        page.set_viewport_size({'width': width, 'height': height}); settle()
        page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTo(0, e.scrollHeight)')
        page.locator('.v2-summary a[href="#assistant-recent"]').click(); page.wait_for_timeout(400)
        settle()
        assert page.locator('#assistant-recent').bounding_box()['y'] >= 0
        page.screenshot(path=str(OUT / f'history-{width}.png'))
        history.screenshot(path=str(OUT / f'rows-{width}.png'))
    (OUT / 'browser-results.json').write_text(json.dumps({'completed_cards': 0,
        'completed_rows': 2, 'different_instances_preserved': True, 'links': links,
        'history_toggle': True, 'summary_anchor': True, 'browser_errors': errors}, ensure_ascii=False, indent=2), encoding='utf-8')
    browser.close()
    print('PASS: two history rows, zero completed cards, distinct board links, history toggle and anchor')
