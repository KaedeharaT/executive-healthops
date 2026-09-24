"""Entry contracts and real role navigation; screenshots remain visual evidence."""
import ast
import json
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal

from streamlit.testing.v1 import AppTest
from tests.ui_selection import open_member, select_table_row
from executive_health_ai.services.health_visualization import HealthPoint, HealthSeries
from executive_health_ai.ui.charts.health import metric_trend_chart

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamlit_app.py"


def radio(app, label, value):
    next(x for x in app.radio if x.label == label).set_value(value)
    app.run(timeout=30)
    assert not app.exception


def button(app, label):
    next(x for x in app.button if x.label == label).click()
    app.run(timeout=30)
    assert not app.exception


def test_every_inventoried_business_element_has_a_retained_renderer_and_destination():
    elements = json.loads((ROOT / "docs/ux_v2_elements.json").read_text(encoding="utf8"))
    functions = {node.name for path in [APP, *(ROOT / "src").rglob("*.py")]
                 for node in ast.walk(ast.parse(path.read_text(encoding="utf8"))) if isinstance(node, ast.FunctionDef)}
    assert len(elements) == 94 and len({e["id"] for e in elements}) == 94
    for element in elements:
        assert element["function"] in functions, element
        assert element["new"] and element["old"]
        assert element["action"] in {"KEEP", "MOVE", "MERGE", "COLLAPSE", "SECONDARY", "ADVANCED"}


def test_original_ui_functions_are_retained_including_advanced_capabilities():
    inventory = json.loads((ROOT / "docs/ux_v2_widget_inventory.json").read_text(encoding="utf8"))
    for path in {f["path"] for f in inventory["functions"]}:
        current = {n.name for n in ast.walk(ast.parse((ROOT / path).read_text(encoding="utf8"))) if isinstance(n, ast.FunctionDef)}
        previous = {f["function"] for f in inventory["functions"] if f["path"] == path}
        assert previous <= current, (path, previous - current)


def test_member_primary_paths_and_secondary_service_actions_remain_reachable():
    app = AppTest.from_file(APP).run(timeout=30)
    radio(app, "当前视图", "成员健康中心")
    nav = next(x for x in app.radio if x.label == "成员健康中心导航")
    assert len(nav.options) == 5
    for name in ["健康", "计划", "服务", "历程", "首页"]:
        radio(app, "成员健康中心导航", name)
    radio(app, "成员健康中心导航", "服务")
    assert next(x for x in app.radio if x.label == "服务内容").value == "我的申请"
    radio(app, "服务内容", "可用服务")
    assert any(x.label == "服务分类" for x in app.selectbox)
    assert any(x.label == "申请服务" for x in app.button)
    radio(app, "服务内容", "服务记录")


def test_manager_selection_changes_inspector_and_keeps_processing_entry():
    from sqlalchemy import select
    from executive_health_ai.database import SessionLocal
    from executive_health_ai.models import Patient, Task
    with SessionLocal() as session:
        member = session.scalar(select(Patient))
        session.add_all([Task(patient_id=member.id, title=f"V2选择事项{n}", instruction="核对已有资料", status="PENDING", priority="MEDIUM", assignee="健康管理师", responsible_role="health_manager", due_at=datetime.now(timezone.utc), source="ux_preservation_test") for n in range(2)])
        session.commit()
    app = AppTest.from_file(APP).run(timeout=30)
    # Large work lists use a selectable grid; keyboard access selects the same
    # underlying record and must keep the command attached to that record.
    assert len(app.dataframe) >= 1
    next(x for x in app.text_input if x.label == '查找待办').set_value('V2选择事项')
    app.run(timeout=30)
    assert len(app.dataframe[0].value) == 2
    select_table_row(app, 1).run(timeout=30)
    assert not app.exception
    assert any('V2选择事项1' in str(x.value) for x in app.markdown)
    assert any(b.label == '处理当前任务' for b in app.button)
    next(x for x in app.text_input if x.label == "查找待办").set_value("__no_matching_member__")
    app.run(timeout=30)
    assert any("当前筛选下暂无事项" in c.value for c in app.caption)
    assert not any(str(b.key).startswith("today-") for b in app.button)


def test_360_quick_actions_open_original_management_forms():
    app = AppTest.from_file(APP).run(timeout=30)
    radio(app, "工作区", "成员"); open_member(app).run(timeout=30)
    button(app, "安排随访")
    assert next(x for x in app.radio if x.label == "管理操作").value == "安排随访"
    assert any(x.label == "需要完成什么" for x in app.text_area)
    radio(app, "成员页面", "概览"); button(app, "记录阶段结果")
    assert next(x for x in app.radio if x.label == "管理操作").value == "记录阶段结果"
    assert any(x.label == "记录阶段结果并安排下一步" for x in app.button)


def test_admin_all_integrations_rules_system_and_legacy_tools_are_accessible():
    app = AppTest.from_file(APP).run(timeout=30)
    radio(app, "当前视图", "系统管理")
    radio(app, "系统", "集成与数据")
    for key in ["integration-open-ai", "integration-open-knowledge", "integration-open-device", "integration-open-data"]:
        next(b for b in app.button if b.key == key).click(); app.run(timeout=30)
        assert not app.exception
    radio(app, "系统", "规则与知识")
    for value in ["规则", "专业知识", "设备"]:
        radio(app, "配置内容", value)
    radio(app, "系统", "自动化运营")
    radio(app, "系统", "系统状态")
    assert any(e.label == "AI质量治理（高级）" for e in app.expander)
    assert any(e.label == "操作记录" for e in app.expander)
    selector = next(x for x in app.selectbox if x.label == "选择兼容工具")
    assert len(selector.options) == 15
    # Every retained compatibility renderer runs, rather than just existing as a string.
    for value in selector.options:
        next(x for x in app.selectbox if x.label == "选择兼容工具").set_value(value)
        app.run(timeout=30); button(app, "打开兼容工具")


def test_doctor_pending_completed_and_manager_readonly_use_same_workspace():
    app = AppTest.from_file(APP).run(timeout=30)
    radio(app, "当前视图", "医生工作台")
    for mode in ["已完成", "待复核"]:
        radio(app, "复核工作", mode)
    radio(app, "当前视图", "运营后台")
    radio(app, "工作区", "医疗协同")
    assert not any(b.label == "提交判断并交回健管" for b in app.button)
    radio(app, "医疗协同内容", "外部医疗")
    assert not app.exception


def test_compact_chart_padding_is_object_for_streamlit_frontend():
    series = HealthSeries("weight", "体重", "kg", (
        HealthPoint(datetime(2026, 1, 1, tzinfo=timezone.utc), Decimal("90"), "健康数据"),
        HealthPoint(datetime(2026, 9, 1, tzinfo=timezone.utc), Decimal("85.8"), "健康数据")))
    spec = metric_trend_chart((series,), compact=True).to_dict()
    # Streamlit mutates padding.bottom at runtime; numeric padding causes a JS error.
    assert set(spec["padding"]) == {"left", "right", "top", "bottom"}
    assert spec["encoding"]["x"]["axis"]["labels"] is True


def test_care_team_projection_has_no_write_path_or_synthetic_identity():
    from executive_health_ai.ui.view_models import care_team_context
    from executive_health_ai.database import SessionLocal
    from executive_health_ai.models import Patient
    from sqlalchemy import select
    with SessionLocal() as session:
        member = session.scalar(select(Patient))
        before = (set(session.new), set(session.dirty), set(session.deleted))
        people = care_team_context(session, member.id)
        assert people and all(len(row) == 3 for row in people)
        assert (set(session.new), set(session.dirty), set(session.deleted)) == before
