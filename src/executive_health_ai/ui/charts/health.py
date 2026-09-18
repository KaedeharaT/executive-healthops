"""One chart grammar for all role views; only homepage previews are compact."""
import altair as alt
import pandas as pd
import streamlit as st

from executive_health_ai.services.health_visualization import option_label

BLUE = "#185da8"


def metric_trend_chart(series, *, compact=False):
    drawable = [s for s in series if s.has_trend]
    if not drawable:
        return None
    if len({s.unit for s in series}) != 1:
        raise ValueError("不同单位不能放在同一数值坐标轴。")
    rows = [{"时间": p.at, "数值": float(p.value), "指标": s.label, "单位": s.unit, "来源": p.source} for s in series for p in s.points]
    frame = pd.DataFrame(rows)
    low, high = frame["数值"].min(), frame["数值"].max()
    pad = (high - low) * .15 or max(abs(high) * .05, 1)
    at = pd.to_datetime(frame["时间"], utc=True)
    date_format = "%Y/%m" if (at.max() - at.min()).days > 90 else "%m/%d"
    if (at.max() - at.min()).total_seconds() < 86400:
        date_format = "%m/%d %H:%M"
    return alt.Chart(frame).mark_line(point=alt.OverlayMarkDef(filled=True, size=30 if compact else 48), strokeWidth=2).encode(
        x=alt.X("时间:T", title="时间", axis=alt.Axis(format=date_format, tickCount=3 if compact else 5, labels=True, ticks=True, domain=True, grid=False, labelAngle=0, labelOverlap=True)),
        y=alt.Y("数值:Q", title=series[0].unit, scale=alt.Scale(zero=False, domain=[low-pad, high+pad], nice=True), axis=alt.Axis(labels=True, ticks=True, domain=True, tickCount=3 if compact else 5, grid=True)),
        color=alt.Color("指标:N", scale=alt.Scale(range=[BLUE, "#609bd0"]), legend=alt.Legend(title=None, orient="top")),
        tooltip=[alt.Tooltip("时间:T", title="时间", format="%Y/%m/%d %H:%M"), alt.Tooltip("数值:Q", format=".3~f"), alt.Tooltip("单位:N"), alt.Tooltip("来源:N"), alt.Tooltip("指标:N")],
    ).properties(height=190 if compact else 280).configure_view(stroke=None).configure_axis(gridColor="#e2e8f0", labelColor="#334155", titleColor="#334155", domainColor="#64748b", tickColor="#64748b")


def render_metric_trend(series, *, key, compact=False):
    chart = metric_trend_chart(series, compact=compact)
    if chart is None:
        for item in series:
            if item.points:
                st.write(item.label + " · " + item.comparison)
        st.caption("暂无足够数据形成趋势。")
        return False
    st.altair_chart(chart, width="stretch", theme=None, key=key)
    return True


def render_blood_pressure_trend(series, *, key, compact=False):
    return render_metric_trend(tuple(s for s in series if s.code in {"systolic_bp", "diastolic_bp"}), key=key, compact=compact)


def render_sleep_trend(series, *, key, compact=False):
    return render_metric_trend(series, key=key, compact=compact)


def render_activity_trend(series, *, key, compact=False):
    return render_metric_trend(series, key=key, compact=compact)


def render_report_comparison(series, *, key):
    return render_metric_trend(series, key=key)


def render_compact_sparkline(code, series, *, key):
    st.markdown("**" + option_label(code, series) + "**")
    render_metric_trend(series, key=key, compact=True)
    st.caption("；".join(s.comparison for s in series if s.points))
