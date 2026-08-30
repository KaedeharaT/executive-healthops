"""Transparent rule-based associations and clinician-review summaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.blood_pressure import build_blood_pressure_records
from executive_health_ai.models import HealthEvent, MedicationEvent, Observation, SleepSession
from executive_health_ai.services.analysis import (
    calculate_cgm_summary, calculate_medication_adherence, calculate_sleep_summary,
)


@dataclass(frozen=True)
class PossibleAssociation:
    insight_type: str
    title: str
    content: str
    evidence_count: int
    confidence: float
    status: str


class InsightNarrator(Protocol):
    """Replaceable narration boundary; V0.1 deliberately has no LLM call."""

    def narrate(self, insight: PossibleAssociation) -> str: ...


class DeterministicNarrator:
    """Chinese rule-based narrator with an explicit non-causality boundary."""

    def narrate(self, insight: PossibleAssociation) -> str:
        return f"{insight.content} 这是时间关联，不能证明因果。"


def generate_possible_associations(session: Session, patient_id: UUID) -> list[PossibleAssociation]:
    """Find repeatable temporal co-occurrences or abstain when evidence is sparse."""

    events = list(session.scalars(select(HealthEvent).where(HealthEvent.patient_id == patient_id)))
    sleeps = list(session.scalars(select(SleepSession).where(SleepSession.patient_id == patient_id)))
    observations = list(session.scalars(select(Observation).where(Observation.patient_id == patient_id)))
    medication_events = list(session.scalars(select(MedicationEvent).where(MedicationEvent.patient_id == patient_id)))
    associations: list[PossibleAssociation] = []
    dinners = [event for event in events if event.event_type in {"alcohol", "meal"}]
    matched_sleep = sum(any(0 <= (sleep.sleep_start - dinner.start_at).total_seconds() <= 12 * 3600 for sleep in sleeps) for dinner in dinners)
    if matched_sleep >= 2:
        associations.append(PossibleAssociation("possible_association", "晚间活动与入睡时间", f"过去 {len(dinners)} 次商务晚宴或饮食事件中，有 {matched_sleep} 次在随后 12 小时内记录到睡眠会话。", matched_sleep, 0.65, "needs_clinician_review"))
    trips = [event for event in events if event.event_type == "business_trip"]
    trip_sleep = sum(any(event.start_at <= sleep.sleep_end <= (event.end_at or event.start_at) + timedelta(days=1) for sleep in sleeps) for event in trips)
    if trip_sleep >= 1:
        associations.append(PossibleAssociation("possible_association", "出差与睡眠记录", f"{trip_sleep} 次出差时间段与睡眠记录波动在时间上重合。", trip_sleep, 0.55, "needs_clinician_review"))
    cgm = calculate_cgm_summary(observations)
    meal_count = sum(event.event_type == "meal" for event in events)
    if cgm.count >= 20 and meal_count >= 1:
        associations.append(PossibleAssociation("possible_association", "CGM 与饮食记录", f"已有 {cgm.count} 条 CGM 数据及 {meal_count} 条饮食记录，可用于与医生讨论餐后时间序列模式。", meal_count, 0.60, "needs_clinician_review"))
    adherence = calculate_medication_adherence(medication_events)
    if adherence.scheduled_count >= 3:
        associations.append(PossibleAssociation("possible_association", "服药记录与健康数据", f"本期共有 {adherence.scheduled_count} 条服药计划记录，可与血压、CGM 与睡眠时间轴并列查看。", adherence.scheduled_count, 0.50, "needs_clinician_review"))
    if associations:
        return associations
    return [PossibleAssociation("abstain", "跨域关联暂不判断", "现有跨域记录数量不足，暂不输出时间关联结论。", 0, 0.0, "insufficient_data")]


def generate_clinician_summary(session: Session, patient_id: UUID, period_days: int = 30) -> dict[str, object]:
    """Create material for clinician review, never a treatment recommendation."""

    observations = list(session.scalars(select(Observation).where(Observation.patient_id == patient_id)))
    records = build_blood_pressure_records(observations)
    cgm = calculate_cgm_summary(observations)
    sleep = calculate_sleep_summary(session.scalars(select(SleepSession).where(SleepSession.patient_id == patient_id)))
    adherence = calculate_medication_adherence(session.scalars(select(MedicationEvent).where(MedicationEvent.patient_id == patient_id)))
    associations = generate_possible_associations(session, patient_id)
    return {
        "period_days": period_days,
        "blood_pressure_measurements": len([record for record in records if record.is_complete]),
        "cgm": cgm,
        "sleep": sleep,
        "medication_adherence": adherence,
        "possible_associations": associations,
        "questions_for_clinician_review": [
            "近期晨间血压趋势与睡眠缩短同时出现时，是否需要进一步确认既定测量方法或现有管理计划？",
            "请确认 CGM、生活事件与服药记录的时间线是否完整，再决定是否需要后续随访。",
        ],
        "safety_note": "用于健康管理与医生沟通，不构成疾病诊断或治疗建议。",
    }
