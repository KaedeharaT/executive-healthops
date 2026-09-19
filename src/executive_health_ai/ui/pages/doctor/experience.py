from datetime import date, datetime, time, timedelta

import streamlit as st
from sqlalchemy import select

from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentApprovalRequest, AgentGoal, DoctorReview, HealthAssessment, HealthProblem, MedicationPlan, Patient, Task
from executive_health_ai.services.longitudinal import HealthAssessmentService
from executive_health_ai.services.care_commands import complete_review
from executive_health_ai.ui import experience as ux
from executive_health_ai.ui import components as c
from executive_health_ai.services.product_projection import ProductProjectionService


def detail(app, patient, review, *, read_only=False):
    st.subheader("需要医生判断的问题")
    st.write(ux.business_text(review.question_for_doctor or "请核实本次健康变化是否需要进一步医学评估。"))
    st.caption(f"{patient.display_name} · 提交于 {ux.when(review.created_at)} · {'已完成' if review.status != 'PENDING' else '待我复核'}")
    st.caption("为什么现在：这项医学问题已由健康管理团队提交，需要人工判断后才能继续安排。")
    clinical, decision = st.container(), st.container()
    with clinical:
        with st.container(key="v2-context-doctor"):
            with SessionLocal() as session:
                review_view = ProductProjectionService().doctor(session, review)
                problem, context = review_view.problem, review_view.member
                baseline = HealthAssessmentService().latest_baseline(session, patient.id, include_draft=False)
                data = context.observations
                meds, tasks = review_view.medications, review_view.completed_actions
                payload = app._risk_evidence_payload(session, patient.id, review.risk_event_id) if review.risk_event_id else {"raw_evidence": None, "source_name": "阶段结果提交资料"}
            c.section_header("关键背景与趋势")
            if problem:
                st.caption("关联关注事项：" + ux.business_text(problem.title))
            brief = ux.business_text(review.doctor_brief or "资料待补充，请联系健康管理师。")
            st.write(brief[:120] + ("…" if len(brief) > 120 else ""))
            from executive_health_ai.ui.pages.health_visualization import render_doctor_trend
            render_doctor_trend(patient.id, review)
            c.section_header("本次判断的依据")
            ux.evidence_summary(payload)
            with c.secondary_details("关键成员背景与提交摘要"):
                st.write(ux.business_text(review.doctor_brief or "资料待补充，请联系健康管理师。"))
            with st.expander("重要健康背景与年度基线"):
                if baseline:
                    snapshot = baseline.baseline_json or {}
                    st.write(f"{baseline.cycle_year or baseline.assessed_at.year}年度健康基线 · {app._label(baseline.status)}")
                    conditions = [ux.business_text(r.get("title")) for r in snapshot.get("health_problems", []) if isinstance(r, dict)]
                    st.caption("已有健康问题：" + ("；".join(conditions) or "暂无已确认资料"))
                    history = snapshot.get("procedures_or_hospitalizations", [])
                    events = [ux.business_text(r.get("description") or "医疗记录") for r in history if isinstance(r, dict)] if isinstance(history, list) else []
                    st.caption("手术 / 住院：" + ("；".join(events) or "暂无已确认资料"))
                else:
                    st.caption("尚无已确认年度基线；缺少记录不代表没有既往病史。")
            with c.secondary_details("全部关键指标记录"):
                latest = {row.metric_code: row for row in data}
                priority = ["systolic_bp", "diastolic_bp", "hba1c", "ldl_c", "weight"]
                ordered = [latest[code] for code in priority if code in latest] + [r for code, r in latest.items() if code not in priority]
                st.dataframe([{"指标": ux.metric_name(r.metric_code), "当前记录": float(r.value_numeric), "单位": r.unit, "记录时间": ux.when(r.observed_at)} for r in ordered], hide_index=True, width="stretch")
            with st.expander("完整资料位置与核对信息"):
                app._render_evidence_action(payload, key_scope=f"ux-doctor-evidence-{review.id}")
            with c.secondary_details("用药与健康问题摘要"):
                if problem:
                    st.write(ux.business_text(problem.title))
                st.caption("当前用药：" + ("；".join(f"{r.drug_name} {r.dose or ''}{r.dose_unit or ''}" for r in meds if r.status.lower() == "active") or "暂无已确认记录"))
            with st.expander("已采取行动"):
                for task in tasks:
                    st.write(ux.business_text(task.title))
                if not tasks:
                    st.caption("尚无已完成行动记录。")
    with decision:
        with st.container(key="v2-panel-doctor-decision"):
            if review.status != "PENDING":
                st.subheader("医生结论")
                st.write(ux.business_text(review.opinion or "已完成复核，意见待补充。"))
                ux.next_action("健康管理师执行医生建议，并记录随访结果", context.owner)
                return
            if read_only:
                ux.next_action("等待医生完成医学复核，之后由健康管理师跟进", review.doctor_name if review.doctor_name != "待分配医生" else "内部医生")
                return
            st.subheader("医生结论与后续执行")
            st.caption("提交后由健康管理师执行，并回写随访结果。")
            with st.form(f"ux-doctor-review-{review.id}"):
                identity, specialty = st.columns(2)
                doctor = identity.text_input("医生姓名", value="演示医生")
                department = specialty.text_input("科室", value=review.department or "全科/健康管理")
                opinion = st.text_area("医生人工意见")
                instruction = st.text_area("交给健康管理师的下一步")
                due = st.date_input("建议跟进日期", value=date.today()+timedelta(days=7), min_value=date.today())
                st.caption("执行角色：健康管理师。当前计划负责人：" + ux.business_text(context.owner) + "。提交后返回统一待办队列；具体任务分派以保存记录为准。")
                submit = st.form_submit_button("提交判断并交回健管", type="primary")
            if submit:
                try:
                    with SessionLocal() as session:
                        complete_review(session, session.get(DoctorReview, review.id), doctor, department, opinion, instruction, datetime.combine(due, time(9), ux.LOCAL))
                        session.commit()
                    st.session_state["doctor-flash"] = "医学判断已保存，跟进任务已交给健康管理师。"
                    st.rerun()
                except ValueError:
                    st.error("请填写医生姓名、人工判断及后续执行说明，并确认本次复核仍待处理。")


def workspace(app, members, *, patient=None, read_only=False):
    c.page_shell("doctor", "医学复核" if read_only else "待我复核", "明确问题、核对依据，判断后由健康管理师执行。", "医疗协同" if read_only else "医生工作台")
    if message := st.session_state.pop("doctor-flash", None):
        st.success(message)
    with SessionLocal() as session:
        pending = ux.pending_doctor_work(session, patient.id if patient else None)
        query = select(DoctorReview).where(DoctorReview.status == "CONFIRMED").order_by(DoctorReview.reviewed_at.desc())
        if patient:
            query = query.where(DoctorReview.patient_id == patient.id)
        completed = list(session.scalars(query))
        approval_query = select(AgentGoal.member_id).join(AgentApprovalRequest, AgentApprovalRequest.goal_id == AgentGoal.id).where(AgentApprovalRequest.required_role == "DOCTOR", AgentApprovalRequest.status == "PENDING")
        if patient:
            approval_query = approval_query.where(AgentGoal.member_id == patient.id)
        approval_members = list(dict.fromkeys(session.scalars(approval_query)))
    c.summary_strip([("待复核", len(pending)), ("已完成", len(completed)), ("执行交接", "医生判断 → 健管跟进")])
    queue_filter, queue_selection = st.columns([1, 2.8])
    mode = queue_filter.radio("复核工作", ["待复核", "已完成"], horizontal=True, format_func=lambda value: "待我复核" if value == "待复核" else "历史", key=f"ux-doctor-mode-{patient.id if patient else 'all'}")
    rows = pending if mode == "待复核" else completed
    people = {m.id: m for m in members}
    if patient:
        people[patient.id] = patient
    if not read_only and approval_members:
        from executive_health_ai.ui.pages.manager.experience import approvals
        with st.expander("需要医生确认的后续安排", expanded=not rows):
            for member_id in approval_members:
                member = people.get(member_id)
                if member:
                    st.caption(member.display_name)
                    approvals(app, member_id, "DOCTOR")
    if not rows:
        ux.empty_state("当前没有待复核事项" if mode == "待复核" else "暂无已完成复核", "新增医学问题会统一进入此队列。")
        return
    selected = queue_selection.selectbox("选择复核事项", rows, format_func=lambda r: f"{people[r.patient_id].display_name} · {ux.business_text(getattr(r, 'question_for_doctor', None) or getattr(r, 'title', None) or '年度基线医学确认')}", key=f"ux-doctor-selected-{patient.id if patient else 'all'}")
    member = people[selected.patient_id]
    if isinstance(selected, DoctorReview):
        detail(app, member, selected, read_only=read_only)
    elif not read_only:
        # Existing annual-baseline / historical-alert decisions retain their service path.
        ctx = app._member_doctor_context(member.id)
        app._render_legacy_doctor_reviews(member, {**ctx, "reviews": [], "alerts": [a for a in ctx["alerts"] if a.id == selected.id]})
    else:
        ux.next_action("等待医生核对医学资料", "内部医生")

    with st.expander("查看复核队列"):
        for row in rows:
            ux.work_item(people[row.patient_id].display_name, getattr(row, "question_for_doctor", None) or getattr(row, "title", None) or "年度基线医学确认", ux.when(getattr(row, "created_at", None)))
        st.caption("复核记录未设置独立截止时间；按提交时间处理，紧急事项由健管人工联系。")
