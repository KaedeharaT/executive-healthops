# 简历项目描述｜Executive HealthOps

## 一句话版本

独立设计并开发面向企业高管健康管理场景的 AI 辅助 HealthOps 原型，将分散的体检报告与连续健康数据转化为有优先级、有人负责、可追溯且持续跟进的长期健康运营闭环。

## 3 条 Bullet 版本

- 构建体检报告解析与 Evidence Traceability 链路：将规则解析与本地开源大模型 语义辅助结果整理为可人工确认的健康资料，并回溯至来源页码、表格或原始片段。
- 设计“确定性规则 + Human-in-the-loop”主流程：Canonical Health Data 经规则生成 `RiskEvent`，进入统一运营工作台，并驱动健康管理师、Problem / Plan / Task、医生复核、服务跟进、Outcome 与长期健康时间线。
- 通过报告结构化、风险优先级、证据整理、任务追踪、医生复核上下文和成员历史汇总，减少健康管理师重复的信息整理与跨角色协调工作，目标是提升单个健康管理师可管理的成员规模并降低单位运营成本，不虚构 ROI。
- 基于 Streamlit、FastAPI、SQLAlchemy、Alembic 与可配置的本地 / 兼容 API LLM 接口实现可运行原型，并建立 **364 条自动化回归测试**保障核心流程（v0.9.0 作品集验收）。

## 5 条详细版本

- 设计 Canonical Health Data 分层，保留原始来源、标准化观测、派生总结和 AI 辅助内容之间的边界。
- 实现 PDF/DOCX/XLSX/CSV 等报告解析流程与候选人工确认，避免将 AI 输出当作原始临床测量或医生结论。
- 实现确定性 Risk Engine 与 TEST/CLINICAL 治理边界；作品集演示仅使用显式 TEST 规则，不夸大为临床风险模型。
- 实现成员健康中心与 HealthOps 运营后台，覆盖健康数据趋势、报告/基线、服务流程、医生协同和纵向时间轴。
- 建立 MedlinePlus、RxNorm、openFDA、WHO ICD-11 等来源的治理、审核与 APPROVED-only Chunk 检索；知识检索是受治理参考层，直接参与 LLM 推理仍为渐进能力。

## 1 分钟介绍

我把这个项目定位为企业高管健康管理的 HealthOps 原型，而不是诊断系统。体检报告和连续健康数据先进入 Evidence 与人工确认，再形成 Canonical Health Data；确定性规则生成 `RiskEvent`，统一 Worklist 告诉健康管理师先处理谁，并推动 Problem、Plan、Task、必要的医生复核、服务跟进与 Outcome，最后沉淀为长期健康时间线。报告结构化、证据查找、优先级、任务追踪和结构化医生上下文用于减少健康管理师的重复整理与协调工作。可配置 LLM 接口只做语义辅助与信息整理，不参与风险决策，医生保留医学判断权。

## 诚实边界

这是 Research / Portfolio Prototype；不宣称真实客户使用、临床验证、自动诊断、正式 Clinical Rule 治理或 Apple Health 真机验证。
