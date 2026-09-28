# V7 验收记录

日期：2026-09-29。备份：`backup/pre-v7-workspace-redesign`（`6758e54`）。

## 真实页面

使用 Playwright 驱动真实 Chromium `151.0.7922.34`，视口 `1440 × 900`，从角色首页及公开导航进入。未使用内部详情 URL。

| 工作区 / 主线 | 结果 | 证据 |
|---|---|---|
| 今日工作 → 具体事项 → 返回工作队列 | PASS | After 01、Story 01 / 11 |
| 会员行 → 同一 Member360 | PASS | After 02 / 03 |
| 三文件上传 → 本地 AI → 等待确认 → 完成 | PASS | After 04 / 05、browser-result.json |
| 例外逐项处理，不遍历 11 步 | PASS | After 06；自动预填 10 项，人工补充 6 项 |
| 当前阶段 → 具体任务 → 完成 | PASS | After 07、Story 02 |
| 阶段复盘 → 一次确认 → 下一阶段首项 | PASS | After 08、Story 01 / 02 |
| 年度表 → 同一会员年度管理 | PASS | After 09、Story 05 |
| 服务审核 → 预约 → 执行 → 结果回写 | PASS | After 10、Story 03 / 04 / 06 |
| 提交医生 → 等待 → 判断返回 Today | PASS | After 11 / 13、Story 07–10 |
| 专项管理 | PASS | After 12 |
| 成员首页及五个主要入口 | PASS | After 14、控件 inventory |
| 管理员及组织与人员入口 | PASS | After 15、控件 inventory |

真实资料进度观察到 `0 → 14 → 29 → 43 → 71 → 100%`；本地 AI 请求期间固定于真实步骤 `29%`，文件进度 `2/3`，等待健管后 spinner 停止。知识库显示本流程未使用。已提交后仍有“继续健管确认”，没有跳过原有专业确认及医学边界。

合成写入验收使用隔离副本。正式数据库未删除、重建或重置。正式 `8501` 在最新源代码下冷启动后，又通过 Chromium 只读打开今日工作、Member360 概览/健康档案/管理、服务管理、年度管理，均无页面异常。

## 正式服务

2026-09-29 00:13 后核验：

- `http://127.0.0.1:8501/_stcore/health`：200。
- `http://127.0.0.1:8501`：200。
- `http://127.0.0.1:8000/health`：200。
- Streamlit、FastAPI、Agent worker：UP，进程创建时间与当前启动记录一致。
- 本次启动后没有新增运行异常；追加日志中的旧异常未清空，也未当成本次异常。

## 回归验证

最终全量：`python -m pytest -q`，**917 passed / 0 failed**，耗时 556.99 秒。13 个已有依赖弃用警告，未产生测试失败。

最后的初评布局及提交后入口检查：`tests/test_intake_exceptions.py tests/test_intake_workspace_v2.py tests/test_v7_workspaces.py`，**70 passed / 0 failed**，耗时 29.49 秒。这是上述测试的定向复验，不重复计入 917。

新增 18 个 V7 参数化用例，覆盖单主 CTA、同一会员/年度上下文、表格行入口、例外优先、统一真实进度、等待停止旋转、阶段复盘一次提交及医生双入口。原有业务、医学安全、真实进度和防写事务占用测试继续运行。现有 UI 断言随公开导航改动更新，未移除业务断言。

## 交付范围

可点击控件 248 → 205；可见按钮 93 → 49；同上下文重复入口移除 6；旧渲染函数移除 6；主 CTA 每页最多 1；常规导航最大 3 层。详细统计口径及逐页变化见 [BEFORE_AFTER.md](BEFORE_AFTER.md)。

业务能力删除 0。未修改数据库 Schema、Risk Engine、DoctorReview、Agent 状态机或本地 LLM 配置。未 push。
