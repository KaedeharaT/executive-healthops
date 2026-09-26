# 最近完成：紧凑历史记录

原来的两个大卡片对应两份报告、两个真实 Goal。相同标题和重复完成说明造成了重复 Bug 的观感。本次只调整展示，不合并真实实例、不改 Agent、不写业务数据。

- 活动流程保留原卡片；完成流程仅显示紧凑行。
- 列为完成时间、会员、流程、来源、报告日期、最终产出、下一步、操作。
- 默认最近 5 条，按实际完成时间倒序；查看全部历史在原区域展开，每页最多 20 条。
- 顶部“最近完成”统计可跳转至历史区域。
- 每行唯一“查看”绑定原 Goal；时间轴及完整依据仍在原运行看板。

## 验证

24 项回归测试通过：`pytest tests/test_assistant_instance_groups.py tests/test_care_activity_presentation.py tests/test_product_logic_v5.py -q`。

真实 Chromium 从普通首页进入今日工作，检查两份报告分别为 2026-09-23 / 2026-09-25，逐行点击“查看”，校验运行看板原始报告下载控件绑定的 Goal 与该行一致，两者不同。未使用内部页面路由或会话注入。

结果：完成卡片 0；完成记录 2；错误去重 0。全部历史展开/收起、顶部统计定位均通过。1600×1000 和 1366×768 截图已逐张检查，查看按钮没有换行。

- [1600 页面](images/completed-history/history-1600.png)
- [1366 页面](images/completed-history/history-1366.png)
- [紧凑记录](images/completed-history/rows-1366.png)
- [浏览器断言](images/completed-history/browser-results.json)

未 push。
