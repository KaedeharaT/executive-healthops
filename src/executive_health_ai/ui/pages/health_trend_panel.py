"""Presentation of existing filtered series; no new measurements or trend rules."""
from html import escape

import streamlit as st

from executive_health_ai.services.baseline_visualization import comparison_change, number_text
from executive_health_ai.services.health_visualization import option_label
from executive_health_ai.ui.charts.health import render_metric_trend
from executive_health_ai.ui.components import summary_strip


STYLES = '''<style>
.st-key-health-trend-panel {background:#fff;border:1px solid #cbdbe9!important;border-radius:12px;padding:22px!important;gap:12px!important;}
.st-key-health-trend-panel h3 {color:#193d60;font-size:20px!important;}
.st-key-health-trend-panel hr {margin:8px 0!important;border-color:#e0e7ef;}
.st-key-health-trend-filters {background:#f7f9fc;padding:14px 16px;border-radius:8px;gap:8px!important;}
.st-key-health-trend-filters [data-testid="stSelectbox"] {max-width:440px;}
.st-key-health-trend-filters [data-testid="stButtonGroup"] button {background:white;color:#53677c;border:1px solid #d2dce6;border-radius:7px!important;box-shadow:none;}
.st-key-health-trend-filters [data-testid="stButtonGroup"] button[aria-pressed="true"] {background:#eaf3fc;color:#185da8;border-color:#6a9fd0;}
.st-key-health-trend-summary .v2-summary {border:0;border-radius:0;background:transparent;padding:5px 0;margin:0;}
.st-key-health-trend-summary .v2-summary strong {font-size:18px!important;}
.st-key-health-trend-summary .v2-summary > div:first-child strong {color:#185da8;}
.st-key-health-trend-chart {background:#fff;padding:8px 4px;gap:8px!important;}
.trend-metadata {display:flex;flex-wrap:wrap;gap:12px 28px;font-size:13px;color:#596c7f;padding:8px 0;}
.trend-metadata b {font-weight:500;color:#334d65;margin-right:7px;}
@media(max-width:760px){.st-key-health-trend-panel{padding:14px!important;}.st-key-health-trend-summary .v2-summary{flex-wrap:wrap;}.st-key-health-trend-summary .v2-summary>div{min-width:45%;}}
</style>'''


def ordered_options(options):
    order = ('weight', 'bmi', 'blood_pressure', 'systolic_bp', 'diastolic_bp', 'heart_rate',
             'glucose', 'hba1c', 'ldl_c', 'alt', 'steps', 'exercise_minutes', 'active_calories',
             'sleep_duration', 'deep_sleep_duration', 'rem_sleep_duration', 'awake_duration')
    return {code: options[code] for code in (*order, *[c for c in options if c not in order]) if code in options}


def _joined(values, group):
    if len({s.unit for s in group}) == 1:
        return ' / '.join(values) + ' ' + group[0].unit
    return '；'.join(f'{s.label} {value} {s.unit}' for s, value in zip(group, values))


def summary_values(visible, metrics):
    latest = [s.points[-1] if s.points else None for s in visible]
    refs = [next((m for m in metrics if m.code == s.code and m.unit == s.unit and m.value is not None), None) for s in visible]
    current = _joined([number_text(p.value) if p else '—' for p in latest], visible) if any(latest) else '所选范围无记录'
    baseline = _joined([number_text(m.value) if m else '—' for m in refs], visible) if any(refs) else '暂无年度基线'
    changes = []
    for s, point, reference in zip(visible, latest, refs):
        if point is None or reference is None:
            changes.append('—')
        else:
            delta, _, direction = comparison_change(reference.value, point.value, s.code, s.unit)
            changes.append(direction.split()[0] + number_text(abs(delta)))
    unit_group = [type(s)(s.code, s.label, '个百分点' if s.unit == '%' else s.unit, s.points) for s in visible]
    change = _joined(changes, unit_group) if any(c != '—' for c in changes) else '暂无可比数据'
    dates = [p.at.strftime('%Y-%m-%d %H:%M') if p else '—' for p in latest]
    measured = dates[0] if len(set(dates)) == 1 else '；'.join(f'{s.label} {d}' for s, d in zip(visible, dates))
    return [('当前值 · 所选范围', current), ('年度基线', baseline), ('较年度基线变化', change), ('最近测量', measured)]


def show_all(period_key):
    st.session_state[period_key] = '全部'


def render_result(visible, full_group, metrics, *, code, key, period_key):
    with st.container(key='health-trend-summary'):
        summary_strip(summary_values(visible, metrics))
        if len(visible) > 1:
            st.caption('数值顺序：' + ' / '.join(s.label for s in visible))
    st.divider()
    with st.container(key='health-trend-chart'):
        count = max((len({p.at for p in s.points}) for s in visible), default=0)
        name = '血压' if code == 'blood_pressure' else option_label(code, visible)
        st.markdown('**' + name + ('历史比较' if count < 3 else '趋势') + '**')
        if any(s.has_trend for s in visible):
            if count == 2:
                st.caption('两次结果比较 · 仅有两个时间点，不足以表示长期趋势。')
            render_metric_trend(visible, key=f'{key}-chart', baseline_metrics=metrics, current_marker=True)
            if any(m.value is not None and any(s.code == m.code and s.unit == m.unit for s in visible) for m in metrics):
                st.caption('虚线：已确认年度健康基线；不是医学目标值。末端圆点：所选范围内的当前值。')
            for item in visible:
                if item.has_trend:
                    st.caption(item.label + ' · ' + item.comparison)
        else:
            st.info('当前时间范围内暂无足够数据形成趋势。')
            if not any(s.points for s in visible):
                for series in full_group:
                    if series.points:
                        point = series.points[-1]
                        st.caption(f'范围外最近有效记录 · {series.label} {number_text(point.value)} {series.unit} · {point.at:%Y-%m-%d %H:%M}')
            if st.session_state.get(period_key) != '全部':
                st.button('查看全部时间', key=f'{key}-all-time', on_click=show_all, args=(period_key,))
    st.divider()
    with st.container(key='health-trend-metadata'):
        st.markdown('**数据说明**')
        points = [p for s in visible for p in s.points]
        dates = {p.at for p in points}
        span = f'{min(dates):%Y-%m-%d} → {max(dates):%Y-%m-%d}' if dates else '所选范围无记录'
        quantity = f'{len(dates)} 组（{len(points)} 个数值）' if len(visible) > 1 else f'{len(points)} 点'
        source_names = {'已确认体检报告': '体检记录', '健康数据': '健康记录'}
        sources = '、'.join(dict.fromkeys(source_names.get(p.source, p.source) for p in points)) or '暂无数据'
        values = [('数据范围', span), ('数据点', quantity), ('数据来源', sources)]
        st.markdown('<div class="trend-metadata">' + ''.join(f'<span><b>{label}</b>{escape(value)}</span>' for label, value in values) + '</div>', unsafe_allow_html=True)
        st.caption('时间沿用原始记录时区（UTC）。以上统计与所选指标、时间范围一致；历史数据可用不代表设备当前已连接。')
