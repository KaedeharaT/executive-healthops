# UX V3 · Current UX Failures（Top 15）

证据基准：HEAD `78a1263` 的源码与已有 `docs/images/product-logic-v3/` 截图；本轮只读。严重度表示**本次设计必须优先解决的使用问题**，不是临床事故、后台逻辑错误或生产安全认证结论。推论与直接可见事实分开。

## P0 · 主任务判断与执行顺序

|ID|具体观察|为什么阻碍使用|证据|冻结决策|
|---|---|---|---|---|
|F01|医生详情右侧结论表单、提交按钮在首屏出现，左侧原始依据排在趋势之后、更低位置|可以在尚未看到依据完整性时就被引导填写结论；是布局风险，不声称医生实际误判|[doctor-review.png](../images/product-logic-v3/doctor-review.png)；`ui/pages/doctor/experience.py::detail` 的 `clinical, decision = st.columns`，先趋势/evidence再右侧表单|P5单一阅读顺序：问题→相关上下文→依据→判断/交接|
|F02|今日顶部“今天待处理”的计算仅排除等待成员/医生，没有按今日截止或当前健管分配筛选|文案容易被理解成“今天到期且归我”，实际是另一集合；不要通过改业务规则掩盖标签问题|[manager-today.png](../images/product-logic-v3/manager-today.png)；`manager/experience.py::today` 的 `sum(i.status not in ...)`|P3叫“需处理”，明确范围；今天到期与逾期各自有真实口径；不能未确认身份就写“我”已认领|
|F03|工作列表左侧显示来源、三行标题/状态/截止/Owner，优先级不直接显示；右侧通用按钮“处理”与“完成跟进”没有说明实际将进入什么流程|用户不易解释为什么选这项，以及点击后做什么；列表不能只依赖排序表达优先级|同上截图；`today` 的label拼接与callback/route_target分支|短行明确人/问题/优先/截止/状态；右侧具名下一步，处理进入原命令上下文|

## P1 · 信息权重和上下文

|ID|具体观察|后果/设计判断|证据|冻结决策|
|---|---|---|---|---|
|F04|健康页在图前依次出现页面说明、健康导航、年度基线、当前状态说明、从基线到现在、两选择器、比较条；截图主图从约页面中段开始|轴已可读，但主要视觉被标题和解释前置占位；不能用再删轴解决|[member-health.png](../images/product-logic-v3/member-health.png)；`member::overview`、`baseline_visualization::render_baseline_overview/render_baseline_progress`|P2合并紧凑摘要，基线/当前与主图连成一个阅读段|
|F05|首页任务区下面是摘要、双趋势，健康团队标题到1100px截图底部才出现|负责人虽然在摘要中可见，完整团队和近期安排出现偏晚；不能宣称负责人完全缺失|[member-home.png](../images/product-logic-v3/member-home.png)；`member::home` 的 `care_team` 位于趋势之后|保留摘要负责人，团队与下个节点并入同一近期安排区；压缩Hero内部留白|
|F06|360顶部两条摘要带加一条关注长文；相同主要关注又在右侧当前管理中出现|同一事实重复抢权重，当前行动被分散在多个区域|[member-360.png](../images/product-logic-v3/member-360.png)；`manager::member_detail`|一个紧凑抬头；关注在开放事项中解释，抬头只保留短语|
|F07|360选健康后，仍有五区域radio，再叠健康内容radio，且上方摘要高度不变|形式上是同页控制，实际用户仍经历层层选择；不能只凭导航层级计数说简单|[member-360-health.png](../images/product-logic-v3/member-360-health.png)；`streamlit_app.py::render_member_archive`|保留五种360视图；健康内部以主图+具名详情代替并排新一层菜单|
|F08|管理员集成页首次进入即默认 `数据导入`，右侧大上传表单自动显示，左侧又有检查按钮|页面默认诱导上传，而非先判断哪个连接需处理|[admin-integrations.png](../images/product-logic-v3/admin-integrations.png)；`admin::integrations` 的默认 mode|P6状态概况先行；选中连接后才加载对应配置，原上传全部保留|
|F09|医生关键指标固定取四列，截图“低密度脂蛋白…”被截断；与本次问题关联的图反而更明确|核心医学名称不可为等宽卡片牺牲；固定四指标与上下文相关性不等价|[doctor-review.png](../images/product-logic-v3/doctor-review.png)；`doctor::detail` priority列表和`ordered[:4]`|P5相关指标短表允许换行；完整指标进健康详情，不删|
|F10|计划页右侧展示多个历史阶段结果，虽标了旧计划名称，但紧邻当前计划标题及任务|视觉归属可能让成员误读成当前计划成果；不是数据本身未标计划|[member-plan.png](../images/product-logic-v3/member-plan.png)；`member::plan` 阶段结果遍历 `view.outcomes`|当前计划结果先，历史按所属计划折叠；不把旧值覆盖年度基线|
|F11|系统“规则与知识”中又有“设备”，集成中心也有设备配置；专业知识配置同样多入口|两个入口可能让管理员以为维护两套设置，增加位置记忆|`admin::workspace` 配置内容选项与 `integrations` 分支|设备归集成；知识内容归规则与知识、连接归集成；旧入口明确跳同一配置|

## P2 · 阅读负担和恢复提示

|ID|具体观察|后果/设计判断|证据|冻结决策|
|---|---|---|---|---|
|F12|“同一事项在此处理；成员详情显示依赖…”、“管理顺序：目标→当前计划…”等解释系统组织的长caption直接在任务页|界面解释自身架构，用户仍需找实际工作；属于ui-ux的self-narrating UI|`manager::today`、`member::plan`；今日/计划截图|位置与顺序表达逻辑，说明进入帮助或详情；医学边界提示保留在相关上下文|
|F13|今日队列固定540px滚动区，超过12项又进入折叠区，外层页面也能滚动|有双滚动与剩余事项可发现性风险；没有实测断言所有用户都会漏看|`manager::today` container(height=540)、visible[:12]、其他事项expander|队列保留完整入口和数量，采用清晰分页/连续区；详情不再第二长列表|
|F14|首页已有两次“查看趋势”，底部另有计划/数据/报告三个快捷按钮，外加任务CTA和多个折叠区|每个动作有价值，但默认入口总量稀释今日任务；不能通过删除功能处理|`member::home`、`health_visualization::render_previews`|共用一个变化入口；报告回体检上下文，缺资料时才提升为首页主动作；原路径映射保留|
|F15|多页日期/来源/责任说明用约13px caption，小字号承载必要信息；医生/360截图可见浅细文字|不宣称所有颜色未达WCAG；需要把关键元信息与补充说明分层，实际对比度留后续测量|`ui/styles.py` caption/summary small；医生、首页、360截图|必要日期/责任≥14px，正文16；关键字段不能降成低权重注脚；200%缩放与键盘验收明确|

## Anti-pattern复核

|Skill检查项|当前证据结论|对应问题/处理|
|---|---|---|
|Card wall|局部存在同权框/条叠加，不是全平台都没分组|F05/F06/F08；Section、行、图混合|
|Dashboard for dashboard’s sake|当前今日已是工作队列，不应回滚成统计大盘|保留现有方向，只修口径与动作|
|Too many equal-weight sections|360摘要/当前管理/服务重复权重|F06|
|Technical vocabulary leakage|当前核心截图未见UUID/RiskEvent；不能沿用已修复问题当本轮事实|保留词汇合同，高级技术字段继续可到达|
|Long text inside lists|今日多行标签仍有长解释|F03/F13|
|Repeated information|360主要关注、首页下个服务在多个展开处|F06/F14|
|Actions far from context|通用处理进入其他页面；医生表单与证据阅读脱节|F01/F03|
|Empty decorative areas|截图局部留白多；无证据说全站空卡片|减少无内容固定高度；不强行填假数据|
|Too many secondary buttons|首页多个快捷入口与趋势按钮|F14|
|Excessive tabs / nested menus|360两排局部导航与健康档案内切换叠加|F07|
|Charts without decision purpose|现有基线/血压趋势有明确价值，轴肉眼可见|保留；旧专用图迁详情，不删|
|No recovery / context loss|本轮未实际执行所有失败分支，不标已失败|04明确加载/空/失败/失效状态，批准后运行验证|

## 不属于本轮的问题

没有复现新的Timeline崩溃，不声称轴消失，不认定医疗规则错误，也不把演示身份边界包装成已解决。仅通过设计提出组织方式；没有改代码来“顺手修”以上任何一项。
