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
    labels = ''.join(f"<span class='{'active' if step == current else ''}'>{'当前 · ' if step == current else ''}{escape(step)}</span>" for step in steps)
    st.markdown(f"<div class='v2-workflow' aria-label='当前阶段'>{labels}</div>", unsafe_allow_html=True)


@contextmanager
def detail_panel(title, *, key, meta=""):
    with section(title, key=key, description=meta):
        yield
