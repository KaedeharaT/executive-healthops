"""Frozen UX V3 contracts: retained routes, read-only facts and task context."""
import ast
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest
from tests.ui_selection import open_member, select_table_row

from executive_health_ai.services.product_projection import ManagerWorkView, Member360View

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamlit_app.py"


def radio(app, label, value):
    next(item for item in app.radio if item.label == label).set_value(value)
    app.run(timeout=45)
    assert not app.exception


def test_frozen_121_elements_have_source_renderer_and_assigned_destination():
    rows = json.loads((ROOT / "docs/ux_v3_implementation/elements.json").read_text(encoding="utf8"))
    assert len(rows) == len({r["id"] for r in rows}) == 121
    for row in rows:
        assert row["destination"] and row["preserved"]
        assert row["visibility"] in {"PRIMARY", "SECONDARY", "DETAIL", "ADVANCED", "LEGACY"}
        functions = {n.name for n in ast.walk(ast.parse((ROOT / row["source"]).read_text(encoding="utf8"))) if isinstance(n, ast.FunctionDef)}
        assert row["renderer"] in functions, row["id"]


def test_today_count_is_date_bounded_and_keeps_waiting_work_in_queue():
    now = datetime(2026, 9, 20, 3, tzinfo=timezone.utc)
    def item(at, status="待处理"):
        return SimpleNamespace(due_at=at, status=status, priority=3)
    items = (item(now), item(now+timedelta(days=1)), item(now-timedelta(days=1)), item(None), item(now, "等待医生"), item(now, "等待成员"))
    view = ManagerWorkView(items, (object(),))
    counts = dict(view.counts(now))
    assert counts["今天待处理"] == 1 and counts["已逾期"] == 1
    assert counts["等待医生"] == counts["等待成员"] == 1
    assert len(view.items) == 6  # Filtered summary never removes future/unscheduled facts.


def test_current_plan_outcomes_cannot_inherit_a_different_plan_result():
    current = SimpleNamespace(id="current", owner="真实负责人")
    baseline = SimpleNamespace(cycle_year=2026, assessed_at=datetime(2026, 1, 20))
    outcomes = (SimpleNamespace(program_id="past"), SimpleNamespace(program_id="current"), SimpleNamespace(program_id=None))
    tasks = tuple(SimpleNamespace(status=s, responsible_role=r) for s, r in (("PENDING", "member"), ("COMPLETED", "member"), ("PENDING", "health_manager")))
    view = Member360View("member", current, (current,), tasks, (), (), baseline, (), None, outcomes)
    assert view.current_outcomes == (outcomes[1],)
    assert view.historical_outcomes == (outcomes[0], outcomes[2])
    assert len(view.active_tasks) == 2 and len(view.member_actions) == 1
    assert view.owner == "真实负责人" and view.cycle == "2026年度健康管理"
    assert len(view.outcomes) == 3  # History remains accessible, never discarded.


def test_home_has_one_shared_trend_entry_and_preserves_secondary_actions():
    app = AppTest.from_file(APP).run(timeout=45)
    radio(app, "当前视图", "成员健康中心")
    radio(app, "成员健康中心导航", "首页")
    labels = [b.label for b in app.button]
    assert labels.count("查看健康变化") <= 1
    assert "查看服务安排" in labels and "查看健康计划" in labels and "上传体检报告" in labels
    assert any(e.label == "当前管理进展与下一步" for e in app.expander)
    assert not app.exception


def test_admin_lands_on_status_and_configuration_requires_selection():
    app = AppTest.from_file(APP).run(timeout=45)
    radio(app, "当前视图", "系统管理")
    nav = next(r for r in app.radio if r.label == "系统")
    assert nav.value == "系统状态" and len(nav.options) == 4
    next(b for b in app.button if b.label == "检查数据与集成").click()
    app.run(timeout=45)
    assert not app.exception
    assert not app.get("file_uploader")
    select_table_row(app,0)
    app.run(timeout=45)
    assert not app.exception and app.get("file_uploader")


def test_doctor_form_follows_context_and_evidence_in_single_reading_order():
    source = (ROOT / "src/executive_health_ai/ui/pages/doctor/experience.py").read_text(encoding="utf8")
    body = source[source.index("def detail("):source.index("def workspace(")]
    assert body.index("render_doctor_trend(patient.id") < body.index("ux.evidence_summary(payload)") < body.index('with st.form(')
    assert "clinical, decision = st.columns" in body
    assert "complete_review(session" in body


def test_new_projections_are_read_only_and_keep_shared_baseline_and_observation_sources():
    source = (ROOT / "src/executive_health_ai/services/product_projection.py").read_text(encoding="utf8")
    tree = ast.parse(source)
    writes = {"add", "add_all", "delete", "commit", "flush", "merge"}
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in writes]
    assert "BaselineVisualizationService().build" in source and "HealthVisualizationService().build" in source


def test_doctor_history_and_member_360_details_keep_frozen_navigation_budget():
    app = AppTest.from_file(APP).run(timeout=45)
    radio(app, "当前视图", "医生工作台")
    assert len(next(r for r in app.radio if r.label == "医生工作").options) == 2
    radio(app, "医生工作", "历史")
    radio(app, "当前视图", "运营后台")
    radio(app, "工作区", "成员")
    open_member(app); app.run(timeout=45)
    assert len(next(r for r in app.radio if r.label == "成员页面").options) == 5
    radio(app, "成员页面", "健康")
    assert not any('资料' in frame.value.columns for frame in app.dataframe)
    next(b for b in app.button if b.label=='查看完整健康档案').click().run(timeout=45)
    assert any('年度健康基线' in frame.value.to_string() for frame in app.dataframe)
    assert not any('选择方式' in x.label for x in app.checkbox)
