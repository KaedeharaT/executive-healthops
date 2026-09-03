"""Portfolio and tools-shell UI that is intentionally independent of domain logic."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import streamlit as st


def render_portfolio_landing(request_navigation: Callable[..., None]) -> None:
    """Render the anonymous portfolio entry screen and delegate navigation."""
    st.markdown(
        "<div class='portfolio-landing'><div class='portfolio-kicker'>Portfolio Demo</div>"
        "<h1>Executive HealthOps</h1>"
        "<p>企业高管 AI 健康运营平台。将体检资料、连续健康数据、确定性风险分流、"
        "健康管理师与医生协同、长期健康历程整合为可追溯的健康管理闭环。</p></div>",
        unsafe_allow_html=True,
    )
    left, right = st.columns(2, gap="medium")
    with left:
        if st.button("进入成员健康中心", type="primary", key="portfolio-enter-member", width="stretch"):
            st.session_state["portfolio-demo-landing-dismissed"] = True
            request_navigation(surface="成员健康中心")
    with right:
        if st.button("进入 HealthOps 运营后台", key="portfolio-enter-ops", width="stretch"):
            st.session_state["portfolio-demo-landing-dismissed"] = True
            request_navigation(surface="运营后台")
    st.caption("演示数据已匿名化；风险展示仅用于工作流演示，医学判断仍由人工负责。")


def render_more_workspace_shell(
    *,
    page_header: Callable[..., None],
    load_members: Callable[[], list[Any]],
    render_integration_center: Callable[[], None],
    render_ai_improvement: Callable[[], None],
    render_risk_rules: Callable[[], None],
    render_audit: Callable[[dict[str, list[object]]], None],
    audit_context: Callable[[Any], dict[str, list[object]]],
    member_display: Callable[[Any], str],
) -> None:
    """Keep the More-page navigation shell separate from domain renderers."""
    page_header("更多", "数据接入、专业资料与系统管理。", eyebrow="平台工具")
    options = ["风险规则", "操作记录", "系统"]
    if st.session_state.get("more-navigation") not in {None, *options}:
        st.session_state.pop("more-navigation", None)
    more = st.session_state.get("more-navigation")
    if more is None:
        st.subheader("管理工具")
        st.caption("选择一个工具后才加载对应内容。")
        entries = [
            ("风险规则", "查看已审核的风险与健康管理规则"),
            ("操作记录", "查看最近的人工处理记录"),
            ("系统", "查看集成状态、导入数据和高级治理信息"),
        ]
        for start in range(0, len(entries), 2):
            columns = st.columns(2)
            for column, (title, description) in zip(columns, entries[start:start + 2]):
                with column:
                    with st.container(border=True):
                        st.markdown(f"**{title}**")
                        st.caption(description)
                        if st.button("查看", key=f"more-open-{title}", width="stretch"):
                            st.session_state["more-navigation"] = title
                            st.rerun()
        return
    if st.button("← 返回更多", key="more-back"):
        st.session_state.pop("more-navigation", None)
        st.rerun()
    if more == "风险规则":
        render_risk_rules()
    elif more == "操作记录":
        st.subheader("操作记录")
        members = load_members()
        patient = st.selectbox("选择成员", members, format_func=member_display, key="audit-member")
        render_audit(audit_context(patient.id))
    else:
        render_integration_center()
        with st.expander("AI 质量治理（高级）"):
            render_ai_improvement()
