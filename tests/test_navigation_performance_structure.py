"""Structural guards for Streamlit navigation lazy loading.

These intentionally test query shape rather than timing: elapsed-time assertions
are unreliable across developer machines and databases.
"""
from pathlib import Path

from streamlit.testing.v1 import AppTest
from tests.ui_selection import open_member, select_table_row


APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
MORE_SHELL = APP.parent / "src" / "executive_health_ai" / "ui" / "pages" / "shell.py"


def _function_source(name: str, next_marker: str) -> str:
    text = APP.read_text(encoding="utf-8")
    return text.split(f"def {name}", 1)[1].split(next_marker, 1)[0]


def _radio(app: AppTest, label: str):
    return next(item for item in app.radio if item.label == label)


def test_members_workspace_uses_batch_summary_not_full_member_context() -> None:
    from tests.ui_source import source as renderer_source
    source = renderer_source("render_members_workspace", "KNOWLEDGE_CATEGORIES")
    assert "member_directory(session, members)" in source
    projection = (APP.parent / "src/executive_health_ai/services/information_presentation.py").read_text(encoding="utf8")
    assert ".in_(ids)" in projection and "ManagementLog" in projection
    assert "_context(member.id)" not in source
    assert "select(Observation)" not in source


def test_dashboard_context_never_queries_observations_and_is_bounded() -> None:
    source = _function_source("_dashboard_context", "def _member_summary_context")
    assert "Observation" not in source
    assert ".limit(" in source


def test_more_root_routes_before_loading_its_selected_module() -> None:
    root_source = _function_source("render_more_workspace", "def render_collaboration_workspace")
    shell_source = MORE_SHELL.read_text(encoding="utf-8")
    assert "render_support_directory(_ui_adapter())" in root_source
    directory = (MORE_SHELL.parent / "support_navigation.py").read_text(encoding="utf8")
    assert 'request_navigation(surface="系统管理")' in directory
    assert 'pop("more-navigation", None)' in directory
    assert 'render_more_workspace_shell' not in shell_source
    assert "TARGETS.get(legacy,'系统状态')" in directory
    assert "render_data_gateway(load_members())" not in shell_source
    assert "render_audit(_context(" not in shell_source


def test_main_routes_before_loading_members() -> None:
    source = _function_source("main", "if __name__")
    assert source.index('if page == "今日"') < source.index('members = _navigation_stage("member list", _members)')
    assert source.index('if page == "医疗协同"') < source.index('members = _navigation_stage("member list", _members)')
    assert source.index('if page == "服务运营"') < source.index('members = _navigation_stage("member list", _members)')
    assert source.index('if page == "更多"') < source.index('members = _navigation_stage("member list", _members)')
    assert "_context(" not in source
    assert "RiskEvaluationService" not in source and "ReportParsingService" not in source


def test_more_menu_uses_only_basic_installed_streamlit_widgets() -> None:
    source = MORE_SHELL.read_text(encoding="utf-8")
    assert "placeholder=" not in source
    assert "st.button(" in source and "st.navigation(" not in source


def test_device_overview_is_bounded_and_defers_review_and_upload_work() -> None:
    source = _function_source("render_data_gateway", "def _device_overview_snapshot")
    assert "_device_overview_snapshot()" in source
    assert 'if device_view == "设备概览"' in source and "return" in source
    overview = source.split('if device_view == "设备概览"', 1)[0]
    assert "RawIngestionRecord" not in overview
    assert "render_report_upload" not in overview
    assert "ingest(" not in overview and "ReportParsingService" not in overview


def test_navigation_profile_script_is_read_only_and_records_real_reruns() -> None:
    source = (APP.parents[0] / "scripts" / "profile_navigation.py").read_text(encoding="utf-8")
    assert "AppTest" in source and "before_cursor_execute" in source
    assert "ReportParsingService" not in source and "RiskEvaluationService" not in source
    assert "route:" in source and "side_effects local_llm=0" in source


def test_navigation_reuses_imported_session_factory_and_has_opt_in_timing_only() -> None:
    source = APP.read_text(encoding="utf-8")
    main_source = _function_source("main", "if __name__")
    assert "create_engine(" not in source
    assert "SessionLocal" in source and "st.cache_resource" not in source
    assert "_navigation_stage(\"sidebar\"" in main_source
    assert "HEALTHOPS_PROFILE_NAV" in source


def test_navigation_root_has_no_ai_risk_or_seed_side_effects() -> None:
    source = APP.read_text(encoding="utf-8")
    main_source = _function_source("main", "if __name__")
    more_source = _function_source("render_more_workspace", "def render_collaboration_workspace")
    assert all(token not in main_source for token in ("seed_", "LocalLLM", "ReportParsingService", "RiskEvaluationService", "ingest("))
    assert all(token not in more_source for token in ("LocalLLM", "health_check", "ReportParsingService", "RiskEvaluationService"))


def test_all_sidebar_and_more_pages_render_without_exception() -> None:
    """Exercise installed Streamlit's real widget API, not documentation assumptions."""
    root = APP
    for workspace in ["今日", "成员", "年度管理", "医疗协同", "服务运营"]:
        app = AppTest.from_file(root)
        app.run(timeout=30)
        _radio(app, "工作区").set_value(workspace)
        app.run(timeout=30)
        assert not app.exception
    for page in ["数据与集成", "自动化运行", "规则与知识", "系统状态"]:
        app = AppTest.from_file(root)
        app.run(timeout=30)
        _radio(app, "当前视图").set_value("系统管理")
        app.run(timeout=30)
        _radio(app, "系统").set_value(page)
        app.run(timeout=30)
        assert not app.exception
    for page in ["进行中", "历史"]:
        app = AppTest.from_file(root)
        app.run(timeout=30)
        _radio(app, "工作区").set_value("医疗协同")
        app.run(timeout=30)
        _radio(app, "医疗记录").set_value(page)
        app.run(timeout=30)
        assert not app.exception


def test_member_card_opens_all_five_member_sections_without_widget_state_errors() -> None:
    app = AppTest.from_file(APP)
    app.run(timeout=30)
    _radio(app, "工作区").set_value("成员")
    app.run(timeout=30)
    open_member(app)
    app.run(timeout=30)
    assert not app.exception
    section = next(radio for radio in app.radio if radio.key and radio.key.startswith("member-section-"))
    for name in ("概览", "管理", "健康", "医疗", "历程"):
        section.set_value(name)
        app.run(timeout=30)
        assert not app.exception


def test_member_center_renders_all_five_personal_health_pages_without_exception() -> None:
    app = AppTest.from_file(APP)
    app.run(timeout=30)
    _radio(app, "当前视图").set_value("成员健康中心")
    app.run(timeout=30)
    client_navigation = _radio(app, "成员健康中心导航")
    for page in ("首页", "健康", "历程", "计划", "服务"):
        client_navigation.set_value(page)
        app.run(timeout=30)
        assert not app.exception
