"""Timeline presentation must keep risk state separate from event category."""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from executive_health_ai.services.longitudinal import (
    HealthTimelineService,
    TimelineEvent,
    get_timeline_event_type_display,
)


def _event(event_type: str, severity: str = "BLUE", **kwargs) -> TimelineEvent:
    return TimelineEvent(
        occurred_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
        event_type=event_type,
        title="示例事件",
        summary="合成展示数据",
        severity=severity,
        source="synthetic",
        expandable_details={},
        **kwargs,
    )


def test_only_formal_risk_events_receive_a_traffic_light_indicator() -> None:
    service = HealthTimelineService()
    risk = service._display_event(_event("risk", "YELLOW", risk_level="YELLOW"))
    doctor = service._display_event(_event("doctor_review", "BLUE"))
    report = service._display_event(_event("report", "AMBER"))
    medication = service._display_event(_event("medication_change", "BLUE"))
    health_data = service._display_event(_event("health_data_summary", "AMBER"))

    assert risk.risk_indicator == "TRAFFIC_LIGHT" and risk.risk_label == "中风险"
    assert all(item.risk_indicator == "NONE" and item.risk_level is None for item in (doctor, report, medication, health_data))


def test_risk_traffic_lights_and_unknown_are_accessible_and_distinct() -> None:
    service = HealthTimelineService()
    low = service._display_event(_event("risk", "GREEN", risk_level="GREEN"))
    medium = service._display_event(_event("risk", "YELLOW", risk_level="YELLOW"))
    high = service._display_event(_event("risk", "RED", risk_level="RED"))
    unknown = service._display_event(_event("risk", "GRAY", risk_level="UNKNOWN"))

    assert (low.risk_indicator, low.risk_label) == ("TRAFFIC_LIGHT", "低风险")
    assert (medium.risk_indicator, medium.risk_label) == ("TRAFFIC_LIGHT", "中风险")
    assert (high.risk_indicator, high.risk_label) == ("TRAFFIC_LIGHT", "高风险")
    assert (unknown.risk_indicator, unknown.risk_label) == ("NEUTRAL", "暂无正式风险评估")


def test_event_type_badges_are_human_labels_not_internal_enums() -> None:
    assert get_timeline_event_type_display("doctor_review") == "医生"
    assert get_timeline_event_type_display("external_referral") == "外部医疗"
    assert get_timeline_event_type_display("health_data_summary") == "健康数据"
    assert get_timeline_event_type_display("medication_change") == "用药"
    assert get_timeline_event_type_display("program_start") == "健康管理"
    assert get_timeline_event_type_display("unknown_internal_event") == "健康记录"


def test_linked_risk_does_not_turn_report_doctor_or_outcome_into_a_risk_dot() -> None:
    service = HealthTimelineService()
    report = service._display_event(_event("report", "YELLOW"))
    doctor = service._display_event(_event("doctor_review", "RED"))
    outcome = service._display_event(_event("outcome", "GREEN"))

    assert report.risk_indicator == doctor.risk_indicator == outcome.risk_indicator == "NONE"
    assert report.event_type_label == "体检"
    assert doctor.event_type_label == "医生"
    assert outcome.event_type_label == "阶段结果"


def test_synthetic_program_identifier_is_replaced_by_a_program_type_label() -> None:
    service = HealthTimelineService()
    synthetic = SimpleNamespace(title="synthetic_prog", program_type="NINETY_DAY")
    named = SimpleNamespace(title="睡眠稳定计划", program_type="NINETY_DAY")

    assert service._program_display_title(synthetic) == "90天代谢健康计划"
    assert service._program_display_title(named) == "睡眠稳定计划"


def test_renderer_uses_neutral_event_markers_and_traffic_lights_only_for_risk() -> None:
    source = Path(__file__).resolve().parents[1].joinpath("streamlit_app.py").read_text(encoding="utf-8")
    timeline = source.split("def render_longitudinal_timeline", 1)[1].split("def _client_device_status", 1)[0]
    assert "timeline-event-marker" in timeline
    assert "timeline-event-badge" in timeline
    assert "event.risk_indicator" in source.split("def _timeline_risk_indicator", 1)[1].split("def _active_program", 1)[0]
    assert "colors =" not in timeline
    assert "event.severity" not in timeline


def test_timeline_normal_user_view_hides_internal_enum_and_synthetic_program_title() -> None:
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "streamlit_app.py")
    app.run(timeout=30)
    next(item for item in app.radio if item.label == "工作区").set_value("成员")
    app.run(timeout=30)
    next(item for item in app.button if item.label == "查看成员").click()
    app.run(timeout=30)
    assert not app.exception
    visible = "\n".join(
        str(item.value)
        for collection in (app.title, app.subheader, app.caption, app.markdown)
        for item in collection
        if "<style>" not in str(item.value)
    ).lower()
    assert all(value not in visible for value in ("synthetic_prog", "doctor_review", "external_referral", "health_data_summary"))
