# HealthOps UX V3 实施映射

设计依据：`docs/ux_v3_research/00…08`。本轮用户已明确批准并授权实施，研究文档的“等待批准”是上一阶段历史记录，不改写该记录。

起点：`78a1263536bdf1f05c6e0fec64ac15423d9e4ca5`；本地备份：`backup/pre-ux-v3-implementation`。不重新研究，不回滚导航，不新增业务事实表。

## 主线与落地

|主线|默认入口|实现|详情保留|
|---|---|---|---|
|健康状态|成员健康、成员360健康|共同的 `ProductProjectionService.health/member`，比较紧凑表在选择器前；同源正式趋势|全指标比较、年度基线确认/修订/依据、参考范围、体检、健康档案、来源记录|
|健康运营|成员今日行动/计划/服务、健管今日/360管理、医生复核|一个主行动；队列选择与处理分离；医生先问题与依据后表单；阶段结果按计划归属|计划接受/调整、任务完成、随访、服务、人工确认、自动跟进|
|长期记录|成员历程、360历程|沿用原时间轴只读投影及错误边界|完整历程、筛选、来源、历史阶段结果|
|支撑层|管理员四个区域；健管更多保留跳转|先真实状态再配置；高级诊断及具名兼容工具保留|AI、知识、设备、导入、规则、自动化、反馈治理、审计与15项兼容工具|

## 实施文件

|文件|责任|
|---|---|
|`ui/components.py`|12个组合组件，包括页面壳、Section、摘要、紧凑比较、工作行、团队、进度、时间线、详情/高级折叠；复用 `ui/experience.py` 的状态、负责人、截止、下一步、空状态与依据|
|`ui/styles.py`|统一角色宽度、正文/元信息字号、44px按钮、24px区间距、比较表和队列样式；保留Legacy样式|
|`services/product_projection.py`|只读扩展：当前任务、成员行动、当前/历史结果、年度周期、日期口径工作统计、医生上下文；无新增写操作|
|`ui/pages/member/experience.py`|首页四区；共同趋势下钻；当前结果和历史结果分区；原历程实现保留|
|`ui/pages/baseline_visualization.py`|关键比较前置，共用图形和全指标详情；不修改Baseline计算|
|`ui/pages/health_visualization.py`|当前记录/变化在指标选择前；首页共同下钻；原血压、睡眠、活动、报告/医生趋势保留|
|`ui/pages/manager/experience.py`|真实今日数量、短队列、具名处理、事项背景/依据、紧凑360抬头、主动作及管理快捷详情|
|`ui/pages/doctor/experience.py`|按问题→背景/趋势→依据→完整背景/药物/动作→医生表单→交接顺序；不截断完整指标集|
|`ui/pages/admin/experience.py`|系统状态默认页；集成未选中时不铺表单；设备兼容入口打开同一配置|
|`streamlit_app.py`|薄路由/详情组织调整：360健康详情选择、服务业务标签及完整服务记录入口、最近体检报告前置、合作方连接设置默认折叠；原业务命令保留|

## 写入边界

- 成员任务：`TaskTransitionService.complete`。
- 医生结论：`care_commands.complete_review`。
- 建立/调整计划、随访、结果：`care_commands.save_program/schedule_followup/record_outcome` 与原 `apply_outcome_decision`。
- 服务申请/取消：原 `MemberServiceOperations`。
- 报告确认、Risk处理及自动化审批仍走原服务。没有创建另一套UI写入事实。
- 本轮没有修改医学规则、Baseline快照语义、医生权限、时间轴服务、Agent执行权限、数据库模型或迁移。

## 可复核验证

`tests/test_ux_v3_implementation.py` + 原角色、元素保留、图表坐标轴、Baseline/Timeline、业务命令/API测试。真实浏览器脚本：`scripts/qa_ux_v3.py`；合成数据写入验收：`scripts/qa_ux_v3_commands.py --allow-synthetic-writes`。

环境使用隔离副本 `.runtime/ux_v3_visual.db`，Streamlit `127.0.0.1:18509`。日常数据库不用于本轮浏览器写入。

全量测试基线：522 passed / 0 failed / 0 skipped；最终：530 passed / 0 failed / 0 skipped。两次均9条既有Alembic配置弃用警告。真实Chromium覆盖24个桌面页面状态、3个窄屏状态；任务、医生交接、阶段结果回写由浏览器实际提交验证，详见03。
