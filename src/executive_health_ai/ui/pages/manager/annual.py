"""Portfolio first annual landing page; all detail remains in Member360."""
from datetime import date
from html import escape
import streamlit as st
from executive_health_ai.database import SessionLocal
from executive_health_ai.services import annual_portfolio as portfolio
from executive_health_ai.ui import components as c
from executive_health_ai.ui.presentation import data_table
from executive_health_ai.ui.status_dictionary import status_label


def open_member(app, row):
    st.session_state['member-return-origin'] = '年度管理'
    st.session_state[f'annual-program-{row.member.id}'] = str(row.id)
    st.session_state.pop(f'workflow-mode-{row.member.id}',None)
    st.session_state.pop(f'workflow-detail-{row.member.id}',None)
    st.session_state.pop(f'action-focus-{row.member.id}',None)
    st.session_state['annual-members-epoch'] = st.session_state.get('annual-members-epoch', 0) + 1
    app._open_member_management(row.member.id)


def render(app):
    from executive_health_ai.ui.pages.manager.workflow import flash
    flash()
    with SessionLocal() as session:
        all_rows = portfolio.load(session)
    with st.container(key='soft-annual-header'):
        c.page_shell('manager', '年度管理', '管理一批会员的全年进度：基线、阶段推进、复盘与待处理事项。')
        st.caption('我负责的会员，今年管理到哪了？选择年度周期，进入同一个 Member360 的管理页。')
    summary_surface = st.container(key='soft-annual-summary')
    saved = st.session_state.get('annual-saved-filters', {})
    def choose(column, label, options, key, default='全部', **kwargs):
        value = saved.get(key, default)
        return column.selectbox(label, options, index=options.index(value) if value in options else 0, key=key, **kwargs)
    with st.expander('筛选年度进度'):
        a,b,d = st.columns(3)
        years = sorted({r.year for r in all_rows}, reverse=True)
        year = choose(a,'年度', ['全部'] + [str(y) for y in years], 'annual-year', str(date.today().year))
        stage = choose(b,'当前阶段', ['全部', *portfolio.STAGES], 'annual-stage')
        owner = choose(d,'责任健管', ['全部'] + sorted({r.view.owner or '待分配' for r in all_rows}), 'annual-owner')
        a,b,d = st.columns(3)
        overdue = choose(a,'是否逾期', ['全部','是','否'], 'annual-overdue')
        doctor = choose(b,'是否等待医生', ['全部','是','否'], 'annual-doctor')
        review = choose(d,'是否待复盘', ['全部','是','否'], 'annual-review')
        a,b = st.columns([2,1])
        query = a.text_input('查找年度目标或会员', value=saved.get('annual-filter-search',''), key='annual-filter-search', placeholder='年度目标关键词 / 会员称呼').strip()
        status = choose(b,'周期状态', ['全部'] + sorted({r.view.program.status for r in all_rows}),
                             'annual-filter-status', format_func=lambda value: '全部' if value == '全部' else status_label(value))
    st.session_state['annual-saved-filters'] = dict(zip(['annual-year','annual-stage','annual-owner','annual-overdue',
        'annual-doctor','annual-review','annual-filter-search','annual-filter-status'], [year,stage,owner,overdue,doctor,review,query,status]))
    rows = portfolio.filter_rows(all_rows, year=year, stage=stage, owner=owner, overdue=overdue,
                                 doctor=doctor, review=review, status=status, query=query)
    with summary_surface:
        c.summary_strip(portfolio.summary(rows))
        st.caption(f'{len(rows)} 个年度周期 · 汇总按筛选范围内会员去重；阶段分布按周期计数。')
    with st.container(key='soft-annual-table'):
        st.subheader('年度进度工作表')
        st.caption('阶段进度按已完成入组节点或阶段内已排期事项计算，不代表健康改善比例。开放事项统计本周期任务、复查与服务。阶段复盘窗口 14 天；年度复盘窗口 30 天。')
        records = []
        for row in rows:
            view, p = row.view, row.view.program
            state = '逾期' if row.overdue else status_label(p.status) if row.abnormal or row.stage == '已结束' else '待医生' if row.waiting_doctor else '待复盘' if row.review_due else '正常'
            records.append({'会员':row.member.display_name,'责任健管':view.owner or '待分配','年度阶段':str(row.year)+' · '+row.stage,
                '当前进度':row.progress,'开放事项':row.open_count,'下一步':row.next_node,'状态':state})
        chosen = data_table(rows, records, key='annual-members', label='选择年度会员', auto_select=False,
                            activate_on_cell=True, empty='当前筛选没有年度周期，请调整筛选条件。')
        if chosen:
            open_member(app, chosen)
            st.rerun()
