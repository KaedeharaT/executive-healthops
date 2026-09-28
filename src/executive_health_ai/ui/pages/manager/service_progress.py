"""Service and specialty views reuse Member360 and the existing action loop."""
import streamlit as st
from executive_health_ai.database import SessionLocal
from executive_health_ai.services.service_operations_projection import special_programs, service_stage, service_next
from executive_health_ai.ui import experience as ux
from executive_health_ai.ui.presentation import data_table


def member_progress(view, *, compact=False):
    from executive_health_ai.models import ServiceCatalogItem
    from sqlalchemy import select
    with SessionLocal() as session:
        names = {x.id:x.name for x in session.scalars(select(ServiceCatalogItem))}
    st.subheader('健康服务执行')
    rows = list(view.services)
    data_table(rows, [{'服务':names.get(r.service_item_id,'会员服务'),
        '状态':service_stage(r,view.tasks,view.logs), '负责人':r.assigned_manager or view.owner,
        '计划时间':ux.when(r.scheduled_at or r.sla_due_at), '结果':r.result_summary or '等待执行与回写',
        '下一步':service_next(r,view.tasks,view.logs)} for r in rows],
        key=f'member-service-progress-{view.program.id if view.program else "none"}',selectable=False,
        empty='暂无已申请服务；可在管理工作区按阶段方案安排服务。')
    if not compact:
        st.caption(f'完成任务 {sum(t.status == "COMPLETED" for t in view.tasks)} · '
            f'开放任务 {sum(t.status not in {"COMPLETED","CANCELLED"} for t in view.tasks)} · '
            f'开放复查 {sum(r.status != "CLOSED" for r in view.rechecks)} · '
            f'已预约服务 {sum(r.status == "SCHEDULED" for r in rows)}')
        st.caption('任务与服务完成表示执行进度，不代表健康改善或医学有效。预约、回访与结果通过上方具体事项继续处理。')


def open_special(app, row):
    program = row['program']
    st.session_state['member-return-origin'] = '专项管理'
    st.session_state[f'annual-program-{program.patient_id}'] = str(program.id)
    st.session_state[f'workflow-mode-{program.patient_id}'] = '阶段评估'
    app._open_member_management(program.patient_id)


def workspace(app):
    app._page_header('专项管理','查看已记录的专项指标、目标与执行进度；选择记录进入该会员的同一管理工作区。')
    with SessionLocal() as session:
        rows = special_programs(session)
    members = app._patient_map()
    query = st.text_input('搜索专项',placeholder='会员、方案或指标').strip().casefold()
    rows = [r for r in rows if not query or query in (app._member_display(members.get(r['program'].patient_id))+
        r['program'].title+ux.metric_name(r['outcome'].metric)).casefold()]
    records=[]
    for row in rows:
        p,o,phase,n = row['program'],row['outcome'],row['phase'],row['next']
        records.append({'会员':app._member_display(members.get(p.patient_id)), '专项':ux.metric_name(o.metric),
            '方案':p.title, '起始状态':f'{o.baseline_value} {o.unit}', '当前值':f'{o.current_value} {o.unit}',
            '目标':f'{o.target_value} {o.unit}' if o.target_value else '尚未记录目标',
            '记录日期':str(o.evaluation_date), '阶段':phase.title if phase else '待确认阶段',
            '执行进度':f'{row["completed"]} / {row["total"]} 项任务', '责任健管':p.owner or '待分配',
            '下一步':n.title if n else '阶段复盘 / 核对下一安排', '下一日期':ux.when(n.due_at) if n else '待确认'})
    chosen=data_table(rows,records,key='special-programs',auto_select=False,
        empty='尚无已记录专项指标结果。请在会员管理的阶段评估中记录有来源的起点、当前值和目标。')
    st.caption('数值来自已有阶段结果，可能不是最新设备测量；请核对记录日期与来源。指标变化不代表服务造成的效果。')
    if chosen:
        with st.expander('本条指标依据',expanded=True):st.write(chosen['outcome'].evidence)
        st.button('进入该会员专项管理',type='primary',on_click=open_special,args=(app,chosen))
