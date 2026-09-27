# Member360 管理操作闭环

## 原因与改变

原来的概览按钮仅调用 `request_navigation(... member_section='管理')`。管理页默认显示任务表和工作分类，没有绑定具体事项，也没有完成后续接下一项的处理器。

现在概览、会员顶部摘要和管理工作区共享 `ManagementActionLoop.project`，从当前年度计划、开放任务、复查、服务、医生复核与阶段记录读取真实状态。优先考虑紧急风险、已到期工作、任务优先级和截止时间；选择结果绑定稳定记录 ID。点击概览的“处理下一步”直接打开该事项详情和相应业务表单。

没有新增数据库模型或第二套状态机。所有写入复用 `ManagementWorkflowService`、`TaskTransitionService`、`care_commands` 和 `MemberServiceOperations`；原管理工作分类、表格、日志、复查、阶段评估、服务及计划调整入口仍保留。

## 可实际操作的合成演示

从会员列表搜索 **Demo Executive A**，查看会员 → 概览 → 处理下一步：

1. **核对本周生活方式记录（合成）**：填写结果，选择完成程度及后续安排，点击“完成本次处理”。
2. **电话随访执行情况（合成）**：点击“继续处理下一项”，记录随访情况并完成。
3. **阶段健康沟通服务（合成）**：进入现有审核、安排、开始执行和结果回写操作。
4. **复核服务结果与下一步**：处理服务完成后由原业务服务生成的待办；它不会被漏掉或自动当作已完成。
5. **开始阶段复盘**：系统按已有记录整理完成事项、管理日志、复查和服务结果；健管核对指标与草稿，勾选确认后提交阶段总结。
6. **确认并进入下一阶段**：核对下一阶段目标、已有安排和第一件管理事项，确认后直接打开新事项。

用户始终留在同一会员内。正常管理工作区顶部可见“下一件要做”，另有新增管理记录、创建随访、安排复查、申请服务及提交医生判断五个快捷入口。

当前原 Demo 记录已归档，因此另建了明确标识的合成 Demo Executive A；没有恢复或覆盖原归档历史。`scripts/seed_management_action_loop.py` 为幂等补充脚本，已有演示进度不会被重置。浏览器完成操作全部发生在隔离数据库副本；正常平台中的新演示链保留待处理状态。

## 边界与无断点状态

| 状态 | 用户可做的下一步 |
| --- | --- |
| 普通管理 / 随访 | 写入结果和管理日志；完成后重新查询下一项 |
| 部分完成 / 未完成 | 必填跟进日期，保留原开放任务，不制造 Completed |
| 复查 | 使用原状态推进表单及报告、医生复核校验 |
| 服务 | 使用原审核、安排、执行、结果回写，不跳过业务流程 |
| 风险 / 医生判断 | 进入原风险或医疗工作流，普通结果表单拒绝代替处理 |
| 无开放事项、阶段尚未完成 | 固定快捷动作；没有计划时提供原计划创建入口 |
| 阶段工作结束 / 已到复盘时间 | 开始阶段复盘；有取消或未处理事项时不宣称全部完成 |
| 阶段复盘已确认 | 展示下一阶段草稿，人工确认后推进 |
| 医学判断未完成 | 保留医生入口，阻止进入下一阶段 |

没有实际调用 LLM 时不显示 AI 已完成。阶段草稿来自实际记录，不能替代医学判断。正式风险、健康基线、Agent 安全与医生责任逻辑均保持原业务服务约束。

## 验证与复现

- 基线：`baseline-action-loop/final-tests.txt`，763 passed / 0 failed。
- 最终全量：`final-verification/final-tests.txt`，778 passed / 0 failed（15 个新增用例）。14 条 warning 为既有依赖弃用提示及隔离目录的 pytest 缓存写入提示，不影响测试执行。
- 新增 15 个行为 / Streamlit AppTest 用例，覆盖优先事项、随访、部分完成、幂等与会员归属、复查门槛、日志后续、服务结果后续、空状态、阶段复盘和下一阶段。未来阶段计划仍保留在表格中，但不会抢在本阶段复盘与人工交接之前。
- 原入口测试更新为验证 Member360 → 管理工作区 → 原服务入口的实际委托关系。
- Chromium：1440×900，从可见菜单和按钮进入；未注入 Session、未使用内部 URL 跳转。详见 `../images/management-action-loop/browser-results.json`。
- 补充浏览器检查：表格行打开事项并返回、创建随访、安排复查、申请服务、医生协同表单均可正常使用，见 `quick-actions-browser.json`。管理日志保存后创建的随访也已实际进入处理表单。
- 10 张截图：`../images/management-action-loop/`，包含具体事项表单、完成后下一项、服务操作、阶段复盘、下一阶段确认及管理工作区。

运行回归：

```powershell
.venv/Scripts/python.exe -X utf8 scripts/verify_neumorphism_suite.py docs/management-action-loop/final-verification
```

重新验收浏览器（确保正常 Demo 链尚未完成）：

```powershell
.\scripts\stop_platform.ps1 -Instance management-action-loop
.venv/Scripts/python.exe -X utf8 scripts/qa_management_action_loop.py --prepare
.venv/Scripts/python.exe scripts/service_processes.py start --instance management-action-loop --profile qa --manifest .runtime/management-action-loop/manifest.json
.venv/Scripts/python.exe -X utf8 scripts/qa_management_action_loop.py
.\scripts\stop_platform.ps1 -Instance management-action-loop
```

QA 使用隐藏进程，PID 与日志仍由现有进程管理器保存。正常平台启动方式不变；本次不推送远端。
