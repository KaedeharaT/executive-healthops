"""Regression coverage for readable baseline charts and the real snapshot crash."""
from datetime import datetime, timezone
from decimal import Decimal
import inspect
import json
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from streamlit.testing.v1 import AppTest

from executive_health_ai.database import SessionLocal
from executive_health_ai.models import HealthAssessment, Observation, Patient
from executive_health_ai.services.baseline_visualization import (
    BaselineComparisonView, BaselineTrendView, BaselineVisualizationService, TrendPoint, comparison_change,
)
from executive_health_ai.ui.charts.baseline import baseline_trend_chart
from tests.test_baseline_visualization import _baseline, _session

APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


def trend(code="weight", label="体重", unit="kg", before="90", after="85.8"):
    points = (TrendPoint(datetime(2026, 1, 1, tzinfo=timezone.utc), Decimal(before), label, "BASELINE", "已确认年度基线"),)
    if after is not None:
        points += (TrendPoint(datetime(2026, 9, 1, tzinfo=timezone.utc), Decimal(after), label, "FOLLOW_UP"),)
    return BaselineTrendView(code, label, unit, Decimal(before), points)


def test_baseline_chart_x_axis_has_visible_dates_ticks_and_title():
    spec = baseline_trend_chart((trend(),)).to_dict()
    x = spec["layer"][0]["encoding"]["x"]
    assert x["title"] == "时间" and x["axis"]["format"] == "%Y/%m"
    assert all(x["axis"][key] is True for key in ("labels", "ticks", "domain"))


def test_baseline_chart_y_axis_has_units_ticks_and_data_relative_domain():
    spec = baseline_trend_chart((trend(),)).to_dict()
    y = spec["layer"][0]["encoding"]["y"]
    assert y["title"] == "数值（kg）"
    assert all(y["axis"][key] is True for key in ("labels", "ticks", "domain", "grid"))
    assert y["scale"]["zero"] is False
    low, high = y["scale"]["domain"]
    assert 80 < low < 85.8 < 90 < high < 95


def test_chart_baseline_reference_and_current_marker_are_distinct_and_tooltips_safe():
    spec = baseline_trend_chart((trend(),)).to_dict()
    layers = spec["layer"]
    assert any(l["mark"]["type"] == "rule" and l["mark"]["strokeDash"] for l in layers)
    assert any(l["mark"].get("shape") == "diamond" for l in layers)
    rows = next(iter(spec["datasets"].values()))
    assert any(r["类型"] == "当前" and "85.8 kg" in r["标记"] for r in rows)
    assert any(r["类型"] == "年度基线" for r in rows)
    fields = {t["field"] for t in layers[0]["encoding"]["tooltip"]}
    assert {"时间", "数值", "单位", "来源"} <= fields
    assert not {"id", "provider_code", "source_id"} & fields


@pytest.mark.parametrize("after,direction,delta", [("91", "↑ 上升", "1"), ("85.8", "↓ 下降", "-4.2"), ("90", "→ 基本持平", "0")])
def test_baseline_delta_direction(after, direction, delta):
    change = comparison_change(Decimal("90"), Decimal(after), "weight", "kg")
    assert change[0] == Decimal(delta) and change[2] == direction
    row = BaselineComparisonView("weight", "体重", "90", after, "kg", "已记录", *change)
    assert direction in row.delta_text and "kg" in row.delta_text
    assert not any(word in row.delta_text for word in ("改善", "恶化", "风险"))


def test_percentage_guards_zero_and_percentage_unit():
    assert comparison_change(Decimal("0"), Decimal("1"), "weight", "kg")[1] is None
    assert comparison_change(Decimal("6.3"), Decimal("6"), "hba1c", "%")[1] is None
    change = comparison_change(Decimal("90"), Decimal("85.8"), "weight", "kg")
    assert round(change[1], 1) == Decimal("-4.7")


def test_single_point_never_draws_fake_trend():
    assert baseline_trend_chart((trend(after=None),)) is None


def test_blood_pressure_has_two_named_series_and_shared_mmhg_axis():
    chart = baseline_trend_chart((trend("systolic_bp", "收缩压", "mmHg", "132", "126"), trend("diastolic_bp", "舒张压", "mmHg", "86", "80")))
    spec = chart.to_dict()
    assert spec["layer"][0]["encoding"]["color"]["scale"]["domain"] == ["收缩压", "舒张压"]
    assert spec["layer"][0]["encoding"]["y"]["title"] == "数值（mmHg）"


def test_incompatible_units_cannot_share_chart_or_generate_comparison():
    with pytest.raises(ValueError, match="不同单位"):
        baseline_trend_chart((trend(), trend("hba1c", "糖化血红蛋白", "%", "6.3", "6")))
    with _session() as session:
        member, _, _ = _baseline(session)
        session.add(Observation(patient_id=member.id, metric_code="weight", value_numeric=80, unit="stone", observed_at=datetime(2026, 8, 1, tzinfo=timezone.utc), source="manual", quality_flag="valid"))
        session.commit()
        row = next(c for c in BaselineVisualizationService().build(session, member.id).comparisons if c.code == "weight")
        assert row.delta is None and row.percentage is None


def _render_progress(member_id, audience):
    from executive_health_ai.database import SessionLocal
    from executive_health_ai.models import Patient
    from executive_health_ai.services.longitudinal import HealthAssessmentService
    from executive_health_ai.ui.pages.baseline_visualization import render_baseline_overview, render_baseline_visualization
    import streamlit as st
    with SessionLocal() as session:
        patient = session.get(Patient, member_id)
        baseline = HealthAssessmentService().latest_baseline(session, patient.id)
    if audience == "member":
        render_baseline_overview(patient, baseline, session_factory=SessionLocal, key_prefix="projection")
    else:
        render_baseline_visualization(patient, baseline, audience="manager", key_prefix="projection", session_factory=SessionLocal, section_header=st.subheader, empty_state=lambda *args: None, render_metric_evidence=lambda *args, **kwargs: None, format_datetime=str)


def test_member_and_manager_use_identical_baseline_comparison_and_chart(monkeypatch):
    import executive_health_ai.database as db
    from sqlalchemy.orm import sessionmaker
    with _session() as session:
        member, _, _ = _baseline(session)
        session.add(Observation(patient_id=member.id, metric_code="weight", value_numeric=85.8, unit="kg", observed_at=datetime(2026, 9, 1, tzinfo=timezone.utc), source="manual", quality_flag="valid"))
        session.commit()
        monkeypatch.setattr(db, "SessionLocal", sessionmaker(bind=session.bind, expire_on_commit=False))
        member_ui = AppTest.from_function(_render_progress, args=(member.id, "member")).run()
        manager_ui = AppTest.from_function(_render_progress, args=(member.id, "manager")).run()
        assert not member_ui.exception and not manager_ui.exception
        assert member_ui.dataframe[0].value.equals(manager_ui.dataframe[0].value)
        assert member_ui.get("vega_lite_chart")[0].proto.spec == manager_ui.get("vega_lite_chart")[0].proto.spec


def test_timeline_real_adapter_contract():
    namespace = runpy.run_path(APP)
    adapter = namespace["_ui_adapter"]()
    from executive_health_ai.ui.pages.member.experience import timeline
    patient = SimpleNamespace(id="contract-member")
    inspect.signature(timeline).bind(adapter, patient, client_view=True)
    inspect.signature(adapter.render_longitudinal_timeline).bind(patient, key_scope="test", client_view=True)
    assert adapter._label("CONFIRMED") == "已确认"


@pytest.mark.parametrize("medications", [[{"name": "测试用药"}], {"status": "PENDING_SUPPLEMENT", "label": "待补充"}])
def test_member_timeline_renders_assessment_lists_and_pending_dicts_without_boundary(medications):
    with SessionLocal() as session:
        patient = session.scalar(select(Patient).order_by(Patient.created_at))
        assessment = HealthAssessment(patient_id=patient.id, version=999, title="历程快照回归", summary="已确认健康快照", assessment_type="BASELINE", status="CONFIRMED", assessed_at=datetime.now(timezone.utc), confirmed_at=datetime.now(timezone.utc), cycle_year=2026, created_by="测试健管", baseline_json={"health_problems": [{"title": "待核对事项"}], "current_medications": medications, "key_metrics": [], "empty": {}})
        session.add(assessment); session.commit()
        patient_id, assessment_id = patient.id, assessment.id
    try:
        app = AppTest.from_file(APP).run(timeout=30)
        next(r for r in app.radio if r.label == "当前视图").set_value("成员健康中心"); app.run(timeout=30)
        app.session_state[f"timeline-selected-event-member-center-journey-{patient_id}"] = f"ASSESSMENT:{assessment_id}"
        next(r for r in app.radio if r.label == "成员健康中心导航").set_value("历程"); app.run(timeout=30)
        assert not app.exception and not app.error
        text = " ".join(str(e.value) for group in (app.markdown, app.caption) for e in group)
        assert "当时健康快照" in text
        assert all(token not in text for token in ("RiskEvent", "AgentGoal", "source_id", str(assessment_id), "Traceback"))
        assert any(r.label == "事件筛选" for r in app.radio)
    finally:
        with SessionLocal() as session:
            session.delete(session.get(HealthAssessment, assessment_id)); session.commit()


def _empty_timeline():
    from uuid import UUID
    from types import SimpleNamespace
    from executive_health_ai.ui.pages.member.experience import timeline
    timeline(SimpleNamespace(_label=str, render_longitudinal_timeline=lambda *args, **kwargs: None), SimpleNamespace(id=UUID(int=0)))


def test_timeline_empty_state():
    app = AppTest.from_function(_empty_timeline).run()
    assert not app.exception and not app.error
    assert any("暂无重要健康事件" in e.value for e in app.caption)


def test_timeline_error_boundary_logs_exception_without_exposing_stack(monkeypatch, caplog):
    from executive_health_ai.ui.pages.member import experience
    def fail(*args, **kwargs):
        raise RuntimeError("deliberate regression fixture failure")
    monkeypatch.setattr(experience.HealthTimelineService, "get_timeline", fail)
    app = AppTest.from_function(_empty_timeline).run()
    assert not app.exception and app.error[0].value == "健康历程暂时无法加载，请稍后重试。"
    assert "member_timeline_render_failed" in caplog.text
    assert "RuntimeError" in caplog.text
