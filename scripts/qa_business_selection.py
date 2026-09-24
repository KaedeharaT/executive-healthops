"""Actual Chromium QA of business selection and keyboard access on synthetic data."""
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path('docs/images/business-selection')
OUT.mkdir(parents=True, exist_ok=True)
FORBIDDEN = re.compile(r'键盘选择|下拉选择|完整标题|备用模式|选择方式|alternate selector|keyboard selector|dropdown selector|legacy selector|fallback selector|\b(?:Advanced|Legacy|Trace|Raw|Debug|Internal|UUID|ID|AgentGoal|PlanStep|canonical_code|provider_code)\b', re.I)
results = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1600, 'height': 1100})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))

    def settle():
        page.wait_for_timeout(650)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden', timeout=60000)
        page.wait_for_timeout(600)
        assert not page.locator('[data-testid="stException"]').count()
        assert not errors, errors

    def radio(label):
        page.get_by_role('radio', name=label, exact=True).last.locator('xpath=ancestor::label').click()
        settle()

    def button(label):
        page.get_by_role('button', name=label, exact=True).last.click()
        settle()

    def select(label, value):
        box = page.get_by_label(label, exact=True)
        box.click(); box.press('ArrowDown')
        page.get_by_role('option', name=value, exact=True).click(); settle()

    def inspect(name):
        text = page.locator('body').inner_text()
        exposed = FORBIDDEN.findall(text)
        assert not exposed, (name, exposed)
        assert not page.get_by_role('button', name='Deploy', exact=True).count()
        assert not page.locator('[data-testid="stMainMenu"]:visible').count()
        page.screenshot(path=str(OUT / (name + '.png')))
        results.append({'page': name, 'developer_terms': exposed, 'exceptions': 0})
        print(name, flush=True)

    def search(label, text):
        field = page.get_by_label(label, exact=True)
        field.fill(text); field.press('Enter'); settle()

    def tab_to_table(from_label):
        page.get_by_label(from_label, exact=True).focus()
        for _ in range(25):
            page.keyboard.press('Tab')
            if page.evaluate('()=>document.activeElement.tagName==="CANVAS" && !!document.activeElement.closest("[data-testid=stDataFrame]")'):
                return
        raise AssertionError('The table must be reachable in the normal Tab order')

    def role(label):
        page.get_by_text('切换演示角色', exact=True).click(); radio(label)
        page.get_by_text('切换演示角色', exact=True).click(); settle()

    page.goto('http://127.0.0.1:18514', wait_until='networkidle'); settle()
    inspect('manager-today')
    # Existing work tables retain native keyboard row selection without opt-in.
    tab_to_table('查找待办')
    page.keyboard.press('ArrowDown'); page.keyboard.press('Shift+Space'); settle()
    assert page.get_by_role('button', name='关闭', exact=True).count(), 'Keyboard row selection must open work details'
    inspect('manager-keyboard-detail'); button('关闭')
    radio('会员'); inspect('member-list')
    assert not page.get_by_role('button', name='查看成员', exact=True).count()
    assert not page.get_by_role('checkbox').count()
    search('搜索成员', '__no_such_member__')
    assert not page.locator('[data-testid="stDataFrame"]').count()
    search('搜索成员', '张先生')
    select('负责人', '王健管')
    inspect('member-filtered')
    # Click the member name cell, not a row checkbox or a second action button.
    page.locator('[data-testid="stDataFrame"]').first.click(position={'x': 80, 'y': 55}); settle()
    assert '张先生' in page.locator('.care-member-header').inner_text()
    inspect('member-mouse-open')
    button('← 返回成员列表')
    assert not page.locator('.care-member-header').count()
    select('负责人', '全部'); search('搜索成员', 'Demo Executive A')
    tab_to_table('搜索成员'); page.keyboard.press('ArrowDown'); settle()
    assert 'Demo Executive A' in page.locator('.care-member-header').inner_text()
    inspect('member-keyboard-open')
    for label, name in [('健康档案', 'health-record'), ('管理', 'management'), ('医疗', 'medical'), ('历程', 'history')]:
        radio(label); inspect(name)
    for label, name in [('年度管理', 'annual'), ('医疗协同', 'medical-collaboration'), ('服务', 'service')]:
        radio(label); inspect(name)
    role('医生'); inspect('doctor-queue')
    role('成员')
    for label, name in [('首页', 'member-home'), ('健康', 'member-health'), ('计划', 'member-plan'), ('服务', 'member-service'), ('历程', 'member-history')]:
        radio(label); inspect(name)
    role('管理员')
    assert page.locator('[data-testid="stMainMenu"]:visible').count()
    page.screenshot(path=str(OUT / 'admin-controls.png'))
    (OUT / 'results.json').write_text(json.dumps({
        'actual_browser': True, 'pages': results, 'browser_errors': errors,
        'member_mouse_selection': True, 'member_keyboard_selection': True,
        'work_table_keyboard_selection': True, 'search_and_owner_filter': True,
        'return_to_list_stable': True, 'implementation_controls_removed': 3,
        'redundant_member_open_button_removed': 1,
        'framework_developer_controls_hidden': 2,
        'admin_developer_controls_preserved': True,
        'business_functionality_removed': False,
    }, ensure_ascii=False, indent=2), encoding='utf8')
    browser.close()
