"""Accessible medical-blue progress shared by existing Agent boards."""
from html import escape
import streamlit as st


def render(p,*,show_activity=True):
    if p is None:return
    st.markdown('''<style>
    .agent-progress-track{height:10px;background:var(--neu-well,#dce6ef);border-radius:6px;overflow:hidden;margin:10px 0 12px;box-shadow:var(--neu-inset);}
    .agent-progress-fill{height:100%;background:var(--blue,#2875b7);border-radius:6px;}
    .agent-progress-title{font-size:22px;font-weight:700;color:var(--text,#193952);}
    .agent-progress-detail{color:var(--muted,#53687c);margin-bottom:10px;}
    .agent-action-spinner{display:inline-block;width:18px;height:18px;border:2px solid #c2d9ed;border-top-color:#2875b7;border-radius:50%;animation:agent-progress-spin 1s linear infinite;margin-right:8px;vertical-align:-2px;}
    @keyframes agent-progress-spin{to{transform:rotate(360deg)}}
    @media(prefers-reduced-motion:reduce){.agent-action-spinner{animation:none}}
    </style>''',unsafe_allow_html=True)
    minutes,seconds=divmod(p.elapsed_seconds,60)
    st.markdown(f'<div class="agent-progress-title">整体进度 {p.progress_percent}% · {escape(p.step_label)}</div>'
        f'<div class="agent-progress-track" role="progressbar" aria-label="整体业务进度" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{p.progress_percent}">'
        f'<div class="agent-progress-fill" style="width:{p.progress_percent}%"></div></div>'
        f'<div class="agent-progress-detail">第 {p.current_step} / {p.total_steps} 步 · 已完成 {p.completed_steps} / {p.total_steps} 步 · 已运行（含等待）：{minutes:02d}:{seconds:02d}</div>',unsafe_allow_html=True)
    if show_activity:
        mark='<span class="agent-action-spinner" aria-label="正在执行"></span>' if p.running else '✓ ' if p.status=='COMPLETED' else '! ' if p.status in {'FAILED','ESCALATED','CANCELLED'} else '● '
        st.markdown(mark+escape(p.current_activity),unsafe_allow_html=True)
    if p.file_total:
        st.progress(p.file_completed/p.file_total,text=f'文件信息提取：{p.file_completed} / {p.file_total}')
        if p.running:st.caption('当前处理：'+p.current_file)
    if p.wait_message:st.info(p.wait_message)
    if p.timeout:st.warning('AI整理未完成：AI服务响应超时。已保留原文件及可核实的规则结果，请重试或转人工处理。')
    if p.status=='WAITING_DOCTOR':st.caption('系统已完成可用资料整理，医生提交后会自动继续。')


def ai_timing(p):
    if not p or not p.ai_used:return
    start=p.ai_started_at.astimezone().strftime('%H:%M:%S') if p.ai_started_at else '未记录'
    state='● 运行中' if p.ai_running else '✓ 完成' if p.ai_status=='SUCCESS' else '! 未完成'
    st.caption(f'本地AI {state} · 开始时间：{start} · 已耗时：{p.ai_elapsed_seconds}秒')
