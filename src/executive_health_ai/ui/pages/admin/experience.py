import os
import streamlit as st
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from executive_health_ai.models import AgentGoal
from executive_health_ai.llm.local_llm_client import LocalLLMSettings
from executive_health_ai.ui import experience as ux
from executive_health_ai.ui import components as c
from executive_health_ai.ui.presentation import data_table


def integration_statuses():
    settings = LocalLLMSettings.from_environment()
    rows = [
        ("数据导入", "可用", "检查 → 预览 → 人工确认 → 正式写入", "数据导入"),
        ("AI服务", "已配置，待测试" if settings.enabled and settings.model else "未配置", "仅辅助整理与有依据的解释", "AI服务"),
        ("专业知识服务", "合作方已配置，待测试" if os.getenv("KNOWLEDGE_API_BASE") else "未连接合作方", "已审核内部规范可单独使用", "专业知识服务"),
        ("设备接入", "3个模拟适配器 / 0个已验证真实连接", "批量导入可用；接口不代表真实连接", "设备接入"),
    ]
    return rows


def integrations(app):
    ux.page_header("集成与数据", "先确认连接状态，再检查或测试；配置不等于连接成功。", "系统")
    rows = integration_statuses()
    c.summary_strip([("数据导入", "可用"), ("AI服务", rows[1][1]), ("专业知识", rows[2][1]), ("真实设备连接", "0个已验证")])
    catalog, config = st.columns([1, 1.8], gap="large")
    with catalog:
        with c.section("连接与服务", key="integration-list"):
            selected = data_table(rows, [{"集成": title, "状态": state, "最后测试": st.session_state.get(f"integration-tested-{mode}", "暂无本次会话测试")} for title,state,summary,mode in rows], key="integrations", label="选择集成", auto_select=False)
    if selected and st.session_state.get('integration-grid-last') != selected[3]:
        st.session_state['integration-center-mode'] = selected[3]
        st.session_state['integration-grid-last'] = selected[3]
    with st.expander('兼容快捷入口'):
        for title, state, summary, target in rows:
            key = {'数据导入':'integration-open-data', 'AI服务':'integration-open-ai', '专业知识服务':'integration-open-knowledge', '设备接入':'integration-open-device'}[target]
            if st.button('检查 · '+title, key=key):
                st.session_state['integration-center-mode'] = target
    mode = st.session_state.get('integration-center-mode')
    with config:
        if not mode:
            with c.section("选择需要检查的连接", key="integration-config-empty"):
                st.write("先看左侧状态，选择“检查”后再配置或测试。")
                st.caption("配置存在不代表连接成功；测试结果和最后同步在对应详情中查看。")
            return
        with c.section(mode, key="integration-config", description=next(row[2] for row in rows if row[3] == mode) + "。配置不等于已连接。"):
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
    section = st.sidebar.radio("系统", ["系统状态", "集成与数据", "自动化运营", "规则与知识"], key="ux-admin-navigation")
    if section == "集成与数据":
        integrations(app)
    elif section == "自动化运营":
        ux.page_header("自动化运营", "按成员查看长期管理的等待、失败和下一步。")
        app._render_admin_automation()
    elif section == "规则与知识":
        mode = st.radio("配置内容", ["规则", "专业知识", "设备"], horizontal=True)
        if mode == "设备":
            st.info("设备配置已归入集成与数据；此兼容入口打开同一份配置。")
            st.button("打开设备接入", on_click=_open_device, type="primary")
        else:
            if mode == "专业知识":
                st.caption("内部规范、已审核资料与知识治理；合作方连接沿用集成中心的同一配置。")
            {"规则": app.render_risk_rules, "专业知识": app._render_knowledge_service_integration}[mode]()
    else:
        c.page_shell("admin", "系统状态", "先查看需要处理的问题，再进入连接与配置。")
        try:
            with app.SessionLocal() as session:
                session.execute(select(1))
                failed = session.scalar(select(func.count()).select_from(AgentGoal).where(AgentGoal.status.in_(("BLOCKED", "FAILED")))) or 0
            ux.metric_row([("数据访问", "可用"), ("自动化需处理", failed), ("当前运行方式", "演示预览")])
            st.caption("数据访问为本次页面查询结果；自动化异常请到自动化运营查看负责人和下一步。")
        except SQLAlchemyError:
            st.error("暂时无法访问数据，请由管理员检查本机服务。")
        with c.section("集成状态", key="system-connections"):
            rows = integration_statuses()
            data_table(rows, [{"集成": title, "状态": state} for title,state,summary,mode in rows], key="system-integrations", selectable=False)
            st.button("检查集成与数据", key="system-open-integrations", type="primary", on_click=_open_integrations)
        with c.secondary_details("运行方式与责任边界"):
            st.info("当前为演示角色预览；角色切换不等于登录或权限认证。")
        with st.expander("操作记录"):
            members = app._members()
            if members:
                member = st.selectbox("选择成员", members, format_func=app._member_display)
                app.render_audit(app._audit_context(member.id))
        with st.expander("AI质量治理（高级）"):
            app.render_ai_improvement(app.SessionLocal)
        legacy_tools(app)


def legacy_tools(app):
    """Explicit, discoverable home for retained historical UI capabilities."""
    with st.expander("高级信息 · 兼容工具"):
        with st.expander("原平台工具目录"):
            from executive_health_ai.ui.pages.support_navigation import render_support_directory
            render_support_directory(app)
        st.caption("保留历史详细视图和管理工具。这里的操作仍使用原有业务服务；仅用于演示管理与核对。")
        members = app._members()
        if not members:
            st.caption("暂无成员资料。")
            return
        member = st.selectbox("兼容工具成员", members, format_func=app._member_display, key="v2-legacy-member")
        options = ["健康数据完整视图", "报告比较", "干预前后比较", "风险监管摘要", "数据接入网关", "成员设备分配", "演示路径", "完整成员摘要", "历史健康问题", "历史医疗记录", "全部异常处理", "原始观测详情", "数据来源详情", "阶段结果详情", "历史时间轴"]
        selected = st.selectbox("选择兼容工具", options, key="v2-legacy-tool")
        if st.button("打开兼容工具", key="v2-legacy-open"):
            st.session_state["v2-legacy-active"] = (selected, str(member.id))
        if st.session_state.get("v2-legacy-active") != (selected, str(member.id)):
            return
        simple = {"健康数据完整视图": lambda: app.render_health_data(member.id),
            "报告比较": lambda: app.render_report_comparison(member),
            "干预前后比较": lambda: app.render_intervention_comparison(member),
            "风险监管摘要": app.render_oversight_summary,
            "数据接入网关": lambda: app.render_data_gateway(members),
            "成员设备分配": lambda: app.render_member_device_assignments(members),
            "演示路径": lambda: app.render_demo_story(members),
            "全部异常处理": lambda: app.render_global_alert_workspace(members)}
        if selected in simple:
            simple[selected]()
        else:
            ctx = app._context(member.id)
            renderers = {"完整成员摘要": lambda: app.render_overview(member, ctx),
                "历史健康问题": lambda: app.render_simple_health_problems(member, ctx),
                "历史医疗记录": lambda: app.render_simple_medical_records(member, ctx),
                "原始观测详情": lambda: app.render_observations(ctx),
                "数据来源详情": lambda: app.render_data_sources(ctx),
                "阶段结果详情": lambda: app.render_outcomes(ctx),
                "历史时间轴": lambda: app.render_timeline(member, ctx)}
            renderers[selected]()


def _open_integrations():
    st.session_state["ux-admin-navigation"] = "集成与数据"


def _open_device():
    st.session_state["integration-center-mode"] = "设备接入"
    _open_integrations()
