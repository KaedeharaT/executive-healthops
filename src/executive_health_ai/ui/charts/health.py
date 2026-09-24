"""One chart grammar for all role views; only homepage previews are compact."""
import altair as alt
import pandas as pd
import streamlit as st

from executive_health_ai.services.health_visualization import option_label
from executive_health_ai.ui.charts.axes import CHART_PADDING, health_axis_config, time_axis_config, numeric_axis_config

BLUE = "#185da8"


def metric_trend_chart(series, *, compact=False, baseline_metrics=(), current_marker=False):
    drawable = [s for s in series if s.has_trend]
    if not drawable:
        return None
    if len({s.unit for s in series}) != 1:
        raise ValueError("不同单位不能放在同一数值坐标轴。")
    rows = [{"时间": p.at, "数值": float(p.value), "指标": s.label, "单位": s.unit, "来源": p.source} for s in series for p in s.points]
    frame = pd.DataFrame(rows)
    references=[{'年度基线':float(m.value),'指标':m.label,'单位':m.unit} for m in baseline_metrics
                if m.value is not None and any(s.code==m.code and s.unit==m.unit for s in series)]
    low, high = min([frame["数值"].min()]+[r['年度基线'] for r in references]), max([frame["数值"].max()]+[r['年度基线'] for r in references])
    pad = (high - low) * .15 or max(abs(high) * .05, 1)
    at = pd.to_datetime(frame["时间"], utc=True)
    date_format = "%Y/%m" if (at.max() - at.min()).days > 90 else "%m/%d"
    if (at.max() - at.min()).total_seconds() < 86400:
        date_format = "%m/%d %H:%M"
    line = alt.Chart(frame).mark_line(point=alt.OverlayMarkDef(filled=True, size=30 if compact else 48), strokeWidth=2).encode(
        x=alt.X("时间:T", title="时间", axis=time_axis_config(date_format, dates=at, compact=compact)),
        y=alt.Y("数值:Q", title=series[0].unit, scale=alt.Scale(zero=False, domain=[low-pad, high+pad], nice=True), axis=numeric_axis_config(series[0].unit, compact=compact)),
        color=alt.Color("指标:N", scale=alt.Scale(range=[BLUE, "#609bd0"]), legend=alt.Legend(title=None, orient="top", labelFontSize=12)),
        tooltip=[alt.Tooltip("时间:T", title="时间", format="%Y/%m/%d %H:%M"), alt.Tooltip("数值:Q", format=".3~f"), alt.Tooltip("单位:N"), alt.Tooltip("来源:N"), alt.Tooltip("指标:N")],
    )
    if references:
        rules=alt.Chart(pd.DataFrame(references)).mark_rule(strokeDash=[6,4],color='#6b7f93').encode(
            y=alt.Y('年度基线:Q'),tooltip=['指标:N','年度基线:Q','单位:N'])
        line=alt.layer(line,rules)
    if current_marker:
        current = alt.Chart(frame.sort_values('时间').groupby('指标', as_index=False).tail(1)).mark_point(
            filled=True, size=85 if compact else 110, color=BLUE, stroke='white', strokeWidth=2).encode(
            x='时间:T', y='数值:Q', tooltip=[alt.Tooltip('时间:T', format='%Y/%m/%d'), '数值:Q', '单位:N', '指标:N', '来源:N'])
        line = alt.layer(line, current)
    return line.properties(height=190 if compact else 320, padding={"left": 8, "right": 8, "top": 8, "bottom": 8} if compact else CHART_PADDING).configure_view(stroke=None).configure_axis(**health_axis_config())


def render_metric_trend(series, *, key, compact=False, baseline_metrics=(), current_marker=False):
    chart = metric_trend_chart(series, compact=compact, baseline_metrics=baseline_metrics, current_marker=current_marker)
    if chart is None:
        for item in series:
            if item.points:
                st.write(item.label + " · " + item.comparison)
        st.caption("暂无足够数据形成趋势。")
        return False
    st.altair_chart(chart, width="stretch", theme=None, key=key)
    return True


def render_blood_pressure_trend(series, *, key, compact=False, baseline_metrics=()):
    return render_metric_trend(tuple(s for s in series if s.code in {"systolic_bp", "diastolic_bp"}), key=key, compact=compact, baseline_metrics=baseline_metrics)


def render_sleep_trend(series, *, key, compact=False, baseline_metrics=()):
    return render_metric_trend(series, key=key, compact=compact, baseline_metrics=baseline_metrics)


def render_activity_trend(series, *, key, compact=False, baseline_metrics=()):
    return render_metric_trend(series, key=key, compact=compact, baseline_metrics=baseline_metrics)


def render_report_comparison(series, *, key):
    return render_metric_trend(series, key=key)


def render_compact_sparkline(code, series, *, key):
    st.markdown("**" + option_label(code, series) + "**")
    render_metric_trend(series, key=key, compact=True)
    st.caption("；".join(s.comparison for s in series if s.points))
