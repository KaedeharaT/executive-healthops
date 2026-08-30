"""Legacy raw-event timeline retained for compatibility API/demo consumers.

New product surfaces use ``services.longitudinal.HealthTimelineService`` and
``TimelineV4Service``. This module is deliberately not the health-story UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.blood_pressure import build_blood_pressure_records
from executive_health_ai.models import (
    Alert, CareTask, DoctorReview, Encounter, FollowUp, HealthEvent, MedicationEvent,
    IngestionJob, Observation, SleepSession, Task,
)


@dataclass(frozen=True)
class TimelineItem:
    occurred_at: datetime
    category: str
    title: str
    detail: str
    source: str


def build_patient_timeline(
    session: Session, patient_id: UUID, days: int = 30
) -> list[TimelineItem]:
    """Deprecated compatibility projection; do not use in new product UI."""

    latest = session.scalar(
        select(Observation.observed_at)
        .where(Observation.patient_id == patient_id)
        .order_by(Observation.observed_at.desc())
    )
    if latest is None:
        return []
    start = latest - timedelta(days=days - 1)
    items: list[TimelineItem] = []
    observations = list(session.scalars(select(Observation).where(
        Observation.patient_id == patient_id, Observation.observed_at >= start
    )))
    for record in build_blood_pressure_records(observations):
        if record.is_complete:
            items.append(TimelineItem(record.observed_at, "blood_pressure", "血压测量", f"{record.systolic_bp} / {record.diastolic_bp} mmHg；心率 {record.heart_rate} 次/分钟", "标准化测量"))
    for observation in observations:
        if observation.metric_code == "glucose" and observation.ingestion_job_id is None and observation.observed_at.minute == 0:
            items.append(TimelineItem(observation.observed_at, "cgm", "CGM 关键读数", f"葡萄糖 {Decimal(observation.value_numeric)} mg/dL", observation.source))
    for job in session.scalars(select(IngestionJob).where(
        IngestionJob.patient_id == patient_id, IngestionJob.completed_at.is_not(None), IngestionJob.completed_at >= start
    )):
        if job.source_system in {"mock_cgm", "cgm"}:
            items.append(TimelineItem(job.completed_at or job.started_at, "ingestion", "CGM data imported", f"{job.records_created} readings · {job.status} · {job.records_invalid} invalid", job.source_system))
        elif job.records_created:
            items.append(TimelineItem(job.completed_at or job.started_at, "ingestion", "Health data imported", f"{job.source_system}: {job.records_created} observations · {job.status}", job.source_system))
    for session_item in session.scalars(select(SleepSession).where(
        SleepSession.patient_id == patient_id, SleepSession.sleep_end >= start
    )):
        items.append(TimelineItem(session_item.sleep_end, "sleep", "睡眠记录", f"睡眠 {session_item.total_sleep_minutes} 分钟；效率 {session_item.sleep_efficiency}%", session_item.source))
    for event in session.scalars(select(MedicationEvent).where(
        MedicationEvent.patient_id == patient_id, MedicationEvent.scheduled_at >= start
    )):
        title = "已记录服药" if event.status == "taken" else "服药计划"
        items.append(TimelineItem(event.taken_at or event.scheduled_at, "medication", title, f"状态：{event.status}", "用户记录"))
    for event in session.scalars(select(HealthEvent).where(
        HealthEvent.patient_id == patient_id, HealthEvent.start_at >= start
    )):
        items.append(TimelineItem(event.start_at, "health_event", _health_event_title(event.event_type), event.description, event.source))
    for encounter in session.scalars(select(Encounter).where(
        Encounter.patient_id == patient_id, Encounter.encounter_at >= start
    )):
        items.append(TimelineItem(encounter.encounter_at, "encounter", f"{encounter.department}就诊/会诊", encounter.reason, "医疗团队"))
    for task in session.scalars(select(CareTask).where(
        CareTask.patient_id == patient_id, CareTask.scheduled_at >= start
    )):
        items.append(TimelineItem(task.scheduled_at, "care_task", "健康任务", task.instruction, task.source))
    for alert in session.scalars(select(Alert).where(
        Alert.patient_id == patient_id, Alert.created_at >= start
    )):
        items.append(TimelineItem(alert.created_at, "alert", "运营 Alert", f"{alert.title}｜状态：{alert.status}｜严重程度：{alert.severity}", alert.source))
    for task in session.scalars(select(Task).where(Task.patient_id == patient_id, Task.created_at >= start)):
        items.append(TimelineItem(task.completed_at or task.created_at, "task", "运营任务", f"{task.title}｜状态：{task.status}", task.source))
    for review in session.scalars(select(DoctorReview).where(
        DoctorReview.patient_id == patient_id, DoctorReview.reviewed_at >= start
    )):
        items.append(TimelineItem(review.reviewed_at, "doctor_review", "医生复核", f"{review.department}｜状态：{review.status}", "doctor_review"))
    for follow_up in session.scalars(select(FollowUp).where(
        FollowUp.patient_id == patient_id, FollowUp.created_at >= start
    )):
        items.append(TimelineItem(follow_up.completed_at or follow_up.created_at, "follow_up", "随访", f"状态：{follow_up.status}；{follow_up.outcome or ''}", follow_up.source))
    return sorted(items, key=lambda item: item.occurred_at)


def _health_event_title(event_type: str) -> str:
    labels = {
        "business_trip": "商务出差", "alcohol": "商务晚宴/饮酒记录", "exercise": "活动记录",
        "meal": "饮食记录", "late_work": "晚间工作记录", "stress": "压力记录", "illness_note": "健康备注",
    }
    return labels.get(event_type, "生活事件")
