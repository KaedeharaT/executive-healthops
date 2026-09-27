# OLD vs NEW — 可见变化与证据

本轮基于 `3b78204`。原先的“视觉重构完成”判定撤回：备份版本与该提交的页面结构过于接近，上一轮按本轮标准判定 **VISUAL REDESIGN = FAIL**。

另一个已证实的问题是原有 `http://127.0.0.1:8501` 服务仍返回旧界面：背景变量为 `#f4f7fa`，本次 Header / Summary 容器均为 0。已保留该进程原有环境配置重新启动，仅重载 Streamlit UI；再次真实打开后，背景为 `#dce5ef`，两个新容器均存在，无页面异常。数据库配置、API 和 worker 未改变。见 [运行服务检查](live-service.json)。

## 对照条件

- `18501`：`backup/pre-neumorphism-redesign` 的原始代码快照。
- `18502`：`3b78204` 的原始代码快照。
- `18503`：本轮修改。
- 三份相同 Demo 数据库副本；截图完成后 SHA256 仍相同：`4cddac460025f93a00b23136dca08e9ae87e37094f60ab1d8921e1ca8f43c506`。
- Chromium 151.0.7922.34，视口 1440×900、deviceScaleFactor=1，相同角色、会员、页面、指标、时间范围和初评步骤。
- 每个截图点在三个浏览器之间同步；滚动偏移逐项核对相同。深区截图若旧页面较短，三者共同采用相同的可达偏移。
- OLD / NEW 直接拼接真实 PNG；50% 图等比例缩小，没有修改页面内容。蓝色 pixel diff 表示任一 RGB 通道变化大于 16。

## 本轮六个核心页面

这里 OLD = `3b78204`，NEW = 本轮修改。点击“50%”直接看缩小后的并排图。

| 页面 | OLD 实际视觉 | NEW 实际视觉 | 截图 |
| --- | --- | --- | --- |
| 今日工作 | 标题、横排数字和助手纵向堆叠 | 蓝色标题与摘要合并；助手状态内凹；活动流程按来源/已完成分栏 | [Before](../images/neumorphism-v2/previous/01-today.png) · [After](../images/neumorphism-v2/revised/01-today.png) · [50%](../images/neumorphism-v2/previous-vs-revised/01-today-50pct.png) |
| Member360 | 会员信息为紧凑文字横排，导航像 Radio | 身份区、年度/责任/阶段区、关注区、下一步分层；等宽分段导航 | [Before](../images/neumorphism-v2/previous/03-member360.png) · [After](../images/neumorphism-v2/revised/03-member360.png) · [50%](../images/neumorphism-v2/previous-vs-revised/03-member360-50pct.png) |
| 健康档案 | 六个简单摘要格，标题与详情表连续排列 | 初评优先；七类图标/状态/说明网格；完整表格独立面板 | [Before](../images/neumorphism-v2/previous/04-archive-details.png) · [After](../images/neumorphism-v2/revised/04-archive-details.png) · [50%](../images/neumorphism-v2/previous-vs-revised/04-archive-details-50pct.png) |
| 健康趋势 | 指标与时间控件上下排列，摘要偏平面 | 并排内凹筛选区、浮起统计带、独立白底图面、数据说明区 | [Before](../images/neumorphism-v2/previous/06-trends-chart.png) · [After](../images/neumorphism-v2/revised/06-trends-chart.png) · [50%](../images/neumorphism-v2/previous-vs-revised/06-trends-chart-50pct.png) |
| Agent 看板 | 标题在面板外，六步是细线圆点 | 标题合入 Header，内凹摘要带，大型六步流程，业务面板重新分组 | [Before](../images/neumorphism-v2/previous/02-agent.png) · [After](../images/neumorphism-v2/revised/02-agent.png) · [50%](../images/neumorphism-v2/previous-vs-revised/02-agent-50pct.png) |
| 初始评估 | Stepper 实际被旧 CSS 压成细长竖列 | 横向十一项网格、蓝色当前步骤、独立表单和操作带 | [Before](../images/neumorphism-v2/previous/05-assessment-form.png) · [After](../images/neumorphism-v2/revised/05-assessment-form.png) · [50%](../images/neumorphism-v2/previous-vs-revised/05-assessment-form-50pct.png) |

完整内容实拍：[初评步骤](../images/neumorphism-v2/details/assessment-stepper.png)、[初评表单](../images/neumorphism-v2/details/assessment-form.png)、[档案七类摘要](../images/neumorphism-v2/details/archive-grid.png)、[工作表格](../images/neumorphism-v2/details/today-table.png)。

上一轮的六页真实 OLD / NEW 也保留在 [original-vs-previous](../images/neumorphism-v2/original-vs-previous)，没有用本轮新版冒充上一轮成果。

## 打开截图后的人工视觉检查

以下判断来自逐张打开原图和 50% 并排图，不由测试或像素比例决定。

- 今日工作：①全屏灰蓝底层；②左右分区的标题/摘要 Header；③助手内凹状态带；④活动流程左右布局；⑤表格所属的内凹筛选栏。最近完成保持紧凑记录，没有改为大卡。
- Member360：①身份标记与姓名组；②年度/责任/阶段独立信息区；③会员关注与专业重点分栏；④明确的下一步横带；⑤全宽等距分段导航。
- 健康档案：①初评移至导入入口前；②初评主面板左侧医疗蓝强调；③七类摘要按四列组织；④统一线性图标、状态及说明；⑤完整详情表有自己的表面边界。
- 健康趋势：①完整外层分析面板；②指标和时间并排；③筛选区域明显内凹；④当前/基线/变化/测量时间形成一条浮起统计区；⑤图表白底与下方说明各自清晰分区。轴、单位、Baseline、Current 均保留。
- Agent 看板：①标题与业务身份合入 Header；②运行摘要内凹；③大型六步流程；④当前步骤凸起、完成步骤绿色；⑤系统发现/风险区移至人工历程前，人工参与和下一步分别成区。证据与最终产出仍保留。
- 初始评估：①独立评估 Header；②步骤区完整内凹；③十一项步骤横向网格；④当前步骤为蓝色、已保存有文字与勾选；⑤表单、分割线、底部草稿/继续操作带明显分层。

## Pixel diff

首屏六页变化区域比例：今日工作 **54.08%**、Member360 **68.70%**、健康档案 **59.18%**、健康趋势 **62.65%**、Agent **57.52%**、初评 **73.97%**。

比例包含背景变化，不能作为美学证明。因此同时记录 108 个区域的变化分布、图像边缘变化，并以上述人工检查确认布局确有变化。所有原图、并排图、50% 图、蓝色 diff 均保留；[完整数值](../images/neumorphism-v2/previous-vs-revised/pixel-diff.json)。

## 保留、测试和 Skill

- 原有 **705 / 705** 控件、表格、图表和流程调用的完整参数契约保留；Deleted **0**，Missing **0**，Actions removed **0**。
- `3b78204` 中的 **6,863** 个中文可见文案片段保留；HTML 容器重组不计作文字删除。
- **112 / 112** 个受保护的业务 Service、Agent、模型、迁移及图表文件 SHA 不变。
- **14** 个匹配页面/滚动视图逐项比对，控件无缺失，表格和图表数量相同，页面错误 **0**。三个数据库副本仍一致。见 [browser-evidence.json](browser-evidence.json) 与 [preservation-results.json](preservation-results.json)。
- 主视口 1440×900，另检查 1366×768、1920×1080、390×844；页面无水平溢出。检查渲染文字及原生表格表头对比度、键盘焦点、按钮交互与 Reduced Motion；结果见 [控件状态检查](../images/neumorphism-v2/details/checks.json)。
- 全量原测试：**703 passed / 0 failed，13 warnings**，见 [测试日志](final-tests.txt)。未修改测试以迁就 UI。最后按钮按下/禁用态与紧凑历史按钮的 CSS 由真实浏览器补充验证。
- 实际重新读取：`D:/executive_health_ai/.agents/skills/ui-ux-pro-max/SKILL.md`；重新检索 Neumorphism、Soft UI、Healthcare SaaS、Enterprise Dashboard、Accessibility 规则。采用 Neumorphism / Soft UI Evolution / Data-Dense Dashboard 的适用规则，保留可见边框和 4.5:1 文字目标。
- 实际最终 Token：[MASTER.md](../../design-system/healthops/MASTER.md)。技术栈仍为 Streamlit；未隐藏入口、增加折叠层级或删除说明。

| 本轮判定 | 结果 |
| --- | --- |
| Visual difference obvious at 50% scale | YES |
| Layout visibly changed | YES |
| Surface hierarchy visibly changed | YES |
| Buttons visibly redesigned | YES |
| Inputs visibly redesigned | YES |
| Tabs visibly redesigned | YES |
| Agent board visibly redesigned | YES |
| Deleted / Missing / Actions removed | 0 / 0 / 0 |
| Tests | 703 / 0 failed |
| Push | NO |
