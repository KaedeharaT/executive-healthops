"""Legacy keys resolve to current admin pages without a second menu."""
import streamlit as st

TARGETS={'风险规则':'规则与知识','专业资料':'规则与知识','操作记录':'系统状态',
         '系统':'数据与集成','集成与数据':'数据与集成','自动化运营':'自动化运行'}


def render_support_directory(app):
    legacy = st.session_state.pop("more-navigation", None)
    st.session_state['ux-admin-navigation']=TARGETS.get(legacy,'系统状态')
    if legacy in {'风险规则','专业资料'}:
        st.session_state['admin-knowledge-mode']='专业知识' if legacy=='专业资料' else '规则'
    app.request_navigation(surface="系统管理")
