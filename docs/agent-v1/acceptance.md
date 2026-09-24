# What I Can See

健管在“今日工作”的管理事项表中收到新报告。点击后，先看到当前步骤和“需要您处理”，再看指标对比、真实趋势、已审核依据和会员背景。初次确认后，需要医学判断的报告直接交给医生；医生返回后，健管一次确认即可建立后续安排。

医生在原有“待我复核”队列收到明确问题。详情页左侧是报告、基线、趋势和背景，右侧填写医学判断、建议、复查项目与日期。提交后，原报告流程自动恢复。

系统替代了手工拼接报告与病史、比较年度基线、整理医生交接材料，以及逐个模块重复建立安排的工作。医学判断仍由医生负责，正式行动仍由健管确认。

演示入口：http://127.0.0.1:18515 。使用现有合成会员 Demo Executive A；完成案例保留在会员记录和管理员“自动化运行”中。

## Agent

| 项目 | 实现 |
|---|---|
| Type | Post-checkup Care Agent |
| Entry | 统一报告解析服务成功接收报告后，复用 `REPORT_UPLOADED` 事件；事件带会员、报告、年度方案及触发时间 |
| Goal | 完成本次体检报告的后续健康管理准备 |
| States | RUNNING、WAITING_MANAGER、WAITING_DOCTOR、WAITING_INPUT、COMPLETED、ESCALATED、FAILED |
| Human gates | 健管核对报告与处理路径 → 必要时医生判断 → 健管确认后续行动 |
| Exit | 已结构化、完成所需人工确认、实际业务记录已建立、负责人及日期齐全、下一节点明确 |

业务步骤固定为 REPORT_RECEIVED → ANALYZING → WAITING_MANAGER_REVIEW → 可选 WAITING_DOCTOR_REVIEW → WAITING_ACTION_APPROVAL → CREATING_ACTIONS → COMPLETED。异常保留 ESCALATED / FAILED；等待不是失败。无需医生时，流程图显示“已跳过”。建立三个月后的复查计划即可完成本次准备，不等待三个月。

## Manager UI

今日工作保留表格、搜索、筛选和原有业务导航。报告详情采用六步流程、发现表、最多两张实际历史趋势、紧凑依据表。主按钮按阶段分别为“确认并继续”“确认并创建后续安排”“返回会员360”。支持修正报告、编辑或删除行动草稿，以及可选服务安排。

## Doctor UI

沿用待复核队列和 DoctorReview。完整上下文含当前已记录健康问题、问卷过敏记录、既往手术住院、有效用药、症状、健康数据、报告与年度基线。提交判断只保存医学意见并发送完成事件；在最终健管确认前，不建立后续医疗安排。

## Member UI

保留首页、健康、计划、服务、历程。新安排通过既有计划与近期节点展示；会员360增加轻量“当前自动跟进”。普通界面没有技术控制台或交互组件选择开关。

## Admin UI

“自动化运行”提供会员、入口事件、状态、业务步骤、等待对象、时间和异常表格。详情查看既有 Goal、Step、Approval、Wait 与工具结果记录。已有自动化及兼容工具保留。记录输入摘要、结构化结果和状态变化，不记录模型隐藏推理。

## Automation

| 交接 | 验证 |
|---|---|
| Report → Manager | PASS |
| Manager → Doctor | PASS |
| Doctor → Resume | PASS；恢复原目标 |
| Resume → Actions | PASS；先形成草稿 |
| Actions → Completed | PASS；真实写入后验证完成条件 |

浏览器案例建立 3 项管理待办，其中关联 1 份复查计划、1 次随访，另写入 1 条管理日志。所有行动都有负责人和日期。可选服务申请也有独立行为测试。

## Safety

LLM diagnosis: NO

LLM prescription: NO

LLM risk decision: NO

Doctor medical responsibility preserved: YES

模型只返回待确认摘要和可追溯至医生原文的行动文字。候选指标由健管明确确认后，通过原有报告服务入档；确定性风险引擎按原规则工作。知识引用仅来自已审核检索结果；没有匹配时明确提示。无法解析的报告转人工；模型不可用时仍可核对报告、提交医生和安排管理行动。

实际连接本地 Ollama / qwen2.5:7b。首次冷启动曾触发 60 秒超时，业务降级正常；模型就绪后的真实摘要调用成功。当前演示已启用模型，原本地服务类型配置已修正；未上传真实个人资料。

## Persistence and preservation

复用 HealthOpsAgentSupervisor、既有事件服务、工具注册表、AgentGoal / AgentPlan / AgentPlanStep / AgentApprovalRequest / AgentRunTrace。仅通过迁移 `0028_post_checkup_context` 为既有目标增加 `context_json`；没有另建目标或流程框架。

业务写入位于服务层，复用 ManagementWorkflowService、现有报告服务、Task、DoctorReview、RecheckPlan、FollowUp、MemberServiceOperations 和 ManagementLog。入口受事件去重与目标唯一约束保护；人工确认使用状态条件更新，行动写入使用同一事务。重复恢复、重复确认不会重复创建业务记录。关联记录校验会员归属；医生操作校验角色及责任医生。

本地应用数据库及独立合成演示数据库已迁移。验收对比确认既有年度基线与风险规则记录保持不变。旧流程模板与历史目标保留；新报告采用本轮有限流程。

## Visual QA

Real browser: YES — Chromium，实际 Streamlit 应用

Screenshots: 10

Technical terms exposed to normal users: 0

Redundant interaction switches: 0

Blocking issues: 0

逐张检查了[全部截图](../images/agent-v1/)。已修复完成状态仍显示待核对、服务空值显示技术值、医生表单挤占首屏，以及新增图表标记影响原图表结构的兼容问题。

证据：[浏览器结果](../images/agent-v1/browser-results.json)、[真实模型调用](../images/agent-v1/live-model-check.json)、[数据库结果](../images/agent-v1/persistence-results.json)。

## Tests

Baseline: 596 passed / 0 failed

Final: 620 passed / 0 failed — [最终全量测试记录](final-tests.txt)；13 条既有弃用警告。

新增测试覆盖入口、上下文、基线对比、两个健管确认点、医生责任边界、原目标恢复、幂等、正式业务写入、完成条件、异常转人工、模型和知识不可用、可选服务、管理接手恢复，以及基线之外的当前病史、过敏、用药与手术记录。

## Git

Backup: `backup/pre-agent-v1`

Commit: `feat: add post-checkup care agent v1`

Push: NO

## Final

AGENT V1: READY

ENTRY: CLEAR

HUMAN GATES: CLEAR

EXIT: CLEAR

MANAGER EXPERIENCE: READY

DOCTOR EXPERIENCE: READY

TECHNICAL LEAKAGE: CLEAN

## Local verification commands

```powershell
$env:PYTHONIOENCODING='utf-8'
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/qa_agent_v1.py
.venv/Scripts/python.exe scripts/verify_agent_v1_demo.py
```

浏览器脚本需要处于待确认状态的独立合成案例。当前数据库已保留完整完成案例；复演应先使用已有合成库准备新的独立副本，再运行 `scripts/seed_agent_v1_demo.py`，不要覆盖业务数据库。普通产品操作仍从上传新报告开始。
