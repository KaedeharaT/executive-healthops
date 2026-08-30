# Product / Page Architecture

来源：当前 `streamlit_app.py` 的 `main()`、`render_member_client_view()`、`render_member_detail()`、`render_more_workspace()`、`render_collaboration_workspace()` 和 `render_service_operations_workspace()`。状态只描述当前代码，不代表生产级身份认证或临床规则就绪。

## 成员健康中心

```mermaid
flowchart TB
  center[成员健康中心\n开发预览；无登录/RBAC\n🧪]
  home[首页\n当前状态、今天、最近变化、下一步\n✅]
  health[健康\n✅]
  plan[计划\n✅]
  service[服务\n🧪 服务目录]
  mine[我的\n🟡]

  overview[健康概览\n基线/风险/主要问题\n✅ 同页展开]
  data[健康数据\n日常/医疗监测/趋势\n✅ 同页指标展开]
  reports[体检\n上传 + 报告列表/详情/依据\n✅ 同页]
  medical[医疗档案\n用药/手术住院/医生意见/病史\n🟡 同页切换]
  timeline[健康历程\n趋势/范围/生命轴/Inspector\n✅]
  current[当前方案\n✅]
  tasks[我的任务\n✅]
  outcomes[阶段结果\n🟡]
  available[可用服务\n✅ 同页服务详情]
  requests[我的申请\n✅ 同页详情]
  records[服务记录\n✅ 同页详情]
  profile[资料 / 设备与数据 / 隐私授权\n🟡]

  center --> home
  center --> health --> overview
  health --> data
  health --> reports
  health --> medical
  health --> timeline
  center --> plan --> current
  plan --> tasks
  plan --> outcomes
  center --> service --> available
  service --> requests
  service --> records
  center --> mine --> profile
```

成员中心的一级导航固定为五项：`首页 / 健康 / 计划 / 服务 / 我的`。图中的第二行是同一业务页内的 Streamlit segmented radio；选中报告、指标、服务、依据或时间轴事件均在当前页面显示，不产生第三层路由。

## HealthOps 运营后台

```mermaid
flowchart TB
  ops[HealthOps 运营后台\n开发预览；无 RBAC\n🧪]
  today[今日\n状态筛选 + 工作列表\n✅]
  members[成员\n成员卡列表\n✅]
  collab[医疗协同\n✅]
  serviceops[服务运营\n状态筛选 + 列表/Inspector\n✅]
  more[更多\n平台工具\n✅]

  overview[概览\n当前重点、下一步、变化、历程预览\n✅]
  management[管理\n方案、任务、依从性、复盘、结果\n🟡]
  health[健康\n数据/体检/基线/健康史/健康历程\n✅ 同页切换]
  medical[医疗\n医生/用药/检查/手术住院\n🟡 同页切换]
  memberservice[服务\n权益、申请、进行中、历史\n🧪]
  internal[内部医生\n复核事项\n✅ 同页处理]
  external[外部医疗\n转诊、预约、反馈\n🟡 同页处理]
  devices[设备\n数据接入与成员分配\n🟡]
  knowledge[知识库\n✅]
  rules[风险规则\n✅ 引擎管理；🧪 仅 TEST 规则]
  audit[操作记录\n✅]
  system[系统\n🟡]

  ops --> today
  ops --> members --> overview
  members --> management
  members --> health
  members --> medical
  members --> memberservice
  ops --> collab --> internal
  collab --> external
  ops --> serviceops
  ops --> more --> devices
  more --> knowledge
  more --> rules
  more --> audit
  more --> system
```

运营后台的一级导航固定为五项：`今日 / 成员 / 医疗协同 / 服务运营 / 更多`。记录详情、报告依据和服务履约详情采用同页列表 + Inspector / 展开区，不属于新业务导航层。

## 可发现性与状态审计

| 页面/能力 | 代码状态 | 重要现实限制 |
|---|---|---|
| 两级导航约束 | ✅ | Streamlit session state 实现，不是 URL 路由或访问控制。 |
| 报告上传与同页详情 | ✅ | 解析候选确认仍限运营端；成员端可上传和查看已整理结果。 |
| 健康时间轴 | ✅ 动态聚合 | 连续设备读数先进入趋势，仅阶段健康数据摘要进入生命轴。 |
| 医疗协同 | ✅ 内外两类 | 外部医疗以登记、状态与反馈为主，无外部医院系统集成。 |
| 服务运营 | ✅ 同页队列 | 初始权益使用演示服务计划；当前不代表真实履约系统。 |
| 隐私与授权 | 🟡 文案与模型 | 未发现登录、访问控制或可操作授权管理流程。 |
