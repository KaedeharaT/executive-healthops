"""Read-only Chromium checks from ordinary role home; never alter care records."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path('docs/images/assistant-instance-groups')
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    results = []
    for port, name in [(8501, 'completed'), (18521, 'active-and-completed')]:
        page = browser.new_page(viewport={'width': 1600, 'height': 1100})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))

        def settle():
            page.wait_for_timeout(500)
            page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden', timeout=90000)
            page.wait_for_timeout(500)
            assert not page.locator('[data-testid="stException"]').count()
            assert not errors, errors

        page.goto(f'http://127.0.0.1:{port}', wait_until='networkidle')
        settle()
        enter = page.get_by_role('button', name='进入 HealthOps 运营后台', exact=True)
        if enter.count():
            enter.click()
            settle()
        page.get_by_role('heading', name='最近完成', exact=True).wait_for(timeout=30000)
        selector = '[class*="st-key-assistant-card-"]'
        active = page.locator('.st-key-assistant-active').locator(selector)
        recent = page.locator('.st-key-assistant-recent').locator(selector)
        cards = page.locator(selector)
        identities = cards.evaluate_all("es => es.map(e => [...e.classList].find(c => c.startsWith('st-key-assistant-card-')))")
        assert len(identities) == len(set(identities)), identities
        assert recent.count() <= 3
        for card in recent.all():
            assert '本次管理已完成' in card.inner_text()
            assert '完成时间：' in card.inner_text()
        for card in active.all():
            assert '本次管理已完成' not in card.inner_text()
        if port == 8501:
            assert active.count() == 0 and recent.count() == 2
            sources = [card.inner_text().split('来源：')[1].split('\n')[0] for card in recent.all()]
            assert len(set(sources)) == 2  # Same member/title, two real report instances.
        else:
            assert active.count() >= 2 and recent.count() == 1
        page.screenshot(path=str(OUT / f'{name}.png'), full_page=True)
        results.append({'page': name, 'active': active.count(), 'recent': recent.count(),
                        'unique_instance_cards': len(set(identities)), 'duplicate_cards': 0})
        # Each retained completed instance must still open its own real board.
        for index in range(recent.count()):
            recent.nth(index).get_by_role('button', name='查看运行看板', exact=True).click()
            settle()
            page.get_by_role('heading', name='本次自动管理已完成', exact=True).wait_for(timeout=90000)
            settle()
            assert page.get_by_role('heading', name='健康管理助手 · 运行看板', exact=True).count()
            page.get_by_role('button', name='← 返回今日工作', exact=True).click()
            settle()
        page.close()
    browser.close()
    (OUT / 'browser-results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False))
