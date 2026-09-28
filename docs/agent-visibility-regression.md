# Agent 可视化回归修复

## 根因与真实复现

基线是 `b134b34`，开始前创建 `backup/pre-agent-visibility-regression-fix`。使用真实 Chromium 从普通健管首页进入，未通过内部路由或 session state 注入打开页面。

1. **今日工作存在导航残留问题。** 首次进入，健康管理助手实际可见。点击工作事项，再切换会员、返回侧栏今日工作，旧 `today-detail` 没有清理，`workbench.today()` 提前返回事项详情，助手完全不渲染。`care-detail` 也有相同的顶层提前返回路径。修复前截图为 `before-today-stale-selection.png`，页面文本中没有助手标题。
2. **Member360 无实例时直接隐藏整块。** 当前运行库中，`scripts/seed_management_action_loop.py` 创建的 Demo Executive A 是 `demo-management-action-loop-a`，没有 Agent 历史。历史验收的 `data/portfolio_demo.db` 使用另一会员记录，包含体检管理完成历史。相同显示名不能视作同一会员、不能跨库挪用历史。原 `member_summary()` 在没有目标时直接 `return`，因此当前 Demo 的自动跟进不可见。
3. **入口位置不利于管理流程。** 自动跟进原本位于概览的阶段、趋势、开放事项和年度基线之后，管理页不显示。`b134b34` 将“处理下一步”直接引向具体事项，让健管更常停留在管理页。

对比 `git diff b134b34^ b134b34`：没有删除 Today 助手、运行看板或 AI/知识组件；没有证据表明 COMPLETED 过滤导致整个 Today 模块消失。不能将此次问题简单归为“最近提交删除了 Agent”。

## 修复

- 侧栏切换工作区时清理 Today 的嵌套详情选择并重置表格选择代次；管理事项与阶段状态保持原样。看板按钮保留原实例编号，并清除旧工作事项选择。
- 今日工作保留计数、最多三张活动卡片、独立完成历史；没有活动流程时显示明确空态及最近运行入口。完全没有实例时禁用查看按钮，不创建假运行。
- 同一个 `member_summary()` 在 Member360 概览和管理页顶部展示；无实例时保留自动跟进说明，有实例时继续显示真实状态、进度、最近完成和下一步。
- 健康资料导入的卡片、Member360 和原看板共享持久化计划步骤；体检流程仍使用原六步看板。
- AI/知识支持继续读取真实调用记录，无调用时明确显示未使用；失败或不可用不标记为成功。
- 未改变 Agent 状态机、医学责任、Risk Engine、业务创建命令或 `b134b34` 的管理操作闭环。

## 浏览器验证与数据边界

截图目录：[agent-visibility-regression](images/agent-visibility-regression/)。

- `18580`：从当前运行库创建的隔离副本，复现旧选择问题并完整执行管理闭环。浏览器记录位于 `management/browser-results.json`。
- `18581`：通过既有服务建立合成会员与管理事项，从普通医疗页面实际上传报告，健管提交医生，医生提交意见，健管确认行动。数据库状态通过真实业务命令进入 WAITING_MANAGER、WAITING_DOCTOR、COMPLETED；没有直接修改状态或伪造调用记录。
- `8501`：重启当前服务后，只读检查真实首页与 Demo Executive A。今日工作和自动跟进区域均可见。该会员尚无运行历史，按钮禁用并说明如何通过资料上传启动真实流程；没有向运行库植入验收 Agent。
- Today、Member360 概览及管理页的入口通过可见控件进入同一看板；以看板控件绑定的实例与数据库唯一记录交叉核对。完成后继续使用同一个实例。
- 知识检索返回真实的 1 条已审核合成依据；本次摘要调用发生超时，界面显示暂不可用。普通页面不显示技术字段、原始调用载荷或标识符。

验收在多次浏览器会话中续跑同一个实例：脚本先适配了现有表格控件键、医生提交按钮及角色弹层，之后继续原流程；没有回写状态来重演截图。`browser-results.json` 记录最后的完成态验证与实际调用，下面的验收映射汇总各会话已验证的页面。医生意见整理同样发生实际超时，流程使用已有规则结果继续，未将其伪装为 AI 成功。

| 状态 / 路径 | 实际结果 | 证据 |
| --- | --- | --- |
| WAITING_MANAGER | 可见，1 条待健管确认 | 01、02、03 |
| WAITING_DOCTOR | 可见，1 条等待医生 | 08 |
| COMPLETED | 独立历史、完成结果及原实例看板 | 04、09、10 |
| 无活动，有历史 | 保留空态和查看最近运行 | 04 |
| 无任何实例 | 保留区域，明确说明并禁用查看 | 05、06 |
| 管理闭环 | 全链条通过，会员上下文保留 | management/browser-results.json |
| 当前运行服务 | 助手、资料导入看板、侧栏返回通过 | 11、12 |

要求的五张截图分别覆盖等待健管、会员自动跟进、运行看板、已完成历史及无活动空态。补充截图覆盖等待医生、AI/知识、完成看板、会员完成状态与实际 8501 页面。截图均需结合浏览器记录读取，不能把隔离案例描述成当前运行会员已经拥有的历史。

## 复验

1. `.venv/Scripts/python.exe scripts/prepare_agent_visibility_regression.py` 建立独立合成库（已有库时拒绝覆盖）。
2. 使用 `scripts/service_processes.py start --instance visibility-scenario --profile qa --manifest .runtime/agent-visibility-regression/scenario-manifest.json` 启动。
3. `.venv/Scripts/python.exe scripts/qa_agent_visibility_regression.py` 从正常首页执行。模型服务可选，其成功、失败与未使用均以实际记录为准。
4. `scripts/qa_management_action_loop.py` 支持 `HEALTHOPS_QA_URL`、`HEALTHOPS_QA_OUTPUT`，在独立当前库副本中复验原闭环，避免覆盖历史验收证据。
5. `.venv/Scripts/python.exe -m pytest -q`。测试共用 `.runtime/pytest_app.db`，应串行启动 pytest 进程。

全量回归：**787 passed / 0 failed**，13 条原有弃用警告。全量测试期间补充了资料导入进度复用和两项回归用例，最终另运行覆盖资料导入、助手、真实 AI/知识、管理闭环的定向回归：**77 passed / 0 failed**。本次共新增 11 项回归用例，包含四状态实际渲染、同实例导航、完成历史、无记录空态、资料导入计划进度与活动卡片上限。

测试输出：[全量](images/agent-visibility-regression/full-tests.txt)、[最终定向回归](images/agent-visibility-regression/final-focused-tests.txt)。

仅本地提交，不 push。
