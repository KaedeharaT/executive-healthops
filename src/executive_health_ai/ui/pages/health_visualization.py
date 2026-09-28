"""Shared selectors and drilldowns; role pages never assemble separate series."""
from datetime import datetime, time
from dataclasses import replace
import pandas as pd
import streamlit as st

from executive_health_ai.database import SessionLocal
from executive_health_ai.services.health_visualization import HealthVisualizationService, PERIODS, LOCAL, default_period, filter_period, option_label, series_options
from executive_health_ai.ui.charts.health import render_metric_trend, render_compact_sparkline, render_report_comparison


def load_series(patient_id):
    with SessionLocal() as session:
        return HealthVisualizationService().build(session, patient_id)


def render_previews(patient_id, *, key, open_trend, maximum=2, series=None, shared_action=False):
    previews = HealthVisualizationService().previews(load_series(patient_id) if series is None else series, maximum)
    if not previews:
        st.caption("暂无足够数据形成趋势。")
    columns = st.columns(len(previews)) if previews else []
    for col, (code, group) in zip(columns, previews):
        with col:
            render_compact_sparkline(code, group, key=f"{key}-{code}")
            st.caption(f"{group[0].points[0].at:%Y/%m/%d} — {group[0].points[-1].at:%Y/%m/%d} · 仅表示观察变化")
            if not shared_action and st.button("查看趋势", key=f"{key}-open-{code}"):
                st.session_state[f"health-metric-pending-{patient_id}"] = code
                open_trend()

    if shared_action and st.button("查看健康变化", key=f"{key}-open"):
        open_trend()


def render_health_explorer(patient_id, *, key=None):
    from executive_health_ai.ui.pages import health_trend_panel as panel
    from executive_health_ai.services.baseline_visualization import BaselineVisualizationService
    options = panel.ordered_options(series_options(load_series(patient_id)))
    st.markdown(panel.STYLES, unsafe_allow_html=True)
    with st.container(border=True, key="health-trend-panel"):
        st.subheader("健康趋势")
        st.caption("查看不同健康指标在所选时间范围内的变化。")
        if not options:
            st.caption("暂无已确认健康数据。上传报告或导入数据后可查看趋势。")
            return
        key = key or f"ux-metric-{patient_id}"
        pending = st.session_state.pop(f"health-metric-pending-{patient_id}", None)
        if pending in options:
            st.session_state[key] = pending
        if st.session_state.get(key) not in options:
            st.session_state[key] = next(iter(options))
        with st.container(key="health-trend-filters"):
            st.markdown("**筛选条件**")
            st.caption(f"当前可查看 {len(options)} 项健康指标")
            metric_control, period_control = st.columns([1, 2], gap='large')
            with metric_control:
                code = st.selectbox("选择健康指标", list(options), format_func=lambda c: option_label(c, options[c]), key=key)
            group = options[code]
            window = st.session_state.get(f"health-data-window-{patient_id}")
            periods = (["时间轴范围"] if window else []) + list(PERIODS)
            period_key = f"ux-period-{patient_id}-{code}"
            if st.session_state.get(period_key) not in periods:
                st.session_state[period_key] = "时间轴范围" if window else default_period(group)
            with period_control:
                period = st.segmented_control("时间范围", periods, required=True, key=period_key)
        if period == "时间轴范围":
            try:
                start = datetime.combine(datetime.fromisoformat(window["start"]).date(), time.min, LOCAL)
                end = datetime.combine(datetime.fromisoformat(window["end"]).date(), time.max, LOCAL)
                visible = filter_period(group, "全部", start=start, end=end)
                st.caption(f"时间轴选择的时间段：{start:%Y年%m月%d日} — {end:%Y年%m月%d日}")
            except (ValueError, KeyError, TypeError):
                st.caption("时间范围无效，请选择其他时间范围。")
                return
        else:
            visible = filter_period(group, period)
        with SessionLocal() as session:
            try:
                baseline = BaselineVisualizationService().build(session, patient_id)
            except ValueError:
                baseline = None
        metrics = baseline.metrics if baseline else ()
        st.divider()
        panel.render_result(visible, group, metrics, code=code, key=key, period_key=period_key)
        with st.expander("数据来源与记录"):
            records = [{"时间": p.at.strftime("%Y/%m/%d %H:%M"), "指标": s.label, "数值": float(p.value), "单位": s.unit, "来源": p.source} for s in visible for p in s.points]
            st.dataframe(pd.DataFrame(records), hide_index=True, width="stretch")


def render_report_trends(patient_id, *, key):
    with SessionLocal() as session:
        series = HealthVisualizationService().report_series(session, patient_id)
    options = {s.code: (s,) for s in series}
    st.subheader("历次体检指标变化")
    if not options:
        st.caption("暂无已确认且包含检查日期的定量指标。")
        return
    code = st.selectbox("比较体检指标", list(options), format_func=lambda c: options[c][0].label, key=f"{key}-metric")
    group = options[code]
    render_report_comparison(group, key=f"{key}-chart")
    recent = replace(group[0], points=group[0].points[-2:])
    st.caption("最近两次比较：" + recent.comparison + "；仅比较人工确认结果，不判断医学好坏。")
    if group[0].has_trend:
        st.caption("横轴为实际体检日期；最后两点对应最近两次该指标的已确认检查。")


def render_doctor_trend(patient_id, review, *, session_factory=SessionLocal):
    with session_factory() as session:
        series = HealthVisualizationService().for_review(session, patient_id, review)
    if not series:
        st.caption("本次问题暂无明确关联的可绘制指标，请先核对问题与依据。")
        return
    options = series_options(series)
    st.markdown("**与本次复核相关的趋势**")
    selected = st.selectbox("复核指标", list(options), format_func=lambda c: option_label(c, options[c]), key=f"review-trend-{review.id}") if len(options)>1 else next(iter(options))
    group = options[selected]
    period = st.selectbox("复核趋势范围", list(PERIODS), index=1, key=f"review-period-{review.id}")
    st.caption("按当前日期回看；所选范围没有记录时不会用旧记录冒充近期数据。")
    render_metric_trend(filter_period(group, period), key=f"review-chart-{review.id}")
