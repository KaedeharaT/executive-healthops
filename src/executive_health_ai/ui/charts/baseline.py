"""Accessible blue-theme charts for annual health baselines."""
from __future__ import annotations

from decimal import Decimal

import altair as alt
import pandas as pd

from executive_health_ai.services.baseline_visualization import BaselineMetricView, BaselineTrendView, CoverageItem


BLUE = "#2563EB"
DEEP_BLUE = "#1E3A8A"
LIGHT_BLUE = "#DBEAFE"
BLUE_GRAY = "#64748B"
AMBER = "#D97706"


def reference_range_chart(metric: BaselineMetricView) -> alt.Chart | None:
    """Render only an interval/threshold explicitly stored in report evidence."""
    if metric.value is None or metric.reference is None:
        return None
    reference = metric.reference
    values = [metric.value, *(value for value in (reference.lower, reference.upper) if value is not None)]
    minimum, maximum = min(values), max(values)
    span = maximum - minimum or max(abs(maximum) * Decimal("0.25"), Decimal("1"))
    domain_low = float(minimum - span * Decimal("0.25"))
    domain_high = float(maximum + span * Decimal("0.25"))
    base = alt.Chart(pd.DataFrame([{"row": metric.label}])).encode(
        y=alt.Y("row:N", axis=None),
    )
    layers: list[alt.Chart] = []
    if reference.kind == "RANGE" and reference.lower is not None and reference.upper is not None:
        interval = pd.DataFrame([{"row": metric.label, "start": float(reference.lower), "end": float(reference.upper)}])
        layers.append(alt.Chart(interval).mark_bar(size=16, cornerRadius=8, color=LIGHT_BLUE).encode(
            y=alt.Y("row:N", axis=None), x=alt.X("start:Q", scale=alt.Scale(domain=[domain_low, domain_high]), title=None), x2="end:Q",
        ))
    else:
        threshold = reference.upper if reference.upper is not None else reference.lower
        if threshold is not None:
            layers.append(alt.Chart(pd.DataFrame([{"threshold": float(threshold)}])).mark_rule(color=BLUE_GRAY, strokeDash=[4, 3], strokeWidth=2).encode(
                x=alt.X("threshold:Q", scale=alt.Scale(domain=[domain_low, domain_high]), title=None),
            ))
    point_color = AMBER if metric.explicit_status != "已记录" else BLUE
    layers.append(alt.Chart(pd.DataFrame([{"row": metric.label, "value": float(metric.value)}])).mark_point(
        filled=True, size=130, color=point_color, stroke="white", strokeWidth=2,
    ).encode(y=alt.Y("row:N", axis=None), x=alt.X("value:Q", scale=alt.Scale(domain=[domain_low, domain_high]), title=None), tooltip=[alt.Tooltip("value:Q", title=metric.label)]))
    return alt.layer(*layers).properties(height=42).configure_view(stroke=None).configure_axis(grid=False, labelColor=BLUE_GRAY)


def baseline_trend_chart(trends: tuple[BaselineTrendView, ...]) -> alt.Chart | None:
    """Plot comparable observations with an explicit annual-baseline marker."""
    selected = [trend for trend in trends if trend.has_follow_up]
    if not selected:
        return None
    rows = [{
        "时间": point.observed_at, "数值": float(point.value), "指标": point.series,
        "类型": "年度基线" if point.point_type == "BASELINE" else "后续记录",
    } for trend in selected for point in trend.points]
    frame = pd.DataFrame(rows)
    line = alt.Chart(frame).mark_line(point=True, strokeWidth=2.5).encode(
        x=alt.X("时间:T", title=None), y=alt.Y("数值:Q", scale=alt.Scale(zero=False), title=selected[0].unit or None),
        color=alt.Color("指标:N", scale=alt.Scale(range=[DEEP_BLUE, BLUE]), legend=alt.Legend(title=None)),
        tooltip=[alt.Tooltip("时间:T", title="时间"), alt.Tooltip("指标:N"), alt.Tooltip("数值:Q"), alt.Tooltip("类型:N")],
    )
    baseline_rows = frame[frame["类型"] == "年度基线"]
    markers = alt.Chart(baseline_rows).mark_point(shape="diamond", filled=True, size=150, color=BLUE).encode(
        x="时间:T", y=alt.Y("数值:Q", scale=alt.Scale(zero=False)), tooltip=["指标:N", "类型:N", "数值:Q"]
    )
    labels = alt.Chart(baseline_rows).mark_text(align="left", dx=8, dy=-10, color=DEEP_BLUE, fontWeight="bold").encode(
        x="时间:T", y=alt.Y("数值:Q", scale=alt.Scale(zero=False)), text=alt.value("年度基线")
    )
    return alt.layer(line, markers, labels).properties(height=260).configure_view(stroke=None).configure_axis(gridColor="#E2E8F0", labelColor="#475569", titleColor="#334155")


def coverage_chart(items: tuple[CoverageItem, ...]) -> alt.Chart:
    order = {"已覆盖": 1.0, "有数据": 1.0, "部分": 0.65, "数据不足": 0.45, "数据时间较早": 0.35, "待补充": 0.2, "暂无数据": 0.08, "不适用": 0.0}
    frame = pd.DataFrame([{"资料": item.label, "覆盖": order.get(item.status, 0.2), "状态": item.status} for item in items])
    return alt.Chart(frame).mark_bar(cornerRadiusEnd=5, size=13).encode(
        y=alt.Y("资料:N", sort=None, title=None),
        x=alt.X("覆盖:Q", scale=alt.Scale(domain=[0, 1]), axis=None),
        color=alt.Color("状态:N", scale=alt.Scale(
            domain=["已覆盖", "有数据", "部分", "数据不足", "数据时间较早", "待补充", "暂无数据", "不适用"],
            range=[BLUE, BLUE, "#60A5FA", "#94A3B8", "#94A3B8", "#CBD5E1", "#E2E8F0", "#E2E8F0"],
        ), legend=None),
        tooltip=["资料:N", "状态:N"],
    ).properties(height=max(140, len(items) * 25)).configure_view(stroke=None)
