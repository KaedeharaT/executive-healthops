"""Structured presentation primitives; selections never write business facts."""
from datetime import date, datetime
from hashlib import sha256

import pandas as pd
import streamlit as st

from executive_health_ai.ui import components as c, experience as ux
from executive_health_ai.ui.status_dictionary import status_label


def preview(value, limit=32):
    text = ' '.join(ux.business_text(str(value or '—')).split())
    return text if len(text) <= limit else text[:limit-1] + '…'


def display_frame(records):
    """Only summaries enter the grid; callers retain the original detail objects."""
    frame = pd.DataFrame([{k: '—' if v is None else v if isinstance(v, (datetime, date, int, float)) else preview(v) for k, v in row.items()} for row in records])
    for name in frame:
        values = [v for v in frame[name] if v is not None and not pd.isna(v)]
        if values and any(isinstance(v, str) for v in values) and not all(isinstance(v, str) for v in values):
            frame[name] = frame[name].map(lambda v: v.strftime('%Y/%m/%d %H:%M') if isinstance(v, datetime) else v.strftime('%Y/%m/%d') if isinstance(v, date) else preview(v))
    return frame


def selected_record(rows, selection):
    state = selection.get('selection', {}) if selection else {}
    indices = state.get('rows', []) or [cell[0] for cell in state.get('cells', [])]
    index = indices[0] if indices else 0
    return rows[index] if rows and isinstance(index, int) and 0 <= index < len(rows) else (rows[0] if rows else None)


def data_table(rows, records, *, key, label='选择记录', selectable=True, empty='暂无记录。', search=False, export=False, auto_select=True, activate_on_cell=True, cell_actions=None):
    """Native sortable grid with built-in keyboard selection and stable source identity.

    Streamlit returns original input indices even after client-side sorting. A data
    signature resets selection when the record set changes, preventing stale actions.
    Updating the selected object's status keeps its detail open.
    """
    rows, records = list(rows), list(records)
    if len(rows) != len(records):
        raise ValueError('表格记录必须与业务对象一一对应')
    if search and rows:
        query = st.text_input('搜索记录', key=key+'-search', placeholder='搜索摘要或下一步')
        pairs = [(r, d) for r, d in zip(rows, records) if not query or query.casefold() in ' '.join(str(v) for v in d.values()).casefold()]
        rows, records = ([p[0] for p in pairs], [p[1] for p in pairs])
    if not rows:
        st.caption(empty)
        return None
    frame = display_frame(records)
    identities = [str(getattr(r, 'id', '') or '') for r in rows]
    stable_objects = all(identities) and len(set(identities)) == len(rows)
    signature = sha256((repr(identities) if stable_objects else repr(records)).encode()).hexdigest()[:12]
    grid_key = f'{key}-{signature}-{st.session_state.get(key+"-epoch", 0)}'
    st.caption(f'{len(rows)} 条 · 点击行查看详情；操作列独立处理' if cell_actions else f'{len(rows)} 条 · 点击行查看详情；点击列名排序' if selectable else f'{len(rows)} 条 · 点击列名排序')
    columns = {}
    for name in frame:
        columns[name] = st.column_config.TextColumn(name, width=180 if name in {'事项','问题','检查项目'} else 140 if name in {'下一步','结果'} else 110)
        values = [v for v in frame[name] if v is not None and not pd.isna(v)]
        if values and all(isinstance(v, datetime) for v in values):
            columns[name] = st.column_config.DatetimeColumn(name, format='YYYY/MM/DD HH:mm')
        elif values and all(isinstance(v, date) for v in values):
            columns[name] = st.column_config.DateColumn(name, format='YYYY/MM/DD')
        elif values and all(isinstance(v, (int, float)) for v in values):
            columns[name] = st.column_config.NumberColumn(name)
    options = dict(hide_index=True, width='stretch', height=min(420, 38+36*len(rows)), row_height=36, key=grid_key, column_config=columns)
    # Text and a neutral blue badge treatment; priority is not a clinical risk.
    status_columns = [col for col in frame if col in {'状态', '优先级'}]
    styled = frame.style.format(na_rep='—')
    if status_columns:
        styled = styled.map(lambda _: 'background-color: #edf4fa; color: #234d70; font-weight: 600', subset=status_columns)
    if cell_actions:
        for name in cell_actions:
            columns[name]=st.column_config.TextColumn(name,width=65,help='点击删除；不会打开会员详情')
        styled=styled.map(lambda value:'color: #a54444; font-weight: 500' if value=='删除' else '',subset=list(cell_actions))
    if not selectable:
        st.dataframe(styled, **options)
        return None
    event = st.dataframe(styled, on_select='rerun', selection_mode='single-cell' if activate_on_cell else 'single-row', **options)
    # Action cells are consumed before the caller can navigate the selected row.
    cells=event.get('selection',{}).get('cells',[])
    if cell_actions and cells and cells[0][1] in cell_actions:
        index,column=cells[0]
        if isinstance(index,int) and 0<=index<len(rows):cell_actions[column](rows[index])
        return None
    selected = selected_record(rows, event)
    if not auto_select and not (event.get('selection', {}).get('rows', []) or event.get('selection', {}).get('cells', [])):
        selected = None
    if export:
        # Export full business text, not the deliberately shortened grid cells.
        def csv_value(value):
            text = ux.business_text(str(value or ''))
            return "'"+text if text.lstrip().startswith(('=', '+', '-', '@')) else text
        full = pd.DataFrame([{k:csv_value(v) for k,v in record.items()} for record in records])
        st.download_button('导出筛选记录（完整内容）', full.to_csv(index=False).encode('utf-8-sig'), file_name='management-records.csv', mime='text/csv', key=grid_key+'-export')
    return selected


def work_filter(items, mode, now):
    def due(item):
        return ux.local_time(item.due_at) if item.due_at else None
    tests = {
        '全部': lambda i: True,
        '今天': lambda i: bool(due(i) and due(i).date() == now.date()),
        '逾期': lambda i: bool(due(i) and due(i) < now),
        '高优先级': lambda i: i.priority <= 1,
        '等待医生': lambda i: i.status == '等待医生',
        '等待会员': lambda i: i.status in {'等待成员', '等待会员'},
        '复查': lambda i: i.source_type == 'recheck' or i.status in {'待复查', '待随访'} or '复查' in i.title,
        '服务': lambda i: i.source_type == 'service_request',
    }
    return [i for i in ux.sorted_work(items, now) if tests[mode](i)]


WORK_FILTERS = ('全部', '今天', '逾期', '高优先级', '等待医生', '等待会员', '复查', '服务')


def task_records(tasks):
    sources = {'manual':'人工安排', 'doctor_review':'医生意见', 'doctor_handoff':'医生交接', 'report':'体检报告', 'management_log':'管理记录', 'consultation':'会诊意见', 'program':'年度方案', 'health_program_human_task':'年度方案', 'recheck_next':'复查计划', 'stage_result':'阶段复盘', 'outcome_continue':'阶段结果', 'outcome_adjustment':'阶段结果'}
    kinds = {'management_log':'日常跟进', 'doctor_handoff':'医疗协同', 'consultation':'会诊执行', 'recheck_next':'复查', 'stage_result':'阶段事项', 'report':'体检'}
    return [{'事项': t.title, '类型': kinds.get(t.source.split(':')[0], '执行任务'), '来源': sources.get(t.source.split(':')[0], '计划与管理记录'),
        '优先级': {'HIGH':'高','MEDIUM':'中','LOW':'低'}.get(t.priority, status_label(t.priority)),
        '状态': status_label(t.status), '负责人': t.assignee or {'member':'会员本人','health_manager':'健康管理师','doctor':'医生'}.get(t.responsible_role, '待分配'),
        '截止时间': ux.local_time(t.due_at) if t.due_at else None, '下一步': '查看结果' if t.status == 'COMPLETED' else t.instruction} for t in tasks]


def task_detail(task):
    st.markdown('### '+ux.business_text(task.title))
    c.summary_strip([('状态', status_label(task.status)), ('优先级', {'HIGH':'高','MEDIUM':'中','LOW':'低'}.get(task.priority, '常规')),
        ('负责人', ux.business_text(task.assignee or '待分配')), ('截止时间', ux.due_date(task.due_at))])
    with st.expander('为什么要处理 · 来源与完整说明', expanded=False):
        st.write(ux.business_text(task.instruction))
        st.caption('来源类别：'+task_records([task])[0]['来源'])
        st.caption('建立于 '+ux.when(task.created_at))
    c.summary_strip([('下一步', '已完成，查看结果与后续安排' if task.status == 'COMPLETED' else '已取消，无需继续执行' if task.status == 'CANCELLED' else preview(task.instruction, 80))])


def tasks(app, ctx):
    history=ctx.get('history_only',False)
    st.subheader('事项历史' if history else '管理事项表')
    rows = list(ctx['tasks'])
    scope = st.radio('事项状态', ['全部','已完成','已取消'] if history else ['未完成', '全部', '已完成'], horizontal=True, key='management-history-status' if history else 'management-task-status')
    rows = [t for t in rows if scope == '全部' or (t.status == 'COMPLETED' if scope == '已完成' else t.status == 'CANCELLED' if scope=='已取消' else t.status not in {'COMPLETED','CANCELLED'})]
    rows.sort(key=lambda t: (t.status in {'COMPLETED','CANCELLED'}, not (t.due_at and ux.local_time(t.due_at) < datetime.now(ux.LOCAL)), t.priority != 'HIGH', ux.local_time(t.due_at) or datetime.max.replace(tzinfo=ux.LOCAL)))
    selected = data_table(rows, task_records(rows), key='management-tasks', search=True, empty='此分类暂无管理事项。', auto_select=False)
    if selected is None:
        return
    with c.detail_drawer('所选事项', key='task-inspector',table_key='management-tasks'):
        task_detail(selected)
        task_action(app,selected)


def task_action(app,task):
    if task.status not in {'COMPLETED','CANCELLED'} and st.button('标记完成', key=f'complete-{task.id}', type='primary'):
        with app.SessionLocal() as session:
            try:
                app.TaskTransitionService().complete(session, task.id, actor=task.assignee or '健康管理师', outcome='已在健康运营工作台记录任务完成。')
                session.commit()
            except ValueError as error:
                session.rollback(); st.error(str(error))
            else:
                st.rerun()

def service_steps(request):
    current = {'REQUESTED':'申请','REVIEWING':'审核','APPROVED':'安排','SCHEDULED':'安排','IN_PROGRESS':'执行','IN_SERVICE':'执行','COMPLETED':'回写','CANCELLED':'已取消'}.get(request.status, '申请')
    c.workflow(['申请','审核','安排','执行','结果','回写'] + (['已取消'] if current == '已取消' else []), current)
    st.caption('阶段表示当前服务状态；“回写”表示查看已保存结果和下一步，不代表已自动完成后续任务。')


def outcome_table(outcomes, *, key, program_names=None):
    def delta(row):
        try:
            value = float(row.current_value)-float(row.baseline_value)
            from math import isfinite
            if not isfinite(value):
                return '暂不可数值比较'
            return ('↑ ' if value > 0 else '↓ ' if value < 0 else '→ ') + f'{abs(value):g} {"个百分点" if row.unit == "%" else row.unit or ""}'
        except (ValueError, TypeError):
            return '暂不可数值比较'
    records = [{'指标': ux.metric_name(o.metric), '记录基线': f'{o.baseline_value} {o.unit or ""}', '当前': f'{o.current_value} {o.unit or ""}', '变化': delta(o), '记录时间': ux.when(o.evaluation_date)} for o in outcomes]
    if program_names is not None:
        for record, outcome in zip(records, outcomes):
            record['所属计划'] = program_names.get(outcome.program_id, '历史健康管理')
    selected = data_table(outcomes, records, key=key, empty='暂无已记录的阶段指标结果。')
    if selected:
        with st.expander('结果依据与结论'):
            st.write(ux.business_text(getattr(selected, 'evidence', '') or getattr(selected, 'evidence_summary', '') or '原记录未附独立依据说明'))
            st.write(ux.business_text(getattr(selected, 'notes', '') or '暂无补充说明'))
            st.caption('记录结论：'+status_label(selected.result)+'；数值方向不自动代表医学改善或服务因果。')
