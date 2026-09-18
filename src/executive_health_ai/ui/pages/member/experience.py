from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from sqlalchemy import select

from executive_health_ai.database import SessionLocal
from executive_health_ai.models import HealthProgram, OutcomeEvaluation, RiskEvent, ServiceRequest, Task
from executive_health_ai.services.longitudinal import HealthAssessmentService, HealthTimelineService
from executive_health_ai.services.task_transitions import TaskTransitionService
from executive_health_ai.services.member_services import MemberServiceOperations
from executive_health_ai.ui import experience as ux


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
    ux.inject_design("member")
    ux.page_header("今日健康", f"{patient.display_name}，从今天最重要的行动开始。", "持续健康管理")
    if message := st.session_state.pop("ux-flash", None):
        st.success(message)
    rows = _tasks(patient.id)
    tasks = [r for r in rows if r.status not in {"COMPLETED", "CANCELLED"} and r.responsible_role == "member"]
    st.subheader("今天最重要的事情")
    if tasks:
        for i, task in enumerate(tasks[:3]):
            left, right = st.columns([5, 1])
            with left:
                ux.work_item(task.title, task.instruction, f"{ux.due_date(task.due_at)} · {ux.owner(task.assignee or '成员本人')}")
            if right.button("去完成", key=f"client-home-complete-{task.id}", type="primary" if i == 0 else "secondary"):
                st.session_state[f"ux-task-{patient.id}"] = str(task.id)
                app.request_navigation(surface="成员健康中心", member_page="计划", member_id=patient.id)
    else:
        ux.empty_state("今天没有待完成任务", "健康管理师会在这里更新下一步。")
    with SessionLocal() as session:
        program = session.scalar(select(HealthProgram).where(HealthProgram.patient_id == patient.id, HealthProgram.status.in_(("ACTIVE", "PLANNED", "PAUSED"))).order_by(HealthProgram.created_at.desc()))
        requests = list(session.scalars(select(ServiceRequest).where(ServiceRequest.patient_id == patient.id)))
        data = ux.observations(session, patient.id)
    st.divider()
    st.subheader(f"{datetime.now(ux.LOCAL).year}年度健康管理")
    if program:
        st.write(f"**{ux.business_text(program.title)}** · {app._label(program.status)}")
        st.caption(f"{ux.owner(program.owner)} · 当前阶段：{app.display_program_phase(program.current_phase)}")
        ux.next_action(tasks[0].title if tasks else "等待健康管理师更新下次复盘安排", program.owner)
    else:
        ux.next_action("上传最近体检报告，建立年度健康基线", "健康管理团队")
    with SessionLocal() as session:
        goal = app._active_agent_goal(session, patient.id)
    if goal:
        st.caption("持续管理状态：" + ux.business_text(goal.current_stage) + " · " + ux.business_text(goal.next_action or "负责人将更新下一步"))
    upcoming = ux.upcoming_service(requests)
    if upcoming:
        st.caption(f"下次服务：{ux.when(upcoming.scheduled_at)} · {ux.owner(upcoming.assigned_manager)}")
    st.subheader("近期变化")
    changes = ux.changes(data)
    for label, value, note in changes:
        ux.work_item(label, value, note)
    if not changes:
        ux.empty_state("暂无足够连续数据", "上传健康数据后可查看变化。")
    cols = st.columns(3)
    if cols[0].button("查看健康计划", key=f"client-home-plan-{patient.id}"):
        app.request_navigation(surface="成员健康中心", member_page="计划", member_id=patient.id)
    if cols[1].button("查看健康数据", key=f"client-home-data-{patient.id}"):
        app.request_navigation(surface="成员健康中心", member_page="健康", member_id=patient.id, archive_view="健康数据")
    if cols[2].button("上传体检报告", key=f"client-home-report-{patient.id}"):
        app._open_member_report_upload(patient.id)


def overview(app, patient, ctx):
    if st.session_state.get(f"client-baseline-expanded-{patient.id}"):
        st.button("返回健康概览", key=f"client-baseline-back-{patient.id}", on_click=app._close_client_baseline, args=(patient.id,))
        app._render_member_baseline_center(patient)
        return
    with SessionLocal() as session:
        baseline = HealthAssessmentService().latest_baseline(session, patient.id)
        data = ux.observations(session, patient.id)
    ux.baseline_summary(baseline, data)
    if baseline:
        st.button("查看年度健康基线", key=f"client-health-baseline-open-{baseline.id}", type="primary", on_click=app._open_client_baseline, args=(patient.id,))
    st.subheader("当前变化")
    for label, value, note in ux.changes(data, 2):
        ux.work_item(label, value, note)
    if not ux.changes(data, 2):
        st.caption("暂无足够连续数据。")
    st.subheader("持续关注事项")
    problems = [p for p in ctx["problems"] if p.status != "CLOSED"]
    for problem in problems[:3]:
        ux.work_item(problem.title, problem.description or "健康管理师正在跟进。", ux.owner(problem.owner))
    if not problems:
        st.caption("暂无已确认的持续关注事项。")
    with st.expander("重要健康背景"):
        st.caption("用药、重大病史和手术住院记录统一保存在医疗档案。")
        app._render_client_medical_archive(patient)


def health_data(app, patient_id):
    ux.page_header("健康数据", "选择指标与时间范围，查看记录来源和变化。")
    window = st.session_state.get(f"health-data-window-{patient_id}")
    with SessionLocal() as session:
        rows = ux.observations(session, patient_id)
    if not rows:
        ux.empty_state("暂无已确认健康数据", "上传报告或导入健康数据后，这里会显示趋势。")
        return
    metrics = list(dict.fromkeys(r.metric_code for r in rows))
    metric = st.selectbox("选择健康指标", metrics, format_func=ux.metric_name, key=f"ux-metric-{patient_id}")
    periods = (["时间轴范围"] if window else []) + ["近30天", "近90天", "全部记录"]
    period = st.radio("时间范围", periods, horizontal=True, key=f"ux-period-{patient_id}")
    all_metric = [r for r in rows if r.metric_code == metric]
    since = datetime.now(ux.LOCAL) - timedelta(days=30 if period == "近30天" else 90)
    if period == "时间轴范围":
        try:
            start = datetime.fromisoformat(window["start"]).date()
            end = datetime.fromisoformat(window["end"]).date()
            visible = [r for r in all_metric if start <= ux.local_time(r.observed_at).date() <= end]
            st.info(f"时间轴选择的时间段：{start:%Y年%m月%d日} — {end:%Y年%m月%d日}")
        except (TypeError, ValueError, KeyError):
            visible = []
            st.warning("时间范围无效，请选择近30天、近90天或全部记录。")
    else:
        visible = [r for r in all_metric if period == "全部记录" or ux.local_time(r.observed_at) >= since]
    latest = all_metric[-1]
    st.caption(f"最后记录：{ux.when(latest.observed_at)} · 历史数据可用不代表设备当前已连接")
    if len(visible) >= 2:
        st.line_chart(pd.DataFrame({"记录时间": [ux.local_time(r.observed_at) for r in visible], ux.metric_name(metric): [float(r.value_numeric) for r in visible]}).set_index("记录时间"), height=260)
    elif visible:
        st.metric(ux.metric_name(metric), f"{float(latest.value_numeric):g} {latest.unit}")
        st.caption("当前范围只有一条数据，暂不判断趋势。")
    else:
        st.caption("所选时间范围暂无记录；切换“全部记录”查看历史数据。")
    with st.expander("数据来源与记录"):
        st.dataframe(pd.DataFrame([{"时间": ux.when(r.observed_at), "数值": f"{float(r.value_numeric):g} {r.unit}", "来源": app.get_provider_display(r.source)} for r in reversed(visible)]), hide_index=True, width="stretch")


def plan(app, patient, ctx):
    ux.page_header("接下来我要做什么", "当前行动、近期节点和阶段结果放在同一处。", "健康计划")
    program = app._active_program(ctx)
    tasks = _tasks(patient.id)
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
    st.subheader("近期节点")
    future = [t for t in tasks if t.status not in {"COMPLETED", "CANCELLED"} and t.due_at and ux.local_time(t.due_at) >= datetime.now(ux.LOCAL)]
    st.caption(" · ".join(f"{ux.when(t.due_at)} {ux.business_text(t.title)}" for t in future[:3]) or "暂无新的未来节点；逾期事项请联系负责人重新安排。")
    st.subheader("阶段结果")
    st.caption("仅记录观察到的前后变化，不将变化归因于某项干预。")
    with SessionLocal() as session:
        outcomes = list(session.scalars(select(OutcomeEvaluation).where(OutcomeEvaluation.patient_id == patient.id).order_by(OutcomeEvaluation.evaluation_date.desc()).limit(5)))
    for outcome in outcomes:
        ux.work_item(ux.metric_name(outcome.metric), f"{outcome.baseline_value} → {outcome.current_value} {outcome.unit}", f"{ux.when(outcome.evaluation_date)} · {app._label(outcome.result)}")
    if not outcomes:
        st.caption("阶段复盘后，确认的结果会显示在这里。")


def timeline(app, patient, *, client_view=True):
    ux.page_header("长期健康历程", "只呈现重要健康事件与人工确认的进展。")
    with SessionLocal() as session:
        events = HealthTimelineService().get_timeline(session, patient.id, limit=100)
        risk_states = {str(r.id): r.status for r in session.scalars(select(RiskEvent).where(RiskEvent.patient_id == patient.id))}
    important = [e for e in events if e.event_type not in {"task", "member_plan_choice", "health_data_summary", "management_signal"}
                 and e.source != "member_plan_choice"
                 and not (e.event_type == "major_problem" and e.source in {"risk_event", "yellow_risk_event"})
                 and (e.event_type != "doctor_review" or e.expandable_details.get("status") == "CONFIRMED")
                 and (e.event_type != "service" or e.expandable_details.get("status") == "COMPLETED")]
    for event in important[:20]:
        title = "阶段结果" if event.event_type == "outcome" else event.title
        summary = event.summary or "已归档健康记录"
        meta = "记录于 " + ux.when(event.occurred_at)
        if event.event_type == "risk":
            state = risk_states.get(event.related_entity)
            meta += " · " + app._label(state)
            if state in {"CLOSED", "DISMISSED_DATA_ISSUE"}:
                title = "历史风险记录 · 已完成"
                summary = "当时记录：" + summary
        elif event.event_type == "medication_change":
            summary = "剂量、频率与医嘱请查看医疗档案。"
        ux.work_item(title, summary, meta)
    if not important:
        ux.empty_state("暂无重要健康事件", "确认报告、基线或阶段结果后会自动归入历程。")
    with st.expander("查看完整历程与依据"):
        app.render_longitudinal_timeline(patient, key_scope="member-center-journey" if client_view else "member-journey", client_view=client_view)
