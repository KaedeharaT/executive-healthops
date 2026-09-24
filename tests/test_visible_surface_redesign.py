"""Regression checks for the visible V1 surface redesign, not business logic."""

from pathlib import Path


APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def _source(name: str, next_marker: str) -> str:
    from tests.ui_source import source
    return source(name, next_marker)


def test_design_system_exposes_shared_surface_helpers_and_tokens() -> None:
    from tests.ui_source import all_ui_source
    source = all_ui_source()
    for helper in (
        "page_header", "section_frame", "summary_metric", "status_badge",
        "health_metric_card", "work_item_card", "member_card", "_empty_state",
        "primary_action", "secondary_action", "detail_panel",
    ):
        assert f"def {helper}" in source
    for token in ("--canvas", "--card", "--ink", "--muted", "--line", "--blue", "--radius"):
        assert token in source
    assert "linear-gradient" not in source


def test_ops_today_uses_prioritized_table_and_selected_detail() -> None:
    source = _source("render_manager_dashboard", "def _render_member_header")
    assert "今日工作" in source
    assert all(label in source for label in ('已逾期','等待医生','今天到期','工作事项'))
    assert "data_table(visible" in source and "总成员数" not in source
    assert "work_detail(app, item" in source and 'auto_select=False' in source


def test_members_and_member_overview_have_distinct_visual_components() -> None:
    members = _source("render_members_workspace", "KNOWLEDGE_CATEGORIES")
    overview = _source("render_simple_member_overview", "def render_simple_health_problems")
    assert "data_table(rows" in members and "最近联系" in members and '当前年度' in members
    assert "当前重点" in overview and "最近健康历程" in overview
    assert "section_frame(" in overview
    assert "render_longitudinal_timeline(patient, key_scope=\"overview\")" not in overview


def test_member_health_is_second_level_and_client_surface_is_personal() -> None:
    health = _source("render_client_health_hub", "def render_member_client_view")
    home = _source("_render_client_home", "def _render_client_plan")
    assert '["健康概览", "健康数据", "体检", "医疗档案"]' in health
    assert "今日健康" in home and "今天需要你完成" in home and "ux.next_action" in home


def test_data_report_service_and_collaboration_use_result_or_action_first_frames() -> None:
    data = _source("render_health_data", "def render_medications")
    report = _source("render_report_review", "def _render_baseline_draft_action")
    service = _source("render_service_operations_workspace", "def _report_candidate_label")
    collaboration = _source("render_collaboration_workspace", "def render_service_operations_workspace")
    assert "health_metric_card(" in data and "最近趋势" in data and "查看全部健康数据" in data
    assert "本次核心结论" in report and "与上次相比" in report and "需要处理" in report
    assert "报告整理记录" in report
    assert "服务事项表" in service and "等待反馈" in service and "detail_drawer(" in service
    assert "data_table(visible" in service and "service_detail(app,selected" in service
    assert "collaboration(_ui_adapter())" in collaboration
