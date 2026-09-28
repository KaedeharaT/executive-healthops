"""Chromium acceptance via visible controls only, against an isolated DB copy."""
import json,sqlite3,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'.runtime/management-action-loop';OUT=ROOT/'docs/images/management-action-loop'
OUT=Path(os.getenv('HEALTHOPS_QA_OUTPUT',str(OUT)))
WORK.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
if '--prepare' in sys.argv:
    with sqlite3.connect(ROOT/'executive_health_ai.db') as source,sqlite3.connect(WORK/'qa.db') as target:source.backup(target)
    (WORK/'manifest.json').write_text(json.dumps({'management':{'source':str(ROOT),'database':str(WORK/'qa.db'),'port':18570}}),encoding='utf-8')
    print('Prepared isolated database copy');sys.exit(0)

from playwright.sync_api import sync_playwright,expect
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':900});page.set_default_timeout(30000)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    def settle():
        page.wait_for_timeout(600);page.locator('[data-testid="stStatusWidget"]').wait_for(state='hidden',timeout=90000)
        assert not page.locator('[data-testid="stException"]').count(),page.locator('body').inner_text()
    def button(name):
        target=page.get_by_role('button',name=name,exact=True)
        expect(target).to_have_count(1)
        target.click();settle()
    def radio(name):page.get_by_role('radio',name=name,exact=True).locator('xpath=ancestor::label').click();settle()
    def shot(name,anchor=None):
        if anchor:page.get_by_text(anchor,exact=True).first.scroll_into_view_if_needed()
        page.screenshot(path=str(OUT/name))
    try:
        page.goto(os.getenv('HEALTHOPS_QA_URL','http://127.0.0.1:18570'),wait_until='networkidle');settle()
        button('进入 HealthOps 运营后台')
        radio('会员');field=page.get_by_label('搜索成员',exact=True);field.fill('Demo Executive A');field.press('Enter');settle()
        page.locator('[data-testid="stDataFrame"]').last.click(position={'x':100,'y':55});settle();button('查看会员 / 进入Member360')
        expect(page.get_by_role('radio',name='概览',exact=True)).to_be_checked()
        shot('01-overview-next.png','处理下一步');button('处理下一步')
        expect(page.get_by_role('button',name='完成本次处理',exact=True)).to_be_visible()
        shot('02-concrete-management-item.png','当前事项详情')
        page.get_by_label('处理结果',exact=True).fill('已核对本周生活方式记录，成员确认资料准确（合成）');button('完成本次处理')
        shot('03-completed-next-item.png','本次已完成');button('继续处理下一项')
        page.get_by_label('随访情况 / 处理结果',exact=True).fill('已完成电话随访，成员反馈执行正常（合成）');button('完成本次处理');button('继续处理下一项')
        shot('04-service-action.png','审核申请');button('审核申请')
        page.get_by_label('服务执行方（可选）',exact=True).fill('合成服务团队');button('确认服务安排');button('确认开始服务')
        page.get_by_label('服务结果',exact=True).fill('健康沟通服务已完成（合成）')
        page.get_by_label('完成依据',exact=True).fill('成员与服务方合成完成确认')
        button('记录服务完成');button('继续处理下一项')
        page.get_by_label('随访情况 / 处理结果',exact=True).fill('已复核服务结果与成员反馈，无需额外后续（合成）');button('完成本次处理')
        expect(page.get_by_role('button',name='开始阶段复盘',exact=True)).to_be_visible()
        shot('05-all-items-to-review.png','本阶段主要事项已完成');button('开始阶段复盘')
        page.get_by_role('checkbox',name='我已核对阶段结果，确认本次复盘').locator('xpath=ancestor::label').click()
        shot('06-stage-review-draft.png','确认阶段总结');button('确认阶段总结')
        shot('07-next-phase-draft.png','确认并进入下一阶段');button('确认并进入下一阶段')
        expect(page.get_by_role('button',name='完成本次处理',exact=True)).to_be_visible()
        assert '确认下一阶段执行安排' in page.locator('body').inner_text()
        shot('08-next-phase-action.png','当前事项详情')
        button('← 返回本会员管理工作区')
        expect(page.get_by_role('button',name='立即处理',exact=True)).to_be_visible()
        shot('09-management-workspace.png','下一件要做')
        button('新增管理记录')
        page.get_by_label('发生了什么',exact=True).fill('合成成员确认下一阶段联系时间')
        page.get_by_label('我做了什么',exact=True).fill('已核对沟通记录')
        page.get_by_label('本次结果',exact=True).fill('等待下一次回访')
        page.get_by_label('下一步',exact=True).fill('回访确认执行情况（合成浏览器验收）')
        button('保存')
        expect(page.get_by_role('button',name='确认保存并建立待办',exact=True)).to_be_visible()
        button('确认保存并建立待办')
        expect(page.get_by_text('下一步：回访确认执行情况（合成浏览器验收）',exact=True)).to_be_visible()
        shot('10-log-creates-next-work.png','继续处理下一项');button('继续处理下一项')
        expect(page.get_by_label('随访情况 / 处理结果',exact=True)).to_be_visible()
        button('← 返回本会员管理工作区')
        assert not errors
        (OUT/'browser-results.json').write_text(json.dumps({'browser':browser.version,'viewport':'1440x900','overview_to_item':True,'item_to_next':True,'service_full_workflow':True,'all_items_to_review':True,'review_to_next_phase':True,'log_creates_actionable_followup':True,'member_context_retained':True,'errors':errors},indent=2),encoding='utf-8')
        print('Management action loop Chromium acceptance passed')
    except Exception:
        page.screenshot(path=str(OUT/'failure.png'));(OUT/'failure.txt').write_text(page.locator('body').inner_text(),encoding='utf-8');raise
    finally:browser.close()
