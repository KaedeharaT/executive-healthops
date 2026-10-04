"""Accessible medical-blue progress shared by existing Agent boards."""
from html import escape
import streamlit as st
from executive_health_ai.ui.experience import business_text


class AgentProgressPanel:
    """One presentation for all workflows; accepts only the read-only projection."""
    @staticmethod
    def render(p,*,show_activity=True,flow_name="健康管理助手",next_action=""):
        if p is None:return
        st.caption(flow_name)
        minutes,seconds=divmod(p.elapsed_seconds,60)
        waiting=p.status in {'WAITING_MANAGER','WAITING_DOCTOR','WAITING_INPUT','WAITING_TIME','WAITING_EVENT'}
        running=p.running and not waiting
        st.markdown(f'<div class="agent-progress-title">整理进度 {p.progress_percent}% · {escape(business_text(p.step_label))}</div>'
            f'<div class="agent-progress-track" role="progressbar" aria-label="整体业务进度" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{p.progress_percent}">'
            f'<div class="agent-progress-fill" style="width:{p.progress_percent}%"></div></div>'
            f'<div class="agent-progress-detail">已完成 {p.completed_steps} / {p.total_steps} 步</div>',unsafe_allow_html=True)
        if show_activity:
            mark='<span class="agent-action-spinner" aria-label="正在整理资料"></span>' if running else '✓ ' if p.status=='COMPLETED' else '! ' if p.status in {'FAILED','ESCALATED','CANCELLED'} else '● '
            activity={'WAITING_MANAGER':'正在等待您确认','WAITING_DOCTOR':'正在等待医生判断','WAITING_INPUT':'资料不足，需要补充','COMPLETED':'已完成本次处理'}.get(p.status,p.current_activity)
            st.markdown(mark+escape(business_text(activity)),unsafe_allow_html=True)
        steps=''.join(f'<span class="{"current" if i==p.current_step-1 else ""}">{"✓ " if done else ""}{escape(business_text(label))}</span>' for i,(label,done) in enumerate(zip(p.labels,p.done)))
        st.markdown('<div class="assistant-steps" aria-label="整理步骤">'+steps+'</div>',unsafe_allow_html=True)
        if p.file_total:
            st.progress(p.file_completed/p.file_total,text=f'文件信息提取：{p.file_completed} / {p.file_total}')
            if p.running:st.caption('当前处理：'+p.current_file)
        if p.wait_message:st.info(p.wait_message)
        if next_action:st.caption('下一步：'+business_text(next_action))
        if p.timeout:st.warning('资料整理暂未完成。原文件和已核实的信息均已保留，请重试或人工补充。')
        if p.status=='WAITING_DOCTOR':st.caption('系统已完成可用资料整理，医生提交后会自动继续。')


def render(p,*,show_activity=True):
    AgentProgressPanel.render(p,show_activity=show_activity)


def ai_timing(p):
    if not p or not p.ai_used:return
    start=p.ai_started_at.astimezone().strftime('%H:%M:%S') if p.ai_started_at else '未记录'
    state='● 运行中' if p.ai_running else '✓ 完成' if p.ai_status=='SUCCESS' else '! 未完成'
    st.caption(f'资料整理 {state} · 开始时间：{start} · 已耗时：{p.ai_elapsed_seconds}秒')
