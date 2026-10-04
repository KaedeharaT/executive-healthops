"""Role UI composition primitives. No persistence or clinical decisions."""
from contextlib import contextmanager
from html import escape
import streamlit as st


PRIORITY_LABELS = {'GREEN': ('✓', '正常跟进'), 'YELLOW': ('!', '需要您确认'),
                   'RED': ('!', '需要优先处理'), 'UNKNOWN': ('○', '资料待完善')}


def priority_strip(level, message='', *, next_action='', label=None):
    """Presentation only: never infer a clinical risk from missing data."""
    from executive_health_ai.ui.experience import business_text
    level = level if level in PRIORITY_LABELS else 'UNKNOWN'
    icon, title = PRIORITY_LABELS[level]
    follow = f'<div class="priority-next">下一步：{escape(business_text(next_action))}</div>' if next_action else ''
    st.markdown(f'<section class="care-priority priority-{level.lower()}" role="status" aria-label="{escape(label or title)}">'
                f'<span class="priority-icon" aria-hidden="true">{icon}</span><div><strong>{escape(label or title)}</strong>'
                f'<p>{escape(business_text(message))}</p>{follow}</div></section>', unsafe_allow_html=True)


def work_level(item):
    """Work priority, not a new medical risk classification."""
    if item.status in {'已完成', 'COMPLETED', 'CANCELLED'}:
        return 'GREEN'
    return 'RED' if item.priority == 0 else 'YELLOW'


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


def summary_strip(values, *, anchors=None):
    items = ''
    for label, value in values:
        content = f"<small>{escape(str(label))}</small><strong>{escape(str(value))}</strong>"
        if anchors and label in anchors:
            content = f'<a href="#{escape(anchors[label], quote=True)}" target="_self" style="color:inherit;text-decoration:none;display:block">{content}</a>'
        items += f'<div>{content}</div>'
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


def filter_bar(*, key, statuses=(), owners=(), search_label='搜索记录', all_statuses=True):
    with st.container(key='soft-filter-'+key):
        columns = st.columns([2, 1, 1])
        query = columns[0].text_input(search_label, key=key+'-query', placeholder='会员、事项或关键词')
        status = columns[1].selectbox('状态', (['全部'] if all_statuses else [])+list(statuses), key=key+'-state')
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


def member_header(name, *, cycle, owner, phase, concern, focus, next_action, updated, demo=False):
    badge = " <span class='ux-badge'>演示会员</span>" if demo else ''
    st.markdown(f"<header class='care-member-header'><small>会员 / {escape(name)}</small><h1>{escape(name)}{badge}</h1>"
        f"<div class='member-meta'><span>责任健管：{escape(owner)}</span><span>{escape(cycle)}</span><span>当前阶段：{escape(phase)}</span></div></header>",unsafe_allow_html=True)


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
            if col.button(f'{state} {phase.title} · {label}', key=key+'-'+str(phase.id), width='stretch', type='secondary'):
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


def intake_steps(steps, selected, responses):
    """Use existing saved sections, never infer completion from step position."""
    cells = []
    for index, title in enumerate(steps):
        saved = title in responses and (title != '当前用药 / 营养补充' or '最近用药' in responses)
        state = 'current' if index == selected else 'done' if saved else 'pending'
        label = '当前填写' if index == selected else '已保存' if saved else '待填写'
        mark = '✓' if saved and index != selected else str(index+1)
        current = ' aria-current="step"' if index == selected else ''
        cells.append(f'<li class="{state}"{current}><b>{mark}</b><span>{escape(title)}<small>{label}</small></span></li>')
    st.markdown('<ol class="neu-intake-steps" aria-label="初始健康评估步骤">'+''.join(cells)+'</ol>', unsafe_allow_html=True)
