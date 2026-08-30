"""V4 correlated lifecycle projection: bounded trends + major event lanes."""

from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from streamlit.testing.v1 import AppTest

from executive_health_ai.blood_pressure import TOKYO_TIMEZONE
from executive_health_ai.models import Base, Observation, Patient
from executive_health_ai.services.longitudinal import (
    HealthTimelineService,
    TimelineEvent,
    TimelineViewport,
    TimelineV4Service,
)


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)()


def _member(session: Session) -> Patient:
    member = Patient(external_id="synthetic-timeline-v4", timezone="Asia/Tokyo")
    session.add(member)
    session.flush()
    return member


def _event(event_type: str, at: datetime, *, risk_level: str | None = None) -> TimelineEvent:
    return HealthTimelineService()._display_event(TimelineEvent(
        occurred_at=at,
        event_type=event_type,
        title="合成重大事件",
        summary="仅供生命轴聚合验证。",
        severity=risk_level or "BLUE",
        source="synthetic",
        expandable_details={},
        group_key=f"{event_type}:{at.isoformat()}",
        risk_level=risk_level,
    ))


def test_v4_contains_bounded_metric_series_and_major_event_lanes() -> None:
    session, member = _session(), None
    member = _member(session)
    start = datetime(2026, 2, 1, tzinfo=TOKYO_TIMEZONE)
    for day in range(45):
        at = start + timedelta(days=day)
        session.add_all((
            Observation(patient_id=member.id, observed_at=at, metric_code="glucose", value_numeric=Decimal("100") + day, unit="mg/dL", source="synthetic_cgm", quality_flag="valid"),
            Observation(patient_id=member.id, observed_at=at, metric_code="sleep_duration", value_numeric=Decimal("420") + day, unit="min", source="synthetic_ring", quality_flag="valid"),
        ))
    session.flush()
    events = [
        _event("program_start", start + timedelta(days=2)),
        _event("medication_change", start + timedelta(days=4)),
        _event("risk", start + timedelta(days=7), risk_level="YELLOW"),
        _event("doctor_review", start + timedelta(days=10)),
        _event("procedure", start + timedelta(days=15)),
        _event("service", start + timedelta(days=20)),
        _event("outcome", start + timedelta(days=30)),
    ]
    view = TimelineV4Service().build_view(
        session, member.id, start=start, end=start + timedelta(days=44),
        metric_codes=("glucose", "sleep_duration"), events=events,
    )

    assert {item.metric_code for item in view.metric_series} == {"glucose", "sleep_duration"}
    assert all(item.aggregation == "日" for item in view.metric_series)
    assert {item.lane for item in view.events} >= {"MANAGEMENT", "MEDICATION", "RISK", "MEDICAL"}
    assert all(item.event_type != "observation" for item in view.events)
    assert view.summary.risk_counts["medium"] == 1
    assert view.summary.medical_counts["医生复核"] == 1
    assert view.summary.service_counts["服务"] == 1


def test_v4_time_window_bounds_series_and_downsamples_high_frequency_cgm() -> None:
    session = _session()
    member = _member(session)
    start = datetime(2026, 1, 1, tzinfo=TOKYO_TIMEZONE)
    for offset in range(1_000):
        session.add(Observation(
            patient_id=member.id, observed_at=start + timedelta(minutes=30 * offset), metric_code="glucose",
            value_numeric=Decimal("100"), unit="mg/dL", source="synthetic_cgm", quality_flag="valid",
        ))
    session.flush()
    window_start, window_end = start + timedelta(days=5), start + timedelta(days=24)
    view = TimelineV4Service().build_view(
        session, member.id, start=window_start, end=window_end, metric_codes=("glucose",), events=[],
    )

    series = view.metric_series[0]
    assert series.aggregation == "日"
    assert len(series.points) <= 20
    assert all(window_start <= point["at"] <= window_end for point in series.points)
    assert len(series.points) < 1_000


def test_v4_time_window_filters_events_and_recalculates_summary() -> None:
    session = _session()
    member = _member(session)
    start = datetime(2026, 2, 1, tzinfo=TOKYO_TIMEZONE)
    old_risk = _event("risk", start - timedelta(days=1), risk_level="RED")
    current_risk = _event("risk", start + timedelta(days=3), risk_level="YELLOW")
    current_medication = _event("medication_change", start + timedelta(days=5))
    view = TimelineV4Service().build_view(
        session, member.id, start=start, end=start + timedelta(days=10), metric_codes=(),
        events=[old_risk, current_risk, current_medication],
    )

    assert list(view.events) == [current_risk, current_medication]
    assert view.summary.risk_counts == {"low": 0, "medium": 1, "high": 0}


def test_v4_report_and_monthly_summary_remain_aggregated_major_events() -> None:
    report = _event("report", datetime(2026, 3, 1, tzinfo=TOKYO_TIMEZONE))
    month = _event("health_data_summary", datetime(2026, 3, 31, tzinfo=TOKYO_TIMEZONE))
    session = _session()
    member = _member(session)
    view = TimelineV4Service().build_view(
        session, member.id, start=None, end=datetime(2026, 4, 1, tzinfo=TOKYO_TIMEZONE),
        metric_codes=(), events=[report, month],
    )
    assert [event.event_type for event in view.events] == ["report", "health_data_summary"]
    assert len([event for event in view.events if event.event_type == "report"]) == 1
    assert len([event for event in view.events if event.event_type == "health_data_summary"]) == 1


def test_v4_renderer_uses_trend_summary_lanes_and_one_inspector() -> None:
    source = Path(__file__).resolve().parents[1].joinpath("streamlit_app.py").read_text(encoding="utf-8")
    timeline = source.split("def render_longitudinal_timeline", 1)[1].split("def _client_device_status", 1)[0]
    assert "健康趋势" in timeline
    assert "当前期间总结" in timeline
    assert 'with section_frame("健康生命轴"' in timeline
    assert "inspector.container" in timeline
    assert "健康历程时间范围" in timeline
    assert "st.slider(" in timeline
    assert "_request_timeline_range" in timeline
    assert "TimelineV4Service" in timeline
    assert "HealthTimelineService().get_timeline" in timeline
    assert "view_health_data" not in timeline  # actions stay in the one inspector below.
    assert "timeline-viewport-" in source
    assert "_render_lifecycle_grid" in timeline
    assert "timeline-card-select-" in source
    assert "查看 >" not in timeline


def test_semantic_year_view_clusters_events_by_month_and_month_drills_down() -> None:
    session = _session()
    member = _member(session)
    service = TimelineV4Service()
    viewport = TimelineViewport(
        datetime(2026, 1, 1, tzinfo=TOKYO_TIMEZONE), datetime(2026, 12, 31, 23, 59, tzinfo=TOKYO_TIMEZONE), "YEAR",
    )
    events = [
        _event("assessment", datetime(2026, 1, 10, tzinfo=TOKYO_TIMEZONE)),
        _event("medication_change", datetime(2026, 7, 9, tzinfo=TOKYO_TIMEZONE)),
        _event("medication_change", datetime(2026, 7, 9, 10, tzinfo=TOKYO_TIMEZONE)),
        _event("report", datetime(2026, 7, 10, tzinfo=TOKYO_TIMEZONE)),
        _event("outcome", datetime(2026, 12, 20, tzinfo=TOKYO_TIMEZONE)),
    ]
    view = service.get_timeline_view(session, member.id, viewport=viewport, metric_codes=(), event_types=None)
    # Substitute deterministic synthetic major events while exercising the
    # same semantic clustering projection.
    clusters = service._semantic_clusters(tuple(events), viewport)

    assert len(clusters) == 3
    july = next(item for item in clusters if item.period_start.month == 7)
    assert july.event_count == 3 and july.zoom_target is not None
    assert july.zoom_target.zoom_level == "MONTH"
    assert july.zoom_target.start.date().isoformat() == "2026-07-01"
    assert view.viewport == viewport


def test_month_and_week_views_group_same_day_without_raw_observation_nodes() -> None:
    service = TimelineV4Service()
    events = [
        _event("medication_change", datetime(2026, 7, 9, 8, tzinfo=TOKYO_TIMEZONE)),
        _event("medication_change", datetime(2026, 7, 9, 12, tzinfo=TOKYO_TIMEZONE)),
        _event("report", datetime(2026, 7, 10, tzinfo=TOKYO_TIMEZONE)),
    ]
    month = TimelineViewport(datetime(2026, 7, 1, tzinfo=TOKYO_TIMEZONE), datetime(2026, 7, 31, 23, tzinfo=TOKYO_TIMEZONE), "MONTH")
    week = TimelineViewport(datetime(2026, 7, 6, tzinfo=TOKYO_TIMEZONE), datetime(2026, 7, 19, 23, tzinfo=TOKYO_TIMEZONE), "WEEK")

    month_clusters = service._semantic_clusters(tuple(events), month)
    week_clusters = service._semantic_clusters(tuple(events), week)
    assert len(month_clusters) == len(week_clusters) == 2
    assert month_clusters[0].event_count == 2
    assert all(event.event_type != "observation" for cluster in week_clusters for event in cluster.main_events)


def test_range_slider_replaces_month_click_as_primary_control_and_grid_rows_stay_compact() -> None:
    source = Path(__file__).resolve().parents[1].joinpath("streamlit_app.py").read_text(encoding="utf-8")
    timeline = source.split("def render_longitudinal_timeline", 1)[1].split("def _client_device_status", 1)[0]
    grid = source.split("def _render_lifecycle_grid", 1)[1].split("def render_longitudinal_timeline", 1)[0]
    longitudinal = Path(__file__).resolve().parents[1].joinpath("src", "executive_health_ai", "services", "longitudinal.py").read_text(encoding="utf-8")

    assert "timeline-range-slider-ui" in source
    assert "近7天" in timeline and "近30天" in timeline and "近3个月" in timeline and "近1年" in timeline and "全部" in timeline
    assert 'st.columns([2.8, 1, 2.8]' in grid
    assert "proportional_y" not in longitudinal
    assert "点击月份" not in timeline


def test_detailed_spine_is_chronological_without_calendar_day_spacing() -> None:
    service = TimelineV4Service()
    viewport = TimelineViewport(
        datetime(2026, 7, 1, tzinfo=TOKYO_TIMEZONE), datetime(2026, 7, 31, 23, 59, tzinfo=TOKYO_TIMEZONE), "MONTH",
    )
    events = (
        _event("program_start", datetime(2026, 7, 3, tzinfo=TOKYO_TIMEZONE)),
        _event("doctor_review", datetime(2026, 7, 9, tzinfo=TOKYO_TIMEZONE)),
        _event("report", datetime(2026, 7, 10, tzinfo=TOKYO_TIMEZONE)),
        _event("health_data_summary", datetime(2026, 7, 31, tzinfo=TOKYO_TIMEZONE)),
    )
    clusters = service._semantic_clusters(events, viewport)
    assert [item.period_start.day for item in clusters] == [3, 9, 10, 31]
    assert [index for index, _ in enumerate(clusters)] == [0, 1, 2, 3]


def test_timeline_range_slider_changes_the_user_path_without_widget_state_error() -> None:
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "streamlit_app.py")
    app.run(timeout=30)
    next(item for item in app.radio if item.label == "工作区").set_value("成员")
    app.run(timeout=30)
    next(item for item in app.button if item.label == "查看成员").click()
    app.run(timeout=30)
    next(item for item in app.button if item.label == "查看完整健康历程").click()
    app.run(timeout=30)
    slider = next(item for item in app.slider if item.label == "健康历程时间范围")
    latest = datetime.fromtimestamp(slider.max / 1_000_000, tz=TOKYO_TIMEZONE).date()
    slider.set_value((latest - timedelta(days=30), latest))
    app.run(timeout=30)
    assert not app.exception
    slider = next(item for item in app.slider if item.label == "健康历程时间范围")
    assert slider.value[1] - slider.value[0] <= timedelta(days=31)


def test_timeline_shortcut_and_slider_remain_synchronized() -> None:
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "streamlit_app.py")
    app.run(timeout=30)
    next(item for item in app.radio if item.label == "工作区").set_value("成员")
    app.run(timeout=30)
    next(item for item in app.button if item.label == "查看成员").click()
    app.run(timeout=30)
    next(item for item in app.button if item.label == "查看完整健康历程").click()
    app.run(timeout=30)

    next(item for item in app.button if item.label == "近7天").click()
    app.run(timeout=30)

    assert not app.exception
    slider = next(item for item in app.slider if item.label == "健康历程时间范围")
    assert (slider.value[1] - slider.value[0]).days <= 7


def test_trend_is_data_only_and_major_event_strip_is_removed() -> None:
    source = Path(__file__).resolve().parents[1].joinpath("streamlit_app.py").read_text(encoding="utf-8")
    trend = source.split("def _render_timeline_v4_trends", 1)[1].split("def _render_timeline_v4_summary", 1)[0]
    timeline = source.split("def render_longitudinal_timeline", 1)[1].split("def _client_device_status", 1)[0]

    assert "mark_rule" not in trend
    assert "重大事件标记" not in trend
    assert "trend_event" not in trend
    assert "TREND_EVENT_FILTERS" not in source
    assert "健康历程时间范围" in timeline


def test_trend_chart_pairs_sleep_deep_sleep_and_steps_calories() -> None:
    source = Path(__file__).resolve().parents[1].joinpath("streamlit_app.py").read_text(encoding="utf-8")
    trend = source.split("def _render_timeline_v4_trends", 1)[1].split("def _render_timeline_v4_summary", 1)[0]

    assert "睡眠趋势 · 总睡眠 / 深度睡眠" in trend
    assert "深度睡眠" in trend
    assert "活动趋势 · 步数 / 活动消耗" in trend
    assert "活动消耗（kcal）" in trend


def test_compact_event_card_hides_demo_names_and_keeps_risk_text() -> None:
    import streamlit_app

    yellow = _event("risk", datetime(2026, 7, 9, tzinfo=TOKYO_TIMEZONE), risk_level="YELLOW")
    medication = _event("medication_change", datetime(2026, 7, 10, tzinfo=TOKYO_TIMEZONE))
    medication = replace(medication, title="开始用药记录：Demo Medication A")
    assert streamlit_app._timeline_card_text(yellow)[0] == "中风险"
    assert streamlit_app._timeline_card_text(medication)[1] == "用药记录"
    direct_demo = replace(medication, title="Demo Medication A")
    assert streamlit_app._timeline_card_text(direct_demo)[1] == "用药记录"


def test_grid_uses_compact_cards_and_short_neutral_connectors() -> None:
    source = Path(__file__).resolve().parents[1].joinpath("streamlit_app.py").read_text(encoding="utf-8")
    grid = source.split("def _render_lifecycle_grid", 1)[1].split("def render_longitudinal_timeline", 1)[0]

    card = source.split("def _timeline_lane_card", 1)[1].split("def _timeline_spine_markup", 1)[0]
    assert "timeline-card-select-" in card
    assert "timeline-spine-node" in source
    assert "max-width:292px" in source
    assert "查看详情" not in grid


def test_grid_has_stable_three_column_timeline_rows() -> None:
    source = Path(__file__).resolve().parents[1].joinpath("streamlit_app.py").read_text(encoding="utf-8")
    grid = source.split("def _render_lifecycle_grid", 1)[1].split("def render_longitudinal_timeline", 1)[0]
    assert 'st.columns([2.8, 1, 2.8], gap="small")' in grid
    assert "timeline-row-" in grid
    assert "timeline-row-spine" in source


def test_left_and_right_lane_mapping_is_explicit() -> None:
    import streamlit_app

    assert streamlit_app._lifecycle_lane(_event("program_start", datetime(2026, 7, 9, tzinfo=TOKYO_TIMEZONE))) == "LEFT"
    assert streamlit_app._lifecycle_lane(_event("medication_change", datetime(2026, 7, 9, tzinfo=TOKYO_TIMEZONE))) == "LEFT"
    assert streamlit_app._lifecycle_lane(_event("service", datetime(2026, 7, 9, tzinfo=TOKYO_TIMEZONE))) == "LEFT"
    for event_type in ("risk", "doctor_review", "external_referral", "report", "procedure", "surgery", "hospitalization", "health_data_summary", "outcome"):
        assert streamlit_app._lifecycle_lane(_event(event_type, datetime(2026, 7, 9, tzinfo=TOKYO_TIMEZONE))) == "RIGHT"


def test_date_is_owned_by_the_center_spine_column() -> None:
    import streamlit_app

    markup = streamlit_app._timeline_spine_markup(
        datetime(2026, 7, 10, tzinfo=TOKYO_TIMEZONE).date(), has_left=True, has_right=True,
        risk_level=None, selected=False, has_next=True,
    )
    assert "07-10" in markup and "timeline-spine-node" in markup
    assert "2026" not in markup


def test_same_day_events_are_grouped_once_per_lane() -> None:
    import streamlit_app

    day = datetime(2026, 7, 9, tzinfo=TOKYO_TIMEZONE)
    rows = streamlit_app._lifecycle_rows([_event("medication_change", day), _event("medication_change", day + timedelta(hours=1)), _event("medication_change", day + timedelta(hours=2))])
    assert len(rows) == 1
    assert len(rows[0]["left"]) == 3 and not rows[0]["right"]


def test_same_day_left_and_right_events_share_one_date_row() -> None:
    import streamlit_app

    day = datetime(2026, 8, 15, tzinfo=TOKYO_TIMEZONE)
    rows = streamlit_app._lifecycle_rows([_event("program_start", day), _event("risk", day, risk_level="YELLOW")])
    assert len(rows) == 1
    assert len(rows[0]["left"]) == len(rows[0]["right"]) == 1


def test_cards_hide_technical_synthetic_names_without_detail_buttons() -> None:
    import streamlit_app

    report = replace(_event("report", datetime(2026, 7, 10, tzinfo=TOKYO_TIMEZONE)), title="合成年度体检报告（较早）")
    _, title, _ = streamlit_app._timeline_card_text(report)
    source = Path(__file__).resolve().parents[1].joinpath("streamlit_app.py").read_text(encoding="utf-8")
    grid = source.split("def _render_lifecycle_grid", 1)[1].split("def render_longitudinal_timeline", 1)[0]
    assert title == "年度体检"
    assert "查看详情" not in grid
    assert "查看 >" not in source


def test_event_selection_is_a_single_card_control_without_floating_or_orphan_actions() -> None:
    source = Path(__file__).resolve().parents[1].joinpath("streamlit_app.py").read_text(encoding="utf-8")
    card = source.split("def _timeline_lane_card", 1)[1].split("def _timeline_spine_markup", 1)[0]

    assert "st.markdown(" not in card
    assert card.count("st.button(") == 1
    assert 'label = f"{badge}\\n\\n**{title}**\\n\\n{summary}"' in card
    assert "查看 >" not in card and "查看详情" not in card


def test_technical_timeline_titles_are_translated_into_human_health_copy() -> None:
    import streamlit_app

    event_day = datetime(2026, 8, 15, tzinfo=TOKYO_TIMEZONE)
    medication = replace(_event("medication_change", event_day), title="Demo Medication B")
    program = replace(_event("program_start", event_day), title="90-Day Metabolic Health Program")
    assessment = replace(_event("assessment", event_day), title="synthetic_assessment")

    assert streamlit_app._timeline_card_text(medication)[1] == "用药记录"
    assert streamlit_app._timeline_card_text(program)[1] == "90天代谢健康计划"
    assert streamlit_app._timeline_card_text(assessment)[1] == "阶段健康评估"


def test_risk_colours_are_reserved_for_formal_risk_nodes() -> None:
    import streamlit_app

    risk_markup = streamlit_app._timeline_spine_markup(
        datetime(2026, 7, 10, tzinfo=TOKYO_TIMEZONE).date(), has_left=False, has_right=True,
        risk_level="RED", selected=False, has_next=False,
    )
    neutral_markup = streamlit_app._timeline_spine_markup(
        datetime(2026, 7, 10, tzinfo=TOKYO_TIMEZONE).date(), has_left=True, has_right=False,
        risk_level=None, selected=False, has_next=False,
    )
    assert "timeline-spine-risk-red" in risk_markup
    assert "timeline-spine-risk" not in neutral_markup


def test_risk_cards_keep_the_same_semantic_level_without_coloring_normal_cards() -> None:
    source = Path(__file__).resolve().parents[1].joinpath("streamlit_app.py").read_text(encoding="utf-8")
    card = source.split("def _timeline_lane_card", 1)[1].split("def _timeline_spine_markup", 1)[0]
    assert "risk_key = event.risk_level.lower()" in card
    assert 'class*="-green-"' in source
    assert 'class*="-yellow-"' in source
    assert 'class*="-red-"' in source


def test_grid_selection_only_updates_the_single_inspector() -> None:
    source = Path(__file__).resolve().parents[1].joinpath("streamlit_app.py").read_text(encoding="utf-8")
    timeline = source.split("def render_longitudinal_timeline", 1)[1].split("def _client_device_status", 1)[0]
    assert "selected_event_key" in timeline
    assert "with inspector.container(border=True)" in timeline
    assert timeline.count("with inspector.container(border=True)") >= 2


def test_clicking_a_timeline_card_updates_the_inspector_without_a_view_button() -> None:
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "streamlit_app.py")
    app.run(timeout=30)
    next(item for item in app.radio if item.label == "工作区").set_value("成员")
    app.run(timeout=30)
    next(item for item in app.button if item.label == "查看成员").click()
    app.run(timeout=30)
    next(item for item in app.button if item.label == "查看完整健康历程").click()
    app.run(timeout=30)

    cards = [item for item in app.button if item.key and item.key.startswith("timeline-card-select-")]
    assert cards and all("查看" not in item.label for item in cards)
    cards[0].click()
    app.run(timeout=30)

    assert not app.exception
    assert any("2026-" in str(item.value) for item in app.markdown)


def test_range_still_filters_the_rows_without_calendar_spacing() -> None:
    import streamlit_app

    events = [
        _event("report", datetime(2026, 7, 10, tzinfo=TOKYO_TIMEZONE)),
        _event("risk", datetime(2026, 8, 15, tzinfo=TOKYO_TIMEZONE), risk_level="YELLOW"),
    ]
    filtered = [event for event in events if event.occurred_at.date() <= datetime(2026, 7, 31, tzinfo=TOKYO_TIMEZONE).date()]
    assert len(streamlit_app._lifecycle_rows(filtered)) == 1


def test_mobile_fallback_and_no_absolute_positioning_architecture() -> None:
    source = Path(__file__).resolve().parents[1].joinpath("streamlit_app.py").read_text(encoding="utf-8")
    grid = source.split("def _render_lifecycle_grid", 1)[1].split("def render_longitudinal_timeline", 1)[0]
    assert "@media (max-width: 760px)" in source
    assert "position:absolute" not in grid.replace(" ", "")


def test_grid_keeps_evidence_and_risk_regression_paths() -> None:
    source = Path(__file__).resolve().parents[1].joinpath("streamlit_app.py").read_text(encoding="utf-8")
    timeline = source.split("def render_longitudinal_timeline", 1)[1].split("def _client_device_status", 1)[0]
    assert "_render_evidence_action(" in timeline
    assert "_timeline_risk_indicator(event)" in timeline
