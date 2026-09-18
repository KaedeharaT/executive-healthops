"""Spec guards complement (never replace) the Chromium screenshot acceptance."""
from datetime import datetime, timezone
from decimal import Decimal
import inspect

import pytest

from executive_health_ai.services.health_visualization import HealthPoint, HealthSeries
from executive_health_ai.services.baseline_visualization import BaselineTrendView, TrendPoint
from executive_health_ai.ui.charts.axes import time_axis_config, numeric_axis_config
from executive_health_ai.ui.charts.health import metric_trend_chart
from executive_health_ai.ui.charts.baseline import baseline_trend_chart

DATES = tuple(datetime(2026, month, 15, tzinfo=timezone.utc) for month in (1, 4, 7, 9))
METRICS = [
    ("weight", "体重", "kg", "90", "85.8"),
    ("bmi", "BMI", "kg/m²", "29.4", "27.9"),
    ("ldl_c", "LDL-C", "mmol/L", "4.15", "3.72"),
    ("hba1c", "糖化血红蛋白", "%", "6.3", "6"),
    ("systolic_bp", "收缩压", "mmHg", "132", "126"),
    ("diastolic_bp", "舒张压", "mmHg", "86", "80"),
    ("glucose", "血糖", "mg/dL", "120", "115"),
    ("heart_rate", "心率", "次/分", "76", "72"),
    ("sleep_duration", "睡眠时长", "小时", "7", "8"),
    ("steps", "步数", "步", "4500", "5000"),
    ("exercise_minutes", "运动时间", "分钟", "30", "45"),
]


def assert_readable_axes(spec, unit):
    encoding = spec.get("layer", [spec])[0]["encoding"]
    for key in ("x", "y"):
        axis = encoding[key]["axis"]
        assert axis is not None
        assert all(axis[flag] is True for flag in ("labels", "ticks", "domain"))
        assert axis["domainColor"] == axis["tickColor"] == "#334155"
        assert axis["domainWidth"] >= 2 and axis["tickWidth"] >= 2
        assert axis["labelFontSize"] >= 12 and axis["titleFontSize"] >= 13
        assert axis["labelPadding"] >= 6 and axis["tickSize"] >= 6
        assert axis["title"]
    assert encoding["x"]["axis"]["title"] == "时间"
    assert unit in encoding["y"]["axis"]["title"]
    assert encoding["y"]["scale"]["zero"] is False
    assert spec["height"] >= 300
    assert spec["padding"]["left"] >= 16 and spec["padding"]["bottom"] >= 16


@pytest.mark.parametrize("code,label,unit,before,after", METRICS)
def test_all_formal_metric_trends_have_explicit_readable_axes(code, label, unit, before, after):
    series = HealthSeries(code, label, unit, (HealthPoint(DATES[0], Decimal(before), "人工记录"), HealthPoint(DATES[-1], Decimal(after), "人工记录")))
    assert_readable_axes(metric_trend_chart((series,)).to_dict(), unit)


@pytest.mark.parametrize("code,label,unit,before,after", METRICS[:6])
def test_all_baseline_trends_use_same_axes_and_keep_annotations(code, label, unit, before, after):
    trend = BaselineTrendView(code, label, unit, Decimal(before), (
        TrendPoint(DATES[0], Decimal(before), label, "BASELINE", "年度基线"),
        TrendPoint(DATES[-1], Decimal(after), label, "FOLLOW_UP", "健康数据"),
    ))
    spec = baseline_trend_chart((trend,)).to_dict()
    assert_readable_axes(spec, unit)
    assert any(layer["mark"]["type"] == "rule" and layer["mark"]["strokeWidth"] >= 2 and layer["mark"]["strokeDash"] for layer in spec["layer"])
    text_layers = [layer for layer in spec["layer"] if layer["mark"]["type"] == "text"]
    assert len(text_layers) == 2 and all(layer["mark"]["fontSize"] >= 13 for layer in text_layers)


def test_time_axis_labels_observed_dates_including_endpoints():
    axis = time_axis_config("%Y/%m", dates=DATES).to_dict()
    assert [(value["year"], value["month"], value["date"]) for value in axis["values"]] == [(at.year, at.month, at.day) for at in DATES]
    assert all(value["utc"] is True for value in axis["values"])
    assert axis["labelFlush"] is False  # Endpoint labels retain right/left padding.
    assert numeric_axis_config("mmHg").to_dict()["title"] == "mmHg"


def test_dense_recent_measurements_do_not_crowd_out_earlier_date_labels():
    dates = [datetime(2026, month, day, tzinfo=timezone.utc) for month, day in [(1, 15), (3, 15), (6, 1), (8, 28), (9, 1), (9, 4), (9, 11)]]
    axis = time_axis_config("%Y/%m", dates=dates).to_dict()
    assert [value["month"] for value in axis["values"]] == [1, 3, 6, 9]
    assert axis["values"][-1]["date"] == 11
    assert axis["labelOverlap"] == "greedy"


def test_both_formal_renderers_use_shared_helpers_and_disable_streamlit_theme():
    for renderer in (baseline_trend_chart, metric_trend_chart):
        source = inspect.getsource(renderer)
        assert "time_axis_config(" in source and "numeric_axis_config(" in source
        assert "axis=None" not in source and "labels=False" not in source
        assert "ticks=False" not in source and "domain=False" not in source
    from executive_health_ai.ui.pages.baseline_visualization import render_baseline_progress
    from executive_health_ai.ui.charts.health import render_metric_trend
    assert "theme=None" in inspect.getsource(render_baseline_progress)
    assert "theme=None" in inspect.getsource(render_metric_trend)
