"""Regression checks for the visible V1 surface redesign, not business logic."""

from pathlib import Path


APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def _source(name: str, next_marker: str) -> str:
    return APP.read_text(encoding="utf-8").split(f"def {name}", 1)[1].split(next_marker, 1)[0]


def test_design_system_exposes_shared_surface_helpers_and_tokens() -> None:
    source = APP.read_text(encoding="utf-8")
    for helper in (
        "page_header", "section_frame", "summary_metric", "status_badge",
        "health_metric_card", "work_item_card", "member_card", "_empty_state",
        "primary_action", "secondary_action", "detail_panel",
    ):
        assert f"def {helper}" in source
    for token in ("--canvas", "--card", "--ink", "--muted", "--line", "--blue", "--radius"):
        assert token in source
    assert "linear-gradient" not in source


def test_ops_today_uses_prioritized_work_cards_not_dashboard_metric_cards() -> None:
    source = _source("render_manager_dashboard", "def _render_member_header")
    assert "今日健康运营" in source
    assert "高风险" in source and "中风险" in source and "等待医生" in source
    assert "优先处理" in source and "work_item_card(" in source
    assert source.count("st.metric(") == 0


def test_members_and_member_overview_have_distinct_visual_components() -> None:
    members = _source("render_members_workspace", "KNOWLEDGE_CATEGORIES")
    overview = _source("render_simple_member_overview", "def render_simple_health_problems")
    assert "member_card(" in members
    assert "当前重点" in overview and "最近健康历程" in overview
    assert "section_frame(" in overview
    assert "render_longitudinal_timeline(patient, key_scope=\"overview\")" not in overview


def test_member_health_is_second_level_and_client_surface_is_personal() -> None:
    client_health = _source("render_client_health_hub", "def render_member_client_view")
    client_home = _source("_render_client_home", "def _render_client_plan")
    assert 'allowed = ["健康概览", "健康数据", "体检", "医疗档案"]' in client_health
    assert "client-hero" in client_home and "我的下一步" in client_home
    assert "work_item_card(" not in client_home


def test_data_report_service_and_collaboration_use_result_or_action_first_frames() -> None:
    data = _source("render_health_data", "def render_medications")
    report = _source("render_report_review", "def _render_baseline_draft_action")
    service = _source("render_service_operations_workspace", "def _report_candidate_label")
    collaboration = _source("render_collaboration_workspace", "def render_service_operations_workspace")
    assert "health_metric_card(" in data and "最近趋势" in data and "查看全部健康数据" in data
    assert "本次核心结论" in report and "与上次相比" in report and "需要处理" in report
    assert "查看解析详情（高级信息）" in report
    assert "服务工作列表" in service and "等待反馈" in service and "detail_panel(" in service
    assert "内部医生" in collaboration and "外部医疗" in collaboration and "collaboration-view" in collaboration
