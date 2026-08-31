"""Product IA V1 guardrails: page boundaries are functional, not cosmetic."""

from pathlib import Path


APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
MORE_SHELL = APP.parent / "src" / "executive_health_ai" / "ui" / "pages" / "shell.py"


def _source(name: str, next_marker: str) -> str:
    return APP.read_text(encoding="utf-8").split(f"def {name}", 1)[1].split(next_marker, 1)[0]


def test_member_home_has_four_decision_sections_and_no_full_record() -> None:
    home = _source("_render_client_home", "def _render_client_plan")
    for heading in ("我现在怎么样", "今天", "最近变化", "我的下一步"):
        assert heading in home
    assert "render_longitudinal_timeline" not in home
    assert "render_member_report_upload" not in home


def test_member_health_uses_four_inline_views_and_timeline_is_primary() -> None:
    health = _source("render_client_health_hub", "def render_global_doctor_workspace")
    assert 'allowed = ["健康概览", "健康数据", "体检", "医疗档案"]' in health
    assert 'st.radio("健康内容", allowed' in health
    client = _source("render_member_client_view", "def render_global_doctor_workspace")
    assert 'page in {"历程", "健康历程"}' in client
    assert 'render_longitudinal_timeline(patient, key_scope="member-center-journey", client_view=True)' in client


def test_member_plan_has_four_execution_sections() -> None:
    plan = _source("_render_client_plan", "def render_member_service_management")
    for heading in ("当前方案", "我的任务", "阶段结果"):
        assert heading in plan
    assert "接受方案" in plan and "希望调整" in plan and "暂缓" in plan


def test_member_service_uses_categories_before_service_items() -> None:
    service = _source("_render_client_service", "def _render_client_profile")
    for heading in ("当前会员", "服务分类", "我的申请", "服务记录"):
        assert heading in service
    assert "client-service-category-filter" in service
    assert "member-service-request" in service


def test_member_and_ops_primary_navigation_have_at_most_five_destinations() -> None:
    source = APP.read_text(encoding="utf-8")
    assert '["首页", "健康", "历程", "计划", "服务"]' in source
    assert '["今日", "成员", "医疗协同", "服务运营", "更多"]' in source


def test_ops_today_is_kpis_plus_worklist_and_member_detail_has_five_tabs() -> None:
    today = _source("render_manager_dashboard", "def _render_member_header")
    member = _source("render_member_detail", "def render_member_archive")
    assert "_status_strip(" in today and '"优先处理"' in today
    assert '["概览", "管理", "健康", "医疗", "历程"]' in member


def test_medical_collaboration_and_service_operations_are_separate() -> None:
    collaboration = _source("render_collaboration_workspace", "def render_service_operations_workspace")
    service_ops = _source("render_service_operations_workspace", "def _report_candidate_label")
    assert "内部医生" in collaboration and "外部医疗" in collaboration
    assert "服务工作列表" in service_ops and "service-operations-selected" in service_ops
    assert "render_doctor_reviews" not in service_ops


def test_more_is_configuration_only_and_navigation_has_no_engine_side_effects() -> None:
    source = APP.read_text(encoding="utf-8")
    more = MORE_SHELL.read_text(encoding="utf-8")
    main = _source("main", 'if __name__ == "__main__"')
    assert "数据接入与设备" in more and "风险规则" in more and "知识库" in more
    assert all(token not in main for token in ("RiskEvaluationService", "ReportParsingService", "ingest(", "LocalLLM"))


def test_report_and_timeline_keep_evidence_as_a_deeper_layer() -> None:
    source = APP.read_text(encoding="utf-8")
    report = _source("render_report_review", "def render_member_detail")
    timeline = _source("render_longitudinal_timeline", "def _client_device_status")
    assert "查看依据" in source
    assert "_render_evidence_action" in report and "_render_evidence_action" in timeline
