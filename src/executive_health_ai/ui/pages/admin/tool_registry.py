"""Technical registry stays in the existing administration workspace."""
import streamlit as st
from sqlalchemy import select
from executive_health_ai.agent.tools import AgentToolRegistry
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentRunTrace


def render():
    st.subheader('业务工具与责任边界')
    with SessionLocal() as session:
        calls = list(session.scalars(select(AgentRunTrace).where(
            AgentRunTrace.action == 'tool_execution').order_by(AgentRunTrace.started_at.desc())))
    latest = {}
    for call in calls: latest.setdefault(call.tool_name, call)
    st.dataframe([{'工具名': tool.name, '用途': tool.description,
        '权限级别': tool.responsibility, '自主权限': tool.autonomy_level, '启用状态': '启用' if tool.enabled else '未配置',
        '最后运行状态': latest[tool.name].status if tool.name in latest else '尚未运行'}
        for tool in AgentToolRegistry().tools], hide_index=True, width='stretch')
    st.caption('知识库未配置。医学判断仍由医生完成；正式风险由确定性规则计算。')
    with SessionLocal() as session:
        from executive_health_ai.services.autonomy_projection import oversight
        st.caption('过去24小时：' + str(oversight(session)))
        decisions = list(session.scalars(select(AgentRunTrace).where(AgentRunTrace.action == 'autonomy_decision')
            .order_by(AgentRunTrace.started_at.desc()).limit(100)))
    st.subheader('自主执行决策')
    st.dataframe([{'时间': t.started_at, '流程': str(t.goal_id), '工具': t.tool_name,
        '风险': t.metadata_json.get('risk_level') or '不适用', '模式': t.metadata_json.get('autonomy_mode'),
        '决定': t.status, '原因': t.metadata_json.get('reason_code'),
        '责任': t.metadata_json.get('required_role') or '系统', '策略版本': t.metadata_json.get('policy_version'),
        '规则版本': t.metadata_json.get('risk_rule_version')} for t in decisions], hide_index=True, width='stretch')
