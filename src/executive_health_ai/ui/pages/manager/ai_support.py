"""Shared business support panel; technical identifiers remain admin-only."""
from html import escape
import streamlit as st
from executive_health_ai.services.agent_capabilities import capabilities, technical_rows
from executive_health_ai.ui import experience as ux


def route(goal, activities, traces):
    st.markdown('<div class="capability-route" role="list" aria-label="本次使用能力"><strong>本次使用能力</strong>' + ''.join(
        f'<span role="listitem" class="{state}">{escape(label)} {"● 当前" if state == "current" else "✓ 已使用" if state == "used" else "○ 尚未使用"}</span>'
        for label,state in capabilities(goal,activities,traces)) + '</div>',unsafe_allow_html=True)


@st.dialog('知识依据详情', width='large')
def knowledge_detail(citations):
    st.caption('真实检索返回的已审核知识；知识依据不是会员事实，也不产生正式风险。')
    for index, item in enumerate(citations, 1):
        st.markdown(f'**{index}. {item.get("title") or "已审核资料"}**')
        for label, key in [('来源','source'),('版本','version'),('位置','location')]:
            if item.get(key): st.caption(label+'：'+str(item[key]))
        st.write(item.get('excerpt') or '本条未保存摘要。')
        url = str(item.get('source_url') or '')
        if url.startswith(('https://','http://')): st.link_button('查看原始来源',url)
        st.divider()


@st.dialog('健管确认摘要', width='large')
def summary_detail(text):
    st.caption('这是资料摘要，请结合原文核对；医学结论以医生意见为准。')
    st.write(text)


def panel(goal, activities, *, key='board-ai-support'):
    with st.container(border=True,key=key):
        st.subheader('整理依据与参考资料')
        st.caption('会员情况以原始资料为准；参考资料不会自动变成会员的诊断。')
        ai, knowledge = st.columns([1.35,1], gap='large')
        for index, activity in enumerate(activities):
            with knowledge if activity.key == 'knowledge' else ai:
                st.markdown(f'**{ux.business_text(activity.title)}**　{activity.mark} {ux.business_text(activity.label)}')
                st.caption('用途：'+ux.business_text(activity.purpose))
                if not activity.used:
                    st.caption('未使用：本步骤没有已发起的调用记录。')
                st.write('结果：'+ux.business_text(activity.result))
                if activity.at: st.caption('记录时间：'+ux.when(activity.at))
                if activity.citations and st.button('查看依据',key=f'{key}-knowledge-{goal.id}-{index}'):
                    knowledge_detail(activity.citations)
                if activity.key == 'summary' and activity.status == 'SUCCESS' and goal.context_json.get('summary'):
                    if st.button('查看摘要',key=f'{key}-summary-{goal.id}'):
                        summary_detail(goal.context_json.get('ai_summary_draft') or goal.context_json['summary'])
                st.divider()


def technical(traces):
    st.markdown('**AI / Knowledge calls**')
    rows = technical_rows(traces)
    if rows: st.dataframe(rows,hide_index=True,width='stretch')
    else: st.caption('无逐次能力审计记录；不根据当前配置补写历史调用。')
