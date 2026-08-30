# Platform Overview

## 审计范围与当前证据

| 层 | CURRENT 证据 |
|---|---|
| 产品入口 | `streamlit_app.py` 的 `main()`、`_render_surface_switcher()`。 |
| API | `src/executive_health_ai/api.py` 的 FastAPI `create_app()`；当前注册成员、接入、报告、风险和工作流路由。 |
| 健康数据 | `Observation`、`RawData`、`RawIngestionRecord`、`IngestionJob`、`SleepSession`。 |
| 报告 | `ReportParsingService`、`ReportExtractionRun`、`ReportExtractionCandidate`、`Document`。 |
| 风险 | `RiskEvaluationService`、`RiskRule`、`RiskEvent`、`RiskOperationsService`。 |
| 长期运营 | `HealthAssessmentService`、`HealthTimelineService`、`TimelineV4Service`、`HealthProgram` 等。 |

本地 SQLite 审计快照（不包含个人内容）：1 名成员、5,673 条 Observation、6 份 Document、21 次 ReportExtractionRun、2 个 HealthAssessment、3 条 RiskRule、2 个 RiskEvent、1 条 ManagementSignal、1 个 DoctorReview、0 个 ServiceRequest。RiskRule：TEST=3、CLINICAL=0、APPROVED=3。

## 总架构

```mermaid
flowchart TB
  subgraph surfaces[产品 Surface]
    member[成员健康中心\n首页 / 健康 / 计划 / 服务 / 我的\n✅ CURRENT]
    ops[HealthOps 运营后台\n今日 / 成员 / 医疗协同 / 服务运营 / 更多\n✅ CURRENT]
  end

  subgraph services[HealthOps 领域服务]
    ingest[接入与标准化\n✅]
    report[报告解析与人工确认\n✅]
    risk[确定性风险引擎\n✅ Engine；🧪 规则内容]
    longitudinal[基线、趋势、时间轴、结果\n✅]
    workflow[健管/医生工作流\n✅]
    serviceops[服务权益与申请\n🧪 Demo catalog]
  end

  subgraph canonical[Canonical Health Data]
    raw[RawData / RawIngestionRecord\n原始载荷与溯源]
    obs[Observation / SleepSession\n标准化健康数据]
    records[Document / Candidate / HealthAssessment\n已确认资料与健康档案]
    operations[RiskEvent / Task / DoctorReview / ServiceRequest\n人工运营事实]
  end

  subgraph sources[当前数据来源]
    apple[Apple Health bridge\n🟡 接口与适配器；真机未验证]
    mocks[Mock Yuwell / Oura / CGM\n🧪]
    files[PDF / DOCX / XLSX / CSV 上传\n✅]
    manual[人工 Observation、健管/医生记录\n✅]
  end

  subgraph localai[本地可选 AI]
    qwen[Ollama + Qwen2.5:7b\n仅本机环回地址\n🟡 可选且可能未启用]
  end

  member --> services
  ops --> services
  apple --> ingest
  mocks --> ingest
  files --> ingest
  files --> report
  manual --> ingest
  ingest --> raw --> obs
  report --> records
  qwen -.语义回退，仅报告文本.-> report
  obs --> risk --> operations
  obs --> longitudinal
  records --> longitudinal
  operations --> longitudinal
  workflow --> operations
  serviceops --> operations
```

## AI 与医疗安全边界

```mermaid
flowchart LR
  reportText[报告文本 / 表格] --> parser[规则解析\n✅]
  parser --> decision{复杂片段且本地 AI 已启用？}
  decision -- 是 --> qwen[Local Qwen semantic fallback\n🟡]
  decision -- 否或不可用 --> candidates[候选资料\n✅]
  qwen --> candidates
  candidates --> human[人工确认 / 修正 / 拒绝\n✅]
  human --> canonical[Observation、Finding、Follow-up\n仅确认内容进入]
  canonical --> deterministic[确定性 Risk Engine\n不调用 AI]
  deterministic --> humanOps[健管 / 医生人工处理]

  forbidden[AI 不负责：\nGREEN/YELLOW/RED 决定\n诊断、处方、改药、自动医疗处置]
  qwen -.禁止.-> forbidden
```

`LocalQwenClient` 会清理常见直接标识并限制为本机环回 Ollama；这不是完整脱敏、访问控制或合规边界。
