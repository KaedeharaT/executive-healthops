# 逐张视觉验收

实际 Chromium；从普通首页正常点击。21 张截图逐张打开检查。

| 截图 | 肉眼检查结果 | 判定 |
|---|---|---|
| [01-manager-today](../images/product-logic-v5/01-manager-today.png) | 紧凑摘要、健康管理助手与统一工作表同屏；负责人、期限和当前动作可见。 | PASS |
| [02-manager-work-detail](../images/product-logic-v5/02-manager-work-detail.png) | 一个阶段流程；现在需要你做及确认主按钮位于第一屏；返回今日工作明确。 | PASS |
| [03-manager-agent-visible](../images/product-logic-v5/03-manager-agent-visible.png) | 等待健管提供继续处理，等待医生明确无需操作。 | PASS |
| [04-member-list](../images/product-logic-v5/04-member-list.png) | 搜索、筛选、唯一会员表格；无选择方式开关；新建周期使用业务入口。 | PASS |
| [05-member360-overview](../images/product-logic-v5/05-member360-overview.png) | 五个页签、年度阶段、分开的会员关注与专业重点、两张真实趋势及开放事项。 | PASS |
| [06-member360-management](../images/product-logic-v5/06-member360-management.png) | 管理事项表格，保留新增管理记录；无重复会员选择。 | PASS |
| [07-management-log](../images/product-logic-v5/07-management-log.png) | 管理日志默认时间轴，完整记录折叠在单层详情中。 | PASS |
| [08-annual-management](../images/product-logic-v5/08-annual-management.png) | 年度全局表格和准确的执行中计数；点击进入同一 Member360 管理页。 | PASS |
| [09-medical-collaboration](../images/product-logic-v5/09-medical-collaboration.png) | 医疗协同只用一个全局医疗表；医生、等待时长和下一步可见。 | PASS |
| [10-doctor-home](../images/product-logic-v5/10-doctor-home.png) | 医生只有待我判断和历史，待判断问题与关键变化同表。 | PASS |
| [11-doctor-review](../images/product-logic-v5/11-doctor-review.png) | 医学问题、数据、基线参考趋势、依据和判断表单，只有一个提交主按钮。 | PASS |
| [12-service](../images/product-logic-v5/12-service.png) | 服务按状态和搜索筛选，统一业务表。 | PASS |
| [13-member-home](../images/product-logic-v5/13-member-home.png) | 成员首页优先显示当前行动、为什么、负责人、期限及当前计划。 | PASS |
| [14-admin-automation](../images/product-logic-v5/14-admin-automation.png) | 管理员自动化运行表，技术状态只在后台显示。 | PASS |
| [15-action-approval](../images/product-logic-v5/15-action-approval.png) | 行动草稿表可核对负责人、日期和依据，一个确认创建主按钮。 | PASS |
| [16-care-completed](../images/product-logic-v5/16-care-completed.png) | 业务完成语言、实际创建数量和下一节点；返回会员或查看事项。 | PASS |
| [17-service-detail](../images/product-logic-v5/17-service-detail.png) | 服务在右侧详情，一级流程和一个当前执行动作。 | PASS |
| [18-admin-detail](../images/product-logic-v5/18-admin-detail.png) | 管理员右侧运行详情；步骤、工具与状态以表格展示，无隐藏推理内容。 | PASS |
| [19-recheck-work-detail](../images/product-logic-v5/19-recheck-work-detail.png) | 今日工作直接进入复查详情；负责人、截止、当前阶段和推进按钮明确。 | PASS |
| [20-log-next-action](../images/product-logic-v5/20-log-next-action.png) | 日志准备的下一步、负责人和日期紧凑显示；一次确认建立待办。 | PASS |
| [21-service-completed](../images/product-logic-v5/21-service-completed.png) | 服务开始并完成后详情持续保留；完成依据、结果和下一步可见。 | PASS |

核心页面文字墙：0 / 21。嵌套展开：0 / 21。阻断问题：0。
普通界面实现方式开关：0。普通界面技术词泄漏：0（19 个普通页面；另 2 个为允许技术信息的管理员页面）。
真实键盘验收通过：搜索会员后 Tab 到原生表格，方向键 / Enter 直接进入 Member360，无模式开关。
浏览器额外完成：日志确认生成五天后的待办并在今日工作搜索打开；复查推进至待预约；服务开始、填写结果并完成且详情不丢失。
