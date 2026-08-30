"""VNext guards for the first-class longitudinal health story."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamlit_app.py"
LONGITUDINAL = ROOT / "src" / "executive_health_ai" / "services" / "longitudinal.py"
LEGACY = ROOT / "src" / "executive_health_ai" / "services" / "timeline.py"


def _source(name: str, next_marker: str) -> str:
    return APP.read_text(encoding="utf-8").split(f"def {name}", 1)[1].split(next_marker, 1)[0]


def test_member_timeline_is_a_primary_destination_not_a_health_subpage() -> None:
    navigation = _source("_render_member_center_navigation", "def _empty_state")
    health = _source("render_client_health_hub", "def render_member_client_view")
    client = _source("render_member_client_view", "def render_global_doctor_workspace")
    assert '["首页", "健康", "历程", "计划", "服务"]' in navigation
    assert '"健康历程"' not in health
    assert 'page in {"历程", "健康历程"}' in client
    assert 'render_longitudinal_timeline(patient, key_scope="member-center-journey", client_view=True)' in client


def test_ops_member_has_first_level_timeline_and_service_stays_in_management_summary() -> None:
    detail = _source("render_member_detail", "def render_member_archive")
    assert '["概览", "管理", "健康", "医疗", "历程"]' in detail
    assert 'render_longitudinal_timeline(patient, key_scope="member-journey")' in detail
    assert 'render_member_service_management(patient)' in detail


def test_new_product_timeline_uses_longitudinal_service_and_monthly_summary_name_is_clear() -> None:
    timeline = _source("render_longitudinal_timeline", "def _client_device_status")
    longitudinal = LONGITUDINAL.read_text(encoding="utf-8")
    legacy = LEGACY.read_text(encoding="utf-8")
    assert "TimelineV4Service" in timeline and "HealthTimelineService" in timeline
    assert "build_patient_timeline" not in timeline
    assert "class MonthlyTimelineSummaryService" in longitudinal
    assert "class HealthDataSummaryService" not in longitudinal
    assert "Deprecated compatibility projection" in legacy

