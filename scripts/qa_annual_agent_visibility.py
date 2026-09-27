"""Real Chromium acceptance using synthetic cases and real local-model call records."""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

OUT=Path('docs/images/annual-agent-ai');OUT.mkdir(parents=True,exist_ok=True)
followup = '--followup' in sys.argv
results=json.loads((OUT/'results.json').read_text(encoding='utf-8')) if followup and (OUT/'results.json').exists() else []
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':900},device_scale_factor=1)
    page.set_default_timeout(25000)
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    def settle():
        page.wait_for_timeout(800)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden',timeout=210000)
        page.wait_for_timeout(400)
        assert not page.locator('[data-testid="stException"]').count(),page.locator('body').inner_text()
        assert not errors,errors
    def button(name):
        page.get_by_role('button',name=name,exact=True).last.click();settle()
    def radio(name):
        page.get_by_role('radio',name=name,exact=True).last.locator('xpath=ancestor::label').click();settle()
    def search(name,value):
        element=page.get_by_label(name,exact=True);element.fill(value);element.press('Enter');settle()
    def select(name,value):
        page.get_by_label(name,exact=True).click()
        page.get_by_role('option',name=value,exact=True).click();settle()
    def row():
        page.locator('[data-testid="stDataFrame"]').last.click(position={'x':100,'y':55});settle()
    def top():
        page.locator('[data-testid="stMain"]').evaluate('(e)=>{e.style.scrollBehavior="auto";e.scrollTo({top:0,behavior:"instant"});}')
        page.wait_for_timeout(250)
    def role(name):
        top();page.get_by_text('切换演示角色',exact=True).click();radio(name);page.keyboard.press('Escape');settle()
    def shot(name,section=None,admin=False):
        top()
        if section:page.locator(section).scroll_into_view_if_needed()
        page.screenshot(path=str(OUT/(name+'.png')))
        text=page.locator('body').inner_text()
        if not admin:
            for forbidden in ['LocalLLMClient','generate_structured','retrieve_knowledge','post_checkup_manager_draft','chain_of_thought','reasoning_content']:
                assert forbidden not in text,(name,forbidden)
        (OUT/(name+'.txt')).write_text(text,encoding='utf-8')
        results[:]=[r for r in results if r['page']!=name]
        results.append({'page':name,'errors':list(errors),'browser':browser.version})
        (OUT/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print(name,flush=True)
    def today_case(query):
        radio('今日工作');search('查找待办',query);row()
    def support_checks():
        cases=json.loads(Path('.runtime/annual-agent-ai/cases.json').read_text(encoding='utf-8'))['goals']
        for case, name, expected in [('structured','18-profile-structured','本步骤未调用 AI'),
                                      ('prose','19-profile-free-text','项有原文依据的候选资料')]:
            if page.get_by_role('button',name='← 返回健康档案',exact=True).count():button('← 返回健康档案')
            radio('今日工作')
            page.locator(f'.st-key-profile-assistant-{cases[case]} button').click();settle()
            text=page.locator('body').inner_text()
            assert expected in text,text
            assert '本步骤未调用知识库' in text
            shot(name,'.st-key-soft-profile-ai-support')
        button('← 返回健康档案')
        radio('今日工作')
        page.locator(f'.st-key-assistant-card-{cases["unavailable"]}').get_by_role('button',name='查看运行看板').click();settle()
        assert '本次未发起模型请求' in page.locator('body').inner_text()
        shot('20-care-ai-unavailable','.st-key-board-ai-support')
        button('← 返回今日工作')
        page.locator(f'.st-key-completed-view-{cases["care"]} button').click();settle()
        shot('27-care-final-ai-support','.st-key-board-ai-support')
        shot('28-care-activity-timeline','.st-key-board-timeline')
        role('管理员');radio('自动化运行');shot('17-admin-call-list',admin=True)
        search('搜索记录','验收会员·基线');row()
        page.get_by_text('技术详情',exact=True).click();settle()
        shot('21-admin-actual-calls','[data-testid="stExpander"]:has-text("AI / Knowledge calls") [data-testid="stDataFrame"] >> nth=2',admin=True)
        assert 'AI / Knowledge calls' in page.locator('body').inner_text()
        button('← 返回自动化运行');search('搜索记录','验收会员·持续 体检后健康管理');row()
        detail=page.locator('[data-testid="stExpander"]').filter(has_text='技术详情')
        if detail.locator('details').get_attribute('open') is None:detail.locator('summary').click();settle()
        shot('25-admin-summary-doctor-calls','[data-testid="stExpander"]:has-text("AI / Knowledge calls") [data-testid="stDataFrame"] >> nth=2',admin=True)
        button('← 返回自动化运行');search('搜索记录','验收会员·持续 健康资料导入');row()
        detail=page.locator('[data-testid="stExpander"]').filter(has_text='技术详情')
        if detail.locator('details').get_attribute('open') is None:detail.locator('summary').click();settle()
        shot('26-admin-profile-calls','[data-testid="stExpander"]:has-text("AI / Knowledge calls") [data-testid="stDataFrame"]',admin=True)
        role('健康管理师');radio('年度管理');select('责任健管','验收健管')
        shot('22-annual-final')
        shot('23-annual-table','.st-key-soft-annual-table')
        radio('会员')
        if page.get_by_role('button',name='← 返回会员',exact=True).count():button('← 返回会员')
        expect(page.get_by_label('搜索成员',exact=True)).to_be_visible()
        shot('24-members-final')
    try:
        page.goto('http://127.0.0.1:18540',wait_until='networkidle');settle()
        if page.get_by_role('button',name='进入 HealthOps 运营后台',exact=True).count():button('进入 HealthOps 运营后台')
        if followup:
            support_checks()
            sys.exit(0)
        radio('会员');shot('01-members-people-first')
        assert '年度阶段分布' not in page.locator('body').inner_text()
        search('搜索成员','验收会员·持续');row()
        expect(page.get_by_role('radio',name='概览',exact=True)).to_be_checked()
        shot('02-member-overview');button('← 返回会员')
        radio('年度管理');select('责任健管','验收健管')
        shot('03-annual-portfolio')
        expect(page.get_by_role('heading',name='年度阶段分布',exact=True)).to_be_visible()
        select('当前阶段','持续管理');row()
        expect(page.get_by_role('radio',name='管理',exact=True)).to_be_checked()
        shot('04-annual-member-management');button('← 返回年度管理')
        expect(page.get_by_label('当前阶段',exact=True)).to_have_value('持续管理')
        select('当前阶段','全部');select('是否逾期','是');shot('05-annual-overdue')
        select('是否逾期','全部')
        for width,height in [(1366,768),(390,844)]:
            page.set_viewport_size({'width':width,'height':height});settle();top()
            bounds=page.locator('[data-testid="stMain"]').evaluate('(e)=>({w:e.clientWidth,s:e.scrollWidth})')
            assert bounds['s']<=bounds['w']+2,bounds
            shot(f'06-annual-{width}')
        page.set_viewport_size({'width':1440,'height':900})
        radio('今日工作')
        page.locator('[class*="st-key-assistant-card-"]').filter(has_text='AI知识调用验收.txt').get_by_role('button',name='查看运行看板',exact=True).click();settle()
        shot('07-care-before-confirmation')
        shot('08-care-ai-support','.st-key-board-ai-support')
        assert '已生成待健管确认摘要' in page.locator('body').inner_text()
        button('查看依据');expect(page.get_by_role('dialog')).to_be_visible();shot('09-knowledge-detail')
        page.keyboard.press('Escape');settle()
        button('查看摘要');expect(page.get_by_role('dialog')).to_be_visible();shot('10-ai-summary')
        page.keyboard.press('Escape');settle()
        top();page.get_by_text('修改整理结果 / 提交医生判断',exact=True).click()
        page.get_by_label('责任医生',exact=True).fill('验收医生')
        page.get_by_label('需要医生判断的问题',exact=True).fill('验收医学问题：请核对资料并明确随访建议。')
        button('提交医生判断')
        assert '等待医生判断' in page.locator('body').inner_text()
        shot('11-care-waiting-doctor')
        role('医生');search('搜索记录','验收医学问题');row()
        page.get_by_label('医学判断',exact=True).fill('已核对验收资料，医学安排由医生确认。')
        page.get_by_label('建议',exact=True).fill('记录睡眠情况。')
        button('提交判断');shot('12-doctor-submitted')
        role('健康管理师')
        shot('13-doctor-return-ai','.st-key-board-ai-support')
        assert '已从医生原文提取随访主题' in page.locator('body').inner_text()
        assert '确认并创建后续安排' in page.locator('body').inner_text()
        button('确认并创建后续安排');shot('14-care-completed')
        button('返回会员360');radio('健康档案')
        page.get_by_role('heading',name='资料导入记录',exact=True).scroll_into_view_if_needed()
        # Archive history is a native table; both real intake cases are visible.
        shot('15-profile-history')
        radio('今日工作');search('查找待办','健康资料');row()
        shot('16-profile-ai-support','.st-key-soft-profile-ai-support')
        support_checks()
    except Exception:
        page.screenshot(path=str(OUT/'failure.png'),full_page=True)
        (OUT/'failure.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
        raise
    finally:
        browser.close()
