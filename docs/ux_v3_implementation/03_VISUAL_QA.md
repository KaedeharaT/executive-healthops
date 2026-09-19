# UX V3 实际浏览器验收

## 环境与证据口径

2026-09-20，实际启动Streamlit于 `http://127.0.0.1:18509`，Playwright启动真实Chromium。内置Browser运行时未发现可用浏览器，因此没有声称使用内置浏览器会话。使用现有Portfolio合成数据库的隔离副本 `.runtime/ux_v3_visual.db`；未修改日常数据库、模型、迁移或Demo seed。

桌面viewport为1500×1100；成员窄屏为640px。截图直接来自浏览器，未拼接、生成或修图。下表是24个页面/视图状态，不是24个独立新页面。图表截图另滚动到图形位置，不能把页面存在图形当成首屏全部可见。

已打开下表截图逐张检查层级、主动作、负责人、状态、下一步、列表密度、留白及图形可读性。普通角色所捕获页面未出现Python异常或UUID / RiskEvent / AgentGoal / PlanStep / canonical_code / provider_code泄漏。管理员配置详情允许必要技术字段。

## 页面检查

图片根目录：[`../images/ux-v3/`](../images/ux-v3/)。

|页面/视图|第一眼重点与主要操作|次级信息与视觉锚点|截图|
|---|---|---|---|
|成员首页|今天待完成任务、原因、截止；去完成|四区结构；当前管理详情折叠，2个变化预览共用下钻入口|[member-home](../images/ux-v3/member-home.png)|
|成员健康|年度起点、当前值、变化方向|紧凑比较在选择器前；一张正式主趋势；完整比较/依据折叠|[member-health](../images/ux-v3/member-health.png)|
|成员健康数据|当前指标及变化；选择指标/时间范围|一张主图，来源与记录在后|[member-health-data](../images/ux-v3/member-health-data.png)|
|成员体检与检查|最近报告、日期与来源|历次指标比较图；历史与上传保留|[member-checkups](../images/ux-v3/member-checkups.png)|
|成员计划|目标、当前阶段、待办任务|进度与任务承接；当前计划结果/历史结果明确分开|[member-plan](../images/ux-v3/member-plan.png)|
|成员服务|正在进行的服务与下一步|申请→确认→安排→执行→完成；可用服务及历史保留|[member-service](../images/ux-v3/member-service.png)|
|成员历程|长期重要事件|时间线、更多事件与完整资料折叠；无异常|[member-timeline](../images/ux-v3/member-timeline.png)|
|健管今日|逾期/今日/等待情况，短队列与选中事项|左选择右处理；右侧具体业务CTA，背景/依据可展开|[manager-today](../images/ux-v3/manager-today.png)|
|360概览|周期、阶段、负责人、关注、下一步|近期趋势、当前计划与服务；管理快捷操作降为详情|[member-360-overview](../images/ux-v3/member-360-overview.png)|
|360健康数据|同源当前记录/变化及趋势|指标选择与完整数据记录|[member-360-data](../images/ux-v3/member-360-data.png)|
|360健康基线|年度基线与当前比较|完整趋势见独立滚动截图；健康其他视图在具名入口|[member-360-health](../images/ux-v3/member-360-health.png)|
|360管理|计划、任务与当前操作|建立/调整计划、随访、服务、结果和自动跟进入口保留|[member-360-management](../images/ux-v3/member-360-management.png)|
|360医疗|成员上下文中的医生问题|同一医生复核视图与趋势；其他医学记录可达|[member-360-medical](../images/ux-v3/member-360-medical.png)|
|健管医疗协同|需要医生判断的事项与执行交接|问题、趋势、依据；内部/外部医疗切换保留|[manager-medical](../images/ux-v3/manager-medical.png)|
|健管服务|服务队列及当前执行状态|右侧服务详情与确认开始服务操作|[manager-service](../images/ux-v3/manager-service.png)|
|健管更多|支撑层具名跳转|专业资料折叠；业务故事无须进入这里|[manager-more](../images/ux-v3/manager-more.png)|
|医生队列|待我复核/历史、成员与医学问题|选中事项在同页展开，队列与详情非两个独立路由|[doctor-queue](../images/ux-v3/doctor-queue.png)|
|医生详情|判断问题→关键背景/相关趋势→依据|完整指标、用药、已有动作可展开；表单在后|[doctor-detail](../images/ux-v3/doctor-detail.png)|
|管理员系统状态|系统可用情况、集成异常/未配置|高级诊断、审计、兼容工具折叠|[admin-system](../images/ux-v3/admin-system.png)|
|管理员集成|导入、AI、知识、设备真实状态|选择后才打开配置，不把配置存在称为连接成功|[admin-integrations](../images/ux-v3/admin-integrations.png)|
|管理员AI配置|明确未配置，本地/外部选择|测试连接表单及高级设置；没有进行真实外部连接认证|[admin-ai-config](../images/ux-v3/admin-ai-config.png)|
|管理员自动化|运行/等待/人工处理情况|技术Trace进入高级诊断|[admin-automation](../images/ux-v3/admin-automation.png)|
|管理员规则|规则与状态|专业规则内容保留，设备兼容入口通往同一集成配置|[admin-rules](../images/ux-v3/admin-rules.png)|
|管理员知识|专业资料及合作方连接状态|连接设置默认折叠，检索/本地资料等能力保留|[admin-knowledge](../images/ux-v3/admin-knowledge.png)|

## 图表与窄屏肉眼检查

|检查|结果|图像证据|
|---|---|---|
|成员健康X轴线、日期刻度、Y轴线、数值与kg单位|VISIBLE|member-health.png|
|年度基线虚线/标签、当前点/标签、↑↓→比较|VISIBLE|member-health.png；member-360-health-chart.png|
|健康数据正式趋势坐标轴与单位|VISIBLE|member-health-data.png|
|360正式基线趋势坐标轴与单位|VISIBLE|member-360-health-chart.png|
|医生相关血压趋势的双序列、图例、mmHg|VISIBLE|doctor-detail.png；实际图形滚动检查|
|悬停显示日期/指标/值/单位/类型/来源|PASS|浏览器实际Tooltip：2026/09/01、体重85.8kg、当前、健康数据|
|640px成员首页、健康、健康数据|PASS|member-home-narrow.png；member-health-narrow-chart.png；member-health-data-narrow-chart.png|
|窄屏正式坐标轴仍可见，主内容没有横向溢出|PASS|640px viewport，main scrollWidth=640；上述窄屏图形截图|
|键盘焦点可见|PASS|实际Tab定位到展开控件，3px outline；不是完整屏幕阅读器认证|

本次没有修改图表轴配置或风险配色。首页预览可简化，正式图不隐藏坐标。单点/空数据和血压、多单位等边界由既有图表测试补充，不用测试代替截图判断。

## 实际交互与结果回写

先捕获上述初始合成场景，再通过 `scripts/qa_ux_v3_commands.py --allow-synthetic-writes` 执行真实UI写入；这条脚本要求隔离端口和显式参数，不对日常数据库运行。

1. 成员首页→去完成→确认完成，任务出现在已完成分类。
2. 医生打开同一待复核事项，阅读趋势与依据后填写合成验收意见及交给健管的下一步，保存成功。
3. 健管今日搜索该交接内容，在统一队列找到已有风险关联的去重事项；不是要求产生第二条重复事实。
4. 成员360管理→记录阶段结果，记录90→85.8kg观察变化、资料不足及继续管理决策。
5. 成员历程显示新医生判断及阶段结果；见 [demo-result-timeline.png](../images/ux-v3/demo-result-timeline.png)。

结果：`member_task_completed`、`doctor_decision_saved`、`doctor_returned_to_manager_queue`、`outcome_command_saved`、`outcome_visible_on_timeline` 均为true。没有进入Agent、规则、集成或Trace页面完成业务。

## 五分钟故事的演示顺序

首页主行动→健康年度基线/当前变化/关注→健管今日→360→医生问题/趋势/依据/交接→当前计划与任务/服务→阶段结果→成员历程。可在现有角色业务入口完成。五分钟是演示编排目标，并非真实用户计时研究；未把合成数据结论描述为医学治疗效果。

## 迭代与最终结果

- 360抬头从两条重复摘要合并为一条，负责人、周期、阶段与下一步仍明确。
- 医生冗长背景折叠到相关趋势和依据之后，决定表单保持在后。
- 健管搜索纳入已有下一步，实际医生交接可直接找到。
- 当前计划不再混入其他计划的阶段结果；历史结果未删除。
- 管理员从状态进入配置；合作方连接表单默认折叠。
- 体检页把最近报告放在历次图形前。

最终检查：24个桌面页面状态 + 3个窄屏状态；阻塞问题0。新增/调整12类任务视图（六个核心页，加健康数据、体检、计划、服务、集成、规则与知识），不是宣称24页全部重写。

完整pytest基线：**522 passed / 0 failed / 0 skipped**，346.98秒；最终：**530 passed / 0 failed / 0 skipped**，361.91秒。均9条既有Alembic配置弃用警告。新增8项回归；原测试因批准后的入口/标题变化更新期望，没有移除业务断言或隐藏失败。测试和截图分别承担业务/交互与视觉证据。

保留清单为121/121；其他边界见 [05_KNOWN_LIMITATIONS.md](05_KNOWN_LIMITATIONS.md)。
