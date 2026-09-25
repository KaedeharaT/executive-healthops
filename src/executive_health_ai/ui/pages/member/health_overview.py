"""Annual starting point, changes and next steps; presentation only."""
from html import escape

import streamlit as st

from executive_health_ai.ui import experience as ux
from executive_health_ai.ui.localization.zh_cn import program_phase
from executive_health_ai.ui.pages.baseline_visualization import render_baseline_progress, _render_comparison_details
from executive_health_ai.ui.styles import MEMBER_OVERVIEW_STYLES


def management_stages(baseline, program):
    """State markers, never a computed completion percentage or medical inference."""
    confirmed = baseline is not None and baseline.status in {"CONFIRMED", "AMENDED"}
    start = ("建立基线", "已完成" if confirmed else "当前 · 待确认" if baseline else "当前 · 待建立", "done" if confirmed else "current")
    if not program:
        return (start, ("持续管理", "待安排", "next"), ("阶段复盘", "待安排", "next"))
    phase, state = program.current_phase, program.status
    if not confirmed:
        if state == "ACTIVE" and phase == "STARTUP":
            return (start, ("持续管理", "下一步", "next"), ("阶段复盘", "待安排", "next"))
        # An existing active plan does not stop just because annual data is pending.
        start = ("建立基线", "待确认" if baseline else "待建立", "next")
    if state != "ACTIVE":
        return (start, (program_phase(phase), ux.business_text(ux.get_status_display(state)), "next"), ("阶段复盘", "待安排", "next"))
    if phase == "REASSESSMENT":
        return (start, ("持续管理", "已进入复盘", "done"), ("阶段复盘", "当前", "current"))
    if phase not in {"STARTUP", "ONGOING", "EXECUTION", "STABILIZATION"}:
        return (start, ("持续管理", "阶段待确认", "next"), ("阶段复盘", "待安排", "next"))
    return (start, (program_phase(phase), "当前", "current"), ("阶段复盘", "下一步", "next"))


def split_domains(domains):
    """Keep every source domain, assigning missing information to one group."""
    missing = tuple(d for d in domains if d.status == "资料不足")
    available = tuple(d for d in domains if d.status != "资料不足")
    focus = tuple(d for d in available if d.status == "需要持续关注")
    return available, missing, focus


def management_stage(baseline, program):
    steps = []
    for title, state, tone in management_stages(baseline, program):
        current = ' aria-current="step"' if tone == "current" else ""
        steps.append(f'<div role="listitem" class="{tone}"{current}><span class="stage-dot" aria-hidden="true"></span><strong>{escape(title)}</strong><small>{escape(state)}</small></div>')
    st.markdown('<div class="overview-stages" role="list" aria-label="年度管理阶段">' + "".join(steps) + '</div>', unsafe_allow_html=True)


def focus_items(domains):
    rows = []
    for item in domains:
        rows.append('<article><div class="overview-focus-title">'
            f'<h4>{escape(ux.business_text(item.label))}</h4><span class="overview-status attention">需要持续关注</span></div>'
            f'<p>{escape(ux.business_text(item.summary))}</p></article>')
    st.markdown('<div class="overview-focus-list">' + ''.join(rows) + '</div>', unsafe_allow_html=True)


def health_domain_summary(domains):
    rows = []
    for item in domains:
        label = {"已建立": "资料已建立", "资料不足": "待补充资料"}.get(item.status, item.status)
        tone = "attention" if item.status == "需要持续关注" else "neutral"
        rows.append(f'<tr><th scope="row">{escape(ux.business_text(item.label))}</th>'
                    f'<td><span class="overview-status {tone}">{escape(label)}</span></td></tr>')
    if rows:
        st.markdown('<table class="overview-domain-list" aria-label="健康领域状态"><thead><tr><th>健康领域</th><th>当前状态</th></tr></thead><tbody>'
                    + ''.join(rows) + '</tbody></table>', unsafe_allow_html=True)
    else:
        st.caption("尚无已整理的领域资料；补充资料后在这里查看。")


def data_coverage(view):
    if view is None or not view.coverage:
        st.caption("建立年度基线后显示资料覆盖情况。")
        return
    st.markdown(f"**{view.covered_count} / {len(view.coverage)} 类资料已覆盖**")
    cells = []
    for item in view.coverage:
        tone = "covered" if item.status == "已覆盖" else "neutral"
        label = "已覆盖" if item.status == "已覆盖" else "待补充 · 部分覆盖" if item.status == "部分" else "待补充" if item.status == "待补充" else "待补充 · "+item.status
        cells.append(f'<div><span>{escape(item.label)}</span><small class="overview-status {tone}">{escape(label)}</small></div>')
    st.markdown('<div class="overview-coverage" aria-label="资料覆盖">' + ''.join(cells) + '</div>', unsafe_allow_html=True)
    st.caption("这是资料完整度，不代表健康评分。")


def render_member_health_overview(app, patient, ctx, view, *, session_factory):
    baseline = view.baseline
    confirmed = baseline is not None and baseline.status in {"CONFIRMED", "AMENDED"}
    health = view.health.baseline if confirmed and view.health else None
    available, missing, focus = split_domains(health.domains if health else ())
    problems = [p for p in ctx.get("problems", ()) if p.status not in {"CLOSED", "RESOLVED"}]
    st.markdown(MEMBER_OVERVIEW_STYLES, unsafe_allow_html=True)
    key = f"member-overview-{patient.id}"
    with st.container(key="member-health-overview"):
        # A — reference point and quiet evidence access.
        with st.container(key="overview-heading"):
            heading, evidence = st.columns([5, 1])
            with heading:
                if baseline:
                    year = baseline.cycle_year or baseline.assessed_at.year
                    st.subheader(f"{year}年度健康基线")
                    date = baseline.confirmed_at or baseline.assessed_at
                    tone = "confirmed" if confirmed else "pending"
                    st.markdown(f'<div class="overview-baseline-meta"><b class="{tone}">{escape(app._label(baseline.status))}</b><span>建立时间：{date:%Y/%m/%d}</span>' + (f'<span>资料覆盖 {health.covered_count} / {len(health.coverage)}</span>' if health else '') + '</div>', unsafe_allow_html=True)
                else:
                    st.subheader("年度健康基线待建立")
                st.caption("这是本年度健康管理的参考起点，后续变化会与此比较。")
            if baseline:
                with evidence.popover("查看依据"):
                    with session_factory() as session:
                        payload = app._baseline_evidence_payload(session, patient.id, baseline)
                    app.render_evidence_panel(payload, key_scope=f"{key}-evidence", client_view=True)

            st.divider()
            management_stage(baseline, view.program)

        # D — the existing shared chart, not another graph implementation.
        with st.container(key="overview-trend"):
            st.subheader("从年度基线到现在")
            st.caption("查看关键健康指标相较年度基线的变化。")
            if health:
                render_baseline_progress(health, key_prefix=key, layout="member_overview")
            else:
                st.caption("目前还没有足够的后续数据形成趋势。" if baseline else "建立并确认年度基线后，即可与后续健康数据比较。")
                if baseline:
                    st.caption("基线尚待人工确认；当前健康记录可在详细资料中查看。")

        # C — never place empty domains before the actual concerns.
        with st.container(key="overview-focus"):
            st.subheader("当前重点关注")
            st.caption("本阶段需要持续管理或进一步确认的健康领域。")
            if focus:
                focus_items(focus)
                st.caption("需要持续关注 · 来自已确认年度资料，不自动等同于当前风险等级。")
            elif not problems:
                st.caption("暂无已确认的重点关注；缺少资料不能推断健康状况。")
            st.divider()
            if problems:
                first = problems[0]
                st.markdown("**当前跟进：** " + ux.business_text(first.title))
            if focus or problems:
                st.caption(f"下一步：由{ux.business_text(view.owner)}核对关注事项与后续安排。")
            details, history = st.columns([1, 1])
            if problems:
                with details.popover(f"持续关注事项 · {len(problems)}项"):
                    for item in problems:
                        ux.work_item(item.title, item.description, ux.owner(item.owner))
                        linked = next((t for t in view.active_tasks if t.health_problem_id == item.id), None)
                        if linked:
                            st.caption("下一步：" + ux.business_text(linked.title) + " · " + ux.due_date(linked.due_at))
            if focus or problems:
                if history.button("查看历次记录", key=f"{key}-history"):
                    app.request_navigation(surface="成员健康中心", member_page="历程", member_id=patient.id)

        # E/F — information-rich domains and one grouped supplement action.
        with st.container(key="overview-domain-coverage"):
            left, right = st.columns([1, 1.2], gap="large")
            with left, st.container(key="overview-health-domains"):
                st.subheader("健康领域概览")
                st.caption("各健康领域在已确认年度资料中的状态。")
                health_domain_summary(health.domains if health else ())
                st.caption("按年度基线整理；有资料不等于指标正常。")
            with right, st.container(key="overview-data-completeness"):
                st.subheader("资料完整性")
                st.caption("核对已覆盖资料与仍需补充的内容。")
                data_coverage(health)
                if missing:
                    st.write("待补充领域指标：" + "、".join(item.label for item in missing))
                elif health:
                    st.caption("各领域均有记录，资料完整度仍需按下方类别核对。")
                else:
                    st.caption("先补充体检和健康资料，由健康管理团队整理年度起点。")
                if health:
                    st.caption("覆盖按资料类别统计；已有自述资料不等于领域指标齐全。")
                st.caption("上传检查资料；用药、病史与生活方式信息由负责人核对。")
                if st.button("补充健康资料", key=f"{key}-supplement", type="primary"):
                    if baseline and not confirmed:
                        app._open_client_baseline(patient.id)
                        st.rerun()
                    else:
                        app._open_member_report_upload(patient.id)

            st.divider()
            # G — all retained detail surfaces, collapsed by default.
            with st.container(key="overview-details"):
                st.markdown("**详细资料**")
                if health:
                    _render_comparison_details(health, label="所有指标与当前对比")
                    with st.expander("健康领域完整说明"):
                        for item in available:
                            st.markdown("**" + ux.business_text(item.label) + "**")
                            st.write(ux.business_text(item.summary))
                if baseline:
                    with st.expander("年度基线完整资料"):
                        st.caption("历史年度、关键指标、参考范围、确认记录及修订依据。")
                        st.button("查看年度健康基线", key=f"client-health-baseline-open-{baseline.id}", on_click=app._open_client_baseline, args=(patient.id,))
                with st.expander("重要健康背景 · 用药与既往史"):
                    app._render_client_medical_archive(patient)
                with st.expander("体检报告与健康数据"):
                    if st.button("查看体检与检查", key=f"{key}-reports"):
                        app._open_member_report_upload(patient.id)
                    if st.button("查看当前健康变化", key=f"{key}-data"):
                        app.request_navigation(surface="成员健康中心", member_page="健康", member_id=patient.id, archive_view="健康数据")
