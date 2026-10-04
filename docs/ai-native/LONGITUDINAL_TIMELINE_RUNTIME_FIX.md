# Member360 历程运行时错误修复记录

日期：2026-10-04。起始 HEAD：`c498bff453ac5ee9e9369f349012fefae1710540`。

## 真实根因

`.runtime/logs/platform/streamlit.stderr.log` 在 16:01:29.502 记录：

```text
ui/pages/manager/experience.py:164 → app._member_summary_context(patient.id)
streamlit_app.py:1390 → session.scalars(select(Observation) ...)
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError)
no such column: observations.source_type
```

异常发生在 Member360 共享上下文查询，尚未执行时间轴 renderer。
worker 日志的最新错误同时为 `no such table: summary_work_items`，来自
`services/daily_summary.py:248`。FastAPI 最新日志是正常启动，没有对应查询异常。

实际报错会员位于根目录 `executive_health_ai.db`，该库为默认 platform 配置使用的数据库，
停留在 `0031_member_wait_input`。另一个 `data/portfolio_demo.db` 已为 `0032_goal_data_loop`，
且不包含报错会员。不能通过切换到另一数据库掩盖问题。

缺少的列及表属于 `bf1b055` 引入的 0032 migration。`git blame` 证明出错的共享
Observation 查询早于 `c498bff`；这是既有 schema 未部署的问题，不是 c498bff 新增时间轴查询导致。

## 数据保护与修复

先使用 SQLite backup API 备份两个库，并保存所有表的列、记录数和原有字段值摘要：

- `.runtime/timeline-runtime-fix/default-before.db` / `default-before.json`
- `.runtime/timeline-runtime-fix/portfolio-before.db` / `portfolio-before.json`

在备份副本上先执行现有 `alembic upgrade head`，验证所有原有列及记录完全一致、
`PRAGMA integrity_check = ok`，再明确设置 DATABASE_URL，对根目录实际运行库执行同一迁移。
没有 rebuild、seed、删除记录或新增演示会员。`data/portfolio_demo.db` 没有迁移或修改。

迁移后及正式浏览器验收后均再次核对所有旧表，除 migration 版本外，所有原有字段及记录完全一致。

| 根目录实际运行库 | 修复前 | 修复后 |
| --- | ---: | ---: |
| patients | 14 | 14 |
| observations | 5678 | 5678 |
| raw_data | 5511 | 5511 |
| raw_ingestion_records | 4075 | 4075 |
| health_assessments（健康评估/基线档案） | 2 | 2 |
| health_journeys | 13 | 13 |
| health_programs | 14 | 14 |
| program_phases | 6 | 6 |
| doctor_reviews | 2 | 2 |
| health_events | 19 | 19 |
| management_logs | 0 | 0 |

另一 Demo 库的会员 2、Observation 1522、RawData 1434、健康评估 1，全部保持不变。

代码修复限定为：

1. 共享 Launcher 启动前只读校验长期数据 schema。缺表/列时明确要求备份及迁移，
   不再启动一个看似正常、进入 Member360 才失败的平台。该检查不自动修改数据库，
   也不把 schema 错误视为会员暂无数据。
2. 在唯一的 LongitudinalTimelineProjection 中支持旧 JSON 的空引用、空指标列表、
   空 change/lookback、空版本、空原始载荷；无有效关联时不捏造 CareEpisode 链接。
3. 未修改 renderer、导航、样式、业务责任边界，未添加另一套旧时间轴。

## 验证

```text
python -m pytest tests/test_timeline_existing_data.py tests/test_longitudinal_timeline.py
  tests/test_health_timeline_v4.py tests/test_goal_data_loop.py
  tests/test_service_processes.py -q --tb=short
133 passed / 0 failed
```

测试包括：0031 真实结构重现 ORM 缺列错误、备份和无损升级、启动前 schema 检查、
旧 Observation、旧 ManagementLog、缺 Snapshot/CareEpisode/Outcome/Goal/Phase、
空会员、nullable source refs、空 JSON 字段、三个状态的 Streamlit renderer。
迁移测试只使用临时库，不修改正式数据库。

正式平台通过 `scripts/start_platform.ps1 -NoBrowser` 启动，明确使用根目录原库，端口 8501/8000。
真实 Chromium 151.0.7922.34 通过「会员 → 点击会员 → Member360 → 历程」访问：

- 原报错会员：正确显示“当前还没有足够的纵向健康记录”及自动形成历程的说明。
- 有纵向历史的合成演示会员：17 个节点，包含状态、基线、管理行动、医生意见和结果；当前状态详情可打开。
- 仅有旧 Observation 的会员：没有新 Goal/Summary/Episode，仍显示当前状态，详情可打开。
- 归档会员通过既有“状态：全部”筛选进入，未更改归档状态。返回概览与会员列表正常。

截图、页面文本、浏览器结果保存在 `.runtime/timeline-runtime-fix/`，未提交含会员内容的截图或数据库。
两库全部会员的 projection 和节点详情也完成只读验证。
