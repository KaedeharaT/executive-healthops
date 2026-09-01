# Current Architecture Gaps & Debt

## Current vs Target

| Area | Current（代码审计） | Target（生产健康运营） | Gap |
|---|---|---|---|
| Authentication / RBAC | 无通用登录；成员中心是 development preview；FastAPI 大多数路由无 auth。 | 成员、健管、医生、管理员的最小权限与会话治理。 | **P0** |
| 临床规则内容 | Risk Engine 存在；SQLite：TEST=3、CLINICAL=0。 | 临床审核、版本化、有效期与发布流程后的 CLINICAL 规则。 | **P0** |
| PHI 安全 | 本地 SQLite/文件；无明确 TLS、at-rest encryption、访问控制。 | 受管密钥、加密、TLS、审计与数据生命周期。 | **P0** |
| 数据库 | SQLite 默认，本地单用户演示形态。 | 多用户 PostgreSQL、备份恢复、并发与运维监控。 | **P1** |
| Apple Health | sync API、adapter、token 检查与 iOS HealthKit 授权/增量/删除源码存在；未真机验证。 | 已签名、真实授权、同步/删除回放与真机验收。 | **P1** |
| 报告解析 | 规则解析、可选的可配置 LLM 语义辅助、候选/证据/人工确认均存在。 | OCR、模板覆盖率、质量监控和生产文件治理。 | **P1** |
| 外部医疗 | ExternalReferral 模型与人工登记/状态/反馈 UI。 | 医院、预约、检查、反馈的受控集成与 SLA。 | **P1** |
| 服务运营 | ServiceRequest 状态与配额消费存在；目录由 demo plan 生成。 | 真实合同、权益、排班、履约、支付/结算集成。 | **P1** |
| 低风险成员提醒 | 风险可生成 GREEN；未发现独立成员消息/提醒投递。 | 有同意记录的提醒渠道和可审计投递。 | **P2** |
| 知识库 | 来源注册、人工审核、版本关系、分块、APPROVED-only 检索、Grounded Answer Contract 与实际使用 Chunk 审计已实现；报告语义抽取继续使用原报告 Fact Evidence，不把知识检索伪装成抽取依据。 | 正式临床知识治理、组织级权限与生产运营。 | **P2** |

## Architecture Debt（当前 3 项）

1. **时间轴兼容窗口**：current `/members/{id}/timeline/v2` 已使用 `HealthTimelineService`；旧 `/members/{id}/timeline` 已标记 deprecated，但 `services/timeline.py` 仍为历史兼容与旧演示 helper 保留。两者事件粒度与语义不同，新功能不得依赖旧实现。
2. **报告入口路径并存**：运营端和成员端都有上传/报告入口，另有 `_render_client_report_intake_entry()` helper；应在后续明确单一共享 intake 的调用边界，避免状态分叉。
3. **旧 V0.1 workflow 兼容表仍存在**：`Alert`/`workflow.py` 与相关 API 已明确 deprecated，仅用于历史读取和兼容测试；新风险由 Observation-driven `RiskEvent`/`RiskOperationsService` 创建并进入统一 Worklist。后续生产迁移完成前不删除历史表或 migration。

已收敛的历史项：月度时间轴摘要已明确命名为
`MonthlyTimelineSummaryService`，避免与即时健康数据的
`HealthDataSummaryService` 同名；成员详情将“历程”作为一级入口，
不再依赖健康档案页的旧入口卡。`CarePlan` / `CareTask` 仅保留 V0.1
fixture 与 migration 兼容；当前工作流使用 `HealthProgram` / `Task`，
新功能不得继续依赖 legacy care 表。

## 不应误画为 CURRENT 的能力

- ❌ 临床风险规则库和临床阈值内容。
- ❌ 生产成员、健管、医生认证与 RBAC。
- ❌ 真实 Apple Health 真机连接。
- ❌ 真实外部医疗系统、预约或急救消息集成。
- ❌ 生产服务合同/权益/支付体系。
- ❌ 云部署、PostgreSQL、托管文件存储、TLS 与静态加密。

## 建议的下一步顺序（非本轮实施）

1. **P0**：先完成身份/RBAC、PHI 边界、CLINICAL 规则治理与部署安全设计，之后才讨论真实用户接入。
2. **P1**：收敛时间轴/工作流的重复路径；完成 Apple Health 真机与报告 OCR/质量验收；明确服务/外部医疗的人工与集成边界。
3. **P2**：在安全与工作流基础稳定后，增加成员提醒投递、正式组织级知识治理和更多产品扩展。
