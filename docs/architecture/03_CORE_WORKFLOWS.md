# Core HealthOps Workflows

## 1. 核心健康运营闭环

```mermaid
flowchart TB
  source[设备 / 报告 / 手工记录] --> ingest[数据接入与标准化\n✅]
  ingest --> raw[RawData / RawIngestionRecord\n保留原始载荷与来源\n✅]
  raw --> observation[Observation / SleepSession\n✅]
  observation --> quality{质量可用且未排除？}
  quality -- 否 --> retained[保留原始记录；不参加风险计算\n✅]
  quality -- 是 --> lifestyle[ManagementRoutingService\n生活方式信号\n🟡]
  quality -- 是 --> risk[RiskEvaluationService\n确定性规则\n✅]
  lifestyle --> reminder[提醒 / 健管信号\n🟡 无外部消息连接器]
  risk --> event[RiskEvent\n✅]
  event --> route{正式风险等级}
  route -- LOW --> low[当前仅引擎记录/展示\n🟡 未见独立成员提醒工作流]
  route -- YELLOW --> manager[健康管理师处理\n确认、联系、观察、调整或升级医生\n✅]
  route -- RED --> urgent[紧急人工处置记录\n✅；不自动联系急救]
  manager --> plan[HealthProgram / Task / FollowUp\n✅]
  manager --> doctor[DoctorReview\n需要医学判断时\n✅]
  doctor --> referral[ExternalReferral\n🟡 人工协调]
  plan --> outcome[OutcomeEvaluation\n✅]
  observation --> story[HealthTimelineService / TimelineV4Service\n动态投影\n✅]
  event --> story
  plan --> story
  doctor --> story
  referral --> story
  outcome --> story
```

`ManagementSignal` 与 `RiskEvent` 是两条不同的路径：前者由 `ManagementRule` 路由生活方式管理，后者由 `RiskRule` 生成正式风险事件。二者都保留证据与 AuditLog，但都不是诊断。

## 2. Report Flow

```mermaid
flowchart TB
  upload[成员/运营端上传 PDF、DOCX、XLSX、CSV\n✅] --> doc[Document + 本地文件引用\n✅]
  doc --> run[ReportExtractionRun\n✅]
  run --> preflight[预检、文本/表格规则解析\n✅]
  preflight --> complex{复杂文本且已配置 LLM Provider 可用？}
  complex -- 是 --> local_llm[configured LLM semantic fallback\n🟡 可选]
  complex -- 否/不可用 --> candidate[ReportExtractionCandidate\n✅]
  local_llm --> candidate
  candidate --> evidence[Evidence\n文件、页码/Sheet、原文或表格文本\n🟡 图片区域取决于来源]
  evidence --> human{健康管理师人工确认？}
  human -- 修正/拒绝 --> candidate
  human -- 确认 Observation --> observation[Observation\n✅]
  human -- 对 Finding 选择管理或医生复核 --> finding[HealthProblem / 医生复核路径\n✅]
  human -- 从 Follow-up 创建任务 --> followuptask[Task\n✅]
  observation --> risk[RiskEvaluationService\n✅]
  candidate --> baseline{是否生成基线草稿？}
  baseline --> draft[HealthAssessment DRAFT\n✅]
  draft --> confirm[健康管理师确认 Baseline\n✅]
  candidate --> compare[ReportComparisonService\n仅比较已确认候选\n✅]
  run --> timeline[每个 Document 只取最新 Run 的报告节点\n✅]
```

### Report evidence 的真实范围

```mermaid
flowchart LR
  result[Finding / Metric] --> action[查看依据]
  action --> document[Document / 原始文件]
  action --> location[Page / Sheet / section]
  action --> text[Evidence text / table row]
  action -.某些来源才有.-> image[图片区域\n🟡 PARTIAL]
```

`ReportExtractionCandidate` 存储 `source_page`、`source_section` 和 `evidence_text`；当前模型没有独立的 bounding-box 列。UI 可显示 `image_region`，但它不是所有报告都能提供的已保证能力。

## 3. Risk Flow

```mermaid
flowchart TB
  obs[Observation] --> usable{valid/manually_corrected\n且未 deleted/excluded？}
  usable -- 否 --> skipped[写入 AuditLog，跳过\n✅]
  usable -- 是 --> rules[RiskRule 查询\nAPPROVED + ACTIVE + metric]
  rules --> scope{scope 与成员匹配？}
  scope -- 否 --> noevent[不评估\n✅]
  scope -- 是 --> window[单位标准化 + 设备类别 + 窗口\nminimum samples / required matches]
  window --> matched{匹配阈值？}
  matched -- 否 --> noevent
  matched -- 是 --> dedup[活动事件去重 + cooldown\n✅]
  dedup --> event[RiskEvent + evidence_json + AuditLog\n✅]
  event --> low[GREEN\n🟡 仅记录/展示]
  event --> yellow[YELLOW\n健管人工操作\n✅]
  event --> red[RED\n紧急人工处置记录\n✅]
  yellow --> review[必要时 DoctorReview\n✅]
```

### 规则现实快照

| 规则类别 | 当前 SQLite 审计数量 | 状态 |
|---|---:|---|
| TEST | 3 | 🧪 APPROVED，但只允许 demo/synthetic/test 成员命中。 |
| CLINICAL | 0 | ❌ 没有经临床治理的可用规则内容。 |
| Risk Engine | 1 个 `RiskEvaluationService` | ✅ 已实现确定性执行器。 |

**TEST rules ≠ CLINICAL rules。** 当前引擎有明确 scope check，不能把这 3 条 TEST 规则描述为生产临床规则。

## 4. Longitudinal Health Timeline

```mermaid
flowchart LR
  continuous[连续 Observation\nCGM、血压、睡眠、活动、体重、心率] --> trend[选定指标趋势\nTimelineV4Service\n✅]
  continuous --> summary[每月 Health Data Summary\n✅]
  discrete[确认基线、报告、RiskEvent、HealthProgram、MedicationPlan、HealthEvent、DoctorReview、ExternalReferral、Outcome、major ServiceRequest] --> aggregate[HealthTimelineService\nDynamic Aggregation\n✅]
  summary --> aggregate
  aggregate --> rows[按日期聚合的生命轴 Row\nLEFT 管理/用药/服务\nCENTER 日期\nRIGHT 风险/医疗/医生\n✅]
  rows --> inspector[单一 Event Inspector\n业务详情 + 查看依据\n✅]
```

时间轴没有 `TimelineEvent` 数据表。`TimelineEvent` 是服务层 dataclass；`HealthTimelineService.get_timeline()` 每次从相关事实表投影，`TimelineV4Service` 再做时间窗口和语义聚合。旧 `services/timeline.py` 仍向 FastAPI `/members/{member_id}/timeline` 提供较早的逐条记录时间线，详见架构债务。

## 5. Service Operations

```mermaid
flowchart TB
  catalog[ServiceCatalogItem\n🧪 Demo catalog] --> plan[ServicePlan / ServicePlanItem\n🧪 金卡演示计划]
  plan --> entitlement[MemberEntitlement\n✅ 配额字段与消费逻辑]
  member[成员] --> request[ServiceRequest\n✅]
  request --> review[健康管理师审核\n✅]
  review --> schedule[安排 scheduled_at\n✅]
  schedule --> complete[完成 + result_summary\n✅]
  complete --> consume[增加 used_quota\n✅]
  complete --> timeline[仅 is_major_timeline_service 进入时间轴\n✅]
```

当前本地数据库 ServiceRequest=0；模型和操作服务存在，但目录通过 `ensure_demo_plan()` 创建，真实合同、支付、排班和第三方履约集成均未发现。

## 6. Doctor Collaboration

```mermaid
flowchart TB
  manager[健康管理师] --> doctorReview[DoctorReview\n问题、brief、人工 opinion\n✅]
  doctorReview --> internal[内部医生工作台\n✅]
  internal --> followup[Task / FollowUp / ManagementPlan\n✅]
  internal --> external[ExternalReferral\n专科、原因、问题、机构、预约、反馈\n🟡]
  external --> timeline[外部医疗协同节点\n✅ 动态投影]
```

`RiskOperationsService` 明确实现 Yellow 风险的医生升级与完成复核。RED 事件的代码记录人工紧急处置，但没有自动急救/转诊/通知连接器。
