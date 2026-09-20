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
from executive_health_ai.ui import components as c
from executive_health_ai.services.product_projection import ProductProjectionService
from executive_health_ai.ui.status_dictionary import status_label


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
    c.page_shell("manager", "今日工作", "先处理逾期和高优先级事项，再完成今天的安排。", "健康管理师工作台")
    now = datetime.now(ux.LOCAL)
    patients = app._patient_map()
    with SessionLocal() as session:
        work = ProductProjectionService().manager(session, now)
        items = ux.sorted_work(work.items, now)
        doctor_count = len(work.pending_doctor)
    c.summary_strip(work.counts(now))
    categories = {"全部事项": None, "入组初评":"intake_review", "复查":"recheck", "阶段复盘":"stage_review", "正式会诊":"consultation", "体检": "report_review", "风险": "risk_event", "医生": "doctor_review", "计划 / 复查": "task", "服务": "service_request", "自动跟进": "automation_approval"}
    selected = st.selectbox("今日事项筛选", list(categories), key="manager-today-filter")
    visible = [i for i in items if selected == "全部事项" or i.source_type == categories[selected] or selected == "医生" and i.status == "等待医生"]
    search = st.text_input("查找待办", placeholder="输入成员、事项或原因", key="v2-work-search")
    visible = [i for i in visible if not search or search.lower() in (app._member_display(patients.get(i.member_id)) + i.title + i.reason + i.next_action).lower()]
    st.caption("今天待处理按本地日期统计；未设截止日期的事项仍保留在队列。即将逾期：" + str(sum(bool(i.due_at and now <= ux.local_time(i.due_at) < now + timedelta(days=1)) for i in items)))
    st.subheader("优先处理")
    if not visible:
        ux.empty_state("当前筛选下暂无事项", "切换类型或调整搜索查看其他待办。")
    else:
        options = {f"{i.source_type}-{i.source_id}": i for i in visible}
        selected_key = "v2-work-selected"
        if st.session_state.get(selected_key) not in options:
            st.session_state[selected_key] = next(iter(options))
        queue, inspector = st.columns([1, 1.3], gap="large")
        with queue:
            with st.container(key="v2-list-today", border=False):
                for item in visible[:6]:
                    member = patients.get(item.member_id)
                    item_key = f"{item.source_type}-{item.source_id}"
                    state = status_label(item.status, context="service_request") if item.source_type == "service_request" else status_label(item.status)
                    if c.work_item_row(app._member_display(member), item.title, item.source_label + (" · 高优先级" if item.priority <= 1 else ""), state,
                                       ux.due_date(item.due_at), key=f"today-select-{item_key}", selected=item_key == st.session_state[selected_key]):
                        st.session_state[selected_key] = item_key
                        st.rerun()
                if len(visible) > 6:
                    with st.expander(f"其他 {len(visible)-6} 项"):
                        for item in visible[6:]:
                            item_key = f"{item.source_type}-{item.source_id}"
                            if st.button(f"{app._member_display(patients.get(item.member_id))} · {ux.business_text(item.title)}", key=f"today-select-{item_key}", width="stretch"):
                                st.session_state[selected_key] = item_key
                                st.rerun()
        item = options[st.session_state[selected_key]]
        member = patients.get(item.member_id)
        with inspector:
            with c.detail_panel(app._member_display(member) + " · " + item.source_label, key="today-detail"):
                ux.status_badge(status_label(item.status, context="service_request") if item.source_type == "service_request" else status_label(item.status) if item.status in {"逾期", "今日跟进"} else item.status)
                st.markdown("### " + ux.business_text(item.title))
                c.summary_strip([("负责人", ux.business_text(item.owner)), ("截止", ux.due_date(item.due_at)), ("优先级", "高" if item.priority <= 1 else "常规")])
                st.markdown("**为什么需要处理**")
                st.write(ux.business_text(item.reason))
                ux.next_action(item.next_action, item.owner)
                callback, args = app._open_member, (item.member_id,)
                if item.source_type == "report_review" and item.document_id:
                    callback, args = app._open_report_review_from_worklist, (item.member_id, item.document_id)
                elif item.route_target == "member_management":
                    callback = app._open_member_management
                elif item.route_target == "member_service":
                    callback = app._open_member_service
                elif item.route_target == "doctor_review":
                    callback, args = app.request_navigation, ()
                action_label = {"report_review":"确认体检资料", "task":"处理当前任务", "service_request":"跟进服务", "risk_event":"处理关注事项", "automation_approval":"确认后续安排"}.get(item.source_type, "查看成员详情")
                if item.route_target == "doctor_review":
                    st.button("查看医生协同", key=f"today-{item.source_type}-{item.source_id}", on_click=callback,
                        kwargs={"surface": "运营后台", "ops_page": "成员", "member_id": item.member_id, "member_section": "医疗"}, type="primary")
                else:
                    st.button(action_label, key=f"today-{item.source_type}-{item.source_id}", on_click=callback, args=args, type="primary", icon=":material/arrow_forward:")
                if member:
                    with st.expander("成员健康背景与依据入口"):
                        with SessionLocal() as session:
                            context = ProductProjectionService().member(session, member.id)
                            evidence = app._risk_evidence_payload(session, member.id, item.source_id) if item.source_type == "risk_event" else None
                        ux.baseline_summary(context.baseline, context.observations, compact=True)
                        if evidence:
                            ux.evidence_summary(evidence)
                            app._render_evidence_action(evidence, key_scope=f"today-evidence-{item.source_id}")
                        else:
                            st.caption("原始依据随事项进入成员健康、体检或医疗详情；未展示原文不代表依据完整。")
                        st.markdown("**之前已完成的行动**")
                        completed = [t for t in context.tasks if t.status == "COMPLETED"]
                        for task in completed[-3:]:
                            st.caption(ux.business_text(task.title))
                        if not completed:
                            st.caption("暂无已完成行动记录。")
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
    from executive_health_ai.services.product_projection import current_program
    current = current_program(programs)
    programs = sorted(programs, key=lambda p: p.id != current.id) if current else programs
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
    from executive_health_ai.ui.pages.manager import workflow
    ux.inject_design("manager")
    if st.button("← 返回成员列表", key="back-to-dashboard"):
        st.session_state.pop("focused_member_id", None)
        st.rerun()
    ctx = app._member_summary_context(patient.id)
    with SessionLocal() as session:
        view = ProductProjectionService().member(session, patient.id, health=True)
    program, pending, baseline, rows = view.program, view.pending_doctor, view.baseline, view.observations
    tasks = view.active_tasks
    ux.page_header(patient.display_name, "", "成员360")
    c.summary_strip([("当前周期", view.cycle), ("当前阶段", view.phase_title or ("资料收集中" if program and program.current_phase=='ONBOARDING' else app.display_program_phase(program.current_phase) if program else "待建立计划")),
                     ("负责人", ux.business_text(view.owner)), ("资料更新", ux.when(max(r.observed_at for r in rows)) if rows else "暂无健康数据")])
    focus = "；".join(ux.business_text(p.title) for p in ctx["problems"] if p.status != "CLOSED") or "暂无已确认关注事项"
    st.caption("主要关注：" + (focus[:70] + "…" if len(focus) > 70 else focus) + f" · 医生待复核：{len(pending)}")
    st.markdown("**下一步：** " + ux.business_text(tasks[0].title if tasks else "核对健康资料，确认下一阶段安排"))
    management_view=workflow.view_for(patient.id)
    workflow.onboarding(management_view)
    if management_view.intake:
        st.caption("会员自己关注："+ux.business_text(management_view.intake.member_concern or "待填写")+" · 专业管理重点："+ux.business_text(management_view.intake.professional_focus or "待初评"))
    section = st.radio("成员页面", ["概览", "健康", "管理", "医疗", "历程"], horizontal=True, label_visibility="collapsed", key=f"member-section-{patient.id}",format_func=lambda x:"健康档案" if x=="健康" else x)
    if section == "概览":
        if management_view.intake:
            workflow.phases(management_view)
            with st.expander("最近管理记录",expanded=True):
                workflow.log_rows(management_view.logs[:2])
                st.button("新增管理记录",key=f"overview-new-log-{patient.id}",on_click=workflow.open_log,args=(app,patient))
        problems = [p for p in ctx["problems"] if p.status != "CLOSED"]
        left, right = st.columns([1.7, 1], gap="large")
        with left:
            from executive_health_ai.ui.pages.health_visualization import render_previews
            with c.section("最近健康趋势", key="360-trend"):
                render_previews(patient.id, key=f"manager-overview-trend-{patient.id}", maximum=1, series=view.health.series,
                    open_trend=lambda: app.request_navigation(surface="运营后台", ops_page="成员", member_id=patient.id, member_section="健康", archive_view="健康数据"))
        with right:
            with c.section("当前管理", key="360-status"):
                st.write(ux.business_text(program.main_goal) if program else "尚未建立计划")
                st.caption("开放事项：" + str(len(tasks)) + " · 医生待复核：" + str(len(pending)))
                last_review=max((r for r in management_view.doctor_reviews if r.status=='CONFIRMED'),key=lambda r:r.reviewed_at or r.created_at,default=None)
                if last_review:
                    st.markdown("**最新医生意见**")
                    st.write(ux.business_text(last_review.opinion[:120]))
                    st.caption("执行交接："+ux.owner(management_view.owner)+" · 完整意见见医疗")
                with SessionLocal() as session:
                    recent = session.execute(select(ServiceRequest, ServiceCatalogItem).join(ServiceCatalogItem, ServiceRequest.service_item_id == ServiceCatalogItem.id).where(ServiceRequest.patient_id == patient.id).order_by(ServiceRequest.requested_at.desc()).limit(1)).first()
                st.markdown("**近期服务**")
                if recent:
                    request, item = recent
                    st.write(item.name + " · " + app._label(request.status, context="service_request"))
                    st.caption(ux.owner(request.assigned_manager))
                else:
                    st.caption("暂无服务安排；可从服务工作台安排。")
        with st.expander("年度健康基线摘要"):
            ux.baseline_summary(baseline, rows, compact=True)
        if st.button("处理下一步", key=f"360-next-{patient.id}", type="primary"):
            app.request_navigation(surface="运营后台", ops_page="成员", member_id=patient.id, member_section="管理")
        with c.secondary_details("管理快捷操作"):
            cols = st.columns(3)
            for col, label, target in zip(cols, ["查看完整健康历程", "建立 / 调整计划", "医生协同"], ["历程", "管理", "医疗"]):
                col.button(label, key=f"ux-overview-{target}-{patient.id}", on_click=app.request_navigation, kwargs={"surface": "运营后台", "ops_page": "成员", "member_id": patient.id, "member_section": target})
            quick = st.columns(2)
            for col, label in zip(quick, ["安排随访", "记录阶段结果"]):
                if col.button(label, key=f"360-quick-{label}-{patient.id}"):
                    st.session_state[f"ux-management-{patient.id}"] = label
                    st.session_state[f"workflow-mode-{patient.id}"] = "原有计划 / 任务 / 自动跟进"
                    app.request_navigation(surface="运营后台", ops_page="成员", member_id=patient.id, member_section="管理")
        with st.expander("处理开放中的健康关注事项"):
            app._render_current_risk_actions(patient)
        with st.expander("近期服务"):
            app.render_member_service_management(patient)
    elif section == "健康":
        mode=st.radio("健康档案内容",["健康资料与趋势","初始评估"],horizontal=True,key=f"workflow-record-{patient.id}")
        if mode=="初始评估":workflow.intake(app,patient)
        else:app.render_member_archive(patient)
        workflow.family(patient,management_view)
    elif section == "管理":
        if management_view.intake:workflow.management(app, patient)
        else:
            management(app, patient)
            with st.expander("计划关联服务与执行结果"):
                app.render_member_service_management(patient)
    elif section == "医疗":
        app.render_member_medical_workspace(patient, app._member_medical_context(patient.id))
        with st.expander("正式会诊与方案拆解"):
            workflow.consultations(app,patient)
    else:
        from executive_health_ai.ui.pages.member.experience import timeline
        timeline(app, patient, client_view=False)
