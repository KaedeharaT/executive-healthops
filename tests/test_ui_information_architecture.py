"""Structural regressions for the concise HealthOps information architecture.

These checks deliberately inspect renderer boundaries rather than asserting pixel
layout.  They protect the user-facing hierarchy without caching mutable health
operations data or invoking business services during navigation.
"""

from pathlib import Path


APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
MORE_SHELL = APP.parent / "src" / "executive_health_ai" / "ui" / "pages" / "shell.py"


def _source(name: str, next_marker: str) -> str:
    return APP.read_text(encoding="utf-8").split(f"def {name}", 1)[1].split(next_marker, 1)[0]


def test_workbench_has_a_light_status_strip_and_a_task_driven_worklist() -> None:
    source = _source("render_manager_dashboard", "def _render_member_header")
    assert "_status_strip(" in source
    assert '"优先处理"' in source
    assert "OperationalWorklistService" in source
    assert "work_item_card(" in source


def test_member_summary_uses_the_five_business_questions() -> None:
    source = _source("render_simple_member_overview", "def render_current_member_state")
    for heading in (
        "当前重点", "下一步", "最近健康历程",
    ):
        assert heading in source


def test_member_overview_keeps_the_full_timeline_as_a_health_drill_down() -> None:
    source = _source("render_simple_member_overview", "def render_current_member_state")
    assert "查看完整健康历程" in source
    assert "render_longitudinal_timeline(patient, key_scope=\"overview\")" not in source


def test_member_detail_keeps_the_five_product_work_areas() -> None:
    source = _source("render_member_detail", "def render_member_archive")
    assert '["概览", "管理", "健康", "医疗", "历程"]' in source
    assert "render_member_management_signals(patient, management_ctx)" in source
    archive = _source("render_member_archive", "def _select_archive_timeline")
    assert 'views = ["数据", "体检", "基线", "健康史"]' in archive


def test_report_review_hides_technical_parse_details_by_default() -> None:
    source = _source("render_report_review", "def render_member_detail")
    assert 'st.expander("查看解析详情（高级信息）")' in source
    for group in ("需要医生复核", "健康管理", "建议复查", "一般记录", "需要人工核对内容"):
        assert group in source


def test_devices_use_daily_and_medical_categories_with_plain_statuses() -> None:
    source = _source("render_data_gateway", "def _device_overview_snapshot")
    assert "日常健康设备" in source and "医疗监测设备" in source
    assignment_source = _source("render_member_device_assignments", "def render_risk_rules")
    assert "已分配" in assignment_source and "未分配" in assignment_source
    assert "provider class" not in assignment_source.lower()


def test_member_center_excludes_internal_technical_records() -> None:
    source = _source("render_member_client_view", "def render_global_doctor_workspace")
    for technical_term in ("AuditLog", "RiskRule", "LLM", "metadata_json"):
        assert technical_term not in source


def test_member_center_uses_a_simple_personal_health_information_architecture() -> None:
    navigation = _source("_render_member_center_navigation", "def _render_sidebar_navigation")
    assert '["首页", "健康", "历程", "计划", "服务"]' in navigation
    health = _source("render_client_health_hub", "def render_member_client_view")
    assert 'allowed = ["健康概览", "健康数据", "体检", "医疗档案"]' in health


def test_client_device_source_uses_human_readable_states_and_a_real_next_step() -> None:
    source = _source("_render_client_profile", "def render_member_client_view")
    assert "我的健康数据来源" in source
    assert "联系健康管理师" in source
    assert "Provider" not in source and "Adapter" not in source


def test_visual_system_has_a_constrained_reading_width_and_quiet_cards() -> None:
    source = APP.read_text(encoding="utf-8")
    assert "max-width:1260px" in source
    assert ".status-strip" in source
    assert ".member-hero" in source and ".client-hero" in source
    assert ".empty-state" in source
    assert ".page-header" in source and "def _page_header" in source
    assert "def summary_metric" in source and "def work_item_card" in source


def test_primary_surfaces_use_product_facing_page_headers() -> None:
    assert "_page_header(\"今日\"" in _source("render_manager_dashboard", "def _render_member_header")
    assert "_page_header(\"成员\"" in _source("render_members_workspace", "KNOWLEDGE_CATEGORIES")
    assert "_page_header(\"医疗协同\"" in _source("render_collaboration_workspace", "def _report_candidate_label")
    assert 'page_header("更多"' in MORE_SHELL.read_text(encoding="utf-8")
    assert "_page_header(\"健康数据\"" in _source("render_health_data", "def render_medications")


def test_member_health_and_more_use_a_second_level_content_selector() -> None:
    archive = _source("render_member_archive", "def _select_archive_timeline")
    more = MORE_SHELL.read_text(encoding="utf-8")
    assert 'st.radio("成员健康内容", views' in archive
    assert "entries = [" in more and 'more-open-' in more


def test_report_first_screen_is_result_first_and_progressively_disclosed() -> None:
    source = _source("render_report_review", "def _render_report_candidate_group")
    assert "_status_strip(" in source
    assert "需要处理" in source
    assert 'with st.expander(f"需要医生复核' in source
    assert 'with st.expander("查看解析详情（高级信息）")' in source


def test_more_root_remains_a_lazy_menu() -> None:
    source = MORE_SHELL.read_text(encoding="utf-8")
    assert 'if more is None:' in source
    assert source.index('if more is None:') < source.index('render_integration_center()')
    assert "管理工具" in source


def test_primary_navigation_and_collaboration_are_task_and_member_oriented() -> None:
    source = APP.read_text(encoding="utf-8")
    more = MORE_SHELL.read_text(encoding="utf-8")
    assert '["今日", "成员", "医疗协同", "服务运营", "更多"]' in source
    assert 'options = ["风险规则", "操作记录", "系统"]' in more
    assert "render_integration_center()" in more
    assert 'with st.expander("AI 质量治理（高级）")' in more
    assert "健管培训助手" not in more
    collaboration = _source("render_collaboration_workspace", "def _report_candidate_label")
    assert 'st.radio("医疗协同内容", ["内部医生", "外部医疗"]' in collaboration


def test_surface_switcher_is_global_and_member_center_is_not_a_more_subpage() -> None:
    source = APP.read_text(encoding="utf-8")
    main = _source("main", "if __name__")
    more = MORE_SHELL.read_text(encoding="utf-8")
    assert '"运营后台", "成员健康中心"' in _source("_render_surface_switcher", "def _render_member_center_navigation")
    assert "_render_surface_switcher" in main and 'if surface == "成员健康中心"' in main
    assert "客户视图预览" not in more and "client-preview-open" not in more


def test_member_center_health_keeps_the_timeline_out_of_home() -> None:
    home = _source("_render_client_home", "def _render_client_plan")
    archive = _source("render_client_health_hub", "def render_member_client_view")
    timeline = _source("render_longitudinal_timeline", "def _client_device_status")
    assert "render_longitudinal_timeline" not in home
    client = _source("render_member_client_view", "def render_global_doctor_workspace")
    assert 'render_longitudinal_timeline(patient, key_scope="member-center-journey", client_view=True)' in client
    assert "HealthTimelineService().get_timeline" in timeline
    assert "not client_view" in timeline


def test_timeline_is_an_aggregated_health_story_with_one_selected_detail_panel() -> None:
    timeline = _source("render_longitudinal_timeline", "def _client_device_status")
    assert '"健康数据"' in timeline
    assert '"health_data_summary"' in timeline
    assert '"查看这段时间的完整健康数据"' in timeline
    assert "timeline-selected-" in timeline
    assert "top_columns" not in timeline and "bottom_columns" not in timeline
    assert "查看前后对比" in timeline


def test_member_center_exposes_longitudinal_record_as_a_primary_view() -> None:
    client = _source("render_member_client_view", "def render_global_doctor_workspace")
    assert 'page in {"历程", "健康历程"}' in client
    assert "_render_client_checkup_page(patient)" in _source("render_client_health_hub", "def render_member_client_view")


def test_member_center_health_keeps_report_upload_inside_the_checkup_view() -> None:
    archive = _source("_render_client_checkup_page", "def _render_client_medical_archive")
    labels = _source("_report_upload_label", "def _report_upload_state")
    state = _source("_report_upload_state", "def _render_client_report_intake_entry")
    assert "体检报告" in archive
    assert "render_member_report_upload(patient)" in archive
    assert "上传新体检报告" in labels and "上传体检报告" in labels
    assert "尚未上传体检报告" in state
