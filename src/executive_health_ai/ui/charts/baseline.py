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
    """Explicit axes, true observations, baseline rules and latest-value labels."""
    if not trends or not any(trend.has_follow_up for trend in trends):
        return None
    if len({trend.unit for trend in trends}) != 1:
        raise ValueError("不同单位的指标不能使用同一数值坐标轴。")
    rows = []
    for trend in trends:
        latest = max((p.observed_at for p in trend.points if p.point_type == "FOLLOW_UP"), default=None)
        for point in trend.points:
            kind = "年度基线" if point.point_type == "BASELINE" else "当前" if point.observed_at == latest else "后续记录"
            rows.append({"时间": point.observed_at, "数值": float(point.value), "指标": point.series,
                         "类型": kind, "单位": trend.unit, "来源": point.source_type,
                         "标记": f"{kind} {float(point.value):g} {trend.unit}"})
    frame = pd.DataFrame(rows)
    values = frame["数值"]
    span = float(values.max() - values.min()) or max(abs(float(values.max())) * .05, 1)
    domain = [float(values.min()) - span * .2, float(values.max()) + span * .2]
    dates = pd.to_datetime(frame["时间"], utc=True)
    date_format = "%Y/%m" if (dates.max() - dates.min()).days >= 60 else "%m/%d"
    x = alt.X("时间:T", title="时间", axis=alt.Axis(format=date_format, tickCount=4, labels=True,
        ticks=True, domain=True, grid=False, labelAngle=0, labelOverlap=True))
    y = alt.Y("数值:Q", title=f"数值（{trends[0].unit}）", scale=alt.Scale(domain=domain, zero=False, nice=True),
        axis=alt.Axis(tickCount=5, labels=True, ticks=True, domain=True, grid=True))
    color = alt.Color("指标:N", scale=alt.Scale(domain=[t.label for t in trends], range=[DEEP_BLUE, BLUE]),
        legend=alt.Legend(title=None, orient="top"))
    tooltip = [alt.Tooltip("时间:T", title="日期", format="%Y/%m/%d"), alt.Tooltip("指标:N"),
        alt.Tooltip("数值:Q", format=".3~f"), alt.Tooltip("单位:N"), alt.Tooltip("类型:N"), alt.Tooltip("来源:N")]
    base = alt.Chart(frame).encode(x=x, y=y, color=color, tooltip=tooltip)
    line = base.mark_line(point=alt.OverlayMarkDef(filled=True, size=55), strokeWidth=2.5)
    baselines = base.transform_filter(alt.datum.类型 == "年度基线")
    current = base.transform_filter(alt.datum.类型 == "当前")
    rules = alt.Chart(frame[frame["类型"] == "年度基线"]).mark_rule(strokeDash=[6, 4], strokeWidth=1.5).encode(y=y, color=color, tooltip=tooltip)
    markers = baselines.mark_point(shape="diamond", filled=True, size=120)
    baseline_labels = baselines.mark_text(align="left", dx=7, dy=-14, fontWeight="bold").encode(text="标记:N")
    current_points = current.mark_point(filled=True, size=140, stroke="white", strokeWidth=1.5)
    current_labels = current.mark_text(align="right", dx=-7, dy=-14, fontWeight="bold").encode(text="标记:N")
    return alt.layer(line, rules, markers, baseline_labels, current_points, current_labels).properties(height=270).configure_view(stroke=None).configure_axis(
        gridColor="#E2E8F0", domainColor=BLUE_GRAY, tickColor=BLUE_GRAY,
        labelColor="#334155", titleColor="#334155", labelFontSize=12, titleFontSize=12,
    )


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
