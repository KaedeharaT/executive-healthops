# Phase 1A 当前能力审计

开始基线：`2e28cb7`（2026-09-29），备份 `backup/pre-ai-native-phase1a`。

| 能力 | 当前实现 | 本轮处理 |
|---|---|---|
| 持久化执行 | AgentGoal / AgentPlan / AgentPlanStep / AgentRunTrace；HealthOpsAgentSupervisor | 继续复用 |
| 唤醒 worker | AgentSchedulerService、run_agent_worker.py | 扩展现有调度周期，不建立第二个 worker |
| 健康事件 | health_events 已承载手术、住院和生活事件 | 在原表增加统一事件信封；历史字段及历史数据保留 |
| 流程事件 | AgentEvent / EventService | 保留兼容投递与运行审计，Phase 1A 入口统一经 HealthEvent Router |
| 资料整理 | ProfileIngestionService、profile_intake、profile_execution | 复用解析、来源核对、预填和人工关卡 |
| 体检后管理 | post_checkup、PostCheckupCareService | 复用固定流程，不增加 Planner |
| 医生判断 | DoctorReview 及既有提交命令 | 医生结果恢复原 Goal，来源和会员归属必须核对 |
| Task / Today | 原 Task 状态机、ProductProjectionService | 保留；自动执行不成为新增人工待办 |
| 风险 | 现有确定性 Risk Engine | 不修改风险等级或交给 LLM |
| 数据 | RawData、Observation、单位规范与质量校验 | 设备原始数据只入数据层；规则变化才唤醒 |
| 视觉 | V7 + AgentProgressPanel | 只增加中文触发原因与来源 |

主要缺口：缺少每会员唯一长期主体；来源类型与业务对象类型混用；原始观测和有意义变化没有统一路由边界；体检后摘要及医生意见整理存在写事务内可选 AI 调用。新增事件信封与会员主体补齐前两项，确定性 Router 隔离原始数据，事务外执行阶段复用现有 worker 解决耗时调用问题。

Phase 1A 只接健康资料、体检报告、医生完成、到期基础能力与合成设备规则验证。其它旧事件/API 保持兼容，不宣称已迁移全平台。既有医学历史事件不自动回放，原始设备事件不铺到普通会员历程。
