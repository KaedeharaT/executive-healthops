"""Shared, non-technical citation rendering for grounded AI answers."""

from __future__ import annotations

from collections.abc import Iterable

import streamlit as st

from executive_health_ai.services.grounded_ai import AICitation, AIAnswer


def _render_group(title: str, citations: Iterable[AICitation]) -> None:
    items = list(citations)
    if not items:
        st.caption("本次没有使用成员事实。" if title == "事实依据" else "未找到可用知识依据。")
        return
    st.markdown(f"**{title}**")
    for citation in items[:5]:
        with st.container(border=True):
            heading = citation.title
            if citation.version:
                heading += f" · {citation.version}"
            st.markdown(f"**{heading}**")
            details = " · ".join(value for value in (citation.organization, citation.display_location) if value)
            if details:
                st.caption(details)
            if citation.excerpt:
                st.write(citation.excerpt)
            if citation.current_status not in {None, "APPROVED", "ACTIVE"}:
                st.warning("该资料当前已归档或需要复核；这里保留的是回答生成时的引用记录。")
            if citation.source_url:
                st.link_button("查看来源", citation.source_url)
    if len(items) > 5:
        st.caption(f"另有 {len(items) - 5} 条依据未展开。")


def render_ai_citations(answer: AIAnswer, *, key: str) -> None:
    """Render factual and knowledge evidence without exposing database IDs."""
    status_labels = {
        "GROUNDED": "有知识依据",
        "PARTIALLY_GROUNDED": "部分依据",
        "INSUFFICIENT_EVIDENCE": "依据不足",
    }
    st.caption(f"依据状态：{status_labels.get(answer.grounded, '待确认')}")
    with st.expander("查看依据", expanded=False):
        _render_group("事实依据", answer.fact_citations)
        _render_group("知识依据", answer.knowledge_citations)
        for limitation in answer.limitations:
            st.caption(limitation)
