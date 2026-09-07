"""Streamlit presentation for a read-only annual health baseline projection."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import html
from typing import Callable

import pandas as pd
import streamlit as st

from executive_health_ai.blood_pressure import TOKYO_TIMEZONE
from executive_health_ai.models import HealthAssessment, Patient
from executive_health_ai.services.baseline_visualization import BaselineVisualizationService
from executive_health_ai.ui.charts.baseline import baseline_trend_chart, coverage_chart, reference_range_chart


def render_baseline_visualization(
    patient: Patient,
    baseline: HealthAssessment,
    *,
    audience: str,
    key_prefix: str,
    session_factory: Callable,
    section_header: Callable[[str], None],
    empty_state: Callable[[str, str], None],
    render_metric_evidence: Callable,
    format_datetime: Callable,
) -> None:
    """Render a read-only projection without exposing technical identifiers."""
    with session_factory() as session:
        view = BaselineVisualizationService().build(session, patient.id, cycle_year=baseline.cycle_year)
    client_view = audience == "member"

    def inline_empty(title: str, detail: str) -> None:
        st.markdown(
            "<div style='padding:.55rem .75rem;border-left:3px solid #CBD5E1;"
            "background:#F8FAFC;color:#475569;border-radius:4px'>"
            f"<strong>{html.escape(title)}</strong><br><span style='font-size:.86rem'>{html.escape(detail)}</span></div>",
            unsafe_allow_html=True,
        )
    st.caption("这是本年度健康管理的参考起点，后续变化会与此进行比较。")
    phase_columns = st.columns(3)
    phase_columns[0].caption("首月 · 建立基线")
    phase_columns[1].markdown("**当前 · 持续管理**")
    phase_columns[2].caption("下一步 · 阶段复盘")

    section_header("健康概览")
    for domain in view.domains:
        status_color = {"需要持续关注": "#B45309", "资料不足": "#64748B"}.get(domain.status, "#2563EB")
        st.markdown(
            "<div class='next-row'><div><div class='focus-title'>"
            f"{html.escape(domain.label)}</div><div class='focus-copy'>{html.escape(domain.summary)}</div></div>"
            f"<div style='color:{status_color};font-weight:700;white-space:nowrap'>{html.escape(domain.status)}</div></div>",
            unsafe_allow_html=True,
        )

    section_header("关键指标基线")
    if not view.metrics:
        inline_empty("暂无已确认指标", "已确认的指标会在这里作为年度参考起点显示。")
    metric_columns = st.columns(2, gap="medium") if view.metrics else []
    for index, metric in enumerate(view.metrics[:6]):
        with metric_columns[index % 2]:
            st.markdown(f"**{metric.label}　{metric.value_text} {metric.unit}**".strip())
            st.caption(metric.explicit_status)
            chart = reference_range_chart(metric)
            if chart is not None:
                st.altair_chart(chart, width="stretch", key=f"{key_prefix}-range-{metric.code}")
                st.caption(f"报告参考范围：{metric.reference.text}")
            else:
                st.caption("报告未提供可用于绘图的明确参考范围；仅显示已确认数值和来源。")
            render_metric_evidence(
                patient.id, metric.source_candidate_id,
                key_scope=f"{key_prefix}-metric-evidence-{metric.code}", client_view=client_view,
            )

    section_header("从基线到现在")
    trend_options: dict[str, tuple[object, ...]] = {}
    by_code = {trend.code: trend for trend in view.trends}
    if "systolic_bp" in by_code and "diastolic_bp" in by_code:
        trend_options["血压"] = (by_code["systolic_bp"], by_code["diastolic_bp"])
    for trend in view.trends:
        if trend.code not in {"systolic_bp", "diastolic_bp"}:
            trend_options[trend.label] = (trend,)
    if trend_options:
        selected_label = st.selectbox("选择指标", list(trend_options), key=f"{key_prefix}-trend-metric")
        window = st.selectbox("时间范围", ["当前管理周期", "7天", "30天", "3个月", "1年", "全部"], key=f"{key_prefix}-trend-window")
        selected = trend_options[selected_label]
        if window not in {"当前管理周期", "全部"}:
            days = {"7天": 7, "30天": 30, "3个月": 90, "1年": 365}[window]
            cutoff = datetime.now(TOKYO_TIMEZONE) - timedelta(days=days)
            selected = tuple(replace(
                trend, points=tuple(point for point in trend.points if point.point_type == "BASELINE" or point.observed_at >= cutoff),
            ) for trend in selected)
        chart = baseline_trend_chart(selected)
        if chart is None:
            inline_empty("暂无足够连续数据形成趋势", "目前只有年度基线，后续同类数据确认后会显示变化。")
        else:
            st.altair_chart(chart, width="stretch", key=f"{key_prefix}-trend-chart")
            st.caption("菱形点标示年度基线；折线仅连接同一指标、同一单位的真实记录。")
    else:
        inline_empty("暂无足够连续数据形成趋势", "当前基线尚无可比较的定量指标。")

    section_header("基线与当前")
    if view.comparisons:
        st.dataframe(pd.DataFrame([{
            "指标": item.label, "年度基线": f"{item.baseline} {item.unit}".strip(),
            "当前记录": f"{item.current} {item.unit}".strip(), "比较状态": item.status,
        } for item in view.comparisons]), hide_index=True, width="stretch")
        st.caption("这里只描述数值是否变化，不自动判断医学上的改善或恶化。")
    else:
        inline_empty("暂无可比较指标", "后续同类数据确认后会显示基线与当前记录。")

    if audience == "manager":
        section_header("基线资料覆盖")
        st.markdown(f"**{view.covered_count} / {len(view.coverage)} 类资料已覆盖**")
        st.caption("这是资料完整度，不代表健康评分。")
        st.altair_chart(coverage_chart(view.coverage), width="stretch", key=f"{key_prefix}-coverage")
        st.dataframe(pd.DataFrame([{"资料": item.label, "状态": item.status} for item in view.coverage]), hide_index=True, width="stretch")
    if view.amendments:
        st.info("该基线曾更新资料。当前图表使用最新有效的修订后基线。")
        with st.expander("查看更新记录"):
            for amendment in view.amendments:
                st.markdown(f"**{format_datetime(amendment.changed_at)} · {amendment.reason}**")
                st.caption(f"确认人：{amendment.confirmed_by}")
                for change in amendment.changes or ("修订内容保留在基线记录中。",):
                    st.write(change)
                st.caption(f"依据：{amendment.evidence}")
