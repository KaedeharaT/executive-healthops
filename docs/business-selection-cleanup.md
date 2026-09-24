# 普通业务界面交互清理

会员现在通过“搜索 / 筛选 → 点击会员行 → Member 360”进入详情。无须选择交互组件，也无须再次点击进入按钮。

## 清理范围

Visible redundant controls removed: **6 类**

1. 共享表格的“键盘选择 / 完整标题”折叠区。
2. “使用下拉选择”复选框。
3. 随上述开关提供的备用选择下拉框。
4. 会员选行后的“查看成员”二次进入按钮，其导航行为已合并到会员行。
5. 普通业务页面顶部的框架 Deploy 部署按钮。
6. 普通业务页面顶部的框架开发菜单。部署与开发菜单仍可在管理员视图使用。

前三项从共享表格实现中移除，作用于所有使用该组件的业务列表，不按页面重复计数。普通业务页面不再包含选择实现方式的开关。

Member selection: **PASS**

Developer terminology exposed: **0 / 19 个实际验收页面状态**

Keyboard accessibility preserved: **YES**

Business functionality removed: **NO**

Push: **NO**

## 业务与无障碍

搜索、状态筛选、负责人筛选、表格、完整详情、Member 360、入组及原有业务命令均保留。完整说明继续在业务详情中查看。

会员表直接响应原生单元格选择事件；筛选变化及返回列表时重置选择，避免旧选择导致误跳转。普通事项表保留原生行选择。键盘能力默认工作，真实浏览器验证了 Tab 进入表格、方向键进入会员，以及 Shift+Space 选中事项并打开详情。

没有增加隐藏的用户模式。管理员原有调试、原始资料及审计能力保持原位置；代码中的业务标识仍可用于内部关联。扫描普通 UI 的文字参数和实际页面，未发现所列 Advanced、Legacy、Trace、Raw、Debug、Internal、UUID、ID、AgentGoal、PlanStep、canonical_code、provider_code 等术语暴露。

应用使用现有 Streamlit 原生选择事件；最低依赖调整到已验证的 1.61 系列。AppTest 不传输原生表格选择状态，因此测试辅助函数补充事件传输，生产界面无需测试专用控件。

## 真实浏览器证据

使用本地 Chromium 与运行中的 Streamlit，连接隔离的合成演示数据库；没有修改原业务数据。

- [会员列表](images/business-selection/member-list.png)
- [搜索与负责人筛选](images/business-selection/member-filtered.png)
- [鼠标点击进入 Member 360](images/business-selection/member-mouse-open.png)
- [键盘进入另一会员](images/business-selection/member-keyboard-open.png)
- [普通事项表键盘打开详情](images/business-selection/manager-keyboard-detail.png)
- [19 个页面状态的检查结果](images/business-selection/results.json)

检查覆盖健管今日工作、会员、Member 360 各页签、年度管理、医疗协同、服务，医生队列及成员五个一级页面。脚本为 `scripts/qa_business_selection.py`。此前 V4 脚本同步适配会员行直接导航。

## 回归测试

全量：**596 passed / 0 failed**，原有 13 个弃用警告。命令：`.venv/Scripts/python.exe -m pytest -q -x`，全部测试执行完成。见 [完整输出](business-selection-tests.txt)。

新增回归覆盖原生单元格到会员身份的映射、必须主动选行才进入详情、返回后稳定停留列表。已有业务回归改用原生表格事件，保留医生确认、业务命令和数据归属断言。真实键盘验证由 Chromium 执行。
