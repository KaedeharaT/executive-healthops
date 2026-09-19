"""Exercise real UI commands against the explicitly isolated synthetic QA server."""
import argparse
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--allow-synthetic-writes", action="store_true")
args = parser.parse_args()
if not args.allow_synthetic_writes:
    parser.error("Pass --allow-synthetic-writes only for the isolated synthetic server on port 18509.")
sys.stdout.reconfigure(encoding="utf8")
results = {}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width":1500,"height":1100})
    def settle():
        page.wait_for_timeout(600)
        page.locator('[data-testid="stStatusWidget"]').wait_for(state="hidden",timeout=60000)
        page.wait_for_timeout(500)
        assert not page.locator('[data-testid="stException"]').count()
    def choose(name):
        page.get_by_role("radio",name=name,exact=True).last.locator("xpath=ancestor::label").click()
        settle()
    def role(name):
        page.get_by_role("button",name="切换演示角色").click()
        choose(name)
        page.keyboard.press("Escape")
    page.goto("http://127.0.0.1:18509",wait_until="networkidle");settle()
    page.get_by_role("button",name="进入成员健康中心",exact=True).click();settle()
    assert "Demo Executive A" in page.locator("body").inner_text(), "Not the approved synthetic story"
    Path(".runtime/ux-v3-command-home.txt").write_text(page.locator("body").inner_text(), encoding="utf8")
    page.screenshot(path=".runtime/ux-v3-command-home.png")
    page.get_by_role("button",name="去完成",exact=False).first.click();settle()
    page.get_by_role("button",name="确认完成",exact=True).first.click();settle()
    choose("已完成")
    assert "完成本周睡眠与活动记录" in page.locator("body").inner_text()
    results["member_task_completed"] = True
    role("医生")
    page.get_by_label("医生人工意见",exact=True).fill("合成数据流程验收：已核对提供的资料；后续复查安排由健康管理师确认。")
    page.get_by_label("交给健康管理师的下一步",exact=True).fill("UX V3浏览器验收随访：核对复查安排与成员执行记录。")
    page.get_by_role("button",name="提交判断并交回健管",exact=True).click();settle()
    assert "医学判断已保存" in page.locator("body").inner_text()
    choose("历史")
    assert "合成数据流程验收" in page.locator("body").inner_text()
    results["doctor_decision_saved"] = True
    role("健康管理师")
    choose("今日")
    page.get_by_label("查找待办",exact=True).fill("UX V3浏览器验收随访")
    page.get_by_label("查找待办",exact=True).press("Enter");settle()
    assert "UX V3浏览器验收随访" in page.locator("body").inner_text()
    assert page.get_by_role("button",name="处理关注事项",exact=False).count() or page.get_by_role("button",name="处理当前任务",exact=False).count()
    results["doctor_returned_to_manager_queue"] = True
    choose("成员")
    if page.get_by_role("button",name="查看成员",exact=True).count():
        page.get_by_role("button",name="查看成员",exact=True).first.click();settle()
    assert "成员360" in page.locator("body").inner_text()
    choose("管理");choose("记录阶段结果")
    page.get_by_label("观察指标",exact=True).click()
    page.get_by_role("option",name="体重",exact=True).click()
    page.get_by_label("起点数值",exact=True).fill("90")
    page.get_by_label("本次数值",exact=True).fill("85.8")
    page.get_by_label("单位",exact=True).fill("kg")
    page.get_by_label("结果依据",exact=True).fill("UX V3合成演示数据：人工核对年度基线及当前观测，仅验收流程，不推断干预因果。")
    page.get_by_label("下一步说明",exact=True).fill("UX V3浏览器验收阶段结果，继续已有人工管理安排。")
    page.get_by_label("观察结果",exact=True).click()
    page.get_by_role("option",name="数据不足",exact=True).click()
    page.get_by_role("button",name="记录阶段结果并安排下一步",exact=True).click();settle()
    assert "阶段结果已回写到计划与历程" in page.locator("body").inner_text()
    results["outcome_command_saved"] = True
    role("成员");choose("历程")
    assert "阶段结果" in page.locator("body").inner_text()
    assert "健康历程暂时无法加载" not in page.locator("body").inner_text()
    results["outcome_visible_on_timeline"] = True
    page.screenshot(path="docs/images/ux-v3/demo-result-timeline.png")
    Path(".runtime/ux-v3-command-results.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps(results,ensure_ascii=False))
    browser.close()
