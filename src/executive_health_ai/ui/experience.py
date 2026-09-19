"""Shared, read-only projections and components for the four role experiences.

Storage identifiers never serve as labels. These projections do not infer risk,
clinical causality, device connectivity or completion from the presence of data.
"""
from __future__ import annotations

import html
import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from sqlalchemy import select

from executive_health_ai.models import Alert, DoctorReview, HealthAssessment, Observation
from executive_health_ai.ui.display import get_status_display
from executive_health_ai.ui.localization.zh_cn import OBSERVATION

LOCAL = ZoneInfo("Asia/Tokyo")
from executive_health_ai.ui.styles import TOKENS

UUID_PATTERN = re.compile(r"\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b")
METRIC_ALIASES = {"收缩压": "收缩压", "舒张压": "舒张压", "体重": "体重", "腰围": "腰围", "糖化血红蛋白": "糖化血红蛋白", "LDL-C": "低密度脂蛋白胆固醇", "HbA1c": "糖化血红蛋白"}


def metric_name(code):
    raw = str(code or "").strip()
    if "\\u" in raw:
        try:
            raw = raw.encode("ascii").decode("unicode_escape")
        except (UnicodeError, ValueError):
            pass
    return OBSERVATION.get(raw, METRIC_ALIASES.get(raw, raw if re.fullmatch(r"[\u4e00-\u9fff（） /·-]{2,30}", raw) else "健康数据"))


def business_text(value):
    decoded = re.sub(r"\\u([0-9a-fA-F]{4})", lambda match: chr(int(match[1], 16)), str(value or ""))
    text = UUID_PATTERN.sub("", decoded)
    for code in sorted(OBSERVATION, key=len, reverse=True):
        text = re.sub(r"\b" + re.escape(code) + r"\b", OBSERVATION[code], text)
    for code, label in {"Yellow RiskEvent": "需要持续关注", "RiskEvent": "健康关注事项", "AgentGoal": "长期管理", "PlanStep": "管理步骤", "WAITING_EVENT": "等待新的进展", "canonical_code": "指标", "provider_code": "数据来源", "raw_record": "原始资料", "ingestion_job": "数据导入", "traceback": "错误详情"}.items():
        text = text.replace(code, label)
    for code, label in {"health_manager": "健康管理师", "internal_doctor": "内部医生", "external_doctor": "外部医生", "care_team": "健康管理团队"}.items():
        text = re.sub(r"\b" + code + r"\b", label, text, flags=re.IGNORECASE)
    return text.strip()


def local_time(value):
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime.combine(value, datetime.min.time(), LOCAL)
    return value.replace(tzinfo=timezone.utc).astimezone(LOCAL) if value.tzinfo is None else value.astimezone(LOCAL)


def when(value, *, due=False, now=None):
    value = local_time(value)
    if value is None:
        return "待安排"
    now = local_time(now or datetime.now(LOCAL))
    days = (value.date() - now.date()).days
    if due and value < now:
        return f"已逾期{abs(days)}天" if days else "今天已逾期"
    if days == 0:
        return f"今天 {value:%H:%M}"
    if days == 1:
        return f"明天 {value:%H:%M}"
    return f"{value.year}年" + f"{value.month}月{value.day}日" if value.year != now.year else f"{value.month}月{value.day}日"


def inject_design(role="manager"):
    from executive_health_ai.ui.styles import LEGACY_STYLES, role_styles
    st.markdown(LEGACY_STYLES, unsafe_allow_html=True)
    st.markdown(role_styles(role), unsafe_allow_html=True)


def page_header(title, description="", eyebrow=""):
    if eyebrow:
        st.markdown(f"<div class='ux-eyebrow'>{html.escape(eyebrow)}</div>", unsafe_allow_html=True)
    st.title(title)
    if description:
        st.caption(description)


def status_badge(status):
    label = get_status_display(status) if str(status).isascii() else status
    st.markdown(f"<span class='ux-badge'>{html.escape(label)}</span>", unsafe_allow_html=True)


def owner(name):
    return "负责人：" + business_text(name or "健康管理团队")


def due_date(value, **kwargs):
    return when(value, due=True, **kwargs)


def next_action(text, responsible=None):
    st.markdown(f"<div class='ux-next'><b>下一步</b>　{html.escape(business_text(text))}<br><small>{html.escape(owner(responsible))}</small></div>", unsafe_allow_html=True)


def empty_state(title, action):
    st.caption(f"{title}。{action}")


def metric_row(values):
    if not values:
        return
    for col, (label, value) in zip(st.columns(len(values)), values):
        col.metric(label, value)


def work_item(title, detail, meta=""):
    st.markdown(f"<div class='ux-row'><b>{html.escape(business_text(title))}</b><br>{html.escape(business_text(detail))}<br><small>{html.escape(business_text(meta))}</small></div>", unsafe_allow_html=True)


def member_summary(patient, program, next_step):
    from executive_health_ai.ui.components import summary_strip
    page_header(patient.display_name or "成员", "", "成员360")
    summary_strip([("当前计划", business_text(program.title) if program else "尚未建立当前计划"),
        ("负责人", business_text(program.owner) if program and program.owner else "待确认"),
        ("下一步", business_text(next_step))])


def observations(session, patient_id, metric=None, since=None):
    query = select(Observation).where(Observation.patient_id == patient_id, Observation.source_deleted.is_(False), Observation.excluded_from_analysis.is_(False), Observation.quality_flag.in_(("valid", "manually_corrected")))
    if metric:
        query = query.where(Observation.metric_code == metric)
    if since:
        query = query.where(Observation.observed_at >= since)
    return list(session.scalars(query.order_by(Observation.observed_at)))


def pending_doctor_work(session, patient_id=None):
    reviews = select(DoctorReview).where(DoctorReview.status == "PENDING")
    baselines = select(HealthAssessment).where(HealthAssessment.status == "WAITING_MEDICAL_REVIEW")
    alerts = select(Alert).where(Alert.status == "WAITING_DOCTOR_REVIEW", Alert.health_problem_id.is_not(None))
    if patient_id:
        reviews = reviews.where(DoctorReview.patient_id == patient_id)
        baselines = baselines.where(HealthAssessment.patient_id == patient_id)
        alerts = alerts.where(Alert.patient_id == patient_id)
    rows = list(session.scalars(reviews))
    # A legacy alert already represented by a review is the same responsibility.
    linked = {r.health_problem_id for r in rows if r.health_problem_id}
    return rows + list(session.scalars(baselines)) + [a for a in session.scalars(alerts) if a.health_problem_id not in linked]


def sorted_work(items, now=None):
    now = local_time(now or datetime.now(LOCAL))
    return sorted(items, key=lambda x: (not (x.due_at and local_time(x.due_at) < now), x.priority > 1, not (x.due_at and local_time(x.due_at).date() == now.date()), x.status in {"等待医生", "等待成员"}, x.priority, local_time(x.due_at) or datetime.max.replace(tzinfo=LOCAL)))


def upcoming_service(rows, now=None):
    now = local_time(now or datetime.now(LOCAL))
    return next(iter(sorted((r for r in rows if r.status == "SCHEDULED" and r.scheduled_at and local_time(r.scheduled_at) >= now), key=lambda r: r.scheduled_at)), None)


def changes(rows, maximum=4):
    grouped = {}
    for row in rows:
        grouped.setdefault(row.metric_code, []).append(row)
    preferred = ["weight", "systolic_bp", "ldl_c", "hba1c", "steps", "sleep_duration"]
    result = []
    for code in [*preferred, *[c for c in grouped if c not in preferred]]:
        values = sorted(grouped.get(code, []), key=lambda r: r.observed_at)
        if len(values) >= 2 and values[0].observed_at != values[-1].observed_at:
            first, last = values[0], values[-1]
            result.append((metric_name(code), f"{float(first.value_numeric):g} → {float(last.value_numeric):g} {last.unit}", f"{when(first.observed_at)} 至 {when(last.observed_at)} · 观察变化，不代表干预效果"))
        if len(result) == maximum:
            break
    return result


def baseline_summary(baseline, rows, *, compact=False):
    st.subheader("年度健康基线")
    if not baseline:
        empty_state("尚未建立健康基线", "上传体检报告后，由健康管理师核对并确认。")
        return
    st.markdown(f"**{baseline.cycle_year or baseline.assessed_at.year}年度健康基线** · {get_status_display(baseline.status)}")
    st.caption(f"建立时间：{when(baseline.confirmed_at or baseline.assessed_at)} · 确认后冻结，后续变化单独记录")
    snapshot = baseline.baseline_json or {}
    latest = {r.metric_code: r for r in rows}
    table = []
    for value in snapshot.get("key_metrics", [])[:4 if compact else 6]:
        code = value.get("metric") or value.get("metric_code")
        current = latest.get(code)
        table.append({"关键指标": metric_name(code), "基线": f"{value.get('value', '未记录')} {value.get('unit', '')}", "当前": f"{float(current.value_numeric):g} {current.unit}" if current else "暂无后续数据"})
    if table:
        st.dataframe(pd.DataFrame(table), hide_index=True, width="stretch")
    st.caption(f"资料覆盖：已记录 {len(snapshot.get('key_metrics', []))} 项关键指标；缺失资料不推断为正常。")


def evidence_summary(payload):
    raw = payload.get("raw_evidence")
    status = payload.get("evidence_status")
    label = "完整依据" if raw and status in {"COMPLETE", "AVAILABLE"} else "部分依据" if raw else "暂无原始依据"
    st.markdown(f"**报告依据 · {label}**")
    st.caption("来源：" + business_text(payload.get("source_name") or payload.get("data_source") or "待补充"))
    if raw:
        st.write(business_text(raw))
    else:
        st.caption("目前仅有整理信息。请先核对原报告，再作医学判断。")
