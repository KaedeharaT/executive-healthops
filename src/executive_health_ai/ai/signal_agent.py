"""Deterministic screening only; it creates reviewable alerts, not diagnoses."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.blood_pressure import TOKYO_TIMEZONE, build_blood_pressure_records
from executive_health_ai.models import AgentRun, Alert, Observation

SCREENING_SYSTOLIC = Decimal("140")
SCREENING_DIASTOLIC = Decimal("90")
REQUIRED_CONSECUTIVE_DAYS = 5


def screen_persistent_bp_signal(session: Session, patient_id: UUID) -> Alert | None:
    """Screen for five consecutive calendar days with a high BP reading.

    The thresholds are transparent operational screening settings.  The result
    explicitly requires manager/clinician review and is never a diagnosis.
    """
    observations = session.scalars(
        select(Observation).where(Observation.patient_id == patient_id, Observation.quality_flag == "valid", Observation.excluded_from_analysis.is_(False))
    ).all()
    daily = defaultdict(list)
    for item in build_blood_pressure_records(observations):
        if item.is_complete:
            daily[item.observed_at.astimezone(TOKYO_TIMEZONE).date()].append(item)
    days = sorted(daily)
    streak: list[object] = []
    qualifying: list[object] | None = None
    for day in days:
        has_screened_value = any(
            record.systolic_bp is not None
            and record.diastolic_bp is not None
            and (record.systolic_bp >= SCREENING_SYSTOLIC or record.diastolic_bp >= SCREENING_DIASTOLIC)
            for record in daily[day]
        )
        if has_screened_value and (not streak or day == streak[-1] + timedelta(days=1)):
            streak.append(day)
        elif has_screened_value:
            streak = [day]
        else:
            streak = []
        if len(streak) >= REQUIRED_CONSECUTIVE_DAYS:
            qualifying = streak[-REQUIRED_CONSECUTIVE_DAYS:]
            break
    if qualifying is None:
        session.add(AgentRun(patient_id=patient_id, agent_name="signal_agent", status="abstained", input_reference_json={"observation_count": len(observations)}, output_json={"reason": "insufficient_screening_evidence_or_no_persistent_pattern"}, needs_human_review=False))
        return None
    evidence = {"rule": "persistent_bp_screen_v0.1", "required_consecutive_days": REQUIRED_CONSECUTIVE_DAYS, "systolic_screening_value_mmhg": str(SCREENING_SYSTOLIC), "diastolic_screening_value_mmhg": str(SCREENING_DIASTOLIC), "local_dates": [str(day) for day in qualifying]}
    existing = session.scalar(select(Alert).where(Alert.patient_id == patient_id, Alert.alert_type == "persistent_bp_screen", Alert.status != "CLOSED"))
    if existing is None:
        existing = Alert(patient_id=patient_id, alert_type="persistent_bp_screen", title="连续 5 天血压数据需人工核实", finding="规则筛查发现连续 5 个本地日存在达到预设筛查值的完整血压记录；此为数据筛查，不构成诊断或治疗建议。", evidence_json=evidence, status="AI_SCREENED", severity="HIGH", responsible_role="health_manager", due_at=None, source="signal_agent_rule_v0.1")
        session.add(existing)
        status = "created_alert"
    else:
        status = "existing_alert"
    session.add(AgentRun(patient_id=patient_id, agent_name="signal_agent", status="completed", input_reference_json={"observation_count": len(observations)}, output_json={"result": status, "evidence": evidence}, needs_human_review=True))
    session.flush()
    return existing
