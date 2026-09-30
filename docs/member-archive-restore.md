# 会员归档入口恢复

> 历史验收记录：后续按用户要求移至会员列表，当前入口与验证见 [会员列表删除入口](member-list-removal.md)。

基线：8163873。复用 MemberArchiveService 的归档事务、关联工作停止与迟到写入保护；没有新增删除引擎、数据库模型或恢复能力。

## 原因与修复

旧归档 Service 和确认框仍在，但入口留在会员列表的“会员管理”里，Member360 Header 没有入口。归档详情路由还直接退回列表，普通健管无法查阅已归档会员。

现在唯一业务入口为 **会员 → Member360 → Header 右上角 ··· → 归档会员**。删除旧列表入口；打开确认框自动收起菜单。姓名必须完全相同，空值、错误姓名和尾随空格均不能确认。关闭或取消不会归档。

运行状态检查在现有归档锁内再次执行。MemberAgent 或 Goal 运行中时，默认归档拒绝；用户明确选择“停止当前流程并归档”后才复用原取消机制。等待状态沿用同一安全归档流程，不将取消冒充完成，不将未决医学问题标记解决。

归档事务保留 MemberAgent、Goal 和旧 Trace；忽略未执行的统一事件、清除后续唤醒时间，保留事件来源和审计。既有迟到事件/写入保护继续工作。没有改动 AI Native 架构、Risk Engine 或医生边界。

会员列表默认“在管”，可筛选“已归档”。归档 Member360 显示“已归档”，固定五个 Tab 只读，不复用可写的工作页面。既有管理员完整历史访问保持不变。

## 验证

- 定向测试：`pytest tests/test_member_archive.py tests/test_navigation_performance_structure.py tests/test_ui_dedup.py tests/test_v7_workspaces.py -q`，**63 passed / 0 failed**。
- 全量首次执行：988 passed；2 条写死旧调用文本的导航结构断言失败。已更新为包含归档筛选的新调用，保留批量查询、路由先于数据加载和无计算副作用断言；以上 63 项复验覆盖这两条，并覆盖新增的归档五 Tab 渲染测试。无未修复失败。
- Chromium 151.0.7922.34，1440×900：完整点击两个隔离合成会员的归档路径；空姓名/错误姓名/尾随空格禁用；取消正常；运行中只能明确停止并归档；归档后在管列表隐藏；已归档详情五 Tab 均可读，无异常。
- 数据库验证：归档前后每张表行数没有减少，原 Trace 标识全部保留；Observation 和 MemberAgent 保留，Goal 取消且不冒充成功，MemberAgent 空闲，无正常人工工作。
- 最终隔离数据：`.runtime/member-archive-restore-final/browser.db`。正式 `executive_health_ai.db` 未重建或执行验收归档。
- 8501 原进程缓存旧模块；按现有受管进程组刷新后，只读 Chromium 检查确认最新筛选与 Header 菜单生效。API、Streamlit、worker 随现有启动器正常启动，不执行数据库迁移。

## 截图

- [Header 唯一入口](images/member-archive-restore/01-member360-header.png)
- [姓名严格确认](images/member-archive-restore/02-name-confirmation.png)
- [归档后正常列表隐藏](images/member-archive-restore/03-active-list-hidden.png)
- [已归档健康资料只读](images/member-archive-restore/04-archived-health-records.png)
- [运行中的合成会员](images/member-archive-restore/05-running-member.png)
- [运行保护与明确停止](images/member-archive-restore/06-running-protected.png)
- [停止并归档后的列表](images/member-archive-restore/07-running-archived.png)

可重复验收脚本：`scripts/qa_member_delete.py`。先指定新的 `HEALTHOPS_ARCHIVE_QA_CASE`（仅目录标识），使用 `--prepare` 创建隔离合成数据，通过现有 QA 启动器加载其 manifest，再运行浏览器验收。不会重置已有数据库。
