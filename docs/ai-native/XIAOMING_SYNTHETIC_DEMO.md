# 小明：完整合成纵向管理演示

入口：**会员 → 搜索“小明” → 点击小明 → Member360 → 历程**。

基线 HEAD：`a54d55b5957ee42004d8180bf513d4e96d94285a`；备份分支：`backup/pre-xiaoming-demo`。
全部资料属于虚构演示会员，不是临床建议或真实医疗记录。

## 演示内容

故事时间为 2025-10-05 至 2026-10-04，覆盖最近 12 个月。身份存储为“小明”，
`external_id=synthetic-demo-xiaoming-v1`。列表显示“演示”，会员页标题旁显示“演示会员”，
沿用现有样式与五个 Tab。没有新增页面、导航或启动时 seed。

| 时间 | 已持久化的事实与真实流程 |
| --- | --- |
| 2025-10 | 入组参考基线、既往用药来源记录；用药为虚构名称，不推断疾病 |
| 2026-01 | 年度合成体检来源、86kg / 175cm，确定性 BMI 28.1；年度基线由演示健管确认 |
| 2026-02 | 问卷涵盖病史自述、家族史、过敏、用药、生活方式；分别确认目标和计划，复用四个阶段 |
| 2026-03 | GREEN 计划内数据检查自动完成，Tool Registry 写日志并创建下一次低风险检查，无人工 Gate |
| 2026-05 | 83.6kg 原始报告；模拟解析为86.3kg；通过报告纠正/确认服务保留候选、修正和正式83.6kg |
| 2026-08 | 近7日睡眠约6.5h，降至5.4h并持续；Summary Change Detector 触发，Risk Engine 产生 YELLOW |
| 2026-08 | 同一流程等待健管；电话原文保留，通过既有自然语言规则提取夜班、睡眠、饮食候选，关联计划调整 |
| 2026-09 | 后续设备记录逐步恢复至6.2h，Outcome 与睡眠事件、随访和调整计划关联，不声称因果或治愈 |
| 2026-09 | 独立合成复查变化由 Responsibility Router 交医生，WAITING_DOCTOR → 正式医生结果 → 原 Goal 恢复 |
| 2026-09 | 已确认医生意见产生复查，WAITING_TIME → 到期 → 报告返回 → 原 Goal 继续，形成第二个有结果的 Episode |
| 2026-09/10 | Agent 汇总阶段资料、健管确认，既有服务进入阶段4；当前82.4kg、睡眠6.2h、GREEN，10月15日随访 |

管理目标采用覆盖本年度持续管理的周期：从86kg向82kg推进，同时改善睡眠规律性。
当前可确定性计算为90%，剩余0.4kg；不展示没有定义的“健康改善率”。
腰围沿用现有指标要求，被列为辅助补充建议，不阻塞管理。

## 数据与流程边界

脚本 `scripts/seed_xiaoming_demo.py` 按历史日期逐日回放服务，不提前把未来数据放入 Agent 上下文：

- 会员入组、初评、目标和计划分别调用现有服务；MemberAgent 持久存在。
- Device / Mobile 原始测量经过 HealthEvent 的 STORE_ONLY、规范化和 Observation 路径。
- Daily Summary 和变化规则由现有确定性服务运行，不对原始设备记录调用 LLM。
- 报告错误属于显式合成 extraction fixture，真正调用候选纠正和确认服务，原候选版本保留。
- 健管沟通调用既有 communication 和 care-result rules，原文保留，健管自述不成为医生意见。
- 医生提交、风险处置、复查推进、阶段确认、下一阶段调用现有服务和 Tool Registry。
- CareEpisode 使用既有版本化关联服务；Timeline 只读业务投影，没有手写 UI 节点。
- 演示规则仅在 seed 单一事务内启用，提交前全部停用，不修改任何既有医学规则。
- 采用 GREEN + YELLOW + Doctor HITL，不为演示强造 RED 紧急医疗场景。
- 当前系统没有独立的全局演示统计排除开关。本轮保留可查询的 SYNTHETIC 标识，没有改造统计体系。

## 运行与重置

本次实际写入的是正式8501正在使用的 **项目根目录 `executive_health_ai.db`**。
没有替换成另一个 `data/portfolio_demo.db`，没有 rebuild。

```powershell
# 推荐先停止平台，以便稳定核对前后记录；不是重建数据库。
pwsh -File .\scripts\stop_platform.ps1
.\.venv\Scripts\python.exe .\scripts\seed_xiaoming_demo.py --database .\executive_health_ai.db
pwsh -File .\scripts\start_platform.ps1
```

重复 seed 找到同一个 external_id 和完整 seed 回执后直接返回，**不重置已经演示操作过的状态**。
每次命令都先通过 SQLite backup API 备份，备份位于 `.runtime/xiaoming-demo/`。

管理员明确重新生成时：

```powershell
.\.venv\Scripts\python.exe .\scripts\seed_xiaoming_demo.py --database .\executive_health_ai.db --reset
```

reset 只删除 seed 回执列出的合成记录，不按姓名猜测、不清空表、不级联删除其他会员。
如果回执外的后续业务记录引用这些数据，命令拒绝 reset，以保留后来工作；可在备份副本演示。
reset 支持 SQLite，外键检查在事务提交前完成，任何校验失败均回滚。

整个写入过程比较所有既有模型表的主键与整行哈希；除显式 reset 的小明记录外，
原有数据有任何改动都会拒绝提交。正式库另以首次备份再次核对，原有14位会员、
5678条 Observation、5511条 RawData、健康档案及所有关键历史均保持原样。
最后仅新增1位小明、1976条 Observation、1976条 RawData、247天 Daily Summary。

## 查看证据

- 健康档案 → 查看完整健康档案：查看原有问卷、报告和基线入口。
- 健康档案 → 来源详情 → 2026-05-10 的83.6kg → 查看原始记录：看83.6原文、86.3错误候选、83.6修正。
  原有来源选择器增加有界的历史报告/修正记录查询，避免连续设备数据把旧确认依据挤出最近12条。
- 医疗 → 历史 → 点击医生事项：正式意见和提交原因；当前没有待医生判断的事项。
- 历程 → 睡眠时长重要变化：7日/30日比较、年度基线、YELLOW、健管行动、观察结果和来源。
- 历程 → 当前状态：年度目标、阶段4、90%目标进度、下一次随访。

截图和真实Chromium验收结果保存在 `docs/images/xiaoming-demo/`。
自动化测试覆盖 seed 幂等、标记、持久Agent、基线/目标/指标、设备/手机来源、Summary、变化依据、
YELLOW、沟通结构化、两个结果关联、医生身份和原Goal恢复、复查等待、阶段推进、当前状态、
12个月双轨、历史纠错入口、原始数据保留、外键及限定范围reset。

验证结果：相关回归测试 **126 passed / 0 failed**；正式库81张表的全部既有记录逐行哈希未变。
正式8501的真实Chromium依次验收五个Tab及变化、行动、医生、结果、当前状态详情，
8501健康检查与8000/docs均返回200，Agent worker继续运行。
