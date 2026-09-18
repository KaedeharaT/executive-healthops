"""Browser QA on a running, isolated synthetic Streamlit instance.

Requires the optional Playwright developer tool. --exercise writes to the
instance's database; use only a disposable copy of data/portfolio_demo.db.
Screenshots are captured before exercising mutations.
"""
import argparse
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:18502")
    parser.add_argument("--screenshots", default="docs/images")
    parser.add_argument("--exercise", action="store_true")
    args = parser.parse_args()
    target = Path(args.screenshots)
    target.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1080}, device_scale_factor=1)
        page.goto(args.url)
        page.get_by_role("button", name="进入成员健康中心", exact=True).click()
        page.get_by_role("heading", name="今日健康", exact=True).wait_for(timeout=60000)

        def settled():
            page.wait_for_timeout(1200)
            page.locator('[data-testid="stStatusWidget"]').wait_for(state="hidden", timeout=60000)
            assert page.locator('[data-testid="stException"]').count() == 0

        def radio(label):
            page.get_by_role("radio", name=label, exact=True).last.locator("xpath=ancestor::label").click()
            settled()

        def button(label):
            page.get_by_role("button", name=label, exact=True).first.click()
            settled()

        def capture(name, bottom=False):
            settled()
            page.locator('[data-testid="stMain"]').evaluate("(el, bottom) => el.scrollTop = bottom ? el.scrollHeight : 0", bottom)
            page.wait_for_timeout(200)
            text = page.locator("body").inner_text()
            for token in ("Yellow RiskEvent", "systolic_bp", "AgentGoal", "PlanStep", "canonical_code", "traceback"):
                assert token not in text, (name, token)
            assert not re.search(r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b", text)
            page.screenshot(path=str(target / f"{name}.png"), full_page=True)
            results.append({"page": name, "interaction": "PASS", "visible_technical_fields": 0})

        capture("member-home")
        radio("健康"); capture("member-health")
        radio("计划"); capture("member-plan")
        radio("历程"); capture("member-timeline")
        radio("首页")
        page.set_viewport_size({"width": 640, "height": 960})
        capture("member-home-narrow")
        page.set_viewport_size({"width": 1440, "height": 1080})
        radio("健康管理师"); capture("manager-today")
        radio("成员"); button("查看成员"); capture("member-360")
        radio("医生"); capture("doctor-review"); capture("doctor-review-decision", bottom=True)
        radio("管理员"); capture("admin-integrations")
        if args.exercise:
            radio("成员"); radio("首页"); button("去完成"); button("确认完成")
            assert "接下来我要做什么" in page.locator("body").inner_text()
            radio("健康"); radio("健康数据")
            results.append({"path": "A", "result": "PASS"})
            radio("健康管理师"); radio("今日"); button("处理")
            radio("管理"); radio("工作进展")
            assert page.get_by_role("button", name="确认处理", exact=True).count() == 1
            page.get_by_label("确认说明", exact=True).fill("演示健管已核对当前资料并接手后续安排")
            button("确认处理")
            results.append({"operation": "manager_approval", "result": "PASS"})
            radio("建立 / 调整计划")
            page.get_by_label("本阶段目标", exact=True).fill("维持可执行的健康记录与按期复盘")
            page.get_by_label("建立依据 / 调整原因", exact=True).fill("根据成员反馈调整执行频率，医学问题交医生确认")
            button("保存健康计划")
            page.get_by_text("健康计划已保存，成员可以查看并反馈。", exact=True).wait_for(timeout=30000)
            radio("安排随访")
            page.get_by_label("需要完成什么", exact=True).fill("核对近期健康记录并回访执行情况")
            button("安排随访")
            page.get_by_text("随访已安排，已进入成员计划与健管工作队列。", exact=True).wait_for(timeout=30000)
            radio("记录阶段结果")
            capture("member-360-outcome", bottom=True)
            page.get_by_label("起点数值", exact=True).fill("132")
            page.get_by_label("本次数值", exact=True).fill("128")
            page.get_by_label("单位", exact=True).fill("mmHg")
            page.get_by_label("结果依据", exact=True).fill("匿名演示数据两次人工核对记录，仅描述观察变化")
            button("记录阶段结果并安排下一步")
            page.get_by_text("阶段结果已回写到计划与历程，后续行动已建立。", exact=True).wait_for(timeout=30000)
            results.append({"path": "B", "result": "PASS"})
            radio("医生")
            assert "暂无原始依据" in page.locator("body").inner_text() or "部分依据" in page.locator("body").inner_text()
            page.get_by_label("医生人工意见", exact=True).fill("演示人工复核：原始依据需补齐，暂不作医学结论。")
            page.get_by_label("交给健康管理师的下一步", exact=True).fill("收集原报告并安排成员复查记录")
            button("提交判断并交回健管")
            page.screenshot(path=".runtime/ux-doctor-after.png", full_page=True)
            page.get_by_text("医学判断已保存，跟进任务已交给健康管理师。", exact=True).wait_for(timeout=30000)
            radio("已完成")
            assert "原始依据需补齐" in page.locator("body").inner_text()
            radio("健康管理师"); radio("今日")
            assert "收集原报告" in page.locator("body").inner_text()
            results.append({"path": "C", "result": "PASS"})
            radio("管理员")
            page.get_by_role("button", name="检查", exact=True).nth(1).click(); settled()
            # Deliberate unavailable local endpoint proves failed tests do not claim connected.
            page.get_by_label("服务地址", exact=True).fill("http://127.0.0.1:1")
            button("测试连接")
            page.get_by_text("连接测试未发送成员健康数据。", exact=True).wait_for(timeout=30000)
            results.append({"path": "D", "result": "PASS"})
        browser.close()
    Path(".runtime/ux-browser-qa.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
