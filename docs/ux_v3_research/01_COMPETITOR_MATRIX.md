# UX V3 · Competitor Matrix

日期：2026-09-20。**6 个医疗/健康产品 + 3 个工作效率产品**。只研究公开官方产品资料、帮助中心、培训中的界面；没有登录竞品账户。下面“首屏”限定为来源展示的具体界面，不冒充登录后完整首页。“Weakness / Reject”是对 HealthOps 适配性的判断，不是对竞品质量的全面评价。

## 证据索引

|代号|官方资料|本次证据范围|
|---|---|---|
|I1|[Included Health healthcare support](https://includedhealth.com/members/healthcare-support/)|需求到服务/人工团队的公开任务组织|
|I2|[Included Health app](https://includedhealth.com/get-the-app/)|已实际打开 Care Coordinator 消息界面官方图片；不是首页全貌|
|M1|[MyChart records/results/care plans](https://www.mychart.org/l/en-us/features/view-medications-test-results-bills/)|结果趋势、用药与 Care Companion 的官方功能说明|
|M2|[MyChart Help](https://www.mychart.org/l/en-us/help/?decisionTreeExpanded=1)|健康摘要、结果、预约、沟通及机构差异|
|M3|[Download result trends](https://www.mychart.org/l/en-us/help/download-results/)|结果→比较趋势→下载的官方路径|
|M4|[Family care](https://www.mychart.org/l/en-us/features/family/)|家庭/代理访问参考；不作为本轮新增能力|
|M5|[Queen’s MyChart patient guide](https://www.queens.org/wp-content/uploads/Queens-Health-System-MyChart-Patient-Guide.pdf)|公开机构使用指南，2024版；正文可访问，截图请求超时，不能声称肉眼核对其图像|
|S1|[Health Cloud Integrated Care Management](https://trailhead.salesforce.com/content/learn/modules/integrated-care-management/explore-integrated-care-management)|已看成员页、展开计划官方截图；成员上下文串起评估/计划/团队|
|S2|[Enhanced Health Timeline](https://trailhead.salesforce.com/content/learn/modules/health-cloud-data-displays/add-objects-to-health-timeline)|事件、事件类型、详情、类别/时间筛选|
|T1|[Livongo blood pressure monitor](https://www.teladochealth.com/livongo/devices/blood-pressure-monitor)|已看手机上的 Health data 界面官方照片，读数/数据入口/底部导航可辨|
|T2|[Health Summary Report](https://library.teladochealth.com/hc/en-us/articles/4416914320147-How-to-Access-Your-Health-Summary-Report-HSR)|30/90天读数总结与趋势|
|T3|[Guide to coaching](https://content.teladochealth.com/cp/Livongo_Guide_to_Coaching_Usage.pdf)|目标与人工教练接续的官方说明|
|O1|[One Medical Care from anywhere](https://www.onemedical.com/seniors/care-from-anywhere/)|预约/消息/检验结果的逐步操作；直接抓取403，Web工具可读官方正文，未获得可验证截图|
|O2|[One Medical lab services](https://www.onemedical.com/services/lab-services/)|结果解释与后续动作接续|
|D1|[Omada Progress page](https://support.omadahealth.com/hc/en-us/articles/115015679427-What-is-my-Progress-page)|已打开官方 Android 首页、Progress 两张截图|
|D2|[Omada step goal](https://support.omadahealth.com/hc/en-us/articles/24346593784339-For-iOS-How-do-I-change-my-step-goal)|从 Progress 到活动目标的路径|
|L1|[Linear Triage](https://linear.app/docs/triage)|收件、责任、处理与队列；最新官方帮助|
|L2|[Linear Peek](https://linear.app/docs/peek)|列表项目预览与键盘操作限制|
|L3|[Linear 2026 design refresh](https://linear.app/now/behind-the-latest-design-refresh)|导航退后、任务内容优先的官方设计解释；未将文字描述当截图验收|
|L4|[Linear split view](https://linear.app/changelog/2022-01-20-linear-preview-new-sidebar-and-team-icons)|历史官方 split view 证据，不宣称2026所有页面外观不变|
|H1|[HubSpot preview a record](https://knowledge.hubspot.com/records/preview-a-record)|已看联系人预览面板官方截图|
|H2|[HubSpot record layout](https://knowledge.hubspot.com/records/work-with-records)|记录页三区域、关联、活动、折叠|
|H3|[Customize record previews](https://knowledge.hubspot.com/object-settings/customize-record-previews)|按团队/对象调整详情优先级|
|N1|[Notion layouts](https://www.notion.com/help/layouts)|已看官方布局编辑器截图；主区/详情区区分，不当最终用户首页|
|N2|[Notion database views](https://www.notion.com/help/category/database-views)|视图/筛选/全页打开|
|N3|[Notion linked views](https://www.notion.com/help/notion-academy/lesson/linked-views)|同一来源多种呈现，不另造事实|

公开图片仅在仓库外临时目录查看，未复制到HealthOps资产。图像来源指向上表官方页面；没有使用 Dribbble/Behance 概念稿。官方截图可能是教学版/旧版，不能据此断言当前每个用户看到相同导航。

## 设计矩阵

|产品|角色|首页/已见视图|导航|主要对象|主要行动|详情模式|图表模式|Timeline|Care Team|Plan|Strength|Weakness（适配判断）|HealthOps Adopt|HealthOps Reject|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|Included Health|成员|公开页面从需求找支持；已见消息详情|全量应用导航未核实|当前需要|获得帮助/连接服务|需求→服务或团队|本次未见健康趋势|本次未核实|具名协调人接续|此组来源未证实长期计划UI|减少先学模块的负担|保险/账单任务占比不适合直接移植|首页一个任务与负责人|聊天优先、保险功能扩张|
|Epic MyChart|患者/家庭|结果/用药/预约等高频活动|随机构配置；无统一数量证据|检查结果/预约/药物|查结果/比较趋势|活动→记录详情→趋势|同一检查历次对比|就诊历史有资料；不推断统一Timeline全貌|与实际医疗提供方关联|Care Companion执行/提醒|普通医疗用语直接可懂|直接照搬会把HealthOps变医院门户|健康页、档案、计划任务关系|缴费/处方续配/家庭代理新增|
|Salesforce Health Cloud|健管|教学首页工作量；已见成员记录|截图5个成员页签，不等于全局5导航|成员/计划/问题/目标|成员上下文新任务/计划|摘要+tabs+展开层级|教学有风险评分趋势|事件及时间筛选|独立团队上下文|问题/目标/行动组织|成员上下文连续|多层树/侧栏信息对HealthOps过重|360与统一责任上下文|评分、保险字段、深树、Lightning皮肤|
|Teladoc/Livongo|持续健康管理成员|照片展示最新健康读数|可辨Home/Programs/Health info/Messages/Account 5项；仅此样本|读数/目标/支持|看记录并联系教练|数据→趋势/总结|血压/血糖、30/90天总结|本次未核实统一事件轴|教练接续|与教练共同目标|连续数值连接行动|产品设备闭环不能假设HealthOps已具备|趋势+下一步+人工支持|仿造真实连接或自动诊断|
|One Medical|患者|帮助页描述首页预约入口|全量数量未核实；My Health/消息路径有依据|预约/结果/照护联系|预约/发消息/查结果|日常任务直接进入|本次未核实趋势UI|本次未核实|通过消息及就诊接续|公开指南提及care plan访问|低摩擦业务动词|依赖真实医疗交付网络|短路径与结果后续|承诺即时消息/预约能力新增|
|Omada|持续管理成员|本周执行内容、日常记录|所见Android图5项：Home/Groups/Messages/Learning/Progress|当前目标/记录/周进展|执行本阶段任务|Progress分组→具体记录|体重历史及不同项目读数|过去目标；不等于事件轴|教练支持入口|周进展/过去目标|执行具有连续性|其图片卡片较多且学习内容不适合照搬|当前任务与历史目标区分|课程墙/社群/默认减重目标|
|Linear|运营效率参考|Triage待处理事项|按团队/视图可变，未报固定数|工作事项|接受/分配/处理|列表+详情/Peek|项目预览有图；非医疗趋势|事项活动，不同于健康历程|责任人而非医疗团队|项目/事项|短队列和上下文操作|快捷键门槛不适合成员|工作人员短行与选中详情|开发词汇/仅键盘入口|
|HubSpot|运营效率参考|列表→联系人预览|账号/Hub不同，未报固定数|客户记录/活动/关联|在记录中处理活动|预览侧栏→完整记录|本次所见预览非图表主导|活动历史|记录Owner/团队配置|任务与关联|不离开列表了解对象|大量关联卡和操作会分散焦点|主从关系与责任/活动详情|50卡上限当设计目标/所有快捷动作同权|
|Notion|信息组织参考|布局编辑器；非用户首页|工作区页面可变，未报固定数|页面/同源视图|选记录、看正文或属性|固定摘要+主区+详情|多种视图可用；本研究不推导健康图样式|视图能力不等于医疗事件语义|无医疗团队假设|任务/目标页面|属性可降层且不丢内容|自由编辑不能替代临床状态约束|同源呈现、非关键属性收起|万能页面编辑器/复制数据库为新事实|

## 每个产品的十问

十问顺序固定：①第一屏 ②一级导航数量 ③对象 ④主CTA ⑤渐进展开 ⑥避免重复 ⑦图表位置 ⑧刻意收起 ⑨分区 ⑩不适合部分。未核实项保留，不填猜测。

### Included Health（I1/I2）

1. 公开支持页先问需求类别；实际看的图片是协调人对话，不能称为用户首页。
2. 登录应用一级导航总数未核实。
3. 可理解的健康需要与服务。
4. 支持页按需求进入服务；单条对话界面是消息操作；全产品主CTA数量未核实。
5. 先选需要，再进入具体支持。
6. 单一入口与团队接续减少用户分诊负担是设计推论，不知道其后台去重机制。
7. 本组页面未见健康图，不能得出没有图表。
8. 内部服务分工不作为用户必须理解的对象。
9. 需要/可获得支持/团队帮助分区。
10. HealthOps 不复制聊天式入口和账单/保险导航。

### Epic MyChart（M1/M2/M3/M5）

1. 官方功能页列高频活动；部署首页因机构不同未作统一断言。
2. 一级菜单总数未核实；指南不能代表所有部署。
3. 结果、用药、预约、健康摘要。
4. 结果详情中的比较趋势/下载；各活动有对应动作，不声称全页只有一个。
5. 结果列表进入具体结果，再比较历次值。
6. 从记录上下文继续操作是可借鉴模式；不推断后台事实模型。
7. 同一检查结果的时间比较中。
8. 原结果范围、备注、历史在详情；通知偏好在设置。
9. 医疗日常活动命名，而非Observation类名。
10. 不增加处方续配、支付或家庭代理授权产品。

### Salesforce Health Cloud（S1/S2）

1. 教学个案从工作量首页进入成员页；实际看的成员图先给身份及负责人。
2. 图中5个成员tab；全局数量未知，可配置，不能混为一谈。
3. 成员、评估、计划、团队。
4. 图中顶部3个快捷动作加更多，计划区另有新建；HealthOps收敛为一个当前主动作。
5. 成员tab与计划逐层展开。
6. 在成员上下文组织不同记录；这是体验观察，不承诺其自动去重。
7. 另一个教学分区有健康评分图；不移植评分。
8. 计划细项折叠，医学背景可展开。
9. 成员抬头、侧边背景、主工作区。
10. 不照搬多层计划树、风险评分或保险字段。

### Teladoc Health / Livongo（T1/T2/T3）

1. 所见官方手机照片显示健康读数及Care options，不能断言默认首页所有内容。
2. 此图底部可辨5项；版本/项目不同可能变化。
3. 测量读数、长期目标、教练。
4. 进入数据/支持；全页面主CTA数量不由照片完整确定。
5. 最新读数进入总结和趋势。
6. 数据和人工支持在一个App中接续，后台同步实现未研究。
7. 健康数据及30/90天总结。
8. 完整读数历史不铺在首页。
9. 读数摘要、服务选项、底部导航。
10. HealthOps只保留已存在数据来源，不把Adapter写成真实设备闭环。

### One Medical（O1/O2）

1. 指南明确首页有预约动作；未肉眼核对当前应用首页。
2. 一级数量未核实。
3. 预约、检验结果、与团队联系。
4. 预约；结果与消息按用户需要直接进入。
5. My Health进入Lab Results等具体内容。
6. 结果解释带后续说明；将下一步留在原事项上下文是HealthOps推导。
7. 本次官方来源没有足够图表布局证据。
8. 历史结果留在健康资料路径。
9. 指南按预约/消息/结果等任务分区。
10. 不新增消息中心或承诺线下网络能力。

### Omada（D1/D2）

1. 所见Android首页为当前周目标/学习任务、日常记录及本周内容。
2. 图中5个底部入口，不能推广到所有项目/版本。
3. 目标、执行、读数、周进展。
4. 当前学习动作有强调按钮；这是截图任务，不复制其内容。
5. Progress→周更新/过去目标/具体健康数据。
6. 当前执行与历史目标分开，避免每个入口都展示全部历史。
7. 体重历史及按项目存在的血糖/血压读数。
8. My Motivation可折叠，历史目标进入详情。
9. 当前周、日常记录、本周其他；进展页按时间/数据分组。
10. 不使用课程卡片墙、用户竞争或默认减重目标。

### Linear（L1/L2/L3/L4）

1. 研究的是Triage工作列表，不把它等同所有人的默认首页。
2. 团队与视图可变；未确认固定一级数量。
3. 工作事项。
4. 处理当前事项；保留可见鼠标入口。
5. 列表选中详情/Peek。
6. 同一工作事项在视图中呈现，避免复制内容是设计推论。
7. 项目预览可以出现图；不据此移植健康Dashboard。
8. 描述与属性放详情，导航弱化。
9. 导航、视图控制、队列、详情。
10. 不引入开发术语，也不采用必须记快捷键才能预览的门槛。

### HubSpot（H1/H2/H3）

1. 所见是联系人预览面板，姓名/联系信息/快捷动作先出现。
2. 全局导航依产品/权限不同，未核实数量。
3. 记录、活动、关联。
4. 面板有多个快捷动作及完整记录入口；HealthOps只突出当前下一步。
5. 列表Preview→可折叠信息/活动/关联→完整记录。
6. 关联预览留在当前页面；不据此声称业务天然无重复。
7. 所见预览未见主图；本轮仅学习工作效率。
8. 关联信息可折叠。
9. 记录页左基础信息、中活动、右关联；HealthOps不照搬三栏。
10. 不移植营销、销售漏斗和过多快捷动作。

### Notion（N1/N2/N3）

1. 已看布局编辑器，不是用户工作首页。
2. 页面树可变，没有固定一级总数。
3. 页面与记录视图。
4. 编辑器应用布局；用户场景打开记录，两个上下文不能混淆。
5. 正文/属性详情区，可收起。
6. linked views修改同一来源，视图设置独立。
7. 视图可选择不同表现；不借此添加医疗总分图。
8. 非关键属性移到详情。
9. 标题、主要内容、详情区。
10. 不允许自由拖拽改变医疗状态语义，不构建第二数据库。

## 对HealthOps的决策

采用“需求→行动”“记录→趋势”“队列→上下文详情”三组模式。拒绝无限卡片、深层计划树、聊天总入口和后台对象导航。公开资料不足处不阻止设计，但明确采用的是HealthOps业务推导，待设计批准后的用户任务测试验证。
