"""VNext guards for the first-class longitudinal health story."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamlit_app.py"
LONGITUDINAL = ROOT / "src" / "executive_health_ai" / "services" / "longitudinal.py"
LEGACY = ROOT / "src" / "executive_health_ai" / "services" / "timeline.py"


def _source(name: str, next_marker: str) -> str:
    from tests.ui_source import source
    return source(name, next_marker)


def test_member_timeline_is_a_primary_destination_not_a_health_subpage() -> None:
    navigation = _source("_render_member_center_navigation", "def _empty_state")
    health = _source("render_client_health_hub", "def render_member_client_view")
    client = _source("render_member_client_view", "def render_global_doctor_workspace")
    assert '["首页", "健康", "计划", "服务", "历程"]' in navigation
    assert '"健康历程"' not in health
    assert 'page in {"历程", "健康历程"}' in client
    assert 'member_pages.timeline(_ui_adapter(), patient)' in client


def test_ops_member_has_first_level_timeline_and_service_stays_in_management_summary() -> None:
    detail = _source("render_member_detail", "def render_member_archive")
    assert '["概览", "健康", "管理", "医疗", "历程"]' in detail
    assert 'timeline(app, patient, client_view=False)' in detail
    assert 'workflow.management(app, patient)' in detail
    # The member tab delegates to the executable workspace; the legacy service
    # summary and annual linked-service view must both remain reachable there.
    from executive_health_ai.ui.pages.manager import workflow
    import inspect
    management = inspect.getsource(workflow.management)
    assert 'render_member_service_management(patient)' in management
    assert "'关联服务'" in management


def test_new_product_timeline_uses_longitudinal_service_and_monthly_summary_name_is_clear() -> None:
    timeline = _source("render_longitudinal_timeline", "def _client_device_status")
    longitudinal = LONGITUDINAL.read_text(encoding="utf-8")
    legacy = LEGACY.read_text(encoding="utf-8")
    assert "TimelineV4Service" in timeline and "HealthTimelineService" in timeline
    assert "build_patient_timeline" not in timeline
    assert "class MonthlyTimelineSummaryService" in longitudinal
    assert "class HealthDataSummaryService" not in longitudinal
    assert "Deprecated compatibility projection" in legacy

