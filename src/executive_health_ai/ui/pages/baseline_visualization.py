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
from executive_health_ai.services.baseline_visualization import BaselineVisualizationService, number_text
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

    render_baseline_progress(view, key_prefix=key_prefix)

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
                st.caption(f"参考下限：{metric.reference.lower if metric.reference.lower is not None else '未提供'} · 参考上限：{metric.reference.upper if metric.reference.upper is not None else '未提供'} · 基线值：{metric.value_text} {metric.unit}")
            else:
                st.caption("报告未提供可用于绘图的明确参考范围；仅显示已确认数值和来源。")
            render_metric_evidence(
                patient.id, metric.source_candidate_id,
                key_scope=f"{key_prefix}-metric-evidence-{metric.code}", client_view=client_view,
            )

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


def render_baseline_progress(view, *, key_prefix: str) -> None:
    """The same comparable projection and chart for members and managers."""
    st.markdown("**基线与当前**")
    if view.comparisons:
        rows = []
        for item in view.comparisons:
            rows.append({"指标": item.label,
                         "年度基线": f"{number_text(item.baseline)} {item.unit}",
                         "当前记录": f"{number_text(item.current)} {item.unit}" if item.delta is not None else "暂无后续数据",
                         "数值变化": item.delta_text,
                         "相对变化": f"{item.percentage:+.1f}%" if item.percentage is not None else "—"})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.caption("暂无可比较指标，已确认的定量数据会显示在这里。")
    st.caption("↑ / ↓ 只表示数值方向，不自动解释为改善或恶化；百分比指标的绝对差使用百分点。")
    st.markdown("**从基线到现在**")
    by_code = {trend.code: trend for trend in view.trends}
    options = {}
    for code in ("weight", "bmi", "ldl_c", "hba1c"):
        if code in by_code:
            options[by_code[code].label] = (by_code[code],)
    if all(code in by_code for code in ("systolic_bp", "diastolic_bp")) and by_code["systolic_bp"].unit == by_code["diastolic_bp"].unit:
        options["血压（收缩压 / 舒张压）"] = (by_code["systolic_bp"], by_code["diastolic_bp"])
    grouped = {t.code for group in options.values() for t in group}
    for trend in view.trends:
        if trend.code not in grouped:
            options[trend.label] = (trend,)
    if not options:
        st.caption("目前还没有足够的后续数据形成趋势。请由健康管理师核对并补充基线指标。")
        return
    columns = st.columns([2, 1])
    selected_label = columns[0].selectbox("选择指标", list(options), key=f"{key_prefix}-trend-metric")
    window = columns[1].selectbox("时间范围", ["当前管理周期", "7天", "30天", "3个月", "1年", "全部"], key=f"{key_prefix}-trend-window")
    selected = options[selected_label]
    if window not in {"当前管理周期", "全部"}:
        cutoff = datetime.now(TOKYO_TIMEZONE) - timedelta(days={"7天":7,"30天":30,"3个月":90,"1年":365}[window])
        selected = tuple(replace(trend, points=tuple(p for p in trend.points if p.point_type == "BASELINE" or p.observed_at >= cutoff)) for trend in selected)
        st.caption("保留年度基线作为起点；后续记录按所选时间范围展示。")
    chart = baseline_trend_chart(selected)
    if chart is None:
        st.caption("目前还没有足够的后续数据形成趋势。")
        st.caption("；".join(f"{t.label} · 基线 {number_text(t.baseline_value)} {t.unit}" for t in selected))
    else:
        # Explicit Vega-Lite axes must not inherit Streamlit's minimalist theme.
        st.altair_chart(chart, width="stretch", theme=None, key=f"{key_prefix}-trend-chart")
        st.caption("虚线 / 菱形：年度基线；末端圆点：当前有效记录。悬停查看日期、数值、单位和来源。")


def render_baseline_overview(patient, baseline, *, session_factory, key_prefix):
    st.subheader(f"{baseline.cycle_year or baseline.assessed_at.year}年度健康基线")
    if baseline.status not in {"CONFIRMED", "AMENDED"}:
        st.caption("基线尚待人工确认，确认后可比较当前变化。")
        return
    with session_factory() as session:
        view = BaselineVisualizationService().build(session, patient.id, cycle_year=baseline.cycle_year)
    confirmed = view.assessment.confirmed_at or view.assessment.assessed_at
    st.caption(f"已确认 · 建立时间：{confirmed:%Y/%m/%d} · 已记录 {len(view.metrics)} 项指标；缺失资料不推断为正常。")
    render_baseline_progress(view, key_prefix=key_prefix)
