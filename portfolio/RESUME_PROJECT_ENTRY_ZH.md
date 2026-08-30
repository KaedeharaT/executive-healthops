# 简历项目描述｜Executive HealthOps

## 一句话版本

独立设计并开发面向企业高管健康管理场景的 AI 辅助 HealthOps 原型，整合体检报告结构化、证据追溯、确定性风险分流、健管/医生协同、长期健康历程与知识治理。

## 3 条 Bullet 版本

- 构建体检报告解析与 Evidence Traceability 链路：将规则解析与本地 Qwen 语义辅助结果整理为可人工确认的健康资料，并回溯至来源页码、表格或原始片段。
- 设计“确定性规则 + Human-in-the-loop”健康运营闭环：风险执行与 LLM 分离，支持健康管理师工作台、内部医生复核、计划任务和长期健康历程。
- 基于 Streamlit、FastAPI、SQLAlchemy、Alembic 与本地 Ollama/Qwen 实现可运行原型，并建立 **315 条自动化回归测试**保障核心流程（v0.9 作品集验收）。

## 5 条详细版本

- 设计 Canonical Health Data 分层，保留原始来源、标准化观测、派生总结和 AI 辅助内容之间的边界。
- 实现 PDF/DOCX/XLSX/CSV 等报告解析流程与候选人工确认，避免将 AI 输出当作原始临床测量或医生结论。
- 实现确定性 Risk Engine 与 TEST/CLINICAL 治理边界；作品集演示仅使用显式 TEST 规则，不夸大为临床风险模型。
- 实现成员健康中心与 HealthOps 运营后台，覆盖健康数据趋势、报告/基线、服务流程、医生协同和纵向时间轴。
- 建立 4 个医学知识来源的来源治理、审核、Chunk 检索和 AI 使用审计；只有 APPROVED 资料可作为正式引用来源。

## 面试 1 分钟介绍

我把这个项目定位为企业高管健康管理的 HealthOps 原型，而不是诊断系统。核心难点是让体检报告、设备数据、人工管理和医生判断保持可追溯且职责明确：规则负责风险分流，Qwen 只做语义整理和知识辅助，健管和医生保留最终人工处理权。作品集中我准备了一条匿名化 Demo Executive A 的完整故事，从体检报告的结构化结果和“查看依据”，到健康基线、风险工作列表、医生复核、健康计划、长期时间轴和知识治理。工程上使用 Streamlit、FastAPI、SQLAlchemy/Alembic 和本地 Ollama/Qwen，并用自动化测试做回归保护。

## 诚实边界

这是 Research / Portfolio Prototype；不宣称真实客户使用、临床验证、自动诊断、正式 Clinical Rule 治理或 Apple Health 真机验证。
