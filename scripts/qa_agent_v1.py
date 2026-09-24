"""Real Chromium walkthrough on the isolated synthetic Agent V1 demo."""
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path('docs/images/agent-v1'); OUT.mkdir(parents=True, exist_ok=True)
FORBIDDEN = re.compile(r'AgentGoal|AgentRun|ToolCall|Trace|Planner|PlanStep|JSON|UUID|Raw|Debug|\bNone\b|Keyboard selector|Dropdown selector|备用选择|完整标题|键盘选择|使用下拉选择|Agent Completed')
results = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1600, 'height': 1100})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))

    def settle():
        page.wait_for_timeout(650)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden', timeout=60000)
        page.wait_for_timeout(400)
        assert not page.locator('[data-testid="stException"]').count(), page.locator('body').inner_text()
        assert not errors, errors

    def radio(label):
        page.get_by_role('radio', name=label, exact=True).last.locator('xpath=ancestor::label').click(); settle()

    def button(label):
        page.get_by_role('button', name=label, exact=True).last.click(); settle()

    def select(label, value):
        box = page.get_by_label(label, exact=True); box.click(); box.fill(value)
        page.get_by_role('option', name=value, exact=True).click(); settle()

    def top():
        page.locator('[data-testid="stMain"]').evaluate('(e)=>e.scrollTo(0,0)'); page.wait_for_timeout(200)

    def shot(name, admin=False):
        text = page.locator('body').inner_text()
        assert admin or not FORBIDDEN.findall(text), (name, FORBIDDEN.findall(text))
        assert not page.get_by_role('checkbox').count(), 'No interaction-mode toggles'
        page.screenshot(path=str(OUT/(name+'.png')))
        results.append({'page': name, 'technical_terms': [] if not admin else 'admin only', 'page_errors': 0})
        print(name, flush=True)

    def role(label):
        top(); page.get_by_text('切换演示角色', exact=True).click(); radio(label)
        page.get_by_text('切换演示角色', exact=True).click(); settle()

    def search(label, value):
        field = page.get_by_label(label, exact=True); field.fill(value); field.press('Enter'); settle()

    def row():
        page.locator('[data-testid="stDataFrame"]:visible').last.click(position={'x': 16, 'y': 53}); settle()

    try:
        page.goto('http://127.0.0.1:18515', wait_until='networkidle'); settle()
        if page.get_by_role('button', name='进入 HealthOps 运营后台', exact=True).count():
            button('进入 HealthOps 运营后台')
        select('今日事项筛选', '体检后管理'); search('查找待办', 'Demo Executive A')
        shot('01-manager-today'); row()
        assert '需要您处理' in page.locator('body').inner_text()
        shot('02-agent-manager-review')
        assert page.locator('.vega-embed').count() >= 2, 'Real historic trends must be present'
        page.get_by_role('heading', name='依据', exact=True).scroll_into_view_if_needed()
        shot('03-agent-evidence')
        top(); page.get_by_text('修改整理结果 / 提交医生判断', exact=True).click()
        page.get_by_label('责任医生', exact=True).fill('演示医生')
        page.get_by_label('需要医生判断的问题', exact=True).fill('肝功能变化是否需要进一步医学处理？')
        button('提交医生判断')
        assert '等待医生判断' in page.locator('body').inner_text()
        role('医生'); search('搜索记录', '肝功能变化是否需要进一步医学处理')
        shot('04-doctor-worklist'); row(); top()
        shot('05-doctor-review')
        page.get_by_label('医学判断', exact=True).fill('已核对本次与既往资料，建议跟踪肝功能变化。当前无需调整用药。')
        page.get_by_label('建议', exact=True).fill('了解饮酒情况并随访执行情况；按建议时间复查肝功能。')
        radio('需要'); page.get_by_label('复查项目', exact=True).fill('肝功能复查')
        button('提交判断')
        assert '医学判断已提交' in page.locator('body').inner_text()
        role('健康管理师'); top()
        assert '确认并创建后续安排' in page.locator('body').inner_text()
        shot('06-manager-action-approval')
        button('确认并创建后续安排'); top()
        assert '本次体检后管理已完成' in page.locator('body').inner_text()
        shot('07-agent-complete'); button('返回会员360'); top()
        assert '当前自动跟进' in page.locator('body').inner_text()
        shot('08-member360-after-agent')
        role('管理员'); radio('自动化运营'); top()
        shot('09-admin-agent-monitor', admin=True)
        role('成员'); radio('计划'); top(); shot('10-member-plan')
        (OUT/'browser-results.json').write_text(json.dumps({'actual_browser': 'Chromium', 'pages': results, 'errors': errors}, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        page.screenshot(path=str(OUT/'failure.png'), full_page=True)
        (OUT/'failure.txt').write_text(page.locator('body').inner_text(), encoding='utf-8')
        raise
    finally:
        browser.close()
