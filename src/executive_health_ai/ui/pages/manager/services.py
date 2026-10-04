"""Service execution; commands retain the original shared operations service."""
from datetime import date, datetime, time, timedelta
import streamlit as st
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import ServiceRequest, ServiceCatalogItem, Task
from executive_health_ai.models.management_workflow import ManagementLog
from executive_health_ai.services.service_operations_projection import SERVICE_STAGES, service_stage, service_context, service_next
from executive_health_ai.ui import components as c, experience as ux

def services(app):
    """A dedicated queue with its service detail in the same page inspector."""
    app._page_header("服务管理", "查看服务到了哪一步，完成预约、执行和结果确认。", eyebrow="健康服务执行")
    members = app._patient_map()
    with SessionLocal() as session:
        from executive_health_ai.services.member_archive import active_ids
        requests = list(session.scalars(
            select(ServiceRequest).where(ServiceRequest.patient_id.in_(active_ids())).order_by(ServiceRequest.requested_at.desc())
        ))
        service_names = {item.id: item.name for item in session.scalars(select(ServiceCatalogItem))}
        tasks = list(session.scalars(select(Task)))
        logs = list(session.scalars(select(ManagementLog)))
        stages = {r.id: service_stage(r,tasks,logs) for r in requests}
        contexts = {r.id: service_context(session,r) for r in requests}
    focused=st.session_state.get('v7-service-detail')
    if focused:
        selected=next((r for r in requests if str(r.id)==focused),None)
        if st.button('← 返回服务管理'):
            st.session_state.pop('v7-service-detail',None)
            st.session_state['service-operations-grid-epoch']=st.session_state.get('service-operations-grid-epoch',0)+1
            st.rerun()
        if selected:service_detail(app,selected,members.get(selected.patient_id))
        else:st.info('此服务已更新，请返回服务管理。')
        return
    filters = ['全部', *SERVICE_STAGES, '已取消']
    active=[r for r in requests if r.status not in {'COMPLETED','CANCELLED','DECLINED'}]
    c.priority_strip('YELLOW' if active else 'GREEN',f'{len(active)} 项服务需要跟进',next_action='选择一项服务，查看当前需要完成的安排。')
    if st.session_state.get('service-operations-filter') not in filters:
        st.session_state.pop('service-operations-filter',None)
    selected_filter = st.radio("服务状态筛选", list(filters), horizontal=True, label_visibility="collapsed", key="service-operations-filter",format_func=lambda label:label+" · "+str(len(requests) if label=="全部" else sum(v==label for v in stages.values())))
    visible = requests if selected_filter == '全部' else [item for item in requests if stages[item.id] == selected_filter]
    query = st.text_input("搜索服务", placeholder="会员、服务或原因", key="service-search").strip().casefold()
    visible = [r for r in visible if not query or query in (app._member_display(members.get(r.patient_id))+service_names.get(r.service_item_id, "")+r.reason).casefold()]
    if not visible:
        app._empty_state("暂无待处理服务", "新的服务申请会按申请时间显示在这里。")
        return
    from executive_health_ai.ui.presentation import data_table, service_steps
    left, right = st.container(), st.container()
    with left:
        app._section_header("服务事项表", "选择一行，审核、预约、执行或确认结果；回访进入同一会员的管理工作区。")
        selected = data_table(visible, [{"服务": service_names.get(r.service_item_id, "会员服务"), "会员": app._member_display(members.get(r.patient_id)),
            "来源方案": contexts[r.id]['plan'], "责任健管": contexts[r.id]['owner'], "计划时间": ux.when(r.scheduled_at or r.sla_due_at),
            "当前状态": stages[r.id], "下一步": service_next(r,tasks,logs)} for r in visible], key="service-operations-grid", auto_select=False)
    if selected is None: return
    st.session_state['v7-service-detail']=str(selected.id)
    st.rerun()


def service_detail(app, selected, member):
    from executive_health_ai.ui.presentation import service_steps
    with SessionLocal() as session:
        catalog = session.get(ServiceCatalogItem, selected.service_item_id)
        name = catalog.name if catalog else '会员服务'
        context = service_context(session,selected)
        tasks = list(session.scalars(select(Task).where(Task.patient_id == selected.patient_id)))
        logs = list(session.scalars(select(ManagementLog).where(ManagementLog.patient_id == selected.patient_id)))
    st.markdown(f"**{name} · {app._member_display(member)}**")
    c.priority_strip('GREEN' if selected.status in {'COMPLETED','CANCELLED','DECLINED'} else 'YELLOW',
                     service_stage(selected,tasks,logs),next_action=service_next(selected,tasks,logs))
    with st.expander('服务进度与安排依据'):
        service_steps(selected)
    st.caption(f"来源方案：{context['plan']} · 阶段：{context['phase']}")
    st.caption(f"预约：{ux.when(selected.scheduled_at)} · 服务方：{selected.service_provider or '待安排'} · 实际完成：{ux.when(selected.completed_at)}")
    with st.expander("申请原因与完整说明"):
        st.write(selected.reason or "成员提交服务申请。")
    st.caption(f"当前状态：{app._label(selected.status, context='service_request')} · 负责人：{selected.assigned_manager or '待分配'}")
    st.caption(f"申请时间：{app._fmt_dt(selected.requested_at)} · 预计处理：{app._fmt_dt(selected.sla_due_at) if selected.sla_due_at else '待确认'}")
    st.write("下一步：" + service_next(selected,tasks,logs))
    if selected.status in {"REQUESTED", "REVIEWING"}:
        if app.primary_action("审核申请", key=f"service-operations-approve-{selected.id}", width="content"):
            with SessionLocal() as session:
                app.MemberServiceOperations().approve(session, selected.id, context['owner'] if context['owner'] != '待分配' else "健康管理师"); session.commit()
            st.rerun()
    elif selected.status == "APPROVED":
        with st.form(f"service-operations-schedule-{selected.id}"):
            schedule_day = st.date_input("预约日期", value=date.today() + timedelta(days=3))
            schedule_time = st.time_input("预约时间", value=time(10, 0))
            provider = st.text_input("服务执行方（可选）")
            if st.form_submit_button("确认服务安排"):
                with SessionLocal() as session:
                    app.MemberServiceOperations().schedule(
                        session, selected.id,
                        datetime.combine(schedule_day, schedule_time, tzinfo=app.TOKYO_TIMEZONE),
                        "健康管理师", provider,
                    )
                    session.commit()
                st.rerun()
    elif selected.status == "SCHEDULED":
        if app.primary_action("确认开始服务", key=f"service-operations-start-{selected.id}", width="content"):
            with SessionLocal() as session:
                app.MemberServiceOperations().start(session, selected.id, selected.assigned_manager or "健康管理师")
                session.commit()
            st.rerun()
    elif selected.status in {"IN_PROGRESS", "IN_SERVICE"}:
        with st.form(f"service-operations-complete-{selected.id}"):
            result = st.text_area("服务结果")
            evidence = st.text_input("完成依据", placeholder="例如：服务方完成确认 / 成员反馈")
            next_action = st.text_input("下一步", value="健康管理师复核结果并确认后续安排")
            if st.form_submit_button("记录服务完成"):
                if not result.strip() or not evidence.strip() or not next_action.strip():
                    st.error("请填写服务结果、完成依据和下一步。")
                else:
                    with SessionLocal() as session:
                        app.MemberServiceOperations().complete(
                            session, selected.id, result, selected.assigned_manager or "健康管理师",
                            completion_evidence=evidence, next_action=next_action,
                        )
                        session.commit()
                    st.rerun()
    else:
        st.write(selected.result_summary or "服务已完成，等待补充结果。")
        st.caption("完成依据：" + (selected.completion_evidence or "人工确认的服务完成记录"))
        st.button('进入会员管理',key=f'service-management-{selected.id}',type='primary',on_click=open_service_member,args=(app,selected))


def open_service_member(app, request):
    if st.session_state.get('ops-navigation') == '服务运营':
        st.session_state['member-return-origin'] = '服务管理'
    if request.program_id:
        st.session_state[f'annual-program-{request.patient_id}'] = str(request.program_id)
    st.session_state[f'action-focus-{request.patient_id}'] = 'NEXT'
    app._open_member_management(request.patient_id)
