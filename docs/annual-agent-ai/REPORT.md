# 年度管理入口与 Agent 能力调用验收

## 年度管理现在和会员有什么区别

会员页用于找人：搜索、状态、负责人筛选，保留原会员表、最近联系、下一步、日期、状态和入组入口。点击进入同一个 Member360 的**概览**，返回按钮为“← 返回会员”。

年度管理用于看全年进度：六项紧凑汇总 → 阶段分布条 → 年度/阶段/责任健管/逾期/等医生/待复盘筛选 → 年度进度工作表。点击进入同一个 Member360 的**管理**，携带所选年度周期，返回按钮为“← 返回年度管理”，保留筛选条件。没有新增会员详情 V2。

- [会员首屏](../images/annual-agent-ai/24-members-final.png)：搜索和会员表在首屏；无阶段驾驶舱。
- [年度管理首屏](../images/annual-agent-ai/22-annual-final.png)：六项汇总与横向阶段分布先出现。
- [年度工作表](../images/annual-agent-ai/23-annual-table.png)：目标、阶段、实际事项进度、开放事项、等待对象、节点和责任人。
- [会员进入概览](../images/annual-agent-ai/02-member-overview.png)、[年度进入管理](../images/annual-agent-ai/04-annual-member-management.png)。

年度页面是只读投影：基线来自既有已确认基线；阶段来自年度计划/阶段记录。14 天阶段复盘窗口、30 天年度复盘窗口是页面提示范围，已在页面说明，不新增业务调度、医学阈值或自动转换阶段。进度按完成的入组节点/已排期事项计算，不用时间经过比例假装管理成效。没有阶段记录时不把年度结束日冒充阶段截止日。历史未关联周期的事项仍留在 Member360，不计入某个周期的完成比例。

原年度表字段保留或明确更名：年度目标 → 年度目标摘要；负责人 → 责任健管；下一日期 → 阶段结束时间；原阶段名称、阶段状态和服务周期仍可在表中查看。表格保留横向滚动；没有将记录逐行卡片化。

## Agent 现在什么时候调用 LLM

| 场景 | 实际代码路径 | 触发与边界 |
|---|---|---|
| 体检后的健管摘要 | `agent/post_checkup.py::analyze/llm_summary` → `LocalLLMClient.generate_structured`，任务 `post_checkup_manager_draft` | 已结构化报告分析时，在读取报告/档案/基线并检索知识后调用；只生成待健管核对的非临床摘要。原医学输出禁限校验保留。 |
| 医生返回后的随访主题 | `agent/post_checkup.py::prepare_actions`，任务 `post_checkup_action_draft` | 存在真实医生结果才调用；只采用医生建议中连续的 2–30 字原文，行动类型和日期仍由原确定性逻辑决定。无可用结果保留原规则标题。 |
| 自由文本问卷/历史档案 | `services/profile_ingestion.py::_parse`，任务 `parse_health_questionnaire/history` | 没有原生/带标签映射事实，也没有已有确定性候选时才调用；字段必须在白名单内，值和证据必须能逐字核实。不可靠时保留原文件并转人工。 |
| 体检报告叙述段 | `services/report_parsing.py::ReportSemanticFallback.extract`，任务 `report_semantic_fallback` | 对实际符合条件的影像、检查结论、建议等叙述段调用；结构化测量继续走确定性解析。健康检查发现服务不可用时没有生成请求，不标记成功。 |
| 仍无事实/候选的报告自由文本 | `services/profile_ingestion.py::_parse`，任务 `parse_health_report` | 保留原有回退路径与原文核对，不增加额外模型调用。 |

`agent/profile_intake.py` 继续使用原 Supervisor、工具注册、确认与医生返回流程；它通过现有 `ProfileIngestionService` 完成解析，没有另建 Agent 框架。原生结构化问卷、可映射的带标签资料不为了展示 AI 而调用模型。

## Agent 什么时候调用知识库

`agent/post_checkup.py::analyze` 实际执行原工具 `retrieve_knowledge`；工具仍由该模块的 `register_tools` 注册，调用 `services/post_checkup.py::PostCheckupCareService.knowledge`，再调用 `services/knowledge_retrieval.py::KnowledgeRetrievalService.search`。

检索使用本次指标标签，只取有效且审核通过的知识文档/分块，类别为 `CLINICAL_GUIDELINE` / `PATIENT_EDUCATION`，现有实现为关键词/词法检索。详情显示真实返回标题、来源、版本、位置和摘录。不调用模型生成引用。返回 0 条显示“检索完成，暂无匹配的已审核知识依据”，不会补造来源。

资料导入流程本次不需要、也没有调用知识检索；看板明确显示“本步骤未调用知识库”。

## 看板现在怎么显示

保留六步流程、当前工作、当前责任、系统发现、正式风险、人工参与、下一步及最终产出；新增紧凑能力路线和独立“AI与知识支持”主区域。

- 能力路线：规则、健康档案、知识库、AI、健管、医生；真实使用、当前责任和未使用分别带文字与符号。
- 支持区：用途、执行结果、真实记录时间；成功/不可用/结果未采用/未执行/未使用分开显示。
- “查看依据”打开原生详情弹窗；“查看摘要”显示保存的原 AI 草稿，避免人工编辑后的摘要冒充原 AI 输出。
- 时间轴增加真实知识检索、摘要整理及医生意见整理；失败保留 △ 与回退说明，不用 ✓ 包装失败。
- 责任分流说明 AI 做了什么、知识提供了什么、医生需要判断什么。
- 普通健管界面不出现内部任务名、Provider、模型名、Prompt。管理员技术详情才显示真实任务、请求是否发出、状态、耗时、输入来源类别、结果摘要。
- 页面明确：AI 摘要 ≠ 正式风险；知识依据 ≠ 会员事实；医生意见 ≠ Agent 推断。

### 审计记录边界

复用 `AgentRunTrace`，新增业务安全 `capability_activity` 元数据；不改数据库模型/迁移。请求级采集器只保留任务、提供方、是否发出请求、时间、耗时和结果状态。结果核对后仅补充可采用标记及数量，不保存 Prompt 全文、完整敏感输入、模型原始响应或隐藏思维链。知识依据只保留实际命中引用的白名单字段。

多段解析分开记录每次请求的核对数量；前端使用本次解析去重后的候选数，不重复累计整份文件数量。只有已有调用证据才显示已调用。旧记录缺少逐次 Provider/耗时等信息时明确缺失，不按当前配置伪造历史。旧医生返回记录无 AI trace 时不显示 AI 已完成。

现有同步事务没有可供另一会话可靠读取的持久化逐请求运行中状态；本轮不伪造“AI 正在生成”动画。已完成调用及真实等待对象正常展示，执行时间来自实际请求。

## 真实浏览器与模型验收

独立 SQLite 副本：`.runtime/annual-agent-ai/qa.db`；合成验收会员与测试上传资料不写入日常数据库。调用本机真实 Ollama `qwen2.5:7b`，未用 UI 假数据或模型桩冒充浏览器成功。

Playwright **Chromium 151**，1440×900；另检查年度页面 1366×768 与 390×844，没有页面级横向溢出。可见原生焦点环，能力状态同时有文字/符号，数据表保留可滚动布局。

已从实际浏览器完成：打开体检 Agent → 查看实际知识与摘要 → 健管提交医生 → 医生提交判断与建议 → 原流程恢复 → 真实模型提取医生原文 → 健管确认并建立后续安排。独立读取实际记录验证整个流程完成且该合成会员未产生正式 Risk。

| 场景 | 实际结果 | 截图 |
|---|---|---|
| 体检知识与摘要 | 3 个真实知识命中；本地模型摘要成功 | [知识详情](../images/annual-agent-ai/09-knowledge-detail.png)、[摘要](../images/annual-agent-ai/10-ai-summary.png) |
| 医生返回 | 本地模型成功从原文提取主题，仍需健管确认 | [医生返回](../images/annual-agent-ai/13-doctor-return-ai.png)、[最终支持区](../images/annual-agent-ai/27-care-final-ai-support.png) |
| 活动时间轴 | 知识、摘要、医生返回后的整理都有实际完成时间 | [真实时间轴](../images/annual-agent-ai/28-care-activity-timeline.png) |
| 原生问卷 | 2 项规则候选；没有 LLM 和知识调用 | [结构化资料](../images/annual-agent-ai/18-profile-structured.png) |
| 自由文本问卷 | 实际 LLM 整理 2 项原文候选；未调用知识库 | [自由文本](../images/annual-agent-ai/19-profile-free-text.png) |
| 模型未启用 | `UNAVAILABLE`，请求未发出；规则结果继续 | [不可用回退](../images/annual-agent-ai/20-care-ai-unavailable.png) |
| 管理员实际记录 | 知识 3 hits，摘要 36,818 ms，医生意见 2,750 ms，自由文本 2,245 ms | [体检与医生调用](../images/annual-agent-ai/25-admin-summary-doctor-calls.png)、[资料解析调用](../images/annual-agent-ai/26-admin-profile-calls.png) |

耗时是本次实际执行值，不是性能承诺。完整安全执行证据在 [execution-evidence.json](execution-evidence.json)，截图清单在 [results.json](../images/annual-agent-ai/results.json)。

共保存 29 张真实 Chromium 截图，已打开检查首屏、表格、能力支持区、管理员调用表和时间轴。验收结束已停止隐藏 QA 实例，并确认 18540 端口无残留监听。

## 测试与元素保护

- Baseline：**710 passed / 0 failed**，见 [基线日志](baseline/final-tests.txt)。
- 新增 20 项专项测试：年度读模型、两入口跳转/历史周期、真实知识与 0 命中、没有调用不能显示成功、原生问卷不调用 LLM、自由文本、不可用回退、医生原文边界、思维链字段不落地、原 AI 草稿、多段解析计数、无伪造 Risk。
- 最新解析/资料导入/调用审计定向回归：**69 passed / 0 failed**。
- 完整回归：**730 passed / 0 failed**，13 项既有依赖警告，见 [final/final-tests.txt](final/final-tests.txt)。随后修正“无阶段时不借用年度截止日”的展示边界，20 项专项测试再次全部通过。完整回归在工作树隔离副本中执行；测试关闭真实 LLM，真实模型路径由上面的独立验收覆盖。
- UI Inventory：695 个原控件调用，修改后 701 个；原控件身份缺失 **0**。原有业务按钮、表格、图表、流程入口保留。见 [preservation.json](preservation.json) 及前后 inventory。
- 风险/责任路由、Supervisor、通用 tools、数据库 models/migrations 等 60 个受保护文件哈希一致。报告解析只增加结果数量审计，不改变原候选校验。

## 设计与复现

实际读取 Skill：`D:/executive_health_ai/.agents/skills/ui-ux-pro-max/SKILL.md`。沿用 `design-system/healthops/MASTER.md` 的医疗蓝、清晰边框、克制 Soft UI 主面板、内凹筛选区与原生表格。本轮搜索类别比较条形图及可预期返回导航规则；宽泛查询返回的漏斗建议不适用，改用阶段分布条。

首次合成验收用 `scripts/seed_annual_agent_qa.py`（现有 QA 数据库存在时拒绝覆盖）；隐藏启动使用 `scripts/start_visual_qa.ps1 -Instance annual-ai -Manifest .runtime/annual-agent-ai/manifest.json`。配置本机模型后运行 `scripts/qa_annual_agent_visibility.py` 走完整交互；已完成的案例使用 `--followup` 做只读复查。`scripts/verify_annual_agent_evidence.py` 对实际记录作只读断言并导出安全证据。停止使用 `scripts/stop_platform.ps1 -Instance annual-ai`。

备份：`backup/pre-annual-agent-ai-visibility`。提交主题：`feat: differentiate annual management and expose agent AI activity`。**不 push**。
