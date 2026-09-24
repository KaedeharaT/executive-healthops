# Visible Changes

本轮修改了真实 Streamlit 应用和 UI。以下对比基于备份提交 `61ab749`；旧版已有部分表格和时间轴，本轮继续重构业务入口、默认展开方式和实际操作。

| 页面 | 以前 | 现在肉眼可见的变化 |
| --- | --- | --- |
| 今日工作 | 表格与默认详情并列，概览指标偏通用 | 五项紧凑工作摘要；完整八列表格；主动选行才打开右侧事项详情，下一步和主要操作集中显示 |
| 会员列表 | 已有表格，但年度与筛选信息不足 | 九列会员目录，增加当前年度、状态和负责人筛选；从同一目录进入 Member 360 |
| Member 360 | 通用会员标题、重复摘要，默认资料较展开 | 紧凑会员 Header，明确分开本人关注与专业重点；保留五个页签；概览含阶段、两张实际数据趋势、开放事项和最近记录 |
| 管理日志 | 填写表单占据页面，保存后生成任务通过附加选择控制 | 高频“新增管理记录”；默认时间轴、分页与表格切换；独立“保存”和“保存并创建下一步”，高级字段折叠 |
| 年度管理 | 选中详情默认展开，阶段以展示为主 | 年度目录先查找，选行再看；阶段可点击；阶段目标、完成数、计划结束和阶段事项表一起显示 |
| 医疗协同 | 医生详情默认占屏；正式会诊先选会员 | 医生复核七列表格与按需抽屉；会诊先看全会员列表，再看六步流程、医生意见表和行动拆解 |
| 服务 | 表格与常驻详情分栏，执行代码在主文件 | 全宽服务表、搜索和状态筛选；按需右侧六步流程；完成后可进入会员管理；执行代码拆入 manager/services.py |
| 阶段结果 | 记录表单在前，数值比较在后 | 首屏先显示前后对比表和可切换趋势图；填写评估按需展开；执行情况、未解决事项和下一阶段建议保留 |

## Information Presentation

统计范围：主浏览器脚本的 **23 个页面/状态**，仅计当前展开的原生业务表格、趋势图和流程组件，重复访问状态分别计数；时间轴按页面中的一组记录计，不按事件条数累加。下方有逐状态明细。补充操作截图不重复计入此表。

| 类型 | 数量 |
| --- | ---: |
| Tables | 22 |
| Charts | 7 |
| Timelines | 2 |
| Steppers | 8 |
| Detail panels（右侧抽屉） | 3 |

年度、复查、会诊等选中后的内嵌详情仍可用；HTML 指标比较表未计入原生表格数量。以上是验收场景计数，不是全平台功能总量。

## Manager

- Today：五项摘要、类型/负责人/时间范围筛选、八列管理事项表、右侧结构化详情；关闭抽屉重置选择，不修改业务记录。
- Member list：九列目录，保留入组与新年度服务周期操作；继续使用批量 member_directory 投影。
- Member360：概览、健康档案、管理、医疗、历程五个页签。Header 展示周期、责任健管、当前阶段、两类关注、下一步及更新时间。
- Health record：自报资料、已确认医疗档案、家庭关系、报告与基线默认摘要化；原有查看和编辑入口保留。初始评估合并为 11 个 UI 步骤，原有当前用药与最近用药两份数据键均保留；支持草稿、继续、提交与健管确认。
- Annual：年度目标、可点击阶段、阶段事项与阶段结果。阶段事项使用同一年度方案、阶段日期范围内的现有任务；未排期事项仍在管理事项中。
- Logs：时间轴/表格切换、搜索、分页和完整导出。浏览器实际提交记录并创建关联任务，验证会员与年度方案一致、只生成一条下一步。
- Recheck：检查项目、原因、日期、状态、医院、负责人、报告状态、下一步表格；七个业务里程碑。底层原有全部状态和合法转换保留。
- Medical：复核表格、趋势/报告/用药依据、正式会诊流程、医生意见和健管确认行动拆解；医生判断权限不变。
- Service：搜索、状态筛选、审批、预约、开始、完成依据及结果回写继续调用原服务。

## Member

保留首页、健康、计划、服务、历程五个入口。首页聚焦当前行动、原因、负责人和期限；健康页把“年度基线到当前”的比较表与图提前到首屏；计划继续显示当前阶段、任务、复查和阶段结果。工作人员配置入口不进入成员导航。

## Preservation

Old elements: **121**

Deleted: **0**

Missing: **0**

逐项保留原盘点的源码入口和目标位置，见 [preservation.json](preservation.json)。结合全量测试检查原有业务能力；管理员 AI、Agent、规则、知识、设备、导入、自动化、反馈、审计、Trace 和兼容工具均保留。浏览器另检查了管理员页面。

## Business Logic

Core workflow changed: **NO**

Risk engine changed: **NO**

Baseline semantics changed: **NO**

Doctor responsibility changed: **NO**

继续复用 ManagementWorkflowService、MemberManagementProjection、ProductProjectionService 和原业务模型。本轮没有修改 models/ 或 services/ 下的业务文件，没有新建第二套事实存储。

趋势图仅在已有已确认基线且指标、单位匹配时绘制年度基线参考线；不会把第一条观测伪装成年度基线。阶段结果如无边界时点测量，明确显示“阶段内首条/最新”，不伪造阶段开始值。

streamlit_app.py 本轮净减少 **94 行**，页面逻辑拆入 manager/，共享组件继续在现有 ui/components.py 与 ui/presentation.py 中统一。

## Visual QA

Actual browser: **YES — Chromium + 实际运行的 Streamlit**

Pages inspected: **27 个页面/操作状态**

Paragraph-heavy core pages: **0 / 13**

Blocking issues: **0**

使用隔离的合成演示数据库 `.runtime/workbench-v4.db`，截图不是患者真实数据；未改动工作区原业务数据库。应用运行于 `http://127.0.0.1:18514`。内置浏览器运行时返回空浏览器列表，因此使用本地 Chromium 实际点击、输入、切换和截图；AppTest 没有替代浏览器验收。

27 张 PNG 均逐张打开检查：指定的 13 张、选中后详情、日志创建与下一步、成员首页/计划、图表提示和管理员。检查重点为表格可读、列表不铺长文、详情有下一步、图表轴和单位、阶段可辨识。

- [主浏览器结果](../images/workbench-v2/browser-results.json)：23 个状态，无浏览器页面错误。
- [日志实际操作](../images/workbench-v2/action-results.json)：保存、下一步唯一性、会员/年度归属、抽屉关闭与切换隔离。
- [图表实际操作](../images/workbench-v2/chart-results.json)：11 类有数据指标切换，真实 hover tooltip 与时间轴，管理员入口。
- 自动回归另覆盖 11 步评估实际保存/提交、阶段选择、阶段任务边界、单位匹配基线、无基线时不造参考线。

### 指定截图

| 页面 | 截图 |
| --- | --- |
| 今日工作 | [manager-today.png](../images/workbench-v2/manager-today.png) |
| 会员列表 | [member-list.png](../images/workbench-v2/member-list.png) |
| Member 360 | [member-360.png](../images/workbench-v2/member-360.png) |
| 健康档案 | [member-health-record.png](../images/workbench-v2/member-health-record.png) |
| 会员管理 | [member-management.png](../images/workbench-v2/member-management.png) |
| 管理日志 | [management-log.png](../images/workbench-v2/management-log.png) |
| 年度管理 | [annual-management.png](../images/workbench-v2/annual-management.png) |
| 复查 | [recheck.png](../images/workbench-v2/recheck.png) |
| 医疗协同 | [medical-collaboration.png](../images/workbench-v2/medical-collaboration.png) |
| 会诊 | [consultation.png](../images/workbench-v2/consultation.png) |
| 服务 | [service.png](../images/workbench-v2/service.png) |
| 阶段结果 | [stage-review.png](../images/workbench-v2/stage-review.png) |
| 成员健康 | [member-health.png](../images/workbench-v2/member-health.png) |

## Testing

Baseline: **588 passed / 0 failed**，备份提交 `61ab749` 的独立 worktree 全量运行，见 [baseline-tests.txt](baseline-tests.txt)。

Final: **594 passed / 0 failed**，见 [final-tests.txt](final-tests.txt)。原有 13 个弃用警告数量未增加。

最后两项展示调整（复查里程碑文案、服务结果到会员管理按钮）后另跑 **43 passed / 0 failed**，见 [final-targeted-tests.txt](final-targeted-tests.txt)，并重新启动 Streamlit 重拍主验收截图。

新增六项针对行为的回归测试；已有源码结构测试随页面拆分更新，原服务业务断言保留。执行命令：`.venv/Scripts/python.exe -m pytest -q`。

## Git

Backup: `backup/pre-chat-driven-workbench-refactor` → `61ab749`

Commit message: `feat: align HealthOps workbench with real care workflows`

Push: **NO**

## Final

REAL CARE WORKFLOW PRIMARY: **YES**

TABLE-FIRST STAFF UX: **READY**

MEMBER 360: **READY**

MANAGEMENT LOG: **READY**

ANNUAL MANAGEMENT: **READY**

MEDICAL COLLABORATION: **READY**

HEALTH VISUALIZATION: **READY**

TEXT WALL: **FIXED**
