"""Regression guards for the five result-first HealthOps product surfaces."""

from pathlib import Path


APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def _source(name: str, next_marker: str) -> str:
    from tests.ui_source import source
    return source(name, next_marker)


def test_shared_design_system_exposes_product_level_helpers() -> None:
    source = APP.read_text(encoding="utf-8")
    for helper in (
        "page_header", "section_frame", "status_badge", "risk_badge", "summary_metric",
        "health_metric_card", "work_item_card", "member_card", "entry_card", "empty_state",
        "primary_action", "secondary_action", "detail_panel", "evidence_action",
    ):
        assert f"def {helper}" in source


def test_ops_today_has_one_priority_frame_and_compact_work_items() -> None:
    today = _source("render_manager_dashboard", "def _render_member_header")
    assert "今日待处理" in today and "c.summary_strip(work.counts(now))" in today
    assert 'st.subheader("优先处理")' in today and "ux.work_item(" in today
    assert "ux.sorted_work(" in today and "visible[:6]" in today


def test_member_overview_keeps_the_two_column_focus_then_next_step_structure() -> None:
    overview = _source("render_simple_member_overview", "def render_simple_health_problems")
    assert "st.columns([1.8, 1])" in overview
    for section in ("当前重点", "下一步", "最近变化", "最近健康历程"):
        assert f'section_frame("{section}"' in overview
    assert "render_longitudinal_timeline" not in overview


def test_member_home_is_personal_and_limits_today_to_six_health_tiles() -> None:
    home = _source("_render_client_home", "def _render_client_plan")
    assert "今天需要你完成" in home and "tasks[1:3]" in home
    assert "最近变化" in home and "render_previews(" in home and "maximum=2" in home
    assert "render_longitudinal_timeline" not in home
    assert "render_member_report_upload" not in home


def test_report_is_result_first_and_parser_controls_are_in_advanced_details() -> None:
    report = _source("render_report_review", "def _render_baseline_draft_action")
    for section in ("本次核心结论", "与上次相比", "需要处理", "查看解析详情（高级信息）"):
        assert section in report
    assert "risk_badge(report_risk" in report
    assert report.index("查看解析详情（高级信息）") < report.index('secondary_action("重新整理报告"')


def test_timeline_has_three_product_frames_and_a_single_detail_column() -> None:
    timeline = _source("render_longitudinal_timeline", "def _client_device_status")
    for section in ("健康趋势", "当前期间总结", "健康生命轴"):
        assert f'_section_frame("{section}"' in timeline or f'section_frame("{section}"' in timeline
    assert "st.slider(" in timeline
    assert "lifecycle = st.container()" in timeline and "inspector = st.container()" in timeline
    assert "_render_lifecycle_grid(" in timeline
    assert "position:absolute" not in timeline


def test_member_health_has_four_second_level_views_and_timeline_is_primary() -> None:
    archive = _source("render_client_health_hub", "def render_member_client_view")
    assert 'allowed = ["健康概览", "健康数据", "体检", "医疗档案"]' in archive
    assert 'st.radio("健康内容", allowed' in archive


def test_member_plan_uses_three_second_level_views() -> None:
    plan = _source("_render_client_plan", "def render_member_service_management")
    assert '["待完成", "等待他人", "已完成"]' in plan
    assert "近期节点" in plan and "阶段结果" in plan and "_complete(task)" in plan


def test_member_service_is_category_first() -> None:
    service = _source("_render_client_service", "def _render_client_profile")
    assert "服务分类" in service and "client-service-category-filter" in service
    assert "我的申请" in service and "服务记录" in service


def test_member_detail_has_five_visual_tabs_only() -> None:
    detail = _source("render_member_detail", "def render_member_archive")
    assert '["概览", "健康", "管理", "医疗", "历程"]' in detail


def test_risk_colours_are_reserved_for_formal_risk_labels() -> None:
    helpers = _source("status_badge", "def health_metric_card")
    assert "high_risk" in helpers and "medium_risk" in helpers and "low_risk" in helpers
    assert "workflow status remains neutral" in helpers


def test_navigation_stays_free_of_local_llm_and_parser_side_effects() -> None:
    main = _source("main", 'if __name__ == "__main__"')
    assert all(token not in main for token in ("ReportParsingService", "LocalLLM", "RiskEvaluationService", "ingest("))
