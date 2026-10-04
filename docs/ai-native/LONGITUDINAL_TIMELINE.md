# 纵向健康管理时间轴

入口：**会员 → 点击会员 → Member360 → 历程**。

本轮基线 HEAD：`bf1b0558425480b9209d9867b046f24c25134dfd`。备份分支：`backup/pre-longitudinal-timeline`。没有新增一级菜单或 Member360 Tab；保留现有 Soft / Restrained Neumorphism。

## 从数据到历程

```mermaid
flowchart LR
  R[Raw 原始资料] --> O[Observation 标准化及确认事实]
  O --> S[Daily Summary / Health State Snapshot]
  S --> C[Meaningful Change 重要变化]
  C --> E[Care Episode 管理过程关联]
  E --> A[已有随访 / 计划 / 医生 / 复查 / 阶段对象]
  A --> U[Outcome 后续观察结果]
  U --> T[Timeline 双轨投影]
  S --> T
  A --> T
```

**Timeline != Memory**：时间轴展示已经留存的状态、变化、行动和结果，不自动形成长期推断或个人响应模式。

**Timeline != Trace**：时间轴回答“会员发生了什么”；Trace 回答“系统如何执行”。普通页面不展示内部标识、工具调用、提示词或 JSON。管理员原有 Trace 能力保留。

## 数据职责与复用

| 对象 | 实现与来源 |
|---|---|
| HealthStateSnapshot | 只读类型化投影，复用 HealthAssessment 版本、DailyHealthSummary / DailySummaryRevision、有效 Observation、当前目标及阶段；没有复制原始测量的新表 |
| TimelineEntry | 统一时间、类型、两轨、状态、目标/阶段/管理过程关联、来源和详情定位；页面不直接查询各业务表 |
| CareEpisode | 轻量引用投影，不复制任务、意见或结果。优先沿已有 RiskEvent → Task → ManagementLog / DoctorReview → RecheckPlan 关系连接 |
| 显式补充关联 | `link_care_episode` 将经过责任人确认的类型化引用追加到现有 HealthEvent，类型为 CARE_EPISODE_LINK；保留版本和前版引用，无自动化事件类别，不唤醒会员 Agent |
| Outcome | 使用真实 OutcomeEvaluation；既有结果服务接受可选 `care_trigger_id`，记录结果时同时保存明确关联 |

关联服务核对同一会员、正式医生意见状态、责任角色与归档保护。重复相同引用不产生新版本。不按日期相近或同一年度计划推断干预因果。历史无明确关联时，保持独立结果或“结果待观察”。

快照支持年度基线、每日摘要、重要变化、阶段复盘、医生决定和当前状态。每日摘要通过 `daily_snapshot` 读取原有确定性结果，普通日常摘要不进入主节点。时间轴不触发每日计算，不扫描 Raw，不调用 LLM。

## 展示规则

- 默认最近 365 天的重要节点，按发生时间从左至右；上轨健康状态，下轨管理行动。虚线连接同一管理过程，点击节点后突出对应过程。
- 筛选只有全部、健康变化、管理行动、医疗、阶段。查看更早记录逐次扩展历史范围。
- 有效年度基线、重要变化、正式医生意见、阶段复盘、结果和当前状态可见；普通 Observation、原始设备记录、每日无变化摘要不会单独铺成主节点。
- 初始评估与年度基线分别命名，草稿医生意见不展示。风险流程关闭写成“风险事项已关闭”，不声称指标恢复。
- 当前状态通过逐指标索引查询获得最新有效值，注明记录日期；与同单位年度基线比较，目标进度复用确定性 `progress`；近7日睡眠来自每日摘要的有记录天数均值，缺测不补零。
- 当前状态保留实际开放风险。即使睡眠观察值有所改善，未经责任流程关闭的关注事项仍显示“需关注”。
- 详情包括当时状态、当前/前值/均值/年度基线、触发依据、关联目标、已留存的自动处理、人工及医生记录、后续结果、数据来源。
- 查看指标趋势切到原有“健康档案 → 健康数据”，不增加图表实现或新入口。
- 无足够数据时只显示等待资料逐步形成历程的空状态。

## 来源与历史真实性

变化节点读取产生变化时的日摘要版本，保留原事件比较值；不使用今天重算的数值冒充当时值。来源详情可查看原测量文字、确认值和保留的修正前记录。已有医生确认记录和正式用药记录才具有医疗来源归属；不从健管自由文字推断医生调整用药。

历史用药的未留存剂量变更、未版本化计划的旧内容、未记录的会员反馈，无法从今天的当前值可靠重建。投影不会补造这些历史。正式用药计划的开始/结束日期可形成节点；没有明确变更记录时不推断剂量调整。

结果结论只使用已经明确记录的改善、稳定、恶化、数据不足等状态。尚无结果则显示“结果待观察”。观察结果与行动的关联是管理过程关系，**不是干预疗效的因果证明**。

后续结果还受发生时间约束：9月1日的睡眠改善可关联8月的随访，但不能算作9月15日医生决定的后续结果。该医生节点仍显示“结果待观察”，先前改善保留在健康状态轨。

## 性能与权限

读取已有摘要、事实和业务对象，不重新聚合原始设备流。每类业务对象最多读取最近 500 条，并提示截断；主画布最多显示最近 60 个节点，可通过筛选减少密度。单指标最新值采用索引查询；原始来源仅在展开详情时按引用读取。

本次没有数据库迁移、没有正式 Demo 重建。关系补录属于原有业务服务权限边界；查看时间轴不写入业务数据。构建结果与详情均按会员验证，不能通过其他会员的引用读取来源。

## 隔离 QA 与复现

`scripts/seed_longitudinal_timeline_qa.py` 只允许在项目 `.runtime` 下创建**不存在**的数据库文件，拒绝正式路径和覆盖。数据是明确通过模型和业务服务写入的合成记录，没有 LLM 故事生成。

```powershell
.venv/Scripts/python.exe scripts/seed_longitudinal_timeline_qa.py --database .runtime/timeline-review.db
$env:DATABASE_URL='sqlite:///file:D:/executive_health_ai/.runtime/timeline-review.db?mode=ro&uri=true'
$env:LOCAL_LLM_ENABLED='false'
$env:PORTFOLIO_DEMO='true'
.venv/Scripts/python.exe -m streamlit run streamlit_app.py --server.port 8511 --server.address 127.0.0.1 --server.headless true
```

先确保 QA 端口空闲。打开后从会员列表选择“纵向历程验收会员”，点击“历程”。另有“历程空状态验收会员”。这个临时实例采用数据库只读连接，不启动 worker。

故事从 2025年10月基线开始，至 2026年10月当前状态；默认视图显示本年度关键记录，更早记录可展开上一年度基线。包括目标确认、计划确认、执行阶段、体重结果、睡眠 YELLOW、健管随访、计划调整、睡眠恢复的观察结果、医生意见、复查安排与阶段复盘。规则标记为隔离 QA 的 TEST 数据，不是临床标准。

截图位于 `docs/images/longitudinal-timeline/`，对应概览、重要变化、管理行动、医生决定、结果、当前状态和空状态。真实 Chromium 从会员列表逐级进入，未使用内部深链接，验证筛选、节点、返回与既有趋势导航。

## 回归验证

新增测试覆盖顺序、两轨、重要变化、普通原始记录不成主节点、年度基线、当前状态、目标/风险/随访/医生/阶段/结果关联、待观察、原始来源、只读查询、无需 LLM、日摘要版本、空状态、草稿医生保护、跨会员与角色校验、关系幂等与版本、历史范围、筛选和唯一入口。

旧 V4 数据服务测试保留；3 项 Member360 UI 测试更新为新规格的五类筛选、重跑状态保持及节点展开详情。

```powershell
.venv/Scripts/python.exe -m pytest tests/test_longitudinal_timeline.py tests/test_goal_data_loop.py tests/test_health_timeline_v4.py tests/test_health_timeline_v2.py tests/test_timeline_risk_indicator_separation.py tests/test_baseline_timeline_fix.py tests/test_longitudinal_health_operations.py tests/test_longitudinal_health_intelligence.py tests/test_observation_driven_risk.py tests/test_yellow_risk_operations.py tests/test_vnext_timeline_navigation.py -q
```

验收使用相关回归集合，不以历史全部测试结果冒充本轮执行结果。

最终相关回归：**151 passed / 0 failed**（1条既有测试客户端弃用提示）。Chromium：`151.0.7922.34`。

正式数据库 SHA-256 与工作前记录一致：

- `data/portfolio_demo.db`：`4c5c0d5e67bead4e0f5595f604998aa8000dbeb4a6adc6e09d521bc777c7fa78`
- `executive_health_ai.db`：`f17e079a5c750cb60bbe6341b2781713839dd610d330a177221ce2fac10c2c97`
