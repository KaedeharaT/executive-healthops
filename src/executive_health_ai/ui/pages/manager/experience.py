from datetime import date, datetime, time, timedelta

import streamlit as st
from sqlalchemy import select

from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentApprovalRequest, AgentGoal, AgentPlanStep, HealthProgram, OutcomeEvaluation, ServiceRequest, ServiceCatalogItem
from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
from executive_health_ai.services.operational_worklist import OperationalWorklistService
from executive_health_ai.services.longitudinal import HealthAssessmentService
from executive_health_ai.services import care_commands
from executive_health_ai.services.chronic_care import apply_outcome_decision
from executive_health_ai.ui import experience as ux


def approvals(app, patient_id, role="HEALTH_MANAGER"):
    with SessionLocal() as session:
        rows = list(session.execute(select(AgentApprovalRequest, AgentGoal, AgentPlanStep).join(AgentGoal, AgentApprovalRequest.goal_id == AgentGoal.id).join(AgentPlanStep, AgentApprovalRequest.plan_step_id == AgentPlanStep.id).where(AgentGoal.member_id == patient_id, AgentApprovalRequest.status == "PENDING", AgentApprovalRequest.required_role == role)))
    for approval, goal, step in rows:
        with st.expander("需要您确认 · " + ux.business_text(goal.title), expanded=True):
            ux.next_action(goal.next_action or "确认后继续已有管理流程", goal.owner)
            st.caption("确认后将执行当前等待的管理步骤；医学结论仍须医生人工复核。")
            decision = st.radio("处理决定", ["同意继续", "退回人工处理"], horizontal=True, key=f"approval-choice-{approval.id}")
            note = st.text_input("确认说明", key=f"approval-note-{approval.id}")
            if st.button("确认处理", key=f"approval-submit-{approval.id}"):
                try:
                    with SessionLocal() as session:
                        HealthOpsAgentSupervisor().decide_approval(session, approval.id, decision="APPROVED" if decision == "同意继续" else "REJECTED", actor="健康管理师" if role == "HEALTH_MANAGER" else "医生", actor_role=role, comment=note)
                        session.commit()
                    st.rerun()
                except (ValueError, PermissionError):
                    st.error("此确认已更新或不属于当前角色，请刷新后重试。")


def today(app):
    ux.inject_design("manager")
    ux.page_header("今日待处理", "先处理逾期和高优先级事项，再完成今天的安排。", "健康管理师工作台")
    now = datetime.now(ux.LOCAL)
    patients = app._patient_map()
    with SessionLocal() as session:
        items = ux.sorted_work(OperationalWorklistService().list_items(session, now), now)
        doctor_count = len(ux.pending_doctor_work(session))
    ux.metric_row([("今天待处理", sum(i.status not in {"等待成员", "等待医生"} for i in items)), ("即将逾期", sum(bool(i.due_at and now <= ux.local_time(i.due_at) < now + timedelta(days=1)) for i in items)), ("等待医生", doctor_count), ("等待成员", sum(i.status == "等待成员" for i in items)), ("高优先级", sum(i.priority <= 1 for i in items))])
    categories = {"全部事项": None, "体检": "report_review", "风险": "risk_event", "医生": "doctor_review", "计划 / 复查": "task", "服务": "service_request"}
    selected = st.radio("今日事项筛选", list(categories), horizontal=True, key="manager-today-filter", label_visibility="collapsed")
    visible = [i for i in items if selected == "全部事项" or i.source_type == categories[selected] or selected == "医生" and i.status == "等待医生"]
    st.subheader("优先处理")
    if not visible:
        ux.empty_state("当前筛选下暂无事项", "切换类型查看其他待办。")
    for item in visible[:12]:
        member = patients.get(item.member_id)
        if not member:
            continue
        left, middle, right = st.columns([3.6, 2, .8])
        with left:
            ux.work_item(f"{app._member_display(member)} · {item.source_label}", item.reason, item.title)
        with middle:
            st.write(ux.business_text(item.next_action))
            st.caption(f"{item.status} · {ux.owner(item.owner)} · {ux.due_date(item.due_at)}")
        callback, args = app._open_member, (member.id,)
        if item.source_type == "report_review" and item.document_id:
            callback, args = app._open_report_review_from_worklist, (member.id, item.document_id)
        elif item.route_target == "member_management":
            callback = app._open_member_management
        elif item.route_target == "member_service":
            callback = app._open_member_service
        right.button("处理", key=f"today-{item.source_type}-{item.source_id}", on_click=callback, args=args)
    if len(visible) > 12:
        with st.expander(f"其他 {len(visible)-12} 项"):
            for item in visible[12:]:
                ux.work_item(app._member_display(patients.get(item.member_id)), item.next_action, ux.due_date(item.due_at))
                st.button("处理", key=f"today-more-{item.source_id}", on_click=app._open_member, args=(item.member_id,))
    with SessionLocal() as session:
        goals = list(session.scalars(select(AgentGoal).where(AgentGoal.status.in_(("ACTIVE", "WAITING", "BLOCKED"))).order_by(AgentGoal.started_at.desc()).limit(10)))
    if goals:
        with st.expander("自动跟进状态"):
            for goal in goals:
                ux.work_item(goal.title, goal.current_stage, goal.next_action)
                st.button("处理确认", key=f"ux-goal-open-{goal.id}", on_click=app._open_member_management, args=(goal.member_id,))


def management(app, patient):
    ctx = app._member_management_context(patient.id)
    programs = ctx["programs"]
    if message := st.session_state.pop("ux-manager-flash", None):
        st.success(message)
    names = {str(p.id): ux.business_text(p.title) for p in programs}
    key = f"ux-program-{patient.id}"
    if pending := st.session_state.pop(f"ux-program-pending-{patient.id}", None):
        st.session_state[key] = pending
    selected = st.selectbox("当前管理计划", list(names), format_func=names.get, key=key) if programs else None
    program = next((p for p in programs if str(p.id) == selected), None)
    if program:
        ux.next_action(program.main_goal, program.owner)
        st.caption(f"{app._label(program.status)} · {ux.when(program.start_date)} — {ux.when(program.end_date)}")
    mode = st.radio("管理操作", ["工作进展", "建立 / 调整计划", "安排随访", "记录阶段结果"], horizontal=True, key=f"ux-management-{patient.id}")
    if mode == "建立 / 调整计划":
        create = st.checkbox("建立新计划", value=program is None, key=f"ux-new-program-{patient.id}")
        with st.form(f"ux-plan-form-{patient.id}"):
            title = st.text_input("计划名称", value="阶段健康管理计划" if create else program.title)
            goal = st.text_area("本阶段目标", value="" if create else program.main_goal)
            owner = st.text_input("负责人", value="健康管理师" if create else program.owner)
            kind = st.selectbox("计划周期", ["NINETY_DAY", "ANNUAL", "STABILIZATION"], format_func=app.display_program_type, disabled=not create)
            start = st.date_input("开始日期", value=date.today() if create else program.start_date, disabled=not create)
            end = st.date_input("结束日期", value=date.today()+timedelta(days=89) if create else program.end_date, disabled=not create)
            reason = st.text_area("建立依据 / 调整原因")
            tier = st.selectbox("首次人工评估层级（已有评估时沿用）", ["NEEDS_MEDICAL_EVALUATION", "LOW", "MODERATE", "HIGH"], format_func=lambda x: {"NEEDS_MEDICAL_EVALUATION": "待医学评估", "LOW": "低", "MODERATE": "中", "HIGH": "高"}[x])
            submitted = st.form_submit_button("保存健康计划", type="primary")
        if submitted:
            try:
                with SessionLocal() as session:
                    saved = care_commands.save_program(session, patient.id, title=title, goal=goal, owner=owner, start=start, end=end, program_id=None if create else program.id, program_type=kind, reason=reason, assessment_risk=tier)
                    session.commit()
                st.session_state[f"ux-program-pending-{patient.id}"] = str(saved.id)
                st.session_state["ux-manager-flash"] = "健康计划已保存，成员可以查看并反馈。"
                st.rerun()
            except ValueError as error:
                st.error(str(error))
    elif mode == "安排随访":
        if not program:
            st.info("先建立当前计划，再安排有归属的随访任务。")
            return
        with st.form(f"ux-followup-{patient.id}"):
            title = st.text_input("随访 / 行动名称", value="阶段健康随访")
            instruction = st.text_area("需要完成什么")
            owner = st.text_input("执行负责人", value=program.owner)
            role = st.radio("由谁执行", ["健康管理师", "成员"], horizontal=True)
            due = st.date_input("截止日期", value=date.today()+timedelta(days=7), min_value=date.today())
            submit = st.form_submit_button("安排随访", type="primary")
        if submit:
            try:
                with SessionLocal() as session:
                    care_commands.schedule_followup(session, session.get(HealthProgram, program.id), title=title, instruction=instruction, owner=owner, role="member" if role == "成员" else "health_manager", due_at=datetime.combine(due, time(17), ux.LOCAL))
                    session.commit()
                st.success("随访已安排，已进入成员计划与健管工作队列。")
            except ValueError as error:
                st.error(str(error))
    elif mode == "记录阶段结果":
        if not program:
            st.info("请先建立当前计划。")
            return
        st.caption("记录观察变化；不将前后差异解释为干预造成的结果。")
        with st.form(f"ux-outcome-{patient.id}"):
            metric = st.selectbox("观察指标", ["systolic_bp", "diastolic_bp", "weight", "ldl_c", "hba1c", "steps", "sleep_duration"], format_func=ux.metric_name)
            baseline = st.text_input("起点数值")
            current = st.text_input("本次数值")
            unit = st.text_input("单位")
            evidence = st.text_area("结果依据", placeholder="记录来源、采集日期及核对情况")
            evaluator = st.text_input("记录人", value="健康管理师")
            result = st.selectbox("观察结果", ["IMPROVED", "STABLE", "WORSENED", "INSUFFICIENT_DATA", "NEEDS_MEDICAL_REVIEW"], format_func=app._label)
            decision = st.selectbox("下一步管理", ["CONTINUE", "ADJUST", "STABILIZE", "DOCTOR_REVIEW"], format_func=lambda x: {"CONTINUE": "继续", "ADJUST": "调整", "STABILIZE": "稳定期", "DOCTOR_REVIEW": "医生复核"}[x])
            note = st.text_area("下一步说明")
            submit = st.form_submit_button("记录阶段结果并安排下一步", type="primary")
        if submit:
            try:
                with SessionLocal() as session:
                    outcome = care_commands.record_outcome(session, session.get(HealthProgram, program.id), metric=metric, baseline_value=baseline, current_value=current, unit=unit, direction="OBSERVED", evaluator=evaluator, evidence=evidence, result=result, notes=note)
                    apply_outcome_decision(session, outcome, decision, evaluator, note)
                    session.commit()
                st.success("阶段结果已回写到计划与历程，后续行动已建立。")
            except ValueError as error:
                st.error(str(error))
    else:
        approvals(app, patient.id)
        app.render_tasks(ctx)
        with st.expander("计划详情与已记录阶段结果"):
            app.render_programs(patient, {**ctx, "programs": [program] if program else []})
        with st.expander("自动跟进与健康管理记录"):
            app._render_member_automation_status(patient.id, audience="manager")
            app.render_member_management_signals(patient, ctx)


def member_detail(app, patient):
    ux.inject_design("manager")
    if st.button("← 返回成员列表", key="back-to-dashboard"):
        st.session_state.pop("focused_member_id", None)
        st.rerun()
    ctx = app._member_summary_context(patient.id)
    program = app._active_program(ctx)
    with SessionLocal() as session:
        pending = ux.pending_doctor_work(session, patient.id)
        baseline = HealthAssessmentService().latest_baseline(session, patient.id)
        rows = ux.observations(session, patient.id)
    tasks = [t for t in ctx["tasks"] if t.status not in {"COMPLETED", "CANCELLED"}]
    ux.member_summary(patient, program, tasks[0].title if tasks else "核对健康资料，确认下一阶段安排")
    st.caption(f"医生待复核：{len(pending)} · 资料更新：{ux.when(rows[-1].observed_at) if rows else '暂无健康数据'}")
    section = st.radio("成员页面", ["概览", "健康", "管理", "医疗", "历程"], horizontal=True, label_visibility="collapsed", key=f"member-section-{patient.id}")
    if section == "概览":
        problems = [p for p in ctx["problems"] if p.status != "CLOSED"]
        left, right = st.columns([1.6, 1], gap="large")
        with left:
            ux.baseline_summary(baseline, rows, compact=True)
        with right:
            st.subheader("当前管理")
            st.write(ux.business_text(program.main_goal) if program else "尚未建立计划")
            st.caption("主要关注：" + ("；".join(ux.business_text(p.title) for p in problems[:3]) or "暂无已确认关注事项"))
            with SessionLocal() as session:
                recent = session.execute(select(ServiceRequest, ServiceCatalogItem).join(ServiceCatalogItem, ServiceRequest.service_item_id == ServiceCatalogItem.id).where(ServiceRequest.patient_id == patient.id).order_by(ServiceRequest.requested_at.desc()).limit(1)).first()
            st.markdown("**近期服务**")
            if recent:
                request, item = recent
                st.write(item.name + " · " + app._label(request.status))
                st.caption(ux.owner(request.assigned_manager))
            else:
                st.caption("暂无服务安排；可从服务工作台安排。")
        from executive_health_ai.ui.pages.health_visualization import render_previews
        st.markdown("**最近健康趋势**")
        render_previews(patient.id, key=f"manager-overview-trend-{patient.id}", maximum=1,
            open_trend=lambda: app.request_navigation(surface="运营后台", ops_page="成员", member_id=patient.id, member_section="健康", archive_view="健康数据"))
        cols = st.columns(3)
        for col, label, target in zip(cols, ["查看完整健康历程", "建立 / 调整计划", "医生协同"], ["历程", "管理", "医疗"]):
            col.button(label, key=f"ux-overview-{target}-{patient.id}", on_click=app.request_navigation, kwargs={"surface": "运营后台", "ops_page": "成员", "member_id": patient.id, "member_section": target})
        with st.expander("处理开放中的健康关注事项"):
            app._render_current_risk_actions(patient)
        with st.expander("近期服务"):
            app.render_member_service_management(patient)
    elif section == "健康":
        app.render_member_archive(patient)
    elif section == "管理":
        management(app, patient)
    elif section == "医疗":
        app.render_member_medical_workspace(patient, app._member_medical_context(patient.id))
    else:
        from executive_health_ai.ui.pages.member.experience import timeline
        timeline(app, patient, client_view=False)
