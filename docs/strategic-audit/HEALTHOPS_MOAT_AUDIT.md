# Executive HealthOps Strategic Moat Audit

审计日期：2026-10-04。范围：当前本地代码、迁移、测试及历史测试结果、实际数据库、真实 Chromium 只读页面。结论针对本机可验证状态，不代表真实客户队列、临床效果或生产安全认证。

## 1. Executive Summary

**如果竞争对手明天拿到相同模型、RAG、Agent 框架和设备 API，HealthOps 仍保有一套已经落地的健康管理业务语义、事实来源与人工责任链、以及持续会员工作状态。但目前尚不能证明它已经拥有难以复制的大规模个人健康历史和个体干预经验。**

整体成熟度 **2.6 / 5**：可用的积累基础，不是已经完成的长期数据护城河。最关键的区别是：存过数据不等于形成记忆；创建过任务不等于知道干预效果；通过合成测试不等于已经持续积累真实会员资产。

本次最重要的三项缺口：

1. **可治理、可被后续决策使用的 Care Memory。** 目前只是少量关键词提示及分散日志，不能可靠回答反复失败原因、曾经有效的调整。
2. **Decision → Intervention → Execution → Outcome 的稳定关联。** 有很多业务对象和部分引用，但没有贯穿一次管理尝试的统一身份与结果证据链。
3. **以目标、指标和时间为依据的统一个人上下文。** 各流程分别拼上下文，指标时间语义及目标版本治理不完整，Memory 工具未进入常规决策链。

### 1.1 审计基线与限制

| 项目 | 实际记录 |
|---|---|
| Current HEAD | `bf1b0558425480b9209d9867b046f24c25134dfd` |
| 开始时 Git 状态 | 仅未跟踪 `.agents/`；没有已有 tracked 文件改动 |
| 历史全量测试 | `.runtime/goal-regression-verified.log`：1083 passed，13 warnings，748.92s；2026-10-02 留存结果 |
| 历史补验 | `.runtime/goal-late-verification.log`：38 passed，6.88s |
| 本轮测试 | 阅读测试及调用链；没有重新执行 pytest，没有重新生成合成业务数据 |
| 正式 Demo | `data/portfolio_demo.db`；81 张表；`0032_goal_data_loop`；integrity_check=ok；foreign_key_check=0 |
| Demo 起始 SHA256 | `4c5c0d5e67bead4e0f5595f604998aa8000dbeb4a6adc6e09d521bc777c7fa78` |
| 默认数据库 | `executive_health_ai.db`；75 张表；`0031_member_wait_input`；integrity_check=ok；foreign_key_check=0 |
| 默认库起始 SHA256 | `f17e079a5c750cb60bbe6341b2781713839dd610d330a177221ce2fac10c2c97` |
| 实际浏览器 | Playwright Chromium `151.0.7922.34`，14 个页面/视图 |
| 浏览数据库 | SQLite backup 得到的隔离副本，以 `mode=ro&uri=true` 加载；8511 审计实例，未启动 worker |

**两个数据库不能混为一谈。** `scripts/start_portfolio_demo.ps1:16` 默认指定 Demo 库；`database.py:10` 的通用默认值指向根目录旧库。旧库有 14 位会员、5678 条 Observation、5511 条 Raw、21 个 AgentGoal、5 个 MemberAgent、1825 个报告候选；没有 management_goals / daily_health_summaries / communication_records / report_candidate_revisions 表，management_logs 和 stage_reviews 为零。没有修改或升级它。详细关系重建和页面审计以正式 Demo 为准，不能把 Demo 的零记录推广成所有部署均为零，也不能把旧库较大记录数当作真实长期客户积累。

本轮浏览禁用了外部 LLM，故页面中 AI“未配置”不能用来判断原平台的 LLM 在线状态。8501、8000 原有监听未被操作。浏览器内置连接列表为空后，采用本地 Playwright Chromium；未以 HTML 静态渲染冒充浏览器。

本机审计证据位于 `.runtime/strategic-audit/`：`initial.json`、`rows.json`、`coverage.json`、`member-story-evidence.json`、`tools.json`、`browser-results.json`、14 组截图/页面文字、`legacy-db-aggregate.json`。这些是本地审计证据，不是新增业务模块。

### 1.2 当前主要模块与审计方法

| 层 | 实际审计入口 | 判断重点 |
|---|---|---|
| 健康事实 | `models/patient.py`、`observation.py`、`raw_data.py`、`clinical.py`、`medication.py`、`longitudinal.py` | 时间、来源、确认、历史 |
| 长期管理 | `models/program.py`、`management_workflow.py`、`goal_data.py`；`services/chronic_care.py`、`management_action_loop.py` | 目标、阶段、行动、结果 |
| Agent | `models/agent.py`、`member_agent.py`；`agent/supervisor.py`、`planner.py`、`scheduler.py` | 持久身份、等待恢复、实际完成条件 |
| 工具与责任 | `agent/tools.py`；`services/tool_execution.py`、`care_tools.py`、`autonomy.py`、`responsibility.py` | 写入、幂等、人工边界 |
| 资料与设备 | `services/profile_ingestion.py`、`report_parsing.py`、`health_events.py`；`integrations/` | Raw 与候选、规范化、多条接入路径 |
| 日状态 | `services/daily_summary.py`、`goal_metrics.py`、`risk_triage.py` | 确定性、规则、重算、相关历史 |
| 知识和模型 | `models/knowledge.py`、`ai_governance.py`；`services/knowledge_retrieval.py`、`ai_feedback.py`；`llm/local_llm_client.py` | 可替换性、知识与事实分离 |
| UI | `streamlit_app.py`、`ui/pages/manager/`、`member/`、`doctor/`、`admin/` | 用户需要做什么、技术泄漏、空态 |
| 持久化与测试 | `alembic/versions/`、SQLite PRAGMA、`tests/` | 代码承诺是否真正进入 schema 和持久记录 |

未发现独立 repositories 层；多数服务使用 SQLAlchemy Session 及直接 ORM。审计实际搜索、读取了上述代码、迁移、测试和既有设计文档；没有以 README 或类名作为成熟证据。

## 2. What HealthOps Already Owns

可以称为“三个护城河基础”，不能称为已经不可复制的三个成品：

1. **一套连续健康管理的业务语言。** 会员、年度基线、报告候选、确认事实、阶段、复查、随访、服务、医生意见和归档边界已形成真实模型与调用关系。
2. **可追踪的人机协作责任链。** 风险等级、角色门槛、原文证据、人工决定、同一工作恢复和工具执行记录已经落地；这比单次聊天更接近真实交付。
3. **可承载长期积累的会员数据与执行底座。** 多时点 Observation、Raw 分离、修正版本、持续 MemberAgent、等待与幂等为长期使用提供基础。

### COMPOUNDING ASSETS

| 可复利资产 | 当前已有载体/数据 | 当前是否已形成实质资产 |
|---|---|---|
| Personal longitudinal data | Demo 1522 条 Observation，1434 条 Raw，30 条 SleepSession | 有合成纵向样本；不能证明真实会员长期规模 |
| Confirmed facts | 报告确认、年度基线、DoctorReview、ClinicalRecommendation | 有正式事实语义；历史 Observation 确认来源不齐 |
| Corrections | ReportCandidateRevision、Observation.supersedes_id、FeedbackRecord | 新写入链可保留错误；Demo 修订表为零，旧数据无补齐 |
| Goal history | HealthProgram.main_goal、ManagementGoal | 旧目标文字存在；正式 ManagementGoal 为零，单计划单目标且无完整目标修订链 |
| Human decisions | AgentApprovalRequest 4、AuditLog 91、管理/阶段确认逻辑 | 有责任证据，缺统一“采纳/修改/拒绝了哪条建议”关系 |
| Doctor decisions | ClinicalRecommendation 3 条 confirmed、DoctorReview 2 条 pending | 医生归属可记录；本次待办没有形成闭环返回样本 |
| Care memory | care_context trace + ManagementLog + ExecutionBarrier | Demo care_context=0；仅关键词提示，GAP |
| Intervention history | Task、CareTask、RecheckPlan、ServiceRequest、ManagementLog | 各对象可执行，有部分链接；尚非统一管理尝试历史 |
| Outcomes | OutcomeEvaluation 4、服务结果、任务处理结果 | 能记结果；不能可靠归到某次干预或比较个人响应 |
| Individual response patterns | 无统一对象和更新协议 | 尚未形成 |

上述资产真正的壁垒来自持续业务使用、可信来源、纠错、责任与效果关联。拥有这些表本身仍然可以复制。

## 3. What Is Still Commodity

### COMMODITIZABLE CAPABILITIES

| 能力 | 当前形态 | 战略定位 |
|---|---|---|
| LLM provider | Ollama / OpenAI-compatible 客户端 | 可采购、可替换；不是主要壁垒 |
| RAG engine / vector DB | 已审知识的关键词检索；无需现有向量库 | 检索实现可替换，审核知识与使用证据才值得积累 |
| Agent framework | 自有 Supervisor、Scheduler、Planner | 耐用运行工程有价值；框架名和 Agent 数量不是壁垒 |
| Wearable adapter | 网关、Apple Health 与模拟适配器 | 同指标接入可复用，接口数量不是个人健康经验 |
| OCR / 文档解析 | Report / Profile 解析与候选提取 | 原始 OCR 可商品化；人工纠错与证据链可成为资产 |
| UI framework | Streamlit、既有 Soft Neumorphism 组件 | 保持易用即可，无需为护城河再造界面 |
| 数据库、日志、队列 | SQLAlchemy、SQLite、持久队列与 Trace | 必要工程基础；缺少语义关联时不会自动变成 Memory |

## 4. Personal Health Data Model Audit

**结论：已经是初步纵向健康数据库，不只是“当前值数据库”；但尚不是完整、统一、可按历史时点重建的个人健康语义模型。**

### 4.1 覆盖范围

| 健康领域 | 当前模型/服务 | 时间与来源能力及缺口 |
|---|---|---|
| 基础身份、责任人 | Patient、ExternalIdentity、年度 HealthProgram | 有身份/时区/创建归档时间；个人属性不是完整时态版本链 |
| 健康档案、家族史 | IntakeAssessment.responses、HealthAssessment.baseline_json、FamilyRelation | 能表达家族疾病/亲属；大量 JSON/文本，缺逐事实有效期与统一修正标识 |
| 个人病史、手术/住院 | HealthProblem、Intake、HealthEvent | `profile_ingestion.py:489` 可把有日期证据的手术/住院写入事件；缺日期时不会补造 |
| 过敏 | Intake/基线快照中的过敏史 | 能保留来源候选；非独立纵向 Allergy 事实链 |
| 用药 | MedicationPlan、MedicationEvent | 开始/结束/处方人、服用事件；与管理干预效果未统一关联 |
| 生活方式与问卷 | Intake、结构化资料、Observation、ExecutionBarrier | 可表示行为与障碍；偏好、意愿、执行背景未形成长期语义 |
| 健康目标、计划、阶段 | ManagementGoal、HealthProgram、ManagementPlan、ProgramPhase | 人工确认与目标值；目标改版、多目标并行、计划版本关系不足 |
| 体检、检验 | Document、ReportExtractionRun/Candidate、Observation | 报告日期、页码/原文、确认写入；不是所有旧事实都具完整链 |
| 手机、设备 | Device、RawData、RawIngestionRecord、Observation、SleepSession | 支持统一数值接入，但 session 数据、累计值与区间值的语义仍有分叉 |
| 随访、复查 | Task、FollowUp、RecheckPlan、ManagementLog | 时间、结果、部分来源引用；Demo FollowUp 表为零不等于完全没有随访，部分由 Task 表示 |
| 医生意见 | Encounter、ClinicalRecommendation、DoctorReview、ConsultationCase | 明确医生归属与确认；旧医生流程不都绑定 AgentGoal |
| 服务结果 | ServiceRequest、ServiceEvent、ManagementLog | 结果/依据/完成时间、后续 Task；不能等同健康改善 |
| 风险事件、管理信号 | RiskEvent、ManagementSignal | 正式风险与生活方式信号分开；规则与证据可追踪 |
| 阶段结果 | StageReview、WeeklyReview、OutcomeEvaluation | 有内容与决定；Demo StageReview=0，量化结果没有干预 FK |
| 沟通记录 | CommunicationRecord + ManagementLog | 新原文层保留参与角色、来源、关联行动；旧日志不等于已保留每次原始对话 |

代码证据：`models/clinical.py:18/40`、`models/management_workflow.py:9/29/59/78/99/111`、`models/goal_data.py:10/91`、`services/post_checkup.py:67`、`services/profile_ingestion.py:430`。

### 4.2 时间：支持纵向，但不支持全域 as-of 重建

Observation 有 `observed_at` 与 `created_at`；Raw 有 `recorded_at` 与 `received_at`；Document/解析 Run 有上传/解析时间；事实有 `confirmed_at`；基线有年度周期、assessed/confirmed/version/superseded；沟通有 occurred/created。同一指标多时间点和趋势真实存在，索引为 `(patient_id, metric_code, observed_at)`。

缺口：并非所有对象同时保存发生、进入系统、确认、修改和失效时间；`CommunicationRecord` 只有 confirmed_by，没有 confirmed_at；ManagementGoal 没有目标修正关系；Intake.version 是表单 schema 版本，不等于每个答案历史版本。`chronic_care.adjust_management_plan:130` 直接覆盖 plan.content，AuditLog 没有保留旧计划全文。因此“今天查询去年当时已知状态”与“今天已修正后回看去年”尚未统一区分。

### 4.3 Raw → Normalized → Confirmed：新链真实存在，覆盖不完整

| 层 | 真实实现 | 审计结论 |
|---|---|---|
| Raw | 原文件引用、RawData payload/checksum/times；网关拒绝/未匹配也有 RawIngestionRecord | RawData ORM 更新/删除保护；文件外部保留策略、全库不可篡改约束未因此成立 |
| Normalized | canonical mapping、normalize_unit、quality_for；候选与 Observation 分开 | 显式换算和质量过滤可复用；不存在一套覆盖所有文本事实的统一 normalized version 协议 |
| Governed | Observation.confirmation_status、confirmed_by/at、evidence_ref、provenance_json | GOVERNED 表示规则治理，绝不能在审计里解释为“人工已确认” |
| Correction | 新 Observation 指向 supersedes_id，旧值 excluded；候选修订不可变 | 新写入可完整保留 83.6 → 误提取86.3 → 纠正83.6；不代表旧记录已补有完整历史 |

实际 Demo：1522 条 Observation 中，1404 条有 raw_record_id（约92.2%），118 条没有；source_type 非空为0，confirmed_by 非空为0，全部状态是迁移兼容默认 GOVERNED；version>1 为0。22 条已有报告候选对应 ReportCandidateRevision=0。数据仍有 source 文本和部分文档引用，不能说“全无来源”；但也不能说重要事实均具统一来源/确认链。

错误留存的正证据：`data_provenance.py:8/24/37/65`、`models/goal_data_hooks.py:50/61/68`、`tests/test_goal_data_loop.py:212` 明确断言旧 AI 候选86.3、Raw原文83.6、最终83.6同时存在。这是实际持久模型与测试，不只是文档设想。限制：初始候选修订通过 after_insert 建立，既有候选没有历史追补；ORM事件不防直接 SQL/bulk 绕过；RawIngestionRecord 处理状态仍会更新，不应把整张表称为绝对不可变。

### 4.4 多源与 Metric 基础语言

`health_events.py:17` 接受 MANUAL / REPORT / QUESTIONNAIRE / MOBILE / DEVICE / SYSTEM；`integrations/codes.py` 定义43个 canonical 数值指标及别名、默认单位、类别与合理范围。代码包括体重/BMI/腰围、血压、血糖/HbA1c、血脂、心率/静息心率、睡眠时长/分期时长、步数/运动/能量等。

Demo 实际出现12种：glucose1344、heart_rate60、steps30、active_calories30、exercise_minutes30、systolic_bp7、diastolic_bp7、weight5、bmi3、ldl_c3、hba1c2、alt1。不能拿43个注册名当43种真实数据覆盖。

Registry 缺显式 value_type、point/interval/cumulative 时间语义、聚合策略、来源优先级及审批发布版本。source_capability 在 Goal requirements 中按类别拼出，未统一回到 Metric 定义；QUESTIONNAIRE 等来源不是每项可用性判断的完整约束。质量枚举沿用 valid/questionable/invalid/missing_context/suspect/duplicate/manually_corrected，和风险等级分开，这是正确边界。

新设备提供既有标准数值时，通常只需 Adapter + 身份绑定 + 契约验证，不必改 Agent/UI/Risk。新设备带区间运动、重叠睡眠、类别症状等新语义时，当前核心仍需扩展。网关把除 healthkit 外的来源统一标 DEVICE；`integrations/service.py:112` 与 `health_event_measurements` 仍是不同规范化入口。**不存在“每种设备都必须重构核心”的全面重大失败，但语义不完备会迫使部分新类别改核心。**

### 4.5 Goal → Metric → Plan

`goal_metrics.py:11/37/52/79`：9种目标；CORE/SUPPORTING/OPTIONAL；14/90日新鲜度；逐指标查最新可靠值，避免大量 CGM 挤掉其他指标。腰围属于减重 SUPPORTING，不阻断计划。进度由 Decimal 计算，无数值目标不伪造百分比。

`management_goals.py:38/80/113/136/156`：从会员关注/既有方案整理目标；两个人工关卡恢复同一 MANAGEMENT_SETUP；要求基线后创建/复用阶段并通过工具建事项。不是独立第二套年度管理。

成熟度限制：类型判断是关键词/正则，计划主要复用阶段或三阶段模板，初始行动固定为核对基线；不是根据长期响应动态制定个性化方案。映射写死在代码，虽有 `goal-metrics-1` 和每目标快照，却无审核、生效、回滚、适用范围的语义治理。部分调用使用快照，Daily Summary 和管理页 readiness 又读当前映射，未来改版可能产生口径漂移。program_id 唯一限制一计划一目标，没有完整的目标变更历史。当前正式 Demo 目标表0，旧库尚无该表。

### 4.6 Daily Summary / Meaningful Change

这不是只存在于测试的函数：`agent/scheduler.py:21` 调 `run_daily_batch`；Observation hook 合并会员/本地日期 dirty 项；worker 批处理已结束日期。但当前 Demo 摘要、修订、待聚合项都是0；存量数据不会因为函数存在而自动成为摘要；归档会员也被排除。**生产调用链已接入，本机数据未证明持续运行成效。**

| 检查 | 实际实现与限制 |
|---|---|
| 来源 | 只读有效 Observation，不读海量 Raw、不调用 LLM；已有30条 SleepSession不自动转为sleep_duration Observation，当前睡眠摘要缺数据 |
| 聚合 | 累计类取MAX，体重/BMI/腰围取LATEST，其余MEAN；每值有样本数/方法/最后证据ID；缺来源累计/区间语义，多个独立睡眠段取MAX会漏计 |
| 缺失 | 无有效值不建空摘要；完整度用目标CORE分母，无目标不伪造百分比；不是总数据库字段完成率 |
| 唯一/版本 | member/date唯一，输入hash相同不增版本，重算保存DailySummaryRevision；删除来源可使当前摘要失效且保留旧版 |
| 7/30日 | ManagementRule 至少近期若干天，7日均值驱动；30日均值列入解释，但不是普遍30日变化判据 |
| 个人基线 | lookback读取年度基线；不等于已建立个人基线偏离检测器 |
| 变化定义 | 已审核ManagementRule阈值/百分比/趋势/连续规则；新命中RiskRule；已确认数值目标首次跨100% |
| 持续时间 | 连续规则使用最近N个有值摘要，未核对日期连续，缺天可能被误当连续 |
| 正式风险 | Summary只复用THRESHOLD/SYNTHETIC_TEST_THRESHOLD条件；实际匹配使用最后一条Observation，不一定是展示的日均值，需统一解释口径 |
| 幂等 | 同summary/rule/day只发一次事件；防重复成立，但规则改版不在摘要输入hash，旧日修正不自动重算其后窗口，事件旧payload也不会自动更新 |
| 当前规则资产 | Demo仅3条TEST/SYNTHETIC_DEMO_FLAG风险规则、1条合成活动管理规则；不能视为正式临床规则覆盖 |

证据：`daily_summary.py:30/112/187/246`、`goal_data_hooks.py:17/29`、`health_events.py:59`。RiskRule/ManagementRule 已有版本及人工审核，不能说全部是散落的 `if metric>x`。但条件支持、指标相关集合、聚合类别、时间窗口在多个服务硬编码，下一阶段需要在现有注册机制上统一版本化健康规则与时间语义，不另造一套风险引擎。

两种设备路径应分开评价：HealthEvent RAW 路径 STORE_ONLY，不唤醒Agent；网关 `_ingest_record` 每条持久Observation仍调用确定性 RiskEvaluationService 和 ManagementRoutingService。没有发现逐Raw调用LLM，但不能宣称所有设备入口都只在日批处理发生后才评估信号。大规模性能需要用真实适配器路径压测，不以50/100条RAW事件测试替代。

## 5. Memory Audit

**Database ≠ Memory。Care Memory = GAP。** 现有记录已足以作为记忆的证据原料，但没有系统化成为后续管理可用的长期上下文。

| Memory类别 | 实际实现 | 成熟判断 |
|---|---|---|
| Fact Memory | `care_memory.facts` 返回 current_profile；确认报告、Observation、年度基线 | 有事实投影，避免复制医疗事实；文本事实治理不统一 |
| Working Memory | AgentGoal.context_json、PlanStep、wait、next_action、Tool trace | 四类中最完整；为何开始、做到哪、等谁、下一步均可持久 |
| Care Memory | `remember_result` 从ManagementLog.result识别“夜班/出差/联系不上”，写care_context trace；longitudinal读最近30条 | 仅有来源和时间的提示；无跨干预归纳、有效/失败原因、合并、冲突与失效机制 |
| Preference / Interaction | MemberPlanChoice、ExecutionBarrier、日志/问卷中的偏好与拒绝 | 可记录个别意愿，不形成有范围和时效的偏好档案；Demo选择记录0 |

`care_memory.py:22` 每个Goal最多一条care_context；`care_results.py:126` 结果确认时调用；自然语言沟通 `communications.confirm` 和阶段复盘不统一更新它。`get_care_context` 已注册，但搜索正常Planner/运行代码未发现调用，主要为注册定义、管理工具展示及测试。不是“没有记忆类”，而是已有类没有进入完整学习闭环。

自然语言入口也要区分：`care_result_extraction.py` 是有证据约束的随访结构化路径；新增`communications.py`主要用关键词及“若干周”正则提取监测/复查节点，summary常直接保留原文。原文留存和医生归属是正资产，但不能把当前规则解析称作已经成熟的任意会议理解或长期语义记忆。

用户给出的“三个月两次睡眠干预失败，因夜班，减少夜间咖啡曾短暂改善”不能由当前Care Memory结构可靠表达与检索。ExecutionBarrier能保存出差及解决措施，WeeklyReview能写原因，这值得保留；但Agent不会自动把多条记录组合为带证据、时间范围、置信/确认状态的可用管理经验。

| 记忆治理问题 | 当前答案 |
|---|---|
| 何时形成 | 一个特定随访结果确认路径、三个关键词命中 |
| 谁更新 | 业务服务写Trace；没有专门记忆审核角色/授权协议 |
| 来源与时间 | 有ManagementLog id、occurred_at、recorded_at |
| confirmed vs inferred | 无统一字段，提示文本不是新的正式健康事实 |
| time range / confidence | 无统一范围/置信/证据充分度 |
| 合并、过期、重述、刷新 | 未实现治理协议 |
| 冲突、纠错、supersedes | 原事实可修正，但不能自动标记引用它的记忆失效或修订 |
| 当前数据 | Demo care_context=0，无法证明积累和再利用 |

职责当前“大体分开但边界局部混用”：Observation/HealthAssessment是事实与快照，DailySummary是派生状态，AgentGoal是工作状态，CareMemory却储存在执行Trace中。Trace保留策略和执行上下文不该决定长期照护记忆的有效期。不要把所有内容塞进一张万能Memory表；先明确事实、工作状态、照护经验三种治理协议。

## 6. Health Agent Audit

### 6.1 一个会员的持续身份：真实实现

`models/member_agent.py` 对member_id设唯一约束；`services/member_agents.py` 用会员锁、唯一约束与事务处理并发创建。ensure/synchronize/wake保留同一ID，状态由全部未完成Goal共同决定，不只看最新一次Goal。归档停止后保留历史，Demo两位会员有两个MemberAgent，归档会员Agent为IDLE，四个工作Goal为CANCELLED而非伪造COMPLETED。

`tests/test_health_event_runtime.py:52/62/69/91/177/213/272` 覆盖重启、数据库唯一性、独立进程确认同步、并发、未来到期、并行Goal、医生返回原Goal。持久身份不只是概念。但身份持续不等于每次决策都读取长期Care Memory。

### 6.2 实际决策上下文

| 路径 | 实际读什么 | 缺什么 |
|---|---|---|
| Post-checkup | 本报告候选、年度基线、相关历史指标、最多30个HealthProblem、20条手术/住院、用药、现有方案/风险 | 有长期事实，不只是当前prompt；未系统引入Care Memory、干预效果及ManagementGoal语义 |
| Daily meaningful change | 相关指标集合、7/30日摘要、年度基线、目标/阶段、最多5日志/5沟通、3医生意见、明确提及用药 | 范围受控但硬编码相关性；日志依赖关键词，不能稳定找到“夜班导致执行失败”而未写“睡眠”的记录 |
| DAILY_CARE | 当前阶段、开放事项、医生意见、事件payload | 历史效果与个人偏好不成为统一规划输入 |
| Stage review | 已完成任务、阶段日志、检查、服务、开放问题及证据 | 阶段快照可读，未回写治理后的长期经验 |
| 通用read工具 | 一些返回完整投影，一些仅返回count、exists或最后25条Observation | 名称get_member_summary并不意味着完整个人模型；高频数据可能挤掉低频指标 |

`services/post_checkup.py:67` 与 `agent/post_checkup.py:158` 有实际上下文及有界LLM摘要；没有发现把全部人生Raw塞给LLM的主链。问题不是“完全没有Context Selector”，而是只有各流程局部Selector，没有统一的 Member Context Assembly 合同：本次Goal、事实版本、相关历史、既往干预、记忆状态、未解决责任和引用证据未统一组合。

### 6.3 Planner：L1，而非L3

`agent/planner.py` 的POST_CHECKUP_TEMPLATE及CARE_TEMPLATES规定固定顺序；`validate`要求 `tuple(proposed) == expected`。不同Goal/条件选择模板，允许既定责任分支与版本化重启。因此是 **L1条件分支（底层L0流程骨架）**，工具运行受控但不是L2自主选择工具计划，更不是L3基于长期个人历史动态重规划。

这不是要求升级成自由Agent。下一步应先使有限计划真正读取可信长期证据，保持人工关卡，再按业务需要允许有限、可解释的重规划。

### 6.4 Tool Registry与执行边界

实际注册 **57个工具，56启用、1禁用**：31个启用read；25个write，其中14 MANAGER_REQUIRED、6 AUTO_GOVERNED、5 AUTO_SAFE；1个禁用read。所有声明idempotent=True，均经registry执行器留下trace。没有让模型直接执行SQL的工具，也没有自动开药/诊断的临床写工具。

`tool_execution.py:10` 用会员锁、事务、输入hash、goal/tool/幂等键及已有trace防重复；相同键不同内容报错。`agent/tools.py:87` 执行前查归属、活动会员、流程阶段与AutonomyPolicy。多数新业务工具调用既有Service；部分旧工具直接ORM修改Task/Goal/Plan或写AuditLog。因此“工具都只调用业务Service、完全没有直接DB写”不成立。

READ_ONLY是业务权限含义，不是SQLite只读：读取工具仍可能ensure_member_agent、写执行trace；retrieve_knowledge还可能补建已审核chunks。timeout_seconds是元数据，通用execute没有统一壁钟超时执行器；外部解析单独使用claim/fencing及脱离事务机制。不可把这些元数据直接等同所有运行保障已经完备。

所有工具下表的“幂等/Trace”均指实际共用执行路径；read工具的幂等声明不表示结果永久缓存。没有DOCTOR_REQUIRED写工具：医生判断由医生业务提交，不由模型工具代行。

| Tool | 权限 / 自主级别 | 读写 | 幂等 / Trace | handler是否调用Service、是否直接ORM | 代码位置 |
|---|---|---|---|---|---|
| `get_member_summary` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接ORM读取/上下文判断 | `src/executive_health_ai/agent/tools.py:161` |
| `get_report_status` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接ORM读取/上下文判断 | `src/executive_health_ai/agent/tools.py:164` |
| `get_latest_baseline` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接ORM读取/上下文判断 | `src/executive_health_ai/agent/tools.py:173` |
| `get_report_comparison` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接ORM计数（不是实际报告比较） | `src/executive_health_ai/agent/tools.py:183` |
| `get_recent_observations` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接ORM读取/上下文判断 | `src/executive_health_ai/agent/tools.py:187` |
| `get_active_risks` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接ORM读取/上下文判断 | `src/executive_health_ai/agent/tools.py:191` |
| `get_active_work_items` | READ_ONLY / AUTO_SAFE | read | Y / Y | 调用OperationalWorklistService | `src/executive_health_ai/agent/tools.py:195` |
| `get_pending_doctor_reviews` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接ORM读取/上下文判断 | `src/executive_health_ai/agent/tools.py:199` |
| `get_current_plan` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接ORM读取/上下文判断 | `src/executive_health_ai/agent/tools.py:202` |
| `get_open_tasks` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接ORM读取/上下文判断 | `src/executive_health_ai/agent/tools.py:206` |
| `get_service_status` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接ORM读取/上下文判断 | `src/executive_health_ai/agent/tools.py:209` |
| `get_latest_outcome` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接ORM读取/上下文判断 | `src/executive_health_ai/agent/tools.py:212` |
| `get_timeline_summary` | READ_ONLY / AUTO_SAFE | read | Y / Y | 调用投影/Timeline Service | `src/executive_health_ai/agent/tools.py:216` |
| `verify_post_checkup_success` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接ORM读取/上下文判断 | `src/executive_health_ai/agent/tools.py:220` |
| `evaluate_confirmed_observations` | AUTO_WRITE / AUTO_SAFE | write | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/services/agent_business_tools.py:28` |
| `create_followup_task` | AUTO_WRITE / AUTO_GOVERNED | write | Y / Y | 直接ORM写Task/Goal/Plan/Audit | `src/executive_health_ai/services/agent_business_tools.py:35` |
| `schedule_followup` | AUTO_WRITE / AUTO_GOVERNED | write | Y / Y | 直接ORM写Task/Goal/Plan/Audit | `src/executive_health_ai/services/agent_business_tools.py:43` |
| `create_member_reminder` | AUTO_WRITE / AUTO_GOVERNED | write | Y / Y | 直接ORM写Task/Goal/Plan/Audit | `src/executive_health_ai/services/agent_business_tools.py:35` |
| `record_goal_progress` | AUTO_WRITE / AUTO_SAFE | write | Y / Y | 直接ORM写Task/Goal/Plan/Audit | `src/executive_health_ai/services/agent_business_tools.py:85` |
| `assign_work_item` | MANAGER_CONFIRM / MANAGER_REQUIRED | write | Y / Y | ORM更新Goal + RiskOperationsService | `src/executive_health_ai/services/agent_business_tools.py:47` |
| `request_doctor_review` | AUTO_WRITE / AUTO_SAFE | write | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/services/agent_business_tools.py:56` |
| `update_plan_status` | MANAGER_CONFIRM / MANAGER_REQUIRED | write | Y / Y | 直接ORM写Task/Goal/Plan/Audit | `src/executive_health_ai/services/agent_business_tools.py:69` |
| `create_service_request` | MANAGER_CONFIRM / MANAGER_REQUIRED | write | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/services/agent_business_tools.py:75` |
| `record_management_note` | MANAGER_CONFIRM / MANAGER_REQUIRED | write | Y / Y | 直接ORM写Task/Goal/Plan/Audit | `src/executive_health_ai/services/agent_business_tools.py:85` |
| `get_member_context` | READ_ONLY / AUTO_SAFE | read | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/agent/post_checkup.py:44` |
| `get_report` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接读取Goal.context_json | `src/executive_health_ai/agent/post_checkup.py:45` |
| `get_baseline` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接读取Goal.context_json | `src/executive_health_ai/agent/post_checkup.py:46` |
| `get_health_history` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接读取Goal.context_json | `src/executive_health_ai/agent/post_checkup.py:47` |
| `get_current_management` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接读取Goal.context_json | `src/executive_health_ai/agent/post_checkup.py:48` |
| `retrieve_knowledge` | READ_ONLY / AUTO_SAFE | read | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/agent/post_checkup.py:49` |
| `complete_agent_goal` | READ_ONLY / AUTO_SAFE | read | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/agent/post_checkup.py:50` |
| `create_doctor_review` | MANAGER_CONFIRM / MANAGER_REQUIRED | write | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/agent/post_checkup.py:55` |
| `confirm_report_preparation` | MANAGER_CONFIRM / MANAGER_REQUIRED | write | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/agent/post_checkup.py:57` |
| `create_care_arrangements` | MANAGER_CONFIRM / MANAGER_REQUIRED | write | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/agent/post_checkup.py:59` |
| `parse_profile_document` | AUTO_WRITE / AUTO_SAFE | write | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/agent/profile_intake.py:68` |
| `match_profile_document` | AUTO_WRITE / AUTO_SAFE | write | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/agent/profile_intake.py:70` |
| `approve_profile_document` | MANAGER_CONFIRM / MANAGER_REQUIRED | write | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/agent/profile_intake.py:72` |
| `request_profile_review` | MANAGER_CONFIRM / MANAGER_REQUIRED | write | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/agent/profile_intake.py:74` |
| `get_member_profile` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接ORM读取Patient | `src/executive_health_ai/services/care_tools.py:26` |
| `get_health_record` | READ_ONLY / AUTO_SAFE | read | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/services/care_tools.py:32` |
| `get_observations` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接ORM读取/上下文判断 | `src/executive_health_ai/agent/tools.py:187` |
| `get_annual_baseline` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接ORM读取/上下文判断 | `src/executive_health_ai/agent/tools.py:173` |
| `get_current_phase` | READ_ONLY / AUTO_SAFE | read | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/services/care_tools.py:38` |
| `get_open_management_items` | READ_ONLY / AUTO_SAFE | read | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/services/care_tools.py:44` |
| `get_recent_management_logs` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接ORM读取ManagementLog | `src/executive_health_ai/services/care_tools.py:49` |
| `get_doctor_review` | READ_ONLY / AUTO_SAFE | read | Y / Y | 直接ORM读取DoctorReview | `src/executive_health_ai/services/care_tools.py:56` |
| `get_care_context` | READ_ONLY / AUTO_SAFE | read | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/services/care_tools.py:169` |
| `prepare_stage_review` | READ_ONLY / AUTO_SAFE | read | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/services/care_tools.py:114` |
| `create_management_item` | MANAGER_CONFIRM / MANAGER_REQUIRED | write | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/services/care_tools.py:63` |
| `create_followup` | AUTO_WRITE / AUTO_GOVERNED | write | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/services/care_tools.py:63` |
| `create_recheck` | MANAGER_CONFIRM / MANAGER_REQUIRED | write | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/services/care_tools.py:90` |
| `write_management_log` | AUTO_WRITE / AUTO_GOVERNED | write | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/services/care_tools.py:78` |
| `execute_approved_plan_check` | AUTO_WRITE / AUTO_GOVERNED | write | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/services/care_tools.py:140` |
| `apply_management_result` | MANAGER_CONFIRM / MANAGER_REQUIRED | write | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/services/care_tools.py:131` |
| `complete_management_item` | MANAGER_CONFIRM / MANAGER_REQUIRED | write | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/services/care_tools.py:102` |
| `start_next_phase` | MANAGER_CONFIRM / MANAGER_REQUIRED | write | Y / Y | 业务Service/投影适配器（内部可用ORM） | `src/executive_health_ai/services/care_tools.py:121` |
| `knowledge_search`（禁用） | READ_ONLY / AUTO_SAFE | read | Y / 不执行 | 禁用；无业务执行 | `src/executive_health_ai/services/care_tools.py:183` |

### 6.5 是否以真实业务结果结束

新管理路径较强：`care_runtime.py:90` 的finish检查ManagementGoal的计划确认/actions_verified、实际Task结束或明确NoAction、ManagementLog、StageReview及下一ACTIVE Phase。PostCheckup创建行动前有责任/日期/依据确认，保存实体引用，不是只返回“分析完成”。GREEN正常进度允许明确NoAction，正确。

弱处：旧`get_latest_outcome`只检查该会员是否存在任何OutcomeEvaluation；`verify_post_checkup_success`默认`context.get('outcome_recorded', True)`。Supervisor另有success_criteria检查，不能据此声称所有流程都虚假完成，但这个工具单独不能证明本次闭环。`record_goal_progress`只写AuditLog，AIInsight/摘要/知识回答本质为文字产物，不能计作行动效果；治理后的Communication原文与summary也不自动意味着健康结果。

## 7. Human Loop Audit

### 7.1 GREEN / YELLOW / RED

`services/autonomy.py` 将GREEN→OUT_OF_LOOP、YELLOW→ON_THE_LOOP、RED→IN_THE_LOOP与tool权限下限结合。缺风险覆盖不等于GREEN；红色不能由模型降级或自动关闭；医生工具/医学决定不会因GREEN自动获得许可。`risk_autonomy.py` 执行确定性风险、生成责任问题、绑定医生返回来源，符合方向。

`tests/test_autonomy_policy.py` 包括伪造risk receipt拒绝、老医生结果不能清除新RED、GREEN已批准计划检查、YELLOW正常结果、原工具批准后恢复；不是仅测试颜色文字。

### 7.2 搜索到的Human Gate类别

| Gate / 入口 | 人确认什么 | 评价 |
|---|---|---|
| Intake exception questions | 不确定事实、冲突、必须信息 | 符合exception-only；可选缺失不阻塞，未发现主路径恢复到52项全确认 |
| PROFILE_INTAKE REVIEW | 来源/档案更新；遇医学问题转DoctorReview | 医生回来后还等健管入档；部分步骤仍一律确认，需测重复劳动 |
| MANAGEMENT_SETUP目标 | 当前管理目标与指标 | 必须健管；小问题、同Goal恢复 |
| MANAGEMENT_SETUP计划 | 当前有限计划 | 必须健管，基线前置，不由AI设治疗目标 |
| Post-checkup manager review | 报告整理、变化、责任路径 | 即使无新正式风险也常需一次整体确认；不完全exception-only |
| Post-checkup action approval | 后续安排、日期、责任与依据 | 高责任动作合理；已批准可逆事项是否需要二次审核尚未按例外细分 |
| FOLLOWUP_RESULT | 对照原文确认结构化内容及后续安排 | 保留原文，但所有处理结果都走WAITING_MANAGER，未按不确定性/低风险免审 |
| Communication confirm | 沟通来源及拟创建监测/复查/日志 | 医生归属检查明确；没有统一置信例外门槛 |
| STAGE_REVIEW / start_next_phase | 阶段结果、下一阶段 | 关键阶段应人负责，已有门槛；旧推进路径另述 |
| DoctorReview | 明确医学问题、用药/诊断/检查/治疗/转诊 | 必须医生；AI只能准备材料 |
| RED / ESCALATE / takeover | 紧急、高责任、不安全继续 | 不能自动闭合，需要责任人实际处置 |
| Service审批/资源安排 | 权益、时间、提供方及服务结果 | 人工运营边界，不能与医学意见混同 |
| 管理员知识/规则/模型版本批准 | 内容生效、规则上线、模型发布 | 治理Gate，不是每日会员Human Work |
| 会员选择/信息填写 | 接受、调整、暂缓、讨论、初评信息 | 已有参与能力，但未统一为MEMBER Human Gate |

**剩余伪HITL倾向**：Post-checkup整理确认后再确认后续行动、自然语言结果逐次确认、医生结论回来后又由健管确认入档。它们不全是无意义审核；必须区分医学责任、事实异常和已经批准范围内重复抄写，不能一刀切删除关卡。当前没有统计每次事件的人力分钟数、重复确认率和无修改通过率，无法量化负担。

### 7.3 过度自动化与旁路

审阅主Agent链未发现自动开药、自动诊断或模型关闭RED的合法工具。`communications.record:13` 要求DOCTOR角色或关联已确认DoctorReview，健管输入“王医生说”本身不获得医生身份；医疗复查沿用既有医生依据。

但一致性尚未完成：`chronic_care.progress_program_phase:94` 可直接完成旧阶段/激活新阶段，无新StageReview门槛；`adjust_management_plan:130`修改自由文本，不调用统一责任策略；`MemberServiceOperations.record_choice`接受方案可把当前计划设ACTIVE，不等同新目标/计划两个Gate；`goal_loop.gate:11` 页面读取时可自动prepare并commit目标草稿。这些是**静态可见的旁路风险**，本轮没有执行它们，也未证实发生了临床越权。建议下一阶段按入口封闭边界和测试，不在本轮修复。

角色检查多使用调用者传入的role/actor，UI使用演示角色切换并明确写“不代表登录鉴权”。责任策略不等于端到端身份认证/签署授权；部署到真实多角色业务时必须另行验证认证和服务边界。

### 7.4 Router、医生与会员本人

ResponsibilityRouter.ROUTES为AUTO/MANAGER/DOCTOR/ESCALATE，**没有MEMBER**。旧Risk route还用SELF_MANAGEMENT/HEALTH_MANAGER/INTERNAL_DOCTOR/EXTERNAL_DOCTOR/EMERGENCY_MANUAL_ACTION；有转换，但不是全平台单一责任语言。

Post-checkup、Profile及新的Daily风险路径可绑定DoctorReview并恢复原Goal，测试覆盖。`chronic_care.complete_outcome_doctor_review:195`则直接确认意见并创建Task，没有统一HealthEvent原Goal恢复；Consultation/ClinicalRecommendation也不能仅凭“医生相关”就宣称都属于same Goal loop。结论为“核心Agent医生链成立，全域尚未统一”。

会员并非完全缺席：成员页能填写初评、上传资料、选择接受/调整/暂缓/讨论方案、申请服务；MemberPlanChoice和执行障碍能留原话/原因。但选择更新任务/方案时没有统一绑定等待会员的Goal/问题ID，也没有稳定的偏好/意愿记忆。WAITING_MEMBER状态存在不等于所有会员输入都会自动恢复原事项。本次成员主页还同时显示“完善健康档案/继续填写”和“目前无需你操作”，下一步表述存在矛盾。

### 7.5 真实浏览器与普通健管体验

| 实际只读页面 | 观察 |
|---|---|
| 今日工作 | 提示逾期初评及责任人；没有要求启动Agent |
| 会员 | 搜索/筛选/点击行进入Member360；当前在管仅Synthetic Workflow Member |
| Member360概览 | 当前资料收集状态、责任人及下一步；无足够健康趋势时不伪造数据 |
| 健康档案 | 初评/资料入口在现有页内，未增加独立Goal/Risk模块 |
| 管理 | 显示“尚未进入正式年度健康管理”“资料收集中”“继续处理初评”；无阶段0/0，无新增安排按钮 |
| 医疗 | 无当前医疗记录时显示说明，不伪造医学结论 |
| 历程 | 展示现有入组记录；活跃会员尚无长期管理链 |
| 年度管理 | 1位会员、1待基线、0持续管理；明确进度不是健康改善比例 |
| 服务管理 | 对当前无待办状态作说明；未执行申请/批准 |
| 专项管理 | 当前无专项记录；未虚构项目 |
| 医疗协同 | 当前无需要处理的问题 |
| 医生 | “待我判断0”“提交以后系统与健管继续执行”；归档会员不在当前队列 |
| 管理员 | 系统状态、集成表、运行/治理展开；标明演示预览 |
| 会员本人 | 有初评入口/上传/计划服务；下一步文案冲突如上 |

14个视图均实际加载，无Traceback/只读写入错误。不是对所有按钮或各业务状态的端到端验收：本轮不新增数据、不确认目标/计划，因此完成后正式管理态、医生实际提交只由代码/既有测试支持。

可见文本未出现Goal/Event/Tool/Trace/Planner/UUID/LLM Provider。代码命中`operations_board.py:125`的Goal/Event在technical expander且`if admin`保护，不应误报为健管泄漏；`intake_workspace.py:164`的JSON是上传文件格式提示，属轻度技术词，不是裸载荷。没有在本次普通页面看见“启动Agent/继续Agent/开始工作流”。管理员故障恢复控制不计为普通健管按钮驱动。

UI保持既有V7导航、左工作区/中央处理/右下一步及Soft Neumorphism。本轮没有视觉修改。主要产品问题转向“当前为何需要我”和会员本人下一步的一致性，不是缺新页面。

## 8. Outcome Loop Audit

### 8.1 五条真实业务链与断点

标记含义：AUTOMATED=存在自动业务调用；HUMAN_REQUIRED=责任上需要人；MANUAL_DUPLICATION=有重复核对倾向；DATA_GAP=证据不足；MEMORY_GAP=未形成可用长期经验；BROKEN_LINK=对象关系未闭合；NOT_IMPLEMENTED=未实现。不是把未执行过的真实客户流程标PASS。

| 链路 | 已实现段 | 人工与断点 | 本地持久证据 |
|---|---|---|---|
| 新会员→资料→Intake→Goal→Baseline→Plan→Phase | 上传与候选整理AUTOMATED；初评确认后prepare；目标/计划事件恢复并创建阶段/事项AUTOMATED | 事实例外、目标、基线、计划HUMAN_REQUIRED；成员输入统一恢复BROKEN_LINK；后续Care Memory GAP | 活跃合成会员仍Intake DRAFT；ManagementGoal0。完整推进由test_goal_data_loop的合成集成测试支持，未在正式库完成 |
| 体检→Data→Change/Risk→Agent→Doctor/Manager→Action→Result | Report候选/确认、基线比较、Risk、准备医生问题、创建任务/复查/服务均有代码链 | 报告/路径/动作多次确认MANUAL_DUPLICATION倾向；医学HUMAN_REQUIRED；行动完成至量化效果BROKEN_LINK；MEMORY_GAP | 4报告、22候选、2pending医生复核；4工作Goal均因归档取消，不可当完成闭环 |
| Raw Device→Normalization→Observation→Daily→Change→Risk→Autonomy→Action | RAW STORE_ONLY、dirty-day、日批处理、变化事件与Risk/AutonomyAUTOMATED | 旧SleepSession未进Observation DATA_GAP；来源时间语义/重算事件BROKEN_LINK；新临床规则资产DATA_GAP；必要时Human | 1434 Raw/1522 Observation；Daily0；规则为合成演示。不是持续运行结果证明 |
| Due→Agent准备→健管沟通→自然语言结果→记录→后续→Memory | Scheduler到期、同Goal结果处理、create followup/recheck、有限remember_result存在 | 沟通HUMAN_REQUIRED；结果再确认可能MANUAL_DUPLICATION；仅三个关键词提示，跨次经验MEMORY_GAP | 1ManagementLog、1RecheckPlan、0care_context；没有长期再利用证据 |
| Phase→数据/服务/反馈/医生→摘要→决定→Next Phase→Memory | ManagementActionLoop.stage_summary及review/enter_next_phase、STAGE_REVIEW Goal与Gate真实 | 关键阶段HUMAN_REQUIRED；旧推进路径旁路；下一阶段长期经验MEMORY_GAP | 7Phase、1WeeklyReview、4Outcome、0StageReview；测试覆盖推进与sameGoal，未覆盖经验改变下次计划 |

代码主入口：`management_goals.py`、`post_checkup.py`、`daily_summary.py`、`care_results.py`、`management_action_loop.py:115`、`daily_care.py`。底层关系不是完全断开，不能说所有动作都是四张无关联记录；不足在于关联没有覆盖一整次管理尝试及长期结果。

### 8.2 Intervention与Outcome

没有统一Intervention对象；已有Task/ManagementItem语义、FollowUp、RecheckPlan、ServiceRequest可构成执行载体，**无需为了命名再复制一套任务系统**。ManagementLog有related_task/risk/doctor/service/document和follow_up_task_id；ServiceRequest有program/phase及完成证据；CommunicationRecord有related_goal/actions。新Agent的trace还保存结果引用，均应保留。

OutcomeEvaluation包含program、metric、baseline/current/target、评价日期/人/依据和IMPROVED/STABLE/WORSENED/INSUFFICIENT_DATA/NEEDS_MEDICAL_REVIEW。任务有完成/部分/未完成，服务有取消，会员有拒绝/暂缓、ExecutionBarrier有原因。因此“不能记录结果”不成立；**没有统一结果分类、评价窗口与具体干预/决策/Observation证据FK**才是问题。

`InterventionOutcomeService.compare`（`longitudinal.py:1727`）根据人工传入干预时间前后窗口做均值比较；少于2样本提示不足，明确不作因果结论。它确实存在，但没有持久Intervention ID、自动绑定的Outcome和责任审批；UI中的一次前后对比不能证明是哪项措施导致变化。

`chronic_care.apply_outcome_decision:163`可由结果创建继续/调整Task或医生复核，说明反馈已能进入下一步运营。但部分audit只记next_entity类名，未完整保留所创建对象ID；不能稳定跨季度重建所有决策链。

### 8.3 反馈飞轮：2 / 5

已做到：Data → 候选/Agent建议 → 人工纠正/批准 → 部分Action → 业务完成记录/粗粒度Outcome。

未完整做到：Outcome → 有来源的Care Memory/个人响应模式 → 下一次Agent决策 → 受治理的策略改进。`FeedbackRecord`保存prediction/human_correction/model/prompt/evidence，数据集版本不可变，模型激活需人工审核；这是**AI内容质量改进**，不是健康干预效果学习。`ai_feedback.py:76`还明确不把风险反馈和医生结论直接作为训练标签，这是合理边界，应继续保留。

Demo有3条合成AI内容反馈、1个数据集版本、1模型版本，不能声称已有真实会员Outcome学习飞轮。

### 8.4 只用持久数据重建一个会员

对象：`Demo Executive A`，patient id=`23a9d63b3a39425fb9d95585057c53a2`，external_id=`portfolio-demo-executive-a`。这是**已归档合成会员**。记录表示2026年1月至9月的健康事件，但大多集中在10月1日创建；不是已经运行一整年的真实队列。以下不引入LLM补写，也不推断因果。

| 重建部分 | 数据库可证实的故事 | 来源/限制 |
|---|---|---|
| 初始状态 | 年度体检/基线存在；计划关注体重代谢、睡眠与运动 | HealthAssessment `450adae5…`，1月20日assessed/confirmed；HealthJourney `e942b7a2…` |
| 目标 | 90天“改善体重与代谢状态”，辅助改善睡眠/提高运动量；后有半年稳定管理 | HealthProgram `1aa901c3…`、`4b051a90…`；正式ManagementGoal没有记录：MISSING LINK（旧目标尚未接新语义） |
| 基线 | Journey记86kg、5.8h、运动1次/周、晨压146/94；年度报告基线另有90kg | 两种起点来源不同，没有明确统一权威关系；不能擅自选择86或90作为所有进度分母 |
| 关键变化 | 多时点体重/血压/血糖/血脂，以及30天活动与睡眠记录 | Observation发生日期1月15日—9月29日；DailySummary0，无法还原当时的每日变化判定 |
| 风险 | 1条YELLOW血压事件待医生；1条RED血糖事件已关闭 | `3d5261f9…`、`2aae032e…`；证据为synthetic demo flag，没有对应真实触发Observation；后者resolved早于集中seed创建时间，不能用其计算真实响应耗时 |
| 干预/调整 | 连续7天出差影响运动睡眠，记录已降低出差运动门槛、改每日20分钟步行 | ExecutionBarrier `033427fe…`关联Task；WeeklyReview `1d175f1f…`记2/4任务及降低频率；不能证明该调整已被执行或有效 |
| 医生意见 | 3条confirmed建议：规范记录血压、记录CGM及饮食/活动时间、记录睡眠及出差背景 | ClinicalRecommendation `92d7c8e0…`、`c4b15524…`、`acb648ff…`关联Encounter；另2个DoctorReview仍PENDING，不能把占位“待医生填写”当意见 |
| 会员反馈 | 9月30日电话记录会员同意继续安排复查 | ManagementLog `2316404e…`；是健管记载，不是可验证的会员本人提交；MemberPlanChoice0 |
| 阶段结果 | 8月7日记录体重86→81、睡眠5.8→6.6、运动1→3次/周、晨压146/94→134/86，四项标IMPROVED | OutcomeEvaluation `80f6b3c2…`、`4cd50ebc…`、`47ef3f5e…`、`41bbe309…`；均合成结果，program级关联，无干预/测量证据FK：MISSING LINK |
| 阶段决策 | 7条Phase中稳定期首阶段COMPLETED，其余PAUSED | StageReview0；不能补写“经何复盘完成”：MISSING LINK |
| 当前状态 | 会员归档、两个主要Program暂停；复查、服务、任务/AgentGoals取消；历史保留 | AgentGoal.next_action明确“因成员归档停止；未标记为完成”；MemberAgent ID `3c60731b…`仍保留，IDLE，wake_count5 |
| 长期管理经验 | 无法证明曾经两次睡眠干预失败、咖啡调整短暂有效，也无法恢复下一次如何吸取教训 | care_context0、Communication0；统一个人响应/照护经验：MISSING DATA MODEL |

实验结论：**能重建一个人的“档案与服务编年史”，不能完整重建“为什么这样管理、每次尝试怎样、所学经验如何改变下一次决策”。** 同一program/同一日期并不证明因果或同一行动链。

## 9. Knowledge/RAG Readiness

实际基础比“尚未建立知识库”更完整：Demo有27个KnowledgeDocument、85个Chunk、33个SourceRegistry、26个ReviewAudit，KnowledgeUseRecord=0。文件有source/version/review/effective_date/expires_at等字段，`KnowledgeService._eligible_for_formal_ai`检查批准、有效期及AI可用性；检索还能过滤audience/jurisdiction/intended_use/feature。

`knowledge_retrieval.py:62`提供稳定Hit/citation接口，关键词检索可替换BM25或向量检索；没有向量库不扣主要战略分。Agent已有启用`retrieve_knowledge`；另一个通用`knowledge_search`被禁用，不能把后者误读成全平台没有知识接入。

知识记录与会员事实分表；Profile提取合同要求原文evidence，模型摘要不直接成为Observation；KnowledgeDocument不作为患者事实存储。这些是良好边界。本轮没有发现“用医学常识填会员缺失事实”的授权主路径，但没有进行对抗式LLM测试，不能声明所有prompt永久安全。

下一步是把已有治理贯穿**每次建议所用版本/范围/有效日期/引用位置/批准者**以及人如何修改建议，不是先堆RAG功能。新检索引擎不应改变Member Fact、RiskRule或医生责任。还需解决knowledge_search与retrieve_knowledge两套工具合同、检索读时ensure_approved_chunks写入，以及知识使用回执在当前Demo为0的问题。

## 10. Replaceability Audit

| 替换对象 | 成本判断 | 已有边界 | 真实耦合/应保留资产 |
|---|---|---|---|
| LLM | 低到中；兼容协议换endpoint/model较低，新协议中等 | `llm/local_llm_client.py`集中Ollama/OpenAI-compatible调用；结构化schema、受限prompt | 解析器语义质量与schema需回归；不是只改配置即可证明效果等价。事实库与Risk不依赖供应商 |
| RAG | 低到中 | KnowledgeRetrievalHit/citation与治理筛选稳定 | 保留批准版本/范围/引用；检索评分实现可换，不需重做个人数据模型 |
| Agent framework | 中到高 | 业务工具/服务、确定性Risk可复用 | 自有AgentGoal/PlanStep/Trace、模板stage名、UI投影及worker协议耦合；应替换执行实现而非迁走会员身份和责任历史 |
| 新Wearable，同类指标 | 低到中 | IncomingRecord/adapter、canonical registry、单位、Raw/identity契约 | 来源映射、删除/重传/质量契约需验证；不必重写Agent |
| 新Wearable，新时间/值语义 | 中到高 | 已有SleepSession等局部结构 | 点值/区间/累计、跨设备去重、source priority不统一，可能需扩展核心语义 |

### 耦合实证

- Data Model的Observation不绑定模型供应商；ReportCandidate保存提取schema与解析方法，属于边界层。`Intake.responses`、`AgentGoal.context_json`包含模块自定义schema，版本演进仍需治理。
- RiskEvaluationService使用确定性已审核规则，不调用LLM；LLM可建议更严格人工路由，不可自行给正式风险等级或降级。
- `streamlit_app.py`直接导入具体服务、Goal/阶段、投影，并把app对象传给子页，UI并不完全与Agent实现解耦。
- Device RAW主链不直接唤醒Agent；网关仍有每Observation的Risk/ManagementRouting副作用。设备和Agent总体分离，规范化/状态聚合边界尚未完全统一。
- 最应保持稳定的是Member身份、事实/来源/修正、目标语义、责任协议、AutonomyPolicy和结果链。不存在必须先换框架才能补Care Memory的证据。

### 测试覆盖的是哪一层

| 测试组 | 真正证明什么 | 尚不能证明什么 |
|---|---|---|
| test_goal_data_loop | 持久模型、两次Gate、同Goal恢复、83.6/86.3错误留存、摘要版本、相关指标lookback、角色归属、空态 | 跨季度Care Memory、迁移前旧候选追溯、真实客户有效性 |
| test_health_event_runtime | 一会员一Agent、进程/并发恢复、raw不唤醒、重复事件防护、医生来源绑定 | 所有旧入口/实际设备网关都走相同闭环 |
| test_ai_native_completion | 工具幂等/跨会员保护、结果完成条件、阶段推进、一次夜班提示 | 多次干预失败综合、原因纠正后记忆更新、未来决策使用记忆 |
| test_autonomy_policy | 责任门槛、伪造风险回执、旧医生结果与新RED隔离 | 演示角色之外的完整身份认证和所有旧Service入口 |
| test_unified_data_gateway / Apple Health | 单位、Raw、身份匹配、去重、删除、部分成功与质量 | 大量区间数据/多设备重叠正确聚合、长期吞吐 |
| test_ai_feedback_governance | 人工纠错、去标识、审核数据集、版本发布/回滚 | 健康管理行动效果和个体响应学习 |
| Chromium本轮 | 14个现有只读视图、管理前置空态、技术词可见性 | 目标计划真实提交、当前正式库无样本的日Summary效果 |

例如稳定7天测试确实断言0 HealthEvent/Goal/Task，但没有配置覆盖所有规则的实际运行环境；变化测试配置合成睡眠阈值并验证不带LDL、只带相关用药。它们比“只测函数返回”更强，仍不是长期资产再利用测试。历史1083通过不得换算成“护城河已成熟”。

## 11. Maturity Score

评分衡量**现有系统形成长期资产的能力及已有证据**；不是临床疗效分或代码覆盖率。0不存在、1零散/Demo、2初步、3可用不完整、4系统化、5强长期积累。允许半分区分局部完成度。

| # | 维度 | 分数 /5 | 支持分数的证据 | 未到4/5的原因 |
|---|---|---:|---|---|
| 1 | Personal Health Data Model | 3.0 | 多时间Observation、基线/病史/医疗/阶段对象，实际1522观测；§4/§8.4 | 文本事实/时态/来源覆盖不统一 |
| 2 | Provenance & Versioning | 2.5 | Raw分层、candidate修订、supersedes及纠错测试；§4.3 | 历史候选修订0、source_type缺失、计划覆盖、非全域版本 |
| 3 | Metric / Goal Semantic Model | 2.0 | canonical指标、9种目标、要求快照、确认/进度；§4.4–4.5 | 代码映射、无语义发布治理、多目标/历史不足；Demo无新目标 |
| 4 | Longitudinal Memory | 1.5 | 工作状态持久，来源提示/执行障碍/日志；§5 | 无可治理Care Memory及常规使用；无长期经验重建 |
| 5 | Member-centered Health Agent | 3.0 | 唯一身份、等待/重启/医生恢复及测试；§6.1 | 个性化历史使用分散，部分旧路径不回同Goal |
| 6 | Tool / Planner Runtime | 3.0 | 57工具、trace/幂等/责任、实际业务结果验证；§6.3–6.5 | Planner L1，部分thin tools、直接ORM、超时元数据 |
| 7 | Human in/on/out Loop | 3.0 | Autonomy/Router、医生来源、RED保护；实际空态清楚；§7 | MEMBER未统一、重复审核、旧入口旁路、演示角色不是授权 |
| 8 | Daily State / Change Detection | 2.5 | scheduler真实调用、确定性/版本/去重/相关lookback；§4.6 | 本库0摘要、时间语义/迟到重算/规则覆盖不足 |
| 9 | Intervention → Outcome Loop | 2.0 | 任务/服务结果、4Outcome、前后比较/后续决定；§8 | 干预身份和结果证据不贯通，未来决策不学习 |
| 10 | Knowledge Integration Readiness | 3.0 | 已有审核来源、有效期、范围、引用合同；§9 | 使用回执0、工具合同分叉、未验证全流程引用治理 |
| 11 | Model / Device Replaceability | 3.5 | 模型4.0、设备3.0取均值；§10 | 设备新语义需扩展，UI/framework耦合 |
| | **Overall Moat Maturity** | **2.6** | 上述11项等权平均29/11，四舍五入 | 工程基础较强、长期经验资产仍弱 |

## 12. Top 3 Strategic Gaps

| 排名 | 唯一核心缺口 | 应积累的资产 | 验收应问什么 |
|---|---|---|---|
| 1 | 有治理的Care Memory | 有来源、时段、确认状态、失效/修正关系的照护经验 | 能否准确重建连续两次失败及原因，并在下次方案中使用/引用它？ |
| 2 | 决策—干预—执行—结果关联 | 人/医生选择与修改、会员实际执行及原因、后续测量/反馈 | 能否指出这次结果属于哪次尝试，而不把同时发生冒充因果？ |
| 3 | 目标驱动的统一纵向上下文 | 稳定Goal/Metric/时间语义、有效事实版本、相关历史/Memory选择 | 换模型、换设备后，Agent仍能根据同一套可靠证据作出一致责任分流吗？ |

详见 [GAP_MATRIX.md](GAP_MATRIX.md)。P0表示核心护城河缺口，不等于本轮发现线上急性事故。下一阶段具体六个月投入、依赖和“不做什么”见 [6_MONTH_ROADMAP.md](6_MONTH_ROADMAP.md)。

## 13. Conclusion

HealthOps目前最大的护城河是：**已经连接会员健康事实、持续工作状态与健管/医生责任的业务底座，具备积累可信长期服务历史的能力。**

HealthOps目前最大的战略缺口是：**还不能把“这个人过去做了什么、为什么成败”转化为有证据、可更新并影响下一次决策的长期照护记忆。**

已有工程不能被低估，也不能与已积累的客户资产混同。未来六个月应让少量真实闭环持续产生可重建、可纠错、可复用的个人经验；更强模型、更多设备或更多Agent不会自动补上这层。

本轮只新增三份审计文档；业务代码、UI及数据库未修改，未运行迁移/重建，未commit，未push。

结束复核：两份数据库SHA256均与§1.1起始值相同；HEAD仍为`bf1b0558425480b9209d9867b046f24c25134dfd`；tracked diff和staged diff均为空。仅停止本轮8511审计实例，原8501 PID31600、8000 PID4792仍监听；原有未跟踪`.agents/`未操作。新增文档尚未提交。
