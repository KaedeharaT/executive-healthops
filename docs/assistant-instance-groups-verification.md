# 健康管理助手实例去重验收

## 真实来源

原页面将 `active + recent` 合并为无分区卡片，且卡片标题只包含会员和流程名称。
现场两条完成记录对应不同 Goal 和不同报告，不能按标题合并或删除：

| Goal | 报告 | 完成时间（UTC） |
| --- | --- | --- |
| 8de1f421656b4cba9ef8754fd6784865 | 577c5ffa-8f99-4092-b4fb-2b65a7d1377d | 2026-09-25 08:00:02 |
| 452c77dd29dd40b49527217759ecf649 | 71c39bce-39ff-4967-851b-24cacd45ef7f | 2026-09-25 07:40:24 |

## 修改

- 只修改今日工作展示层；先按 Goal 主键归一和去重，再按当前状态分区。
- 同一实例若出现多个快照，采用最新更新时间；相同更新时间优先完成快照。
- 活动区包含 RUNNING / WAITING_MANAGER / WAITING_DOCTOR / ESCALATED。
- WAITING_INPUT / FAILED 的既有恢复入口保留在“需要人工协助”，不会冒充活动或完成。
- COMPLETED 仅进入“最近完成”，按实际完成时间倒序取最近 3 条；旧记录缺少完成时间时才使用更新时间。
- 卡片显示原报告来源、报告日期和完成时间，以区分同名的真实不同运行。
- 保留各实例的“查看运行看板”；未修改业务数据、状态机、服务或风险逻辑。

## 验证

命令：`.venv/Scripts/python.exe -m pytest tests/test_assistant_instance_groups.py tests/test_care_activity_presentation.py tests/test_product_logic_v5.py -q`

结果：22 passed。覆盖重复输入、同名不同实例、UUID 表示归一、跨状态最新快照、完成排序与 3 条上限、异常恢复入口、空状态，以及现有工作路由回归。

真实 Chromium 从普通首页进入今日工作，无内部路由或会话注入，检查 DOM 实例键并实际点击每条完成流程的看板入口后返回：

| 数据环境 | 活动 | 最近完成 | 重复实例 |
| --- | ---: | ---: | ---: |
| 当前 Demo（8501） | 0 | 2 | 0 |
| 已有独立验收库（18521） | 2 | 1 | 0 |

截图已经肉眼检查，活动与完成分区清晰，来源可区分：

- [当前 Demo](images/assistant-instance-groups/completed.png)
- [活动与完成并存](images/assistant-instance-groups/active-and-completed.png)
- [浏览器断言结果](images/assistant-instance-groups/browser-results.json)

浏览器检查过程没有创建、修改或删除业务记录。未 push。
