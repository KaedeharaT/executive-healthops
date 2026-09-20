# 信息表达重构：真实浏览器验收

## 环境与范围

- 2026-09-21，真实 Streamlit 进程 + Playwright Chromium，1680 × 1100 桌面视口。内置 Browser runtime 无可用实例，使用已安装 Chromium。
- 使用已有匿名合成 QA 数据库副本；未复制任何真实健康资料，未为截图补造健康趋势。
- 25 个业务页面／视图，另含筛选、空状态、行选择及不同会员数据状态。图片在 `images/information-design-v1/`。共保存 36 张截图。本轮未将移动端或全部高级工具逐页视觉验收计入结论。

## 真实交互证据

- 今日工作：直接点击第二行，右侧准确显示“协调合成复查预约”；逾期筛选、搜索无匹配、恢复全部均正常。
- 会员列表：点击表头切换排序；排序后选择首行，实际进入对应 Synthetic Workflow B，未误打开排序前首行。
- 管理日志：时间轴／表格切换；实际下载筛选 CSV，包含下一步和负责人。完整字符串独立于表格摘要保存。
- 集成页：默认先显示状态，未选中时不展开上传配置；点击 AI 行展示对应配置；原兼容快捷入口仍可用。
- 成员计划、服务及医生复核：表格选择后保留原完成、取消、医学判断和回交操作，未新增写入路径。
- 成员健康：实际截图可见 X/Y 轴、数值刻度、时间、kg、年度基线虚线和当前值；健康数据双血压线可见 mmHg 和图例。
- 成员历程：真实打开且事件渲染，无页面异常；普通管理日志没有混入长期事件事实。

## 人工图像复查

已实际查看截图中的队列密度、主操作、表头、阶段节点、长文位置、坐标轴和空状态；不是以 renderer 被调用代替视觉判断。

- 今日工作九条事项集中在一个有界表格，状态、负责人、截止可扫读；长原因和完整下一步进入所选详情。
- 管理事项表四条待办集中显示，单条操作复用原任务服务；列表不再逐条展开完整来源。
- 阶段流横向连接当前节点；截图发现原有 HTML 有序列表被 Streamlit 样式压成竖列，已改为共享语义 list 组件并复拍。
- 无趋势的会员概览不保留空白左列；有真实趋势的会员仍显示趋势与开放事项两栏。
- 成员服务原有流程与新增流程重复显示已合并为一个流程；已安排仍属于安排阶段，不冒充服务正在执行。
- 已检查页面中，默认可见区域超过 80% 为段落正文：0 / 25；阻塞视觉问题：0。此项为截图人工判断，不是自动像素测量。

## 每个截图状态的组件计数

计数为当前展开视图中的实际渲染组件（含下方需要滚动的内容），不是全部集中在截图首屏。TABLE 统计原生 Data Grid，另外成员健康和成员360健康仍保留 HTML 紧凑基线对比表；不将这些对比行误算成新建 Data Grid。TIMELINE 列按事件节点计，SUMMARY 按共享摘要条计；原有统计条可能使用其他组件，0 不表示页面没有概况。

| 页面／截图状态 | TABLE | CHART | TIMELINE 节点 | STEPPER | SUMMARY |
|---|---:|---:|---:|---:|---:|
| [today-row-selection](images/information-design-v1/today-row-selection.png) | 1 | 0 | 0 | 0 | 2 |
| [today-empty](images/information-design-v1/today-empty.png) | 0 | 0 | 0 | 0 | 1 |
| [today-overdue](images/information-design-v1/today-overdue.png) | 1 | 0 | 0 | 0 | 2 |
| [member-360-overview](images/information-design-v1/member-360-overview.png) | 1 | 0 | 1 | 1 | 1 |
| [member-360-management](images/information-design-v1/member-360-management.png) | 1 | 0 | 0 | 1 | 3 |
| [management-items-detail](images/information-design-v1/management-items-detail.png) | 1 | 0 | 0 | 1 | 3 |
| [management-log](images/information-design-v1/management-log.png) | 0 | 0 | 1 | 1 | 1 |
| [management-log-table](images/information-design-v1/management-log-table.png) | 1 | 0 | 0 | 1 | 1 |
| [recheck](images/information-design-v1/recheck.png) | 1 | 0 | 0 | 2 | 1 |
| [recheck-timeline](images/information-design-v1/recheck-timeline.png) | 0 | 0 | 1 | 2 | 1 |
| [annual-member](images/information-design-v1/annual-member.png) | 1 | 0 | 0 | 1 | 1 |
| [stage-result](images/information-design-v1/stage-result.png) | 2 | 0 | 0 | 1 | 1 |
| [stage-review](images/information-design-v1/stage-review.png) | 0 | 0 | 0 | 1 | 1 |
| [member-medical](images/information-design-v1/member-medical.png) | 0 | 0 | 0 | 0 | 2 |
| [annual-management](images/information-design-v1/annual-management.png) | 2 | 0 | 0 | 1 | 0 |
| [medical-collaboration](images/information-design-v1/medical-collaboration.png) | 1 | 1 | 0 | 0 | 1 |
| [consultation](images/information-design-v1/consultation.png) | 2 | 0 | 0 | 1 | 0 |
| [service-operations](images/information-design-v1/service-operations.png) | 1 | 0 | 0 | 1 | 0 |
| [doctor-review](images/information-design-v1/doctor-review.png) | 1 | 1 | 0 | 0 | 1 |
| [doctor-history](images/information-design-v1/doctor-history.png) | 1 | 0 | 0 | 0 | 1 |
| [member-health](images/information-design-v1/member-health.png) | 0 | 1 | 0 | 0 | 0 |
| [member-health-axes](images/information-design-v1/member-health-axes.png) | 0 | 1 | 0 | 0 | 0 |
| [health-data](images/information-design-v1/health-data.png) | 0 | 1 | 0 | 0 | 1 |
| [member-plan](images/information-design-v1/member-plan.png) | 1 | 0 | 0 | 1 | 2 |
| [member-service](images/information-design-v1/member-service.png) | 1 | 0 | 0 | 1 | 0 |
| [member-timeline](images/information-design-v1/member-timeline.png) | 0 | 0 | 6 | 0 | 0 |
| [admin-system](images/information-design-v1/admin-system.png) | 1 | 0 | 0 | 0 | 0 |
| [admin-integrations](images/information-design-v1/admin-integrations.png) | 1 | 0 | 0 | 0 | 1 |
| [admin-ai](images/information-design-v1/admin-ai.png) | 1 | 0 | 0 | 0 | 1 |
| [admin-automation](images/information-design-v1/admin-automation.png) | 1 | 0 | 0 | 0 | 0 |
| [admin-rules](images/information-design-v1/admin-rules.png) | 2 | 0 | 0 | 0 | 0 |
| [manager-today](images/information-design-v1/manager-today.png) | 1 | 0 | 0 | 0 | 2 |
| [members](images/information-design-v1/members.png) | 1 | 0 | 0 | 0 | 0 |
| [member-360-with-trend](images/information-design-v1/member-360-with-trend.png) | 1 | 1 | 0 | 0 | 1 |
| [member-360-health](images/information-design-v1/member-360-health.png) | 0 | 1 | 0 | 0 | 1 |

## 数据与保留边界

- Synthetic Workflow B 当前阶段缺少两条不同时间的有效观测，阶段评估正确显示简短资料不足说明，截图不声称该状态有图。阶段趋势分支由真实共享数据投影及有时间序列的 AppTest 覆盖；正式健康趋势已在实际浏览器验证。
- 只读会员目录批量取周期、阶段、日志、任务、问题与初评；最近联系来自管理日志，不能用任务创建时间冒充。
- 原 121 个保留元素登记逐项核对，121 个 renderer 全部存在，UI 顶层函数删除数为 0；导航与兼容入口继续存在；真实工作流表单、状态推进、日志创建下一步、会诊人工拆解、阶段交接调用原服务。
- 数据库、migration、Risk、Baseline 语义、Agent 权限与医生责任边界未更改。

## 已知非阻塞限制

- 多列表格在详情并排或较窄窗口下允许横向滚动，完整文字仍在详情；这不是将全文塞进表格。
- 日期列保留原生日期类型，未填日期使用 Streamlit 原生空值占位；不虚构负责人或截止时间。
- 时间轴需要逐条阅读；批量搜索／导出请切换管理日志表格视图。
- 工作人员优先桌面；本轮不声称完成所有小屏设备验收。

## 测试与变更范围

- Baseline：576 passed / 0 failed / 0 skipped。
- 新增组件测试覆盖选择映射、筛选后重定位、排序规则、空状态、阶段状态、日志切换与导出入口、实际阶段日期过滤、来源标签和配置显式选择。
- 原有静态 UI 测试中的“必须渲染文字卡片”契约更新为表格加详情；保留原导航、业务动作及按需加载约束。
- 全量最终结果：588 passed / 0 failed / 0 skipped，13 条既有依赖弃用警告，392.27 秒。

展示规则与全平台对象映射： [INFORMATION_PRESENTATION_MAP.md](INFORMATION_PRESENTATION_MAP.md)。
