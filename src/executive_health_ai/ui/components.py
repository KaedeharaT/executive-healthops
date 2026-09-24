"""Role UI composition primitives. No persistence or clinical decisions."""
from contextlib import contextmanager
from html import escape
import streamlit as st


def page_shell(role, title, description="", eyebrow=""):
    """One role density and heading contract; no page-local CSS."""
    from executive_health_ai.ui import experience as ux
    ux.inject_design(role)
    ux.page_header(title, description, eyebrow)


def section_header(title, description=""):
    st.subheader(title)
    if description:
        st.caption(description)


def secondary_details(title):
    return st.expander(title, expanded=False)


def advanced_details(title="高级信息"):
    return st.expander(title, expanded=False)


def comparison_rows(comparisons, maximum=3):
    """Compact baseline/current facts above selectors, with full detail retained."""
    from executive_health_ai.services.baseline_visualization import number_text
    rows = []
    priority = {code: i for i, code in enumerate(("weight", "ldl_c", "hba1c", "systolic_bp", "diastolic_bp", "bmi"))}
    ordered = sorted(comparisons, key=lambda item: priority.get(item.code, 99))
    for item in ordered[:maximum]:
        values = (item.label, f"{number_text(item.baseline)} {item.unit}",
                  f"{number_text(item.current)} {item.unit}" if item.delta is not None else "暂无后续数据", item.delta_text)
        rows.append("<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in values) + "</tr>")
    if rows:
        st.markdown("<div class='v3-comparison'><table><thead><tr><th>指标</th><th>年度基线</th><th>当前</th><th>数值变化</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>", unsafe_allow_html=True)


def work_item_row(member, title, kind, state, due, *, key, selected=False):
    """Selection only. The business command lives in the adjacent detail panel."""
    from executive_health_ai.ui.experience import business_text
    title = business_text(title)
    short = title[:28] + "…" if len(title) > 28 else title
    label = f"{member} · {kind}\n{short}\n{state} · {due}"
    return st.button(label, key=key, width="stretch", icon=":material/arrow_right:" if selected else ":material/subject:")


@contextmanager
def section(title, *, key, description="", emphasis=False):
    with st.container(key=f"v2-{'hero' if emphasis else 'panel'}-{key}"):
        if title:
            st.subheader(title)
        if description:
            st.caption(description)
        yield


def summary_strip(values):
    items = ''.join(f"<div><small>{escape(str(label))}</small><strong>{escape(str(value))}</strong></div>" for label, value in values)
    st.markdown(f"<div class='v2-summary'>{items}</div>", unsafe_allow_html=True)


def care_team(people):
    st.markdown("**负责你的健康团队**")
    for role, name, detail in people:
        st.markdown(f"<div class='v2-team'><span>{escape(role)}</span><strong>{escape(name)}</strong><span>{escape(detail)}</span></div>", unsafe_allow_html=True)


def timeline_event(title, description, date, kind):
    st.markdown(f"<div class='v2-timeline'><div class='v2-date'>{escape(date)}</div><article><small>{escape(kind)}</small><h3>{escape(title)}</h3><p>{escape(description)}</p></article></div>", unsafe_allow_html=True)


def workflow(steps, current):
    # Explicit current state, not an inferred completion history.
    labels = ''.join(f"<div role='listitem' class='flow-step {'active' if step == current else ''}'><b class='flow-dot'>{i+1}</b><span>{'当前 · ' if step == current else ''}{escape(step)}</span></div>" for i, step in enumerate(steps))
    st.markdown(f"<div role='list' class='v2-workflow' aria-label='当前阶段'>{labels}</div>", unsafe_allow_html=True)


@contextmanager
def detail_panel(title, *, key, meta=""):
    with section(title, key=key, description=meta):
        yield


def business_table(*args, **kwargs):
    from executive_health_ai.ui.presentation import data_table
    return data_table(*args, **kwargs)


def filter_bar(*, key, statuses=(), owners=(), search_label='搜索记录'):
    columns = st.columns([2, 1, 1])
    query = columns[0].text_input(search_label, key=key+'-query', placeholder='会员、事项或关键词')
    status = columns[1].selectbox('状态', ['全部']+list(statuses), key=key+'-state')
    owner = columns[2].selectbox('负责人', ['全部']+list(owners), key=key+'-owner')
    return query.strip().casefold(), status, owner


@contextmanager
def detail_drawer(title, *, key, table_key):
    """Nonmodal right inspector. Closing resets only presentation selection."""
    st.markdown('''<style>
    div[class*="st-key-care-drawer-"] {position:fixed;right:16px;top:64px;bottom:16px;
      width:460px;max-width:92vw;overflow-y:auto;background:white;z-index:90;
      border:1px solid #cad8e5;border-radius:12px;padding:20px;box-shadow:0 12px 45px #24395233;}
    div[class*="st-key-care-drawer-"] h3 {font-size:1.05rem;}
    div[class*="st-key-care-drawer-"] .v2-summary>div {min-width:90px;padding:8px;}
    div[class*="st-key-care-drawer-"] .v2-timeline {grid-template-columns:70px 1fr;gap:12px;}
    @media(min-width:1200px) {[data-testid="stMainBlockContainer"]:has(div[class*="st-key-care-drawer-"]) {padding-right:500px!important;}}
    </style>''', unsafe_allow_html=True)
    with st.container(key='care-drawer-'+key):
        a, b = st.columns([4, 1])
        a.subheader(title)
        if b.button('关闭', key=key+'-close'):
            st.session_state[table_key+'-epoch'] = st.session_state.get(table_key+'-epoch', 0)+1
            st.rerun()
        yield


def member_header(name, *, cycle, owner, phase, concern, focus, next_action, updated):
    from executive_health_ai.ui.presentation import preview
    st.markdown(f"<div class='care-member-header'><div class='care-name'><h1>{escape(name)}</h1><small>MEMBER 360 · 全周期健康管理</small></div>"
                f"<div>{escape(cycle)}　·　责任健管：{escape(owner)}　·　{escape(phase)}　<small>更新：{escape(updated)}</small></div>"
                f"<div class='care-focus'><span><b>会员本人关注</b> {escape(preview(concern, 70))}</span>"
                f"<span><b>专业管理重点</b> {escape(preview(focus, 70))}</span></div>"
                f"<div class='care-next'><b>下一步</b> {escape(preview(next_action, 95))}</div>"
                f"</div>", unsafe_allow_html=True)


def stage_stepper(phases, *, key, current_id=None):
    """Clickable stage selection; completion comes from explicit stored status."""
    phases = list(phases)
    if not phases:
        return None
    ids = [str(p.id) for p in phases]
    selected = st.session_state.get(key, str(current_id) if current_id else ids[0])
    if selected not in ids:
        selected = ids[0]
    with st.container(key='care-stage-selector-'+key):
        cols = st.columns(len(phases))
        for col, phase in zip(cols, phases):
            state = '●' if phase.status in {'COMPLETED','REVIEWED'} else '◉' if phase.status == 'ACTIVE' else '○'
            label = '已完成' if phase.status in {'COMPLETED','REVIEWED'} else '当前' if phase.status == 'ACTIVE' else '待开始'
            if col.button(f'{state} {phase.title} · {label}', key=key+'-'+str(phase.id), width='stretch', type='primary' if str(phase.id)==selected else 'secondary'):
                st.session_state[key] = str(phase.id)
                st.rerun()
    return next(p for p in phases if str(p.id)==selected)


def timeline(*args, **kwargs):
    return timeline_event(*args, **kwargs)


def trend_chart(series, *, key):
    from executive_health_ai.ui.charts.health import render_metric_trend
    return render_metric_trend(series, key=key)


def empty_state(title, description=''):
    from executive_health_ai.ui.experience import empty_state as render
    return render(title, description)
