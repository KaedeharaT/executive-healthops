# HealthOps V7 · Restrained Soft Neumorphism

基线：`707b26c`。备份：`backup/pre-v7-neumorphism-restore`。

本轮使用项目内 `ui-ux-pro-max`，采用已核对的 Neumorphism 风格指导：双色柔影、轻凹输入、可见焦点、文字对比和 reduced-motion。技能自动推荐的营销 Hero / Testimonials 模式不适用于本工作台，未采用；医疗蓝与 V7 信息架构按本轮要求保留。

## 单一视觉入口

`src/executive_health_ai/ui/operations_styles.py` 定义正式 Token 与共享组件皮肤。`styles.role_styles()` 统一加载。医生和管理员仅降低主工作面的阴影强度，复用同一配色与组件。

| Token | 用途 / 值 |
|---|---|
| page-bg | 医疗蓝灰背景 `#EAF1F8` |
| surface | 同色系基础表面 `#EDF3F9` |
| surface-raised | 工作表面 `#F0F5FA` |
| surface-inset | 输入与进度轨道 `#E6EEF6` |
| border-soft | `#D4E0EC` |
| shadow-light / shadow-dark | 白色高光 / 低透明度蓝灰阴影 |
| shadow-raised | `6px 6px 16px` 与反向高光 |
| shadow-quiet | `3px 3px 9px`，用于身份区和摘要 |
| shadow-inset / shadow-pressed | 输入、选中状态、按压反馈 |
| text-primary / text-secondary | `#20354C` / `#52677D` |
| medical-blue | `#1969B4` |
| success / warning / danger | `#26734D` / `#946018` / `#AE3939` |
| radius-sm / md / lg | 12 / 16 / 20px |
| radius-pill | Badge、进度轨道 |

## 组件映射

| 共享组件 | 当前实现 | 强度 |
|---|---|---|
| Panel | 原有 v7-main、v2-panel 工作容器 | 当前工作较强；普通面板轻 |
| SummaryCard | 原有右侧摘要、v2-summary | 轻，不给每个数字套 Card |
| PrimaryButton / SecondaryButton | 原生 Streamlit button / form submit | 医疗蓝或浅色轻凸，按下轻凹 |
| SegmentedTabs | 原生水平 radio，保留键盘语义 | 选中 inset |
| InsetInput | 原生文本、选择、数字及多行输入外壳 | inset；适配当前 React Aria DOM |
| AgentProgressPanel | 原组件、原真实进度投影 | 强工作面；12px 凹轨道、18px spinner |
| StatusBadge | 原有 status-badge / ux-badge | 平整 pill，保留文字语义 |
| Table / Timeline | 原生表格与原时间轴 | 平整，无行级阴影 |

Agent 与初评分区卡片的局部 CSS 已归并到共享样式。没有新增第二套组件 Renderer、路由或 Agent。

原生文件进度只装饰 `stProgressBarTrack`，保持填充元素的真实 transform 比例；不对外层容器着色冒充完成量。整体百分比、文件计数、spinner 条件及超时处理均不变。

## 保护范围

未更改导航、表格选择、Tab 数量、例外处理、阶段复盘、年度/服务/医疗/专项流程。未增加按钮、卡片 DOM 或页面层级。无 Schema、业务 Service、Risk、DoctorReview、Agent 状态机或 LLM 修改。

## 浏览器验收

实际 Chromium `151.0.7922.34`，1440×900，从公开菜单点击；无内部详情 URL。Before 为真实 `707b26c`，After 为当前代码，使用相同合成数据副本。正式 Demo 数据库未重建。

- 14 个静态页面状态：可见按钮 **49 → 49**，可点击控件 **205 → 205**，每页强 CTA **≤1**。
- 页面无横向溢出；文档宽 1440px，主工作区宽与滚动宽均 1230px。
- 相同状态页面高度没有增加：多数完全相同，Member360/管理/复盘减少 1px，健康档案减少 23px，初评草稿减少 14px（移除原局部 style 输出产生的间距）。
- 导航层级沿用 V7，最大 3；旧重复入口恢复 0。
- 实际上传问卷、体检文本与自由文本档案，捕获 29% 真正 AI 执行和 2/3 文件进度；进入等待健管后停止 spinner。
- 14 张主要截图中的运行与例外是动态故事状态；控件统计使用两版相同的 14 个静态状态，不混用不同数据计算减量。

原始控件和几何信息位于 `docs/images/v7-neumorphism/{before,after}/inventory.json`。

14 张 Before / After 截图分别保存在上述目录，汇总为 `metrics.json`。可用 `scripts/qa_v7_neumorphism.py --port 18595` 重做公开菜单与布局检查；`--before --port 18594` 用于已准备好的隔离基线实例。运行截图和例外截图来自真实三文件整理及人工核对，不用定时器或静态 HTML 模拟 Agent。

正式 8501 已冷启动加载本轮视觉。Chromium 再次打开今日工作、Member360 概览/健康档案/管理、服务管理和年度管理，无页面异常。Streamlit health、主页与 FastAPI health 均返回 200，Agent worker 正常。

## 测试

**162 passed / 0 failed**。覆盖 V7 工作台、navigation depth/performance、Agent progress、management action loop、intake workspace、Agent visibility、UI dedup、information architecture、role experience、core surfaces。

未新增业务测试或改写原有业务测试。此轮仅视觉样式及局部 CSS 归并，未重新运行全部 917 个测试；上一轮全量基线为 917 passed / 0 failed。

未 push。
