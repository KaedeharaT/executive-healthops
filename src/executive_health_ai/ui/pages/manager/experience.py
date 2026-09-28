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
from executive_health_ai.ui.presentation import data_table, preview, work_filter, WORK_FILTERS, task_records


def approvals(app, patient_id, role="HEALTH_MANAGER", selected_id=None):
    with SessionLocal() as session:
        rows = list(session.execute(select(AgentApprovalRequest, AgentGoal, AgentPlanStep).join(AgentGoal, AgentApprovalRequest.goal_id == AgentGoal.id).join(AgentPlanStep, AgentApprovalRequest.plan_step_id == AgentPlanStep.id).where(AgentGoal.member_id == patient_id, AgentApprovalRequest.status == "PENDING", AgentApprovalRequest.required_role == role)))
    selected = next((r for r in rows if r[0].id == selected_id),None) if selected_id else data_table(rows, [{'安排': goal.title, '负责人': goal.owner, '状态': '待人工确认', '下一步': goal.next_action} for approval,goal,step in rows], key=f'approvals-{patient_id}-{role}', empty='暂无需要您确认的自动跟进安排。')
    for approval, goal, step in [selected] if selected else []:
        from executive_health_ai.agent.post_checkup import is_care_goal
        if is_care_goal(goal):
            if st.button('处理本次体检报告', key=f'care-approval-open-{goal.id}'):
                st.session_state['care-detail'] = str(goal.id)
                app.request_navigation(surface='运营后台', ops_page='今日')
            continue
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


def reset_today_selection():
    """Sidebar navigation opens the workspace, not a previous nested detail."""
    for key in ('care-detail', 'care-origin', 'today-detail'):
        st.session_state.pop(key, None)
    st.session_state['today-work-grid-epoch'] = st.session_state.get('today-work-grid-epoch', 0) + 1


def today(app):
    from executive_health_ai.ui.pages.manager.workbench import today as render
    render(app)



def management(app, patient, action=None):
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
    mode = action or st.radio("管理操作", ["工作进展", "建立 / 调整计划", "安排随访", "记录阶段结果"], horizontal=True, key=f"ux-management-{patient.id}")
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
            target = st.text_input("已确认目标值（选填）", help="仅填写已有方案中确认的目标，不由系统推算。")
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
                    outcome = care_commands.record_outcome(session, session.get(HealthProgram, program.id), metric=metric, baseline_value=baseline, current_value=current, target_value=target.strip() or None, unit=unit, direction="OBSERVED", evaluator=evaluator, evidence=evidence, result=result, notes=note)
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
    origin=st.session_state.get('member-return-origin','会员')
    if st.button('← 返回'+origin, key="back-to-dashboard"):
        st.session_state.pop("focused_member_id", None)
        st.session_state.pop('member-return-origin',None)
        app.request_navigation(surface='运营后台',ops_page={'今日工作':'今日','年度管理':'年度管理','会员':'成员','专项管理':'专项管理','服务管理':'服务运营'}.get(origin,'成员'))
        st.rerun()
    ctx = app._member_summary_context(patient.id)
    management_view=workflow.view_for(patient.id)
    with SessionLocal() as session:
        view = ProductProjectionService().member(session, patient.id, health=True,
            program_id=management_view.program.id if origin in {'年度管理','专项管理','服务管理'} and management_view.program else None)
    program, pending, baseline, rows = view.program, view.pending_doctor, view.baseline, view.observations
    tasks = view.active_tasks
    professional = (management_view.intake.professional_focus if management_view.intake else '') or '；'.join(p.title for p in ctx['problems'] if p.status!='CLOSED' and p.source!='post_checkup_care') or '待初评'
    concern = management_view.intake.member_concern if management_view.intake else '待填写'
    next_task = tasks[0] if tasks else None
    from executive_health_ai.services.management_action_loop import ManagementActionLoop
    with SessionLocal() as session:
        action_state=ManagementActionLoop().project(session,patient.id,management_view.program.id if management_view.program else None)
    next_work=action_state['next']
    from executive_health_ai.services.member_management_projection import onboarding_next
    onboarding=onboarding_next(management_view)
    next_text=(next_work.title+' · '+next_work.owner+' · '+ux.when(next_work.due)) if next_work else ('确认并进入下一阶段' if action_state['review'] else '开始阶段复盘' if action_state['review_ready'] else '新增管理记录或创建随访')+' · '+view.owner
    if onboarding and not next_work:next_text=onboarding[0]+' · '+view.owner
    updated = [r.observed_at for r in rows]+[r.occurred_at for r in management_view.logs]
    if management_view.intake: updated.append(management_view.intake.updated_at)
    cycle=view.cycle+(f' · {program.start_date:%m/%d}—{program.end_date:%Y/%m/%d}' if program and program.end_date else '')
    c.member_header(ux.business_text(patient.display_name), cycle=cycle, owner=ux.business_text(view.owner),
        phase=view.phase_title or management_view.onboarding, concern=concern or '待填写', focus=professional,
        next_action=next_text,
        updated=ux.when(max(updated)) if updated else '暂无记录')
    with st.container(key='soft-member-navigation'):
        section = st.radio("成员页面", ["概览", "健康", "管理", "医疗", "历程"], horizontal=True, label_visibility="collapsed", key=f"member-section-{patient.id}",format_func=lambda x:"健康档案" if x=="健康" else x)
    if section in {'概览', '管理'}:
        from executive_health_ai.ui.pages.manager.post_checkup import member_summary
        with st.container(border=True, key='member-auto-followup'):
            member_summary(patient.id, app=app)
    if section == "概览":
        from executive_health_ai.ui.pages.manager import intake_entry
        if intake_entry.state(management_view.intake) != '已完成':
            reminder, action = st.columns([4,1])
            reminder.caption('初始健康评估尚未完成 · '+intake_entry.state(management_view.intake))
            if action.button('继续评估',key=f'overview-intake-{patient.id}'):
                intake_entry.open_intake(patient,management_view)
                app.request_navigation(surface='运营后台',ops_page='成员',member_id=patient.id,member_section='健康')
                st.rerun()
        st.markdown('**当前阶段**')
        if management_view.phases: workflow.phases(management_view)
        else: workflow.onboarding(management_view)
        import re
        focus_items=[x.strip() for x in re.split('[；，、;\n]', professional) if x.strip()][:5]
        c.summary_strip([('管理重点', preview(f,24)) for f in focus_items])
        from executive_health_ai.ui.pages.health_visualization import render_previews
        render_previews(patient.id,key=f'manager-overview-trend-{patient.id}',maximum=2,series=view.health.series,
            open_trend=lambda:app.request_navigation(surface='运营后台',ops_page='成员',member_id=patient.id,member_section='健康',archive_view='健康数据'))
        left,right=st.columns([1.5,1])
        with left:
            st.subheader('当前开放事项')
            data_table(tasks[:6],[{'事项':t.title,'状态':status_label(t.status),'负责人':t.assignee or view.owner,'截止时间':ux.local_time(t.due_at)} for t in tasks[:6]],key=f'360-open-{patient.id}',selectable=False,empty='暂无开放事项。')
            if len(tasks)>6:st.caption(f'共 {len(tasks)} 条；完整队列见管理页。')
            from executive_health_ai.ui.pages.manager.action_loop import open_next
            st.button('处理下一步',key=f'360-next-{patient.id}',type='primary',on_click=open_next,args=(app,patient))
        with right:
            st.subheader('最近管理记录')
            workflow.log_rows(management_view.logs[:2],key=f'360-recent-{patient.id}')
            st.button('新增管理记录',key=f'overview-new-log-{patient.id}',on_click=workflow.open_log,args=(app,patient))
        with st.expander('年度目标与健康基线'):
            st.write(ux.business_text(program.main_goal) if program else '待建立年度方案')
            ux.baseline_summary(baseline,rows,compact=True)
        from executive_health_ai.ui.pages.manager.service_progress import member_progress
        member_progress(management_view,compact=True)
    elif section == "健康":
        from executive_health_ai.ui.pages.manager.workbench import archive
        archive(app,patient,management_view)
    elif section == "管理":
        workflow.management(app, patient)
    elif section == "医疗":
        from executive_health_ai.ui.pages.manager.workbench import medical
        medical(app,patient)
    else:
        from executive_health_ai.ui.pages.member.experience import timeline
        timeline(app, patient, client_view=False)
