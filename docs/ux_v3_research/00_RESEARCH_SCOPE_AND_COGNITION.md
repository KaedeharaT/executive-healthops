# UX V3 · Research & Design Freeze

研究日期：2026-09-20。代码基准：`78a1263536bdf1f05c6e0fec64ac15423d9e4ca5`，分支 `main`。开始时工作区干净。

**这是待用户批准的设计冻结候选稿，不是已实现、已上线或已完成可用性验证的界面。** 本轮仅新增本目录文档；不启动会初始化数据的应用、不运行写入型测试、不改应用/数据库/README，不 commit、不 push。

## 1. Skill：实际发现、读取与应用

实际检查了项目 Skill/AGENTS 文件以及 `C:/Users/feng/.agents/skills`、`C:/Users/feng/.codex/skills`。用户级现有技能没有匹配的产品 UI/UX Skill。随后将三个指定公开仓库 clone 到仓库外的 `%TEMP%/healthops-ux-v3-research-20260920/`，没有安装到项目，也没有复制第三方正文或资产到项目。

|Skill|实际读取正文与版本|应用位置|未应用的部分|
|---|---|---|---|
|ui-ux|[SKILL.md](https://github.com/atuizz/codex-ui-ux-skill/blob/3c311f71f5aab40af3a10dadb2306578783979d0/ui-ux/SKILL.md)，另读 project-cognition、anti-patterns、ux-evaluation、workflow 四份 reference|本文件项目认知；04 的任务链、恢复路径；06 的反模式审查|不执行其开发阶段，不写 AGENTS|
|frontend-design|[SKILL.md](https://github.com/Hitbullets/codex-skills/blob/56b113571f1e67c25f9867bded2408f30ba1c07a/codex-frontend-design/skills/frontend-design/SKILL.md)|05 三种方向、版式、字体、视觉身份；04 线框|用户禁止实现，故不生成组件代码；不采用不适合医疗产品的夸张视觉|
|ui-ux-pro-max|[SKILL.md](https://github.com/Hitbullets/codex-skills/blob/56b113571f1e67c25f9867bded2408f30ba1c07a/codex-frontend-design/skills/ui-ux-pro-max/SKILL.md)|04 恢复/空状态/窄屏；05 对比度、触控、导航、表单、图表验收|没有宣称执行浏览器可访问性测试；本轮为设计标准|
|frontend-ui-standards|[SKILL.md](https://github.com/MaxHan7/frontend-ui-standards-skill/blob/0609cb07793ee1f8f6626c98042ee2e811f81735/frontend-ui-standards/SKILL.md)|05 分离 token / component metric / page layout；复用与一致性检查|不修改当前 CSS、组件或尺寸|

Skills discovered：4 个指定 Skill；actually read：4；applied：4；unavailable：0。Skill B 实际目录在 `codex-frontend-design/skills/` 下。没有虚构已安装 Skill，也没有运行第三方安装脚本。Skill 指令与用户 STOP IMPLEMENTATION 冲突时，以本轮只做设计为准。

## 2. Project cognition

**Project in human words**：HealthOps 是持续健康管理协作产品：把报告和连续健康资料变成可信的健康状态，让健管组织行动、医生在必要时判断，并把执行结果留在长期记录中。

**Core users**：成员、健康管理师、医生、管理员。成员负责自身行动；健管负责管理推进；医生负责医学判断；管理员负责配置与运行保障。演示角色切换不等于真实鉴权。

**Core business objects**：年度参考起点、当前有效健康记录、报告与依据、关注事项、待处理工作、责任人、医生复核、计划及其任务、服务安排、阶段结果、事件记录。AI、自动化、知识与设备是支撑，不是第五种用户旅程。

**Current stage**：本地可演示的多角色健康运营原型，存在真实服务与投影代码、合成演示资料；本轮没有证据证明真实团队 Pilot 或临床生产成熟度。依据：`ui/pages/shell.py` 演示入口、`ui/pages/admin/experience.py::workspace` 的演示身份说明、当前截图中的角色预览。此处不沿用过去测试数量来推断成熟度。

**Surface / redesign tier**：复杂角色工作台，采用 ui-ux 的项目救援/信息架构重建思路；先冻结任务模型，六页原型，不在旧截图上换色补丁。

|角色|Primary user task|Entry point|First decision|Success criterion|Recovery path|
|---|---|---|---|---|---|
|Member|完成当前最重要行动，理解变化及谁在跟进|首页，或已有任务/报告直达入口|现在由我做，还是等待团队？|完成状态有回执，下一节点与负责人清楚|未完成保留原任务；失败不假报成功；原因/完成说明可展开；去计划查看原任务|
|Manager|把最需处理事项推进到下一责任人或结果|今日统一队列；成员直达 360|谁最需要我、为什么、最晚何时？|处理后同一工作状态更新，后续责任明确|保留筛选与选中事项；失效工作刷新；证据不足回到既有确认/补充流程|
|Doctor|回答指定医学问题并交回执行|待我复核 → 选中问题|问题明确吗？依据足够吗？|人工判断保存，接收健管及跟进说明明确|依据缺失明确标记；可退出回队列，不自动确认；现有表单校验保留输入，刷新前提示未提交|
|Admin|找出异常并进入对应配置/人工处理|系统状态总览或四类系统入口|是未配置、未测试，还是已失败？|真实测试/处理结果可核对，不把配置当成功|显示失败类别与重试入口；诊断按需展开；未保存设置不表示生效|

**Product temperament**：安静、可信、有人负责，数据帮助决定下一步；不做医疗评分娱乐化、不做聊天机器人门户、不模仿开发控制台。

**User-facing vocabulary**：年度健康基线、当前健康状态、健康数据、检查结果、持续关注、待处理、等待医生、负责人、下一步、健康计划、任务、服务进度、阶段结果、健康历程、自动跟进。

**Internal terms that must not appear by default**：Observation、RiskEvent、AgentGoal、PlanStep、Outcome、canonical_code、source_id、provider_code、UUID、raw enum、JSON、Trace。管理员高级诊断可以保留必要技术字段；不能借清理词汇删除可追溯依据。AI/API 等术语只在需要配置时出现。

**Known UX risks**：同一事实在多页重复强调；年度基线与当前记录混淆；任务完成被误解为健康改善；旧结果误归当前计划；可见图表被重构漏接；依据标题被误解为证据完整；演示角色切换被误解为权限；把无数据解释为正常；支撑工具抢占主路径；导航计数合格但实际切换仍过深。

## 3. 固定逻辑与责任边界

健康资料进入 → 年度基线 → 当前状态 → 变化/正式规则风险 → 工作事项 → 健管 → 必要时医生 → 计划/任务/服务 → 执行 → 阶段结果 → 健康历程 → 下一周期。

|概念|回答的问题|事实边界|
|---|---|---|
|健康状态|原来、现在、变化是什么？|基线冻结；当前观测独立；不由图表方向发明医学结论|
|健康运营|谁、为什么、何时、下一步？|沿用现有业务服务；一个事实只有一个写入来源，多个角色投影|
|长期记录|发生过什么、本阶段结果与下一轮？|时间轴只读投影；阶段结果写在所属计划，历史不创建第二份事实|
|支撑层|数据如何进入、辅助如何受控、系统如何运行？|AI/Agent/知识/设备/规则/集成/反馈/审计保留于后台或上下文依据|

不新增季度/年度复盘、家庭代理访问、在线消息、临床评分或新设备连接。竞品有这些能力不意味着 HealthOps 已有；下一周期通过现有基线年度选择、计划建立和结果决定组织。

## 4. 证据与验证边界

- 研究使用官方网页、官方帮助/培训资料与实际打开的公开 UI 图像。竞品已登录全产品导航无法确认时明确记“未核实”，不把营销网站菜单当产品导航。
- 当前产品检查静态源码及本版本已有 `docs/images/product-logic-v3/` 截图。截图是既有证据，**不是本轮重新运行的浏览器验收**；本轮不声称测试 PASS 或视觉实现 PASS。
- 源码逐项盘点见 03 与 03A。运行时记录数量、不同配置下所有分支的实际可达性不由静态扫描证明。
- 六页线框中的示例标题/图形只说明结构，非新增种子数据；人数、状态、下一步均应来自现有事实。
- 本轮结束后停止；等待用户批准设计再另行授权实现。停止要求来自用户第 51 条，不是 Skill 引入的新审批门槛。
