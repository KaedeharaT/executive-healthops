# 长期健康数据、修正和来源

## 数据关系

原文件/RawData/RawIngestionRecord → 解析候选与标准化 → Observation → DailyHealthSummary。

`ReportCandidateRevision` 留存每次解析/修正候选。`Observation.supersedes_id` 连接事实修正链。`DailySummaryRevision` 保存重算前后的摘要版本。`CommunicationRecord` 保存沟通原文，并关联现有 ManagementLog 和实际行动。

## Raw 层

现有上传文件和原始载荷保留。RawData 的 source、record_type、recorded_at、received_at、checksum 和 payload_json 表达来源、产生/进入时间和原始值。REPORT 确认入档时关联报告页码、文件ID、原文与原始数值。手机、设备适配器继续存储供应商原始载荷；未映射/拒绝数据仍保存在 RawIngestionRecord。

原始字段禁止 ORM 覆写、禁止删除；修正不能靠修改原文件或原始载荷完成。历史迁移数据没有原始来源时如实标明，不能反向伪造原文。

## Normalized 层

复用 canonical registry、显式单位换算及质量检查。例如 83600 g → 83.6 kg，而原始载荷仍为83600 g。原始候选与最终指标可以不同；解析方式、run、candidate、原始记录ID形成来源关系。

质量与医学风险分离：valid/manually_corrected 是可分析质量，suspect/questionable/invalid/missing_context/duplicate 保持现有枚举及过滤契约；这些状态不等于 GREEN/YELLOW/RED。医学风险仍由正式 RiskRule 产生。

## Confirmed 与 Correction

Observation 的 confirmation_status、confirmed_by、confirmed_at、evidence_ref、version、supersedes_id、provenance_json 记录治理状态。经规则治理的设备事实为 GOVERNED，人工核对报告为 CONFIRMED。历史既有记录采用兼容治理默认值，不伪造人工确认人。

报告“83.6kg”被AI误提取为“86.3kg”时：报告/Raw 保留83.6；初始 ReportCandidateRevision 保留86.3；人工纠正产生新候选修订，再确认83.6。候选当前投影兼容旧界面，历史修订不可覆盖。

正式事实的修正使用 `correct_observation` 新建版本，旧事实仅标记 excluded_from_analysis，并保留旧值；新事实以 supersedes_id 指向旧事实。网关人工修正沿用同一版本关系。当前计算过滤被排除/来源删除/质量不适用的值。

## 来源展示

普通健管看到实际数值、来源、确认状态和“已修正”。展开原始记录可对照原文及解析候选，不展示数据库字段或技术版本表。审计服务可读取完整修正链、原始载荷与解析版本。

## Daily Summary

只读取 Observation，按会员时区划分自然日。当前摘要唯一键为 member/date；输入未变化不增加版本。重算生成不可变摘要修订。同一摘要/规则/日期变化事件只生成一次，避免重新上传或修正造成重复 Agent 唤醒。

SummaryWorkItem 是有界聚合队列，不是第二个工作流：同一会员同日的单条/批量 Observation 写入被合并为一项，不创建每条设备任务。worker 处理已结束日期；没有有效数据不生成空摘要。当前日可以按需确定性预览，不能把未完整的一天与完整历史日混同为诊断。

## 权限和长期记录

原文、解析候选、健康事实、人工决定、Agent Trace 和实际行动分别保留。成员归档保护沿用原事务边界。医生意见来源必须是明确医生身份或已确认医生记录；文本提及医生不构成授权。目标和计划分别需健管确认，医学判断仍由医生完成。
