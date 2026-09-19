# Competitor UX Research — 2026-09-19

研究范围：9 个产品（6 个医疗/健康，3 个复杂业务平台）。未登录任何竞品账户；区分真实公开产品截图、官方能力说明与设计推断。公开截图不代表完整部署形态。竞品图片仅临时查看，未加入 HealthOps、截图目录或提交。

## 证据与矩阵

|产品 / 用户|首页与一级导航|详情与主要行动|图表 / 时间线|团队 / 计划任务 / 工作台|优点与借鉴|不采用 / 证据边界|
|---|---|---|---|---|---|---|
|Included Health / 成员|实际官方 App 图：问候→当前 check-in→寻找服务；完整导航未观察|当前事项内主 CTA，服务入口按需求|公开图不是健康趋势页，不推断趋势功能|官方说明 Care Team 可接续；健康需要优先于模块分类|首页一项主行动，次要推荐来自真实待办|不复制聊天产品、权益支付或品牌；不新增推荐算法|
|Epic MyChart / 患者与家属|官方资料按健康、结果、用药、预约组织；各医疗机构配置不同|结果→单项详情→比较趋势→团队备注|官方帮助明确结果趋势和时间范围|Care Companion 将计划变成记录任务与 check-in|健康记录与趋势放在同一上下文；计划以执行为先|不新增家庭账户、处方续药或账单；不把公开营销导航当 App 全量菜单|
|Teladoc Health / 长期照护成员|官方 App 图片：医生身份与 goals|目标下列具体检查和行为任务|本轮公开图未呈现长期时间轴|明确负责医生→目标→行动；线下检查由团队协调|服务先显示当前安排及下一步；计划显示负责人|不引入远程问诊交易或商业承诺|
|One Medical / 会员|官方说明预约、虚拟服务、My Health|从需要到预约/记录/联系团队|本轮未可靠获取真实产品图|官方文章描述记录、预约、照护人员联系|减少跨模块选择成本，档案聚合|页面直连403，仅文字证据；不声称观察其完整 UI|
|Omada Health / 慢病管理成员|实际帮助截图：侧栏导航，Progress为独立入口|指标列表→日期范围→趋势|体重主曲线、周/月/年范围；旧截图日期明确|官方说明教练、周更新与目标|一个指标工作区；当前数值与连续记录结合|不照搬减重目标或推断变化即改善；网页截图为2021帮助示例|
|Salesforce Health Cloud / 照护团队|官方产品图：成员身份、上下文页签、关联记录|同一成员下查看资料、计划与动作|官方界面示意含健康时间轴；不是通用数据库对象菜单|Care Plan示意将问题、目标、来源与建议放同处|成员360、列表/详情、明确执行归属|不采用AI自主临床建议、健康评分、销售报价；官网图有合成营销叠层|
|Linear / 运营人员参考|官方截图：紧凑事项行+筛选，状态分组|列表聚焦一项，再看详情|此研究页不是健康图表|负责人/优先级/状态靠近事项|健管队列左列表右处理；筛选不新增导航|不使用工程编号、开发工具文案、暗色皮肤|
|Notion / 复杂信息使用者|官方布局截图：标题与关键属性置顶|主体内容+属性详情面板；次要字段渐进展开|此页面不证明时间线能力|详情布局可按对象组织|低频完整信息放折叠区；保留原文而非删掉|不引入自由建模或拖拽编辑器；不复制图标|
|HubSpot / 业务运营人员|官方说明与截图：记录预览边栏|摘要卡按角色重排，记录上下文不中断|此页仅证明记录预览|团队可配置预览重点|管理员连接摘要和就地检查；工作详情紧邻列表|不引入营销自动化、销售漏斗或50卡布局|

## 直接来源（官方）

- [Included Health App：真实首页、权益、服务与协作截图](https://includedhealth.com/get-the-app/)
- [MyChart 功能](https://www.mychart.org/Features)、[结果与 Care Companion](https://www.mychart.org/features/view-medications-test-results-bills/)、[帮助：比较结果趋势](https://www.mychart.org/l/en-us/help/?decisionTreeExpanded=1)
- [MyChart 医疗机构官方使用指南与截图](https://ccmhealthmn.com/wp-content/uploads/2024/10/MyChart-Quick-Start-Guide-2024.pdf)
  实际查看指南印刷页139的 Result Trends 界面：左侧结果筛选、日期范围、带坐标轴的折线、明细表与下载。此为2024指南中的示例，不代表2026所有机构的部署界面。
- [Teladoc Primary Care：负责医生与目标 App 图](https://www.teladochealth.com/individuals/primary-care)
- [One Medical App 官方指南](https://www.onemedical.com/blog/healthy-living/complete-guide-virtual-care-one-medical/)
- [Omada Progress：网页与移动端实际截图](https://support.omadahealth.com/hc/en-us/articles/115015679427-What-is-my-Progress-page)
- [Salesforce Health Cloud：360、Care Management 产品图](https://www.salesforce.com/healthcare/cloud/)、[官方功能说明](https://help.salesforce.com/s/articleView?id=ind.hc_core_features_in_health_cloud.htm&language=en_US&type=5)
- [Linear 筛选及列表截图](https://linear.app/docs/filters)
- [Notion 布局编辑与详情面板截图](https://www.notion.com/help/layouts)
- [HubSpot 记录预览与截图](https://knowledge.hubspot.com/object-settings/customize-record-previews)

## 观察转为 HealthOps 设计的规则

1. Member：第一动作源于 Task，照护关系源于计划/医生复核/服务记录。不是模仿聊天入口。
2. Health：先看可解释趋势，再展开全量指标比较、依据和病史；基线始终是冻结参考点。
3. Staff：事项队列保留筛选与排序，选中事项在旁边查看原因、责任、证据及动作。
4. Doctor：问题优先，相关趋势与依据在左，人工结论与交回责任在右。
5. Admin：连接状态→选中集成→检查/配置；技术诊断与兼容入口单独展开。
6. 不把竞品存在的能力加入本项目：家庭管理、开药、AI临床决策、真实设备、健康总分均不在本轮范围。

## 三种方向（实现前决策）

- A / 行动型：轻量首页、单主行动、负责人陪伴。优点是低认知负担；单独采用会弱化医学记录。
- B / 记录型：准确日期、单位、来源、结果与趋势。优点是可信；单独采用可能信息过密。
- C / 工作型：紧凑队列、上下文详情、快捷操作。优点是效率；不适合全部套在成员端。

最终：Member=A+B，Staff=B+C。不是竞品换色：沿用 HealthOps 医疗蓝和现有业务边界，重建空间、内容顺序与交互优先级。没有复制 Logo、文案、图片、图标组合或整页布局。
