"""Discoverable support directory; retained URLs/keys route to the admin role."""
import streamlit as st
from executive_health_ai.ui import experience as ux


def render_support_directory(app):
    if st.button("返回今日工作",key="support-return-work"):
        app.request_navigation(surface="运营后台",ops_page="今日")
    legacy = st.session_state.pop("more-navigation", None)
    if legacy in {"风险规则", "操作记录", "系统"}:
        st.session_state["ux-admin-navigation"] = {"风险规则":"规则与知识", "操作记录":"系统状态", "系统":"集成与数据"}[legacy]
        app.request_navigation(surface="系统管理")
    ux.page_header("更多", "健康工作在今日和成员详情处理；系统配置与技术诊断集中在管理员。")
    if st.button("进入系统", key="more-open-系统", type="primary"):
        app.request_navigation(surface="系统管理")
    entries = [("集成与数据", "报告批量导入、AI、知识接口与设备接入", "集成与数据"),
        ("自动化运营", "等待、异常、人工接手与高级诊断", "自动化运营"),
        ("风险规则", "已审核规则与专业知识配置", "规则与知识"),
        ("操作记录", "审计、反馈治理和历史兼容工具", "系统状态")]
    for label, description, target in entries:
        left, right = st.columns([4, 1])
        left.markdown("**" + label + "**")
        left.caption(description)
        if right.button("打开", key="more-open-" + label):
            st.session_state["ux-admin-navigation"] = target
            app.request_navigation(surface="系统管理")
    with st.expander("专业资料"):
        st.caption("业务中的依据与引用仍在报告、数据和医生问题旁边。完整资料检索保留在此。")
        app.render_knowledge_library_entry()
