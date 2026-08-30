"""Regression guards for the current member-first product reconstruction."""

from pathlib import Path


APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
SERVICE = Path(__file__).resolve().parents[1] / "src" / "executive_health_ai" / "services" / "member_services.py"


def _source(name: str, next_marker: str) -> str:
    return APP.read_text(encoding="utf-8").split(f"def {name}", 1)[1].split(next_marker, 1)[0]


def test_primary_navigation_is_limited_and_role_specific() -> None:
    source = APP.read_text(encoding="utf-8")
    assert '["首页", "健康", "历程", "计划", "服务"]' in source
    assert '["今日", "成员", "医疗协同", "服务运营", "更多"]' in source


def test_client_health_is_a_longitudinal_record_and_reports_are_prominent() -> None:
    archive = _source("render_client_health_hub", "def render_member_client_view")
    assert '"健康"' in archive
    assert 'allowed = ["健康概览", "健康数据", "体检", "医疗档案"]' in archive
    checkup = _source("_render_client_checkup_page", "def _render_client_medical_archive")
    assert "render_member_report_upload(patient)" in checkup and "体检报告" in checkup


def test_new_upload_context_clears_prior_report_selection_without_deleting_history() -> None:
    upload = _source("_reset_report_selection_for_new_file", "def render_report_upload")
    assert "st.session_state.pop(selected_key, None)" in upload
    assert "Historical runs remain in the database" in upload
    member_upload = _source("render_member_report_upload", "def _render_member_baseline_center")
    assert "_reset_report_selection_for_new_file" in member_upload


def test_report_result_has_human_risk_routing_and_standard_evidence_entry() -> None:
    report = _source("render_report_review", "def _render_baseline_draft_action")
    for section in ("本次核心结论", "与上次相比", "需要处理", "主要结果", "查看解析详情（高级信息）"):
        assert section in report
    assert "_report_risk_next_step" in report
    member_upload = _source("render_member_report_upload", "def _render_member_baseline_center")
    assert "本次核心结论" in member_upload and 'with st.expander("查看依据")' in member_upload


def test_health_data_separates_daily_activity_medical_monitoring_and_period_summary() -> None:
    data = _source("render_health_data", "def render_medications")
    for heading in ("基础运动数据", "医疗监测数据", "周 / 月 / 年汇总", "睡眠", "深度睡眠", "步数", "活动消耗", "血压", "血糖"):
        assert heading in data
    assert "unknown" not in data.lower()


def test_timeline_is_primary_and_keeps_a_single_detail_panel_below_the_axis() -> None:
    archive = _source("render_member_archive", "def _select_archive_timeline")
    assert 'views = ["数据", "体检", "基线", "健康史"]' in archive
    detail = _source("render_member_detail", "def render_member_archive")
    assert 'render_longitudinal_timeline(patient, key_scope="member-journey")' in detail
    timeline = _source("render_longitudinal_timeline", "def _client_device_status")
    assert "lifecycle = st.container()" in timeline and "inspector = st.container()" in timeline
    assert "position:absolute" not in timeline
    assert "查看体检报告" in timeline and "查看用药与医疗" in timeline


def test_service_catalogue_covers_health_management_medical_assistance_and_member_rights() -> None:
    source = SERVICE.read_text(encoding="utf-8")
    for category in ("健管服务", "精准诊疗", "就医协助", "远程问诊", "会员权益"):
        assert category in source
    for service in ("健康档案数字化管理", "高端体检个性化定制", "MDT多学科会诊", "预约挂号", "住院协调", "手术协调", "远程问诊"):
        assert service in source
