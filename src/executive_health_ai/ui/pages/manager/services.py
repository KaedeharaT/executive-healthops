"""Service execution; commands retain the original shared operations service."""
from datetime import date, datetime, time, timedelta
import streamlit as st
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import ServiceRequest, ServiceCatalogItem
from executive_health_ai.ui import components as c, experience as ux

def services(app):
    """A dedicated queue with its service detail in the same page inspector."""
    app._page_header("服务", "审核服务申请、安排执行并跟进服务结果。", eyebrow="服务工作台")
    members = app._patient_map()
    with SessionLocal() as session:
        from executive_health_ai.services.member_archive import active_ids
        requests = list(session.scalars(
            select(ServiceRequest).where(ServiceRequest.patient_id.in_(active_ids())).order_by(ServiceRequest.requested_at.desc())
        ))
        service_names = {item.id: item.name for item in session.scalars(select(ServiceCatalogItem))}
    app._status_strip(
        ("待审核", sum(item.status in {"REQUESTED", "REVIEWING"} for item in requests), "attention"),
        ("待安排", sum(item.status == "APPROVED" for item in requests), "action"),
        ("进行中", sum(item.status in {"SCHEDULED", "IN_PROGRESS", "IN_SERVICE"} for item in requests), "action"),
        ("等待反馈", sum(item.status == "COMPLETED" and not item.result_summary for item in requests), "neutral"),
    )
    filters = {"全部": set(), "待审核": {"REQUESTED", "REVIEWING"}, "待安排": {"APPROVED"}, "进行中": {"SCHEDULED", "IN_PROGRESS", "IN_SERVICE"}, "等待反馈": {"COMPLETED"}, "已完成": {"COMPLETED"}}
    selected_filter = st.radio("服务状态筛选", list(filters), horizontal=True, label_visibility="collapsed", key="service-operations-filter")
    visible = requests if not filters[selected_filter] else [item for item in requests if item.status in filters[selected_filter]]
    if selected_filter=='等待反馈': visible=[item for item in visible if not item.result_summary]
    query = st.text_input("搜索服务", placeholder="会员、服务或原因", key="service-search").strip().casefold()
    visible = [r for r in visible if not query or query in (app._member_display(members.get(r.patient_id))+service_names.get(r.service_item_id, "")+r.reason).casefold()]
    if not visible:
        app._empty_state("暂无待处理服务", "新的服务申请会按申请时间显示在这里。")
        return
    from executive_health_ai.ui.presentation import data_table, service_steps
    left, right = st.container(), st.container()
    with left:
        app._section_header("服务事项表", "选择记录，在右侧审核、安排或记录结果。")
        selected = data_table(visible, [{"服务": service_names.get(r.service_item_id, "会员服务"), "会员": app._member_display(members.get(r.patient_id)),
            "原因": r.reason, "服务方": r.service_provider or "待安排", "预约时间": ux.when(r.scheduled_at), "负责人": r.assigned_manager or "待分配",
            "状态": app._label(r.status, context="service_request"), "结果": r.result_summary or "待回写"} for r in visible], key="service-operations-grid", auto_select=False)
    if selected is None: return
    with c.detail_drawer("服务详情", key="service", table_key="service-operations-grid"):
        service_detail(app,selected,members.get(selected.patient_id))


def service_detail(app, selected, member):
    from executive_health_ai.ui.presentation import service_steps
    with SessionLocal() as session:
        catalog = session.get(ServiceCatalogItem, selected.service_item_id)
        name = catalog.name if catalog else '会员服务'
    st.markdown(f"**{name} · {app._member_display(member)}**")
    service_steps(selected)
    with st.expander("申请原因与完整说明"):
        st.write(selected.reason or "成员提交服务申请。")
    st.caption(f"当前状态：{app._label(selected.status, context='service_request')} · 负责人：{selected.assigned_manager or '待分配'}")
    st.caption(f"申请时间：{app._fmt_dt(selected.requested_at)} · 预计处理：{app._fmt_dt(selected.sla_due_at) if selected.sla_due_at else '待确认'}")
    st.write("下一步：" + (selected.next_action or "健康管理师确认下一步"))
    if selected.status in {"REQUESTED", "REVIEWING"}:
        if app.primary_action("审核申请", key=f"service-operations-approve-{selected.id}", width="content"):
            with SessionLocal() as session:
                app.MemberServiceOperations().approve(session, selected.id, "健康管理师"); session.commit()
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
        st.button('进入会员管理',key=f'service-management-{selected.id}',type='primary',on_click=app._open_member_management,args=(selected.patient_id,))
