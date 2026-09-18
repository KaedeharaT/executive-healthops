# UX 实屏与交互验收

日期：2026-09-18。实际启动 Streamlit，并以 Chromium / Playwright 访问本机页面。内置浏览器运行时未提供可用浏览器，使用本机浏览器自动化完成验收；不是只运行 AppTest。

## 环境与边界

- 桌面：1440 × 1080；成员窄窗口：640 × 960。
- 数据：`data/portfolio_demo.db` 的隔离副本 `.runtime/ux_visual3.db`。截图无真实成员资料。
- 所有业务提交发生在隔离副本；普通开发数据库未用于验收。
- 角色预览不代表真实登录。AI连接测试使用不可用的本机地址，验证失败不会显示为已连接。

## 实际交互

| 路径 | 验证行为 | 结果 |
|---|---|---|
| A 成员 | 首页去完成 → 计划确认完成 → 健康数据；任务完成持久化 | PASS |
| B 健管 | 今日处理 → 成员360管理 → 审批接手 → 调整计划 → 安排随访 → 录入阶段结果并生成下一行动 | PASS |
| 计划创建 | AppTest经正常导航建立新计划、选择新计划并调整；数据库验证目标与随访/结果 | PASS |
| C 医生 | 待复核详情 → 读取“暂无原始依据”提示 → 人工判断 → 已完成 → 健管看到跟进任务 | PASS |
| D 管理员 | 系统 → 集成 → AI连接测试；失败提示与不发送成员数据的边界 | PASS |
| 系统状态 | 实际查询数据库可达性与待处理自动化数量；独立浏览器页面无异常 | PASS |

## 视觉检查

- 首页保持单一首要任务按钮，空状态为短句；没有全量资料卡墙。
- 健管以紧凑工作行展示原因、下一步、责任人和截止；只把实际截止视为逾期。
- 成员360使用左右聚合摘要，基线与管理/服务同屏；完整处置展开后显示。
- 医生问题、依据完整度、用药与人工结论有明确层次；提交按钮紧接执行责任说明。
- 管理员集成状态明确区分未配置、已配置待测试、模拟适配器和真实连接；技术诊断不默认展开。
- 统一医疗蓝；普通导航选中态不再使用风险红。风险与工作状态均有文字。
- 窄窗口成员行动与按钮自然换行；未发现遮挡、不可点击或整页横向溢出的阻断问题。
- 截图分为首屏与需要滚动的操作表单；Streamlit内部滚动区域不能仅以 full_page 参数声称已检查整页。
- 历程将已关闭风险标为历史记录，原处置建议标注“当时记录”；不会把过去的建议当作当前行动。

阻断视觉问题：0。未把可点击自动等同于视觉合格，已实际查看截图并修正侧栏挤压、关键指标顺序和成员360密度。

最终全量回归：438 passed / 0 failed / 0 skipped（256.07秒）。浏览器再次完整执行 A—D 和上下文审批，所有路径通过；默认检查视图的指定技术字段及UUID检出数为0。此验收针对Portfolio角色体验，不代表真实身份认证、真实设备连接或临床生产验收。

## 可重复执行

先将匿名demo数据库复制到新的隔离文件，以对应 DATABASE_URL 启动 Streamlit，再执行：

```powershell
.\.venv\Scripts\python.exe scripts/qa_role_experience.py --url http://127.0.0.1:18503 --exercise
```

`--exercise` 会提交演示业务操作，仅用于一次性的demo副本。不加该参数只浏览和截图。Playwright为本机验收工具，不是应用运行依赖。

## 截图

- [member-home](images/member-home.png)
- [member-health](images/member-health.png)
- [member-plan](images/member-plan.png)
- [member-timeline](images/member-timeline.png)
- [member-home-narrow](images/member-home-narrow.png)
- [manager-today](images/manager-today.png)
- [member-360](images/member-360.png)
- [doctor-review](images/doctor-review.png)
- [doctor-review-decision](images/doctor-review-decision.png)
- [admin-integrations](images/admin-integrations.png)
- [member-360-outcome](images/member-360-outcome.png)
