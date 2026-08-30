"""Guards for the two-level HealthOps product architecture.

Details, evidence and selected records are intentionally rendered in the
current page.  These checks keep them out of an additional business route.
"""

from pathlib import Path


APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
AUDIT = APP.parent / "docs" / "NAVIGATION_DEPTH_AUDIT.md"


def _source(name: str, next_marker: str) -> str:
    return APP.read_text(encoding="utf-8").split(f"def {name}", 1)[1].split(next_marker, 1)[0]


def test_primary_navigation_is_limited_to_five_per_surface() -> None:
    source = APP.read_text(encoding="utf-8")
    assert '["首页", "健康", "历程", "计划", "服务"]' in source
    assert '["今日", "成员", "医疗协同", "服务运营", "更多"]' in source


def test_member_health_has_at_most_five_second_level_views() -> None:
    health = _source("render_client_health_hub", "def render_member_client_view")
    assert 'allowed = ["健康概览", "健康数据", "体检", "医疗档案"]' in health
    assert "request_navigation" not in health


def test_member_plan_service_and_profile_keep_details_in_their_current_page() -> None:
    plan = _source("_render_client_plan", "def render_member_service_management")
    service = _source("_render_client_service", "def _render_client_profile")
    profile = _source("_render_client_profile", "def _render_client_health_overview")
    assert 'st.radio("计划内容", ["当前方案", "我的任务", "阶段结果"]' in plan
    assert 'st.radio("服务内容", ["可用服务", "我的申请", "服务记录"]' in service
    assert 'st.radio("个人设置内容", ["资料", "设备与数据", "隐私授权"]' in profile


def test_reports_medical_doctors_services_and_timeline_use_inline_detail_patterns() -> None:
    report = _source("_render_client_checkup_page", "def _render_client_medical_archive")
    medical = _source("render_member_medical_workspace", "def render_member_detail")
    collaboration = _source("render_collaboration_workspace", "def render_service_operations_workspace")
    services = _source("render_service_operations_workspace", "def _report_candidate_label")
    external = _source("render_external_doctor_workspace", "def render_demo_story")
    timeline = _source("render_longitudinal_timeline", "def _client_device_status")
    assert "st.columns([1, 1.7]" in report and "render_member_report_upload(patient)" in report
    assert 'st.radio("医疗内容", ["医生复核", "用药", "检查", "手术住院"]' in medical
    assert "member-medical-event-selected" in medical and "detail_panel(" in medical
    assert 'st.radio("医疗协同内容", ["内部医生", "外部医疗"]' in collaboration
    assert "service-operations-selected" in services and "detail_panel(" in services
    assert "external-medical-selected" in external and "detail_panel(" in external
    assert "timeline-selected-" in timeline and "_render_evidence_action" in timeline


def test_member_detail_and_more_respect_secondary_navigation_limits() -> None:
    source = APP.read_text(encoding="utf-8")
    detail = _source("render_member_detail", "def render_member_archive")
    more = _source("render_more_workspace", "def render_oversight_summary")
    assert '["概览", "管理", "健康", "医疗", "历程"]' in detail
    assert 'options = ["数据接入与设备", "知识库", "风险规则", "操作记录", "系统信息"]' in more


def test_depth_audit_documents_only_depth_one_or_two_business_paths() -> None:
    audit = AUDIT.read_text(encoding="utf-8")
    assert "Depth 1/2" in audit
    assert "Depth 1/2 之外的主要业务导航为 0" in audit
    for flow in ("上传体检", "查看报告 / 对比", "健康历程", "医生复核", "服务履约", "查看依据"):
        assert flow in audit
