"""Role UI composition primitives. No persistence or clinical decisions."""
from contextlib import contextmanager
from html import escape
import streamlit as st


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
