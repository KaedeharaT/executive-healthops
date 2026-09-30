# 会员列表删除入口

本轮按新的入口要求，将删除从 Member360 Header 移至会员列表。唯一位置是列表最右侧“操作”列，显示小型“删除”文字；已归档行不重复显示删除。

- 保持现有原生表格、搜索、负责人筛选和 Soft Neumorphism。状态为“在管 / 已归档 / 全部”，默认在管。
- 操作单元格事件在返回行选择之前被单独处理，不设置 Member360 路由。清除选择后再呈现姓名确认；取消、关闭和确认不会触发行跳转或重复弹窗。
- 文案为“删除会员 / 确认删除”，底层仍为原 MemberArchiveService 的安全归档。姓名必须完全相同，包括首尾空格。
- 存在运行中的 MemberAgent 或 Goal 时，界面只提示先完成或停止流程，并提供取消；没有强制停止按钮，归档服务仍在事务锁内再次检查运行状态。
- 正常删除后原地刷新列表；历史档案、Observation、年度管理记录、MemberAgent、Goal、Trace 和审计不物理删除。已归档 Member360 继续只读。
- Member360 Header 的归档菜单已删除，不新增一级导航、不修改 AI Native 架构。

## 验证

`pytest tests/test_member_archive.py tests/test_ui_dedup.py tests/test_v7_workspaces.py tests/test_navigation_performance_structure.py -q`

**63 passed / 0 failed**。

Chromium 151.0.7922.34，1440×900，隔离数据库 `.runtime/member-list-removal/browser.db`：

1. 会员列表直接点击运行中合成会员的操作列；仅弹出阻止删除提示，没有进入 Member360。
2. 非运行合成会员：空姓名、错误姓名、尾随空格均不可确认，取消有效。
3. 正确姓名确认后保持会员列表，原行立即消失。
4. 已归档筛选可以找到该会员；全部筛选同时显示在管和归档记录。
5. 点击普通单元格仍进入 Member360，五个 Tab 均无删除入口。
6. 所有历史表行数不减少，原 Trace ID 保留；归档会员无新的正常人工工作，运行中会员未被归档。
7. 8501 刷新原受管进程组后通过只读 Chromium 验证，列表操作列已加载，Member360 旧入口消失。正式数据库没有删除、重建或用于删除验收。

截图与机器验收记录：`docs/images/member-list-removal/`。

复验脚本：`scripts/qa_member_delete.py`（`--prepare` 准备隔离合成数据；不重置已有验收数据库）。
