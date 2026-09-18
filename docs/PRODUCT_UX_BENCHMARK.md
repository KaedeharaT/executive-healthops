# HealthOps 产品体验参考

研究日期：2026-09-18。仅使用公开产品资料；未复制页面、品牌、图标组合、截图或文案。设计服务于当前 Streamlit 的既有健康管理业务。

| 公开来源 | 可借鉴的信息架构与交互 | 本轮应用 |
|---|---|---|
| [Included Health](https://includedhealth.com/)；[人工协作与行动衔接](https://includedhealth.com/announcements/included-health-evolves-dot-from-answers-to-action-with-human-in-the-loop-support-always/) | 单一入口、从问题到行动、人工团队接续上下文 | 成员首页只列最重要行动；直接进入任务；显示负责人及下一步，不把自动化技术作为产品入口 |
| [Epic MyChart Features](https://www.mychart.org/Features) | 检查结果、用药、预约和提醒聚合；健康记录与偏好分离；当前与历史安排区别 | 健康概览/数据/体检/医疗档案；个人设置离开一级导航；过去预约不当作未来安排 |
| [Salesforce Integrated Care Management](https://trailhead.salesforce.com/content/learn/modules/integrated-care-management/meet-integrated-care-management)；[Health Timeline](https://help.salesforce.com/s/articleView?id=hc_timeline.htm&language=en_US&type=5) | 成员上下文中呈现目标、计划、干预及协作；按角色工作；时间轴可筛选追溯 | 健管今日工作队列 → 成员360；医疗协同使用相同待复核投影；结果回到计划与历程 |

## Member 体验
首页回答“今天做什么”，1—3个行动优先；基线和变化在健康页解释。保留人工负责人；不增加聊天入口。没有连续数据时用短句和下一步，不创建等大空卡片。

## Care Team 体验
工作列表同时显示成员、原因、状态、负责人、截止和下一步。重复业务实体不新增事实表。审批就地处理；计划和结果写入已有服务。医生聚焦问题与依据，运营人员聚焦执行。

## Timeline
默认呈现重要健康事件；更多筛选与原始依据逐步展开。结果只说明观察变化，不推断因果。用药、报告与基线保留各自来源，时间轴仅投影。

## Navigation
普通角色一级不超过5项。二级为页面内内容；选中事项的详情与表单不产生第三条业务路由。管理员的配置与成员健康、医生判断分离。

## Action hierarchy
每个操作上下文只保留一个主提交动作；列表选择是次级动作。状态不代替行动。显式文字与颜色同时表达状态，不用风险色装饰普通运营事项。
