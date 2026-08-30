"""Build a concise factual brief for clinician review."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.models import Alert, HealthProblem, MedicationPlan, Observation


def build_doctor_brief(session: Session, patient_id: UUID, problem: HealthProblem, alert: Alert | None) -> str:
    """Return a non-diagnostic factual brief, with a clear clinician question."""
    medication_count = len(session.scalars(select(MedicationPlan).where(MedicationPlan.patient_id == patient_id, MedicationPlan.status == "active")).all())
    bp_count = len(session.scalars(select(Observation).where(Observation.patient_id == patient_id, Observation.metric_code.in_(["systolic_bp", "diastolic_bp"]))).all())
    evidence = alert.evidence_json if alert else {}
    dates = "、".join(evidence.get("local_dates", [])) or "未提供"
    return (
        f"问题：{problem.title}\n"
        f"筛查依据：{dates}；规则结果仅供复核，不构成诊断。\n"
        f"可用血压 Observation：{bp_count} 条；当前记录中的 active medication plans：{medication_count} 个。\n"
        "请基于完整病史、测量方法和临床判断确认后续管理安排；系统不会自动修改药物或剂量。"
    )
