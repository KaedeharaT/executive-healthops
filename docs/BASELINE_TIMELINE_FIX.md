# 健康基线图表与成员历程专项修复

日期：2026-09-18。起点：`eab74b9`。仅修改图表投影、展示、历程快照渲染和错误展示边界；未修改业务模型、风险规则或 migration。

## 真实复现

使用本机数据库的隔离副本启动 Streamlit，实际进入成员 → 历程，得到：

```text
TypeError: unhashable type: 'list'
main → render_member_client_view
→ member_pages.timeline(_ui_adapter(), patient)
→ render_longitudinal_timeline
→ streamlit_app.py:5251（修复前）
value not in {None, "", [], {}}
```

集合字面量包含不可哈希的列表和字典；选中健康评估事件的快照分支时必然触发。Streamlit折叠区即使未展开也执行渲染，因此用户进入历程就会报错。先前仅用Portfolio数据默认选中其他事件的烟测没有覆盖此分支。

不是函数参数错配、adapter缺方法或Session失效。修复改为支持容器比较的元组过滤，并区分用药/健康问题的记录列表与“待补充”字典；回归测试通过真实入口选中评估事件，验证实际快照已显示且没有触发错误边界。

新增的错误边界仅兜底未来异常：页面显示“健康历程暂时无法加载，请稍后重试。”，后台 `logger.exception()`；全局客户端禁止显示异常详情。未以错误提示代替根因修复。

## 图表根因与修复

- 健康概览此前只有基线/当前表格，没有时间趋势。
- 既有详情图使用Altair；X轴显式 `title=None`，轴线和刻度短线依赖Streamlit默认主题。
- 已在安装的Streamlit前端主题实现中确认 `ticks: false`、`domain: false`。实屏上并非全部数值标签消失：Y值和英文日期标签仍在，缺的是完整可辨识的轴线、时间标题、方向和当前标记。
- 改为显式Vega-Lite轴配置并对基线趋势使用 `theme=None`，保留医疗蓝、浅网格、单位和合理非零范围；没有使用CSS模拟坐标轴。
- 成员健康概览、成员基线详情及健管基线详情共用 `BaselineVisualizationService` 和 `render_baseline_progress`。
- 一次一张指标趋势；血压可使用同一mmHg轴绘制两条线。不同单位禁止共轴。
- 虚线/菱形标记年度基线，末端圆点标记最后有效观测；Tooltip显示日期、值、单位和来源类型。
- 数值方向独立于医学判断。百分比指标差值使用百分点；相对百分比仅用于允许的比例指标，基线为0或无兼容后续值时不计算。
- 只有基线点时显示原值与数据不足提示，不画趋势。
- 修正触及的基线背景渲染中裸条件表达式被Streamlit自动展示为内部对象的问题。

## 验收

实际浏览器：Chromium。桌面1440×1300；窄窗口640×960。原本发生崩溃的数据库副本、匿名Portfolio副本均完成以下检查：

- 成员：首页、健康、历程、展开完整历程、切换体检筛选、计划、服务、返回首页。
- 健管：今日、成员360、健康→基线。
- 医生：待我复核。管理员：集成与数据。
- 历程：没有异常组件或兜底错误；原数据库快照分支实际显示“当时健康快照”。
- 图表：实际SVG的X/Y轴、日期、kg/mmHg单位、基线参考与当前标记可见；鼠标悬停实际弹出日期/值/单位/来源。
- 窄屏仍有两条坐标轴及多个刻度，已人工查看截图；血压双线及图例正常。
- 已检查页面未检出UUID、RiskEvent、AgentGoal、PlanStep、source_id或Python traceback。

截图只使用匿名Portfolio数据：[健康](images/member-health.png)、[历程](images/member-timeline.png)。原业务数据库未被验证操作写入。

## 测试

修复前完整pytest：438 passed / 0 failed / 0 skipped。

新增16项专项回归：坐标轴、单位/范围、基线与当前/Tooltip、上升/下降/持平、百分比边界、单点、血压双线、单位不兼容、两角色相同投影、真实adapter契约、两类快照渲染、空状态和异常日志边界。

最终完整pytest：454 passed / 0 failed / 0 skipped，249.44秒；9项既有依赖弃用警告。命令：`.venv\Scripts\python.exe -m pytest -q --junitxml=.runtime/baseline_timeline_final.xml`。
