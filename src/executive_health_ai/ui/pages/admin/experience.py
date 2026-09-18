import os
import streamlit as st
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from executive_health_ai.models import AgentGoal
from executive_health_ai.llm.local_llm_client import LocalLLMSettings
from executive_health_ai.ui import experience as ux


def integrations(app):
    ux.page_header("集成与数据", "先确认连接状态，再检查或测试；配置不等于连接成功。", "系统")
    settings = LocalLLMSettings.from_environment()
    rows = [
        ("数据导入", "可用", "检查 → 预览 → 人工确认 → 正式写入", "数据导入"),
        ("AI服务", "已配置，待测试" if settings.enabled and settings.model else "未配置", "仅辅助整理与有依据的解释", "AI服务"),
        ("专业知识服务", "合作方已配置，待测试" if os.getenv("KNOWLEDGE_API_BASE") else "未连接合作方", "已审核内部规范可单独使用", "专业知识服务"),
        ("设备接入", "3个模拟适配器 / 0个已验证真实连接", "批量导入可用；接口不代表真实连接", "设备接入"),
    ]
    for title, status, summary, mode in rows:
        left, right = st.columns([5, 1])
        with left:
            ux.work_item(title, status, summary + " · 最后测试：" + st.session_state.get(f"integration-tested-{mode}", "暂无本次会话测试"))
        if right.button("检查", key={"数据导入":"integration-open-data", "AI服务":"integration-open-ai", "专业知识服务":"integration-open-knowledge", "设备接入":"integration-open-device"}[mode]):
            st.session_state["integration-center-mode"] = mode
    mode = st.session_state.get("integration-center-mode", "数据导入")
    st.divider()
    if mode == "数据导入":
        app._render_data_package_import(key_prefix="integration-data")
    elif mode == "AI服务":
        app._render_ai_service_integration()
    elif mode == "专业知识服务":
        app._render_knowledge_service_integration()
    else:
        app._render_device_integration()


def workspace(app):
    ux.inject_design("admin")
    st.sidebar.caption("系统配置与运行保障")
    section = st.sidebar.radio("系统", ["集成与数据", "自动化运营", "规则与知识", "系统状态"], key="ux-admin-navigation")
    if section == "集成与数据":
        integrations(app)
    elif section == "自动化运营":
        ux.page_header("自动化运营", "按成员查看长期管理的等待、失败和下一步。")
        app._render_admin_automation()
    elif section == "规则与知识":
        mode = st.radio("配置内容", ["规则", "专业知识", "设备"], horizontal=True)
        {"规则": app.render_risk_rules, "专业知识": app._render_knowledge_service_integration, "设备": app._render_device_integration}[mode]()
    else:
        ux.page_header("系统状态", "运行信息与操作记录。")
        try:
            with app.SessionLocal() as session:
                session.execute(select(1))
                failed = session.scalar(select(func.count()).select_from(AgentGoal).where(AgentGoal.status.in_(("BLOCKED", "FAILED")))) or 0
            ux.metric_row([("数据访问", "可用"), ("自动化需处理", failed), ("当前运行方式", "演示预览")])
            st.caption("数据访问为本次页面查询结果；自动化异常请到自动化运营查看负责人和下一步。")
        except SQLAlchemyError:
            st.error("暂时无法访问数据，请由管理员检查本机服务。")
        st.info("当前为演示角色预览；角色切换不等于登录或权限认证。")
        with st.expander("操作记录"):
            members = app._members()
            if members:
                member = st.selectbox("选择成员", members, format_func=app._member_display)
                app.render_audit(app._audit_context(member.id))
        with st.expander("AI质量治理（高级）"):
            app.render_ai_improvement(app.SessionLocal)
