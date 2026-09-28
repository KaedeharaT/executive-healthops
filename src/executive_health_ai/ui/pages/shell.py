"""Portfolio and tools-shell UI that is intentionally independent of domain logic."""

from __future__ import annotations

from collections.abc import Callable

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
