from datetime import datetime, timedelta
import logging
from typing import Protocol, Any

import pandas as pd
import streamlit as st
from sqlalchemy import select

from executive_health_ai.database import SessionLocal
from executive_health_ai.models import HealthProgram, OutcomeEvaluation, RiskEvent, ServiceRequest, Task
from executive_health_ai.services.longitudinal import HealthAssessmentService, HealthTimelineService
from executive_health_ai.services.task_transitions import TaskTransitionService
from executive_health_ai.services.member_services import MemberServiceOperations
from executive_health_ai.ui import experience as ux
from executive_health_ai.ui import components as c
from executive_health_ai.services.product_projection import ProductProjectionService
from executive_health_ai.ui.view_models import care_team_context
from executive_health_ai.ui.pages.health_visualization import render_previews, render_health_explorer

logger = logging.getLogger(__name__)


class TimelineAdapter(Protocol):
    def _label(self, value: str | None) -> str: ...
    def render_longitudinal_timeline(self, patient: Any, *, key_scope: str, client_view: bool) -> None: ...


def _tasks(patient_id):
    with SessionLocal() as session:
        return list(session.scalars(select(Task).where(Task.patient_id == patient_id).order_by(Task.due_at, Task.created_at)))


def _complete(task):
    try:
        with SessionLocal() as session:
            TaskTransitionService().complete(session, task.id, actor="成员本人", outcome="成员确认已完成，待健康管理师复核实际结果。")
            session.commit()
        st.session_state["ux-flash"] = "已完成任务，健康管理师已收到进展。"
        st.rerun()
    except ValueError:
        st.error("此任务需要健康管理师核实，请联系负责人。")


def home(app, patient, ctx):
    from executive_health_ai.ui.pages.manager.workflow import view_for, intake
    management=view_for(patient.id)
    if management.intake and management.intake.status=='DRAFT':
        if st.session_state.get(f'member-intake-open-{patient.id}'):
            if st.button("返回首页",key=f'intake-back-{patient.id}'):
                st.session_state.pop(f'member-intake-open-{patient.id}',None);st.rerun()
            intake(app,patient,member=True)
            return
        with c.section("完善健康档案",key="member-intake-action",emphasis=True):
            st.write("完成初始评估，让健康管理师了解你自己希望改善的问题。")
            if st.button("继续填写",key=f'intake-open-{patient.id}',type='primary'):
                st.session_state[f'member-intake-open-{patient.id}']=True;st.rerun()
    c.page_shell("member", "今日健康", f"{patient.display_name}，今天先处理最重要的一件事。", "持续健康管理")
    if message := st.session_state.pop("ux-flash", None):
        st.success(message)
    with SessionLocal() as session:
        view = ProductProjectionService().member(session, patient.id, health=True)
        goal = app._active_agent_goal(session, patient.id)
        people = care_team_context(session, patient.id)
    program, tasks = view.program, view.member_actions
    upcoming = ux.upcoming_service(view.services)
    with c.section("今天需要你完成", key="member-action", emphasis=True):
        if tasks:
            task = tasks[0]
            st.markdown("### " + ux.business_text(task.title))
            reason = ux.business_text(task.instruction or "完成后由健康管理师核对，并安排下一步。")
            st.write(reason[:70] + ("…" if len(reason) > 70 else ""))
            st.caption(f"{ux.due_date(task.due_at)} · {ux.owner(task.assignee or '成员本人')}")
            if st.button("去完成", key=f"client-home-complete-{task.id}", type="primary", icon=":material/arrow_forward:"):
                st.session_state[f"ux-task-{patient.id}"] = str(task.id)
                app.request_navigation(surface="成员健康中心", member_page="计划", member_id=patient.id)
            with c.secondary_details("查看原因与完成说明"):
                st.write(reason)
            if len(tasks) > 1:
                with c.secondary_details("其他今日行动"):
                    for task in tasks[1:3]:
                        ux.work_item(task.title, "", ux.due_date(task.due_at))
                        if st.button("去完成", key=f"client-home-complete-{task.id}"):
                            st.session_state[f"ux-task-{patient.id}"] = str(task.id)
                            app.request_navigation(surface="成员健康中心", member_page="计划", member_id=patient.id)
        else:
            ux.empty_state("目前无需你操作", f"下一步由{ux.business_text(view.owner)}跟进。")
            if not view.baseline and st.button("上传体检报告", key=f"client-home-report-empty-{patient.id}", type="primary"):
                app._open_member_report_upload(patient.id)
    with c.section("当前管理", key="member-management"):
        c.summary_strip([("管理周期", view.cycle), ("当前阶段", view.phase_title or ("完善健康档案" if program and program.current_phase=='ONBOARDING' else app.display_program_phase(program.current_phase) if program else "待建立计划")),
                         ("负责人", ux.business_text(view.owner))])
        next_task = next((t for t in view.active_tasks if t.due_at and ux.local_time(t.due_at) >= datetime.now(ux.LOCAL)), None)
        st.caption((app._label(program.status) + " · " if program else "") + "下一节点：" + (ux.when(next_task.due_at) + " · " + ux.business_text(next_task.title) if next_task else "由负责人确认下一次安排"))
        with c.secondary_details("当前管理进展与下一步"):
            ux.next_action(tasks[0].title if tasks else "等待健康管理师更新下次复盘安排", view.owner)
            if goal:
                st.caption("持续管理状态：" + ux.business_text(goal.current_stage) + " · " + ux.business_text(goal.next_action or "负责人将更新下一步"))
            if st.button("查看健康计划", key=f"client-home-plan-{patient.id}"):
                app.request_navigation(surface="成员健康中心", member_page="计划", member_id=patient.id)
            if st.button("上传体检报告", key=f"client-home-report-{patient.id}"):
                app._open_member_report_upload(patient.id)
    with c.section("最近变化", key="home-trends"):
        render_previews(patient.id, key=f"home-trends-{patient.id}", maximum=2, series=view.health.series, shared_action=True,
            open_trend=lambda: app.request_navigation(surface="成员健康中心", member_page="健康", member_id=patient.id, archive_view="健康数据"))
        with c.secondary_details("其他健康数据"):
            if st.button("查看健康数据", key=f"client-home-data-{patient.id}"):
                app.request_navigation(surface="成员健康中心", member_page="健康", member_id=patient.id, archive_view="健康数据")
    with c.section("近期安排与健康团队", key="home-team"):
        if upcoming:
            ux.next_action(upcoming.next_action or "按约定时间参加服务", upcoming.assigned_manager)
            st.caption("下次服务 · 已预约：" + ux.when(upcoming.scheduled_at))
        else:
            st.caption("暂无已安排的未来服务；复查与随访节点在计划中查看。")
        if st.button("查看服务安排", key=f"client-home-service-{patient.id}"):
            app.request_navigation(surface="成员健康中心", member_page="服务", member_id=patient.id)
        c.care_team(people)


def overview(app, patient, ctx):
    if st.session_state.get(f"client-baseline-expanded-{patient.id}"):
        st.button("返回健康概览", key=f"client-baseline-back-{patient.id}", on_click=app._close_client_baseline, args=(patient.id,))
        app._render_member_baseline_center(patient)
        return
    with SessionLocal() as session:
        view = ProductProjectionService().member(session, patient.id, health=True)
    from executive_health_ai.ui.pages.member.health_overview import render_member_health_overview
    render_member_health_overview(app, patient, ctx, view, session_factory=SessionLocal)


def health_data(app, patient_id):
    c.section_header("健康数据", "选择指标与时间范围，查看记录来源和变化。")
    render_health_explorer(patient_id)


def plan(app, patient, ctx):
    ux.page_header("接下来我要做什么", "当前行动、近期节点和阶段结果放在同一处。", "健康计划")
    with SessionLocal() as session:
        view = ProductProjectionService().member(session, patient.id)
    program, tasks = view.program, list(view.tasks)
    current_outcomes, historical_outcomes = view.current_outcomes, view.historical_outcomes
    program_names = {p.id: ux.business_text(p.title) for p in view.programs}
    if program:
        st.subheader(ux.business_text(program.title))
        st.write(ux.business_text(program.main_goal))
        st.caption(f"{ux.owner(program.owner)} · {ux.when(program.start_date)} — {ux.when(program.end_date)} · {app._label(program.status)}")
        related = [t for t in tasks if t.program_id == program.id and t.status != "CANCELLED"]
        if related:
            done = sum(t.status == "COMPLETED" for t in related)
            st.progress(done / len(related), text=f"行动完成 {done} / {len(related)}；不代表健康改善程度")
        with st.expander("接受或调整当前方案"):
            choice = st.radio("我的选择", ["接受方案", "希望调整", "暂缓", "和健康管理师讨论"], horizontal=True, key=f"member-plan-choice-{patient.id}")
            if st.button("记录选择", key=f"member-plan-choice-save-{patient.id}"):
                with SessionLocal() as session:
                    MemberServiceOperations().record_choice(session, patient.id, choice)
                    session.commit()
                st.success("已记录，健康管理师将跟进您的选择。")
    else:
        ux.empty_state("暂无当前计划", "健康管理师会和您确认目标及行动。")
    phase = app.display_program_phase(program.current_phase) if program else "待建立计划"
    c.workflow(list(dict.fromkeys(["建立基线", phase, "阶段复盘"])), phase)
    actions, progress = st.columns([1.7, 1], gap="large")
    with actions:
        view = st.radio("任务分类", ["待完成", "等待他人", "已完成"], horizontal=True, key=f"client-plan-view-{patient.id}")
        visible = [t for t in tasks if (t.status == "COMPLETED" if view == "已完成" else t.status not in {"COMPLETED", "CANCELLED"} and (t.responsible_role == "member") == (view == "待完成"))]
        selected_id = st.session_state.get(f"ux-task-{patient.id}")
        if selected_id:
            visible.sort(key=lambda t: str(t.id) != selected_id)
        for i, task in enumerate(visible[:5]):
            ux.work_item(task.title, task.instruction, f"{ux.owner(task.assignee)} · {ux.when(task.due_at, due=task.status != 'COMPLETED')}")
            if view == "待完成" and st.button("确认完成", key=f"ux-complete-{task.id}", type="primary" if i == 0 else "secondary"):
                _complete(task)
        if not visible:
            st.caption("此分类暂无任务。新的安排会由负责人更新。")
        if len(visible) > 5:
            with st.expander(f"其他 {len(visible)-5} 项行动"):
                for task in visible[5:]:
                    ux.work_item(task.title, task.instruction, ux.owner(task.assignee))
                    if view == "待完成" and st.button("确认完成", key=f"ux-complete-{task.id}"):
                        _complete(task)
    with progress:
        with st.container(key="v2-panel-plan-review"):
            st.subheader("近期节点")
            future = [t for t in tasks if t.status not in {"COMPLETED", "CANCELLED"} and t.due_at and ux.local_time(t.due_at) >= datetime.now(ux.LOCAL)]
            st.caption(" · ".join(f"{ux.when(t.due_at)} {ux.business_text(t.title)}" for t in future[:3]) or "暂无新的未来节点；逾期事项请联系负责人重新安排。")
            st.subheader("阶段结果")
            st.caption("仅记录观察到的前后变化，不将变化归因于某项干预。")
            for outcome in current_outcomes:
                ux.work_item(ux.metric_name(outcome.metric), f"{outcome.baseline_value} → {outcome.current_value} {outcome.unit}", f"{ux.when(outcome.evaluation_date)} · {app._label(outcome.result)} · {'当前计划' if program and outcome.program_id == program.id else program_names.get(outcome.program_id, '历史计划')}")
            if not current_outcomes:
                st.caption("当前计划尚未记录阶段结果。完成复盘后会显示在这里。")
            with c.secondary_details("历史计划与阶段结果"):
                for outcome in historical_outcomes:
                    ux.work_item(program_names.get(outcome.program_id, "历史计划") + " · " + ux.metric_name(outcome.metric), f"{outcome.baseline_value} → {outcome.current_value} {outcome.unit}", ux.when(outcome.evaluation_date))
                if not historical_outcomes:
                    st.caption("暂无历史阶段结果。")


def timeline(app: TimelineAdapter, patient, *, client_view=True):
    """Contain unexpected rendering failures without exposing health data or paths."""
    try:
        _timeline_content(app, patient, client_view=client_view)
    except Exception:
        logger.exception("member_timeline_render_failed")
        st.error("健康历程暂时无法加载，请稍后重试。")


def _timeline_content(app: TimelineAdapter, patient, *, client_view=True):
    ux.page_header("长期健康历程", "只呈现重要健康事件与人工确认的进展。")
    with SessionLocal() as session:
        events = HealthTimelineService().get_timeline(session, patient.id, limit=100)
        risk_states = {str(r.id): r.status for r in session.scalars(select(RiskEvent).where(RiskEvent.patient_id == patient.id))}
    important = [e for e in events if e.event_type not in {"task", "member_plan_choice", "health_data_summary", "management_signal"}
                 and e.source != "member_plan_choice"
                 and not (e.event_type == "major_problem" and e.source in {"risk_event", "yellow_risk_event"})
                 and (e.event_type != "doctor_review" or e.expandable_details.get("status") == "CONFIRMED")
                 and (e.event_type != "service" or e.expandable_details.get("status") == "COMPLETED")]
    def render_event(event):
        title = "阶段结果" if event.event_type == "outcome" else event.title
        summary = event.summary or "已归档健康记录"
        meta = "记录于 " + ux.when(event.occurred_at) + " · " + ux.business_text(event.event_type_label or "健康记录")
        if event.event_type == "risk":
            state = risk_states.get(event.related_entity)
            meta += " · " + app._label(state)
            if state in {"CLOSED", "DISMISSED_DATA_ISSUE"}:
                title = "历史风险记录 · 已完成"
                summary = "当时记录：" + summary
        elif event.event_type == "medication_change":
            summary = "剂量、频率与医嘱请查看医疗档案。"
        c.timeline_event(ux.business_text(title), ux.business_text(summary), ux.when(event.occurred_at), ux.business_text(meta.split(" · ", 1)[-1]))
    for event in important[:6]:
        render_event(event)
    if len(important) > 6:
        with st.expander(f"更多重要事件 · {min(len(important), 20)-6} 条"):
            for event in important[6:20]:
                render_event(event)
    if not important:
        ux.empty_state("暂无重要健康事件", "确认报告、基线或阶段结果后会自动归入历程。")
    with st.expander("查看完整历程与依据"):
        app.render_longitudinal_timeline(patient, key_scope="member-center-journey" if client_view else "member-journey", client_view=client_view)
