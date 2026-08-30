"""Create the complete, idempotent V0.1 synthetic executive-health story."""

from __future__ import annotations

import argparse
import math
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Callable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from executive_health_ai.blood_pressure import (
    BloodPressureMeasurement, DEMO_PATIENT_EXTERNAL_ID, TOKYO_TIMEZONE, persist_measurement,
)
from executive_health_ai.database import SessionLocal, engine
from executive_health_ai.models import (
    AIInsight, AgentRun, Alert, AuditLog, CarePlan, CareTask, ClinicalRecommendation,
    Device, DoctorReview, Encounter, FollowUp, HealthEvent, HealthProblem, ManagementPlan,
    MedicationEvent, MedicationPlan, Observation, Patient, RawData, ServiceEvent,
    SleepSession, Task, AnnualHealthAccount, ExecutionBarrier, HealthJourney,
    HealthProgram, OutcomeEvaluation, ProgramPhase, WeeklyReview, ExternalIdentity,
    IngestionJob, RawIngestionRecord,
    Document, ExternalReferral, HealthAssessment, ManagementRule, ManagementSignal,
    MemberDeviceAssignment, ReportExtractionCandidate, ReportExtractionRun,
)
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.chronic_care import (
    adjust_management_plan, create_annual_account, create_assessment, create_program,
    create_program_task, record_execution_barrier, record_outcome_evaluation,
    record_weekly_review, transition_to_stabilization,
)
from executive_health_ai.services.ingestion import import_cgm_rows, import_sleep_rows
from executive_health_ai.services.insights import DeterministicNarrator, generate_possible_associations
from executive_health_ai.services.longitudinal import ManagementRoutingService
from executive_health_ai.services.workflow import (
    complete_follow_up, confirm_alert_as_manager, record_doctor_review, screen_member,
)

DEMO_SOURCE = "v01_synthetic_demo"
DEMO_TIMEZONE = "Asia/Tokyo"
DEMO_END_DATE = date(2026, 8, 7)
DEMO_START_DATE = DEMO_END_DATE - timedelta(days=29)


def local_datetime(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=TOKYO_TIMEZONE)


def seed_full_demo(session_factory: Callable[[], Session] = SessionLocal) -> dict[str, int]:
    """Add missing records for the fixed 30-day synthetic patient story."""

    created = {"patients": 0, "devices": 0, "observations": 0, "sleep_sessions": 0, "medication_events": 0, "care_tasks": 0}
    with session_factory() as session:
        patient = session.scalar(select(Patient).where(Patient.external_id == DEMO_PATIENT_EXTERNAL_ID))
        if patient is None:
            patient = Patient(external_id=DEMO_PATIENT_EXTERNAL_ID, display_name="Demo Executive A", birth_date=date(1974, 4, 18), sex="male", timezone=DEMO_TIMEZONE)
            session.add(patient)
            session.flush()
            created["patients"] += 1
        devices = _ensure_devices(session, patient.id)
        created["devices"] += sum(device[1] for device in devices.values())
        bp_device = devices["bp_monitor"][0]
        cgm_device = devices["cgm"][0]
        sleep_device = devices["sleep_tracker"][0]

        for index in range(30):
            day = DEMO_START_DATE + timedelta(days=index)
            systolic, diastolic = _bp_values(index)
            for hour, offset in ((7, 0), (20, 2)):
                measurement = BloodPressureMeasurement(
                    observed_at=local_datetime(day, hour, 30),
                    systolic_bp=Decimal(systolic + offset),
                    diastolic_bp=Decimal(diastolic + (1 if hour == 20 else 0)),
                    heart_rate=Decimal(68 + (index % 4) + (3 if hour == 20 else 0)),
                )
                count, _ = persist_measurement(session, patient.id, bp_device.id, measurement, "yuwell_synthetic_adapter")
                created["observations"] += count

        cgm_rows = _generate_cgm_rows()
        created["observations"] += import_cgm_rows(session, patient.id, cgm_device.id, cgm_rows, "cgm_synthetic_adapter")
        sleep_rows = _generate_sleep_rows()
        created["sleep_sessions"] += import_sleep_rows(session, patient.id, sleep_device.id, sleep_rows, "oura_synthetic_adapter")

        _ensure_health_events(session, patient.id)
        plans = _ensure_medication_plans(session, patient.id)
        created["medication_events"] += _ensure_medication_events(session, patient.id, plans)
        encounters = _ensure_encounters(session, patient.id)
        _ensure_recommendations(session, patient.id, encounters)
        care_plan = _ensure_care_plan(session, patient.id)
        created["care_tasks"] += _ensure_care_tasks(session, patient.id, care_plan)
        session.flush()
        _ensure_rule_insights(session, patient.id)
        program = _ensure_chronic_care_demo(session, patient.id)
        _ensure_operations_demo(session, patient.id, program)
        _ensure_longitudinal_demo(session, patient.id)
        session.commit()
    return created


def reset_demo_data(session_factory: Callable[[], Session] = SessionLocal) -> bool:
    """Delete only this synthetic patient's related data; never touch other patients."""

    with session_factory() as session:
        patient = session.scalar(select(Patient).where(Patient.external_id == DEMO_PATIENT_EXTERNAL_ID))
        if patient is None:
            return False
        patient_id = patient.id
        program_ids = list(session.scalars(select(HealthProgram.id).where(HealthProgram.patient_id == patient_id)))
        journey_ids = list(session.scalars(select(HealthJourney.id).where(HealthJourney.patient_id == patient_id)))
        # Gateway records are also synthetic for this fixed demo member.  Remove them
        # before the member so old failed/unmatched demo jobs cannot pollute the UI.
        synthetic_gateway_job_ids = list(session.scalars(
            select(IngestionJob.id).where(IngestionJob.created_by == "synthetic_gateway_demo")
        ))
        if synthetic_gateway_job_ids:
            session.execute(delete(RawIngestionRecord).where(RawIngestionRecord.job_id.in_(synthetic_gateway_job_ids)))
            session.execute(delete(IngestionJob).where(IngestionJob.id.in_(synthetic_gateway_job_ids)))
        session.execute(delete(RawIngestionRecord).where(RawIngestionRecord.patient_id == patient_id))
        session.execute(delete(IngestionJob).where(IngestionJob.patient_id == patient_id))
        session.execute(delete(ExternalIdentity).where(ExternalIdentity.patient_id == patient_id))
        for model in (
            AuditLog, AgentRun, ServiceEvent, FollowUp, ExecutionBarrier, OutcomeEvaluation,
            Task, ManagementPlan, DoctorReview, Alert, HealthProblem, Observation, SleepSession,
            AIInsight, ClinicalRecommendation, CareTask, MedicationEvent, Encounter, CarePlan,
            MedicationPlan, HealthEvent, RawData, Device,
        ):
            session.execute(delete(model).where(model.patient_id == patient_id))
        session.execute(delete(ManagementSignal).where(ManagementSignal.patient_id == patient_id))
        session.execute(delete(MemberDeviceAssignment).where(MemberDeviceAssignment.patient_id == patient_id))
        session.execute(delete(ExternalReferral).where(ExternalReferral.patient_id == patient_id))
        session.execute(delete(HealthAssessment).where(HealthAssessment.patient_id == patient_id))
        report_ids = list(session.scalars(select(Document.id).where(Document.patient_id == patient_id)))
        if report_ids:
            run_ids = list(session.scalars(select(ReportExtractionRun.id).where(ReportExtractionRun.document_id.in_(report_ids))))
            if run_ids: session.execute(delete(ReportExtractionCandidate).where(ReportExtractionCandidate.extraction_run_id.in_(run_ids)))
            session.execute(delete(ReportExtractionRun).where(ReportExtractionRun.document_id.in_(report_ids)))
            session.execute(delete(Document).where(Document.id.in_(report_ids)))
        if program_ids:
            session.execute(delete(WeeklyReview).where(WeeklyReview.program_id.in_(program_ids)))
            session.execute(delete(ProgramPhase).where(ProgramPhase.program_id.in_(program_ids)))
        if journey_ids:
            session.execute(delete(AnnualHealthAccount).where(AnnualHealthAccount.journey_id.in_(journey_ids)))
        session.execute(delete(HealthProgram).where(HealthProgram.patient_id == patient_id))
        session.execute(delete(HealthJourney).where(HealthJourney.patient_id == patient_id))
        session.delete(patient)
        session.commit()
    return True


def _ensure_devices(session: Session, patient_id: object) -> dict[str, tuple[Device, int]]:
    definitions = {
        "bp_monitor": ("Yuwell", "YE670A", "DEMO-YUWELL-0001", "yuwell_synthetic_adapter"),
        "cgm": ("Demo CGM", "CGM-14D", "DEMO-CGM-0001", "cgm_synthetic_adapter"),
        "sleep_tracker": ("Demo Sleep", "Oura-compatible demo", "DEMO-SLEEP-0001", "oura_synthetic_adapter"),
    }
    result: dict[str, tuple[Device, int]] = {}
    for device_type, (manufacturer, model, serial, source) in definitions.items():
        device = session.scalar(select(Device).where(Device.patient_id == patient_id, Device.serial_number == serial))
        if device is None:
            device = Device(patient_id=patient_id, manufacturer=manufacturer, model=model, device_type=device_type, serial_number=serial, source_system=source, active=True)
            session.add(device)
            session.flush()
            result[device_type] = (device, 1)
        else:
            result[device_type] = (device, 0)
    return result


def _bp_values(index: int) -> tuple[int, int]:
    """Stable early, event-period variation, a short rise, then partial recovery."""

    if index < 10:
        return 132 + (index % 3), 84 + (index % 2)
    if index < 19:
        return 136 + ((index * 2) % 5), 86 + (index % 3)
    if index < 24:
        return 140 + (index - 19), 89 + ((index - 19) // 2)
    return 142 - (index - 24), 90 - ((index - 24) // 2)


def _generate_cgm_rows() -> list[tuple[datetime, Decimal]]:
    rows: list[tuple[datetime, Decimal]] = []
    start = DEMO_END_DATE - timedelta(days=13)
    for day_index in range(14):
        day = start + timedelta(days=day_index)
        for slot in range(96):
            hour, minute = divmod(slot * 15, 60)
            value = 106 + 7 * math.sin(slot / 96 * math.tau)
            if 28 <= slot <= 38 or 48 <= slot <= 58 or 76 <= slot <= 88:
                value += 26 - abs((slot % 20) - 10) * 1.8
            if day_index in {4, 5, 9} and slot >= 72:
                value += 8
            rows.append((local_datetime(day, hour, minute), Decimal(str(round(value, 1)))))
    return rows


def _generate_sleep_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(30):
        day = DEMO_START_DATE + timedelta(days=index)
        delayed = index in {11, 12, 15, 20, 21}
        start_hour = 0 if delayed else 23
        start_minute = 35 if delayed else 10 + (index % 3) * 10
        sleep_start = local_datetime(day, start_hour, start_minute)
        if start_hour == 0:
            sleep_start += timedelta(days=1)
        total = 405 - (30 if delayed else 0) + (index % 4) * 8
        awake = 42 + (15 if delayed else 0) + (index % 3) * 4
        sleep_end = sleep_start + timedelta(minutes=total + awake)
        rows.append({
            "sleep_start": sleep_start, "sleep_end": sleep_end, "total_sleep_minutes": total,
            "deep_sleep_minutes": 78 + (index % 4) * 3, "rem_sleep_minutes": 86 + (index % 5) * 2,
            "awake_minutes": awake, "sleep_efficiency": Decimal(str(round(total / (total + awake) * 100, 1))),
            "avg_heart_rate": Decimal(57 + (2 if delayed else 0) + index % 3),
            "lowest_heart_rate": Decimal(49 + index % 3), "avg_hrv": Decimal(38 - (3 if delayed else 0) + index % 4),
            "stage_segments_json": [
                {"stage": "LIGHT", "minutes": str(max(1, total - (78 + (index % 4) * 3) - (86 + (index % 5) * 2)))},
                {"stage": "DEEP", "minutes": str(78 + (index % 4) * 3)},
                {"stage": "REM", "minutes": str(86 + (index % 5) * 2)},
                {"stage": "AWAKE", "minutes": str(awake)},
            ],
        })
    return rows


def _ensure_longitudinal_demo(session: Session, patient_id: object) -> None:
    """Add only synthetic records that demonstrate longitudinal HealthOps."""
    if session.scalar(select(HealthAssessment).where(HealthAssessment.patient_id == patient_id)) is None:
        session.add(HealthAssessment(patient_id=patient_id, assessment_type="INITIAL", version=1, title="初始健康评估", summary="合成演示：基于已确认体检、设备和既有管理记录的人工基线。", baseline_json={"weight": 81, "sleep_duration_minutes": 405, "activity": "synthetic"}, created_by="合成健康管理师", assessed_at=local_datetime(DEMO_START_DATE, 9)))
    for provider, category, status in (("apple_health", "WELLNESS", "PENDING"), ("mock_cgm", "MEDICAL_MONITOR", "MOCK"), ("mock_yuwell", "MEDICAL_MONITOR", "MOCK")):
        if session.scalar(select(MemberDeviceAssignment).where(MemberDeviceAssignment.patient_id == patient_id, MemberDeviceAssignment.provider == provider)) is None:
            session.add(MemberDeviceAssignment(patient_id=patient_id, provider=provider, device_category=category, assignment_status="ASSIGNED", connection_status=status, assigned_by="合成健康管理师", notes="合成演示设备分配"))
    rule = session.scalar(select(ManagementRule).where(ManagementRule.code == "SYNTHETIC_LOW_ACTIVITY_MANAGEMENT"))
    if rule is None:
        rule = ManagementRule(name="合成活动持续管理信号", code="SYNTHETIC_LOW_ACTIVITY_MANAGEMENT", canonical_code="steps", condition_type="THRESHOLD", threshold_config={"operator": "<", "value": "6000"}, window_config={"minimum_samples": 1}, recommended_route="HEALTH_MANAGER", version="synthetic-v1", review_status="APPROVED", is_active=True, source_reference="SYNTHETIC TEST ONLY — 非临床规则")
        session.add(rule); session.flush()
    for index in range(30):
        day = DEMO_START_DATE + timedelta(days=index)
        for code, value, unit in (("steps", 5200 + (index % 7) * 720, "count"), ("active_calories", 280 + (index % 6) * 35, "kcal"), ("exercise_minutes", 28 + (index % 5) * 7, "minutes")):
            source_id = f"synthetic-longitudinal-{code}-{day.isoformat()}"
            if session.scalar(select(Observation).where(Observation.patient_id == patient_id, Observation.source_record_id == source_id)) is None:
                item = Observation(patient_id=patient_id, observed_at=local_datetime(day, 21), metric_code=code, value_numeric=Decimal(value), unit=unit, source="synthetic_longitudinal", quality_flag="valid", source_record_id=source_id)
                session.add(item); session.flush()
                if code == "steps": ManagementRoutingService().evaluate_observation(session, item.id)
    documents: list[Document] = []
    for name, hash_value, report_date, ldl in (("合成年度体检报告（较早）", "synthetic-report-a", date(2026, 1, 10), "3.8"), ("合成年度体检报告（较新）", "synthetic-report-b", date(2026, 7, 10), "4.2")):
        document = session.scalar(select(Document).where(Document.patient_id == patient_id, Document.title == name))
        if document is None:
            document = Document(patient_id=patient_id, document_type="health_check_report", title=name, storage_reference=f"synthetic://{hash_value}", source="synthetic_demo", status="AVAILABLE")
            session.add(document); session.flush()
        documents.append(document)
        run = session.scalar(select(ReportExtractionRun).where(ReportExtractionRun.document_id == document.id))
        if run is None:
            run = ReportExtractionRun(document_id=document.id, patient_id=patient_id, status="COMPLETED", parser_version="synthetic-v1", canonical_registry_version="synthetic-v1", file_hash=hash_value, file_type="TXT", detected_report_date=report_date, candidate_count=2, completed_at=local_datetime(report_date, 12))
            session.add(run); session.flush()
            session.add(ReportExtractionCandidate(extraction_run_id=run.id, document_id=document.id, patient_id=patient_id, candidate_type="OBSERVATION", canonical_code="ldl", raw_name="LDL", normalized_value=ldl, unit="mmol/L", confidence="HIGH", extraction_method="RULE", evidence_text=f"合成 LDL {ldl}", status="CONFIRMED"))
            session.add(ReportExtractionCandidate(extraction_run_id=run.id, document_id=document.id, patient_id=patient_id, candidate_type="FINDING", summary="合成影像检查结论", confidence="MEDIUM", extraction_method="LLM", evidence_text="合成影像检查结论", status="CONFIRMED"))
    if session.scalar(select(ExternalReferral).where(ExternalReferral.patient_id == patient_id)) is None:
        session.add(ExternalReferral(patient_id=patient_id, specialty="合成外部专科", reason="合成演示：由内部医生人工建议外部协同。", question="请人工确认后续线下协同安排。", organization="合成外部机构", status="WAITING_FEEDBACK"))


def _ensure_health_events(session: Session, patient_id: object) -> None:
    entries = [
        (10, 8, "business_trip", "前往大阪参加客户会议。", "moderate"), (12, 18, "business_trip", "东京返程并完成晚间会议。", "moderate"),
        (11, 20, "alcohol", "商务晚宴记录，已注明仅作时间线背景。", "moderate"), (15, 20, "alcohol", "商务晚宴记录，已注明仅作时间线背景。", "moderate"),
        (20, 20, "alcohol", "客户晚餐记录，已注明仅作时间线背景。", "moderate"), (22, 19, "meal", "工作日晚餐记录。", "low"),
        (4, 7, "exercise", "晨间步行 30 分钟。", "low"), (7, 7, "exercise", "晨间步行 30 分钟。", "low"), (18, 7, "exercise", "晨间步行 30 分钟。", "low"), (26, 7, "exercise", "晨间步行 30 分钟。", "low"),
        (14, 23, "late_work", "晚间工作至较晚时间。", "moderate"), (21, 23, "late_work", "晚间工作至较晚时间。", "moderate"),
    ]
    for offset, hour, event_type, description, severity in entries:
        start = local_datetime(DEMO_START_DATE + timedelta(days=offset), hour)
        exists = session.scalar(select(HealthEvent).where(HealthEvent.patient_id == patient_id, HealthEvent.start_at == start, HealthEvent.event_type == event_type))
        if exists is None:
            session.add(HealthEvent(patient_id=patient_id, start_at=start, end_at=start + timedelta(hours=1), event_type=event_type, description=description, severity=severity, source=DEMO_SOURCE))


def _ensure_medication_plans(session: Session, patient_id: object) -> list[MedicationPlan]:
    definitions = [
        ("演示用药记录 A", "", "按医嘱记录", "", "每日一次", time(8, 0), "心内科"),
        ("演示用药记录 B", "", "按医嘱记录", "", "每日一次", time(20, 0), "内分泌科"),
        ("演示用药记录 C", "", "按医嘱记录", "", "按既定计划", time(22, 30), "睡眠相关咨询"),
    ]
    plans: list[MedicationPlan] = []
    for drug, generic, dose, unit, frequency, scheduled, department in definitions:
        plan = session.scalar(select(MedicationPlan).where(MedicationPlan.patient_id == patient_id, MedicationPlan.drug_name == drug))
        if plan is None:
            plan = MedicationPlan(patient_id=patient_id, drug_name=drug, generic_name=generic, dose=dose, dose_unit=unit, frequency=frequency, route="演示记录", scheduled_time=scheduled, start_date=DEMO_START_DATE, prescriber_name="演示医生", department=department, status="active")
            session.add(plan)
            session.flush()
        plans.append(plan)
    return plans


def _ensure_medication_events(session: Session, patient_id: object, plans: list[MedicationPlan]) -> int:
    created = 0
    for day_offset in range(30):
        day = DEMO_START_DATE + timedelta(days=day_offset)
        for plan_index, plan in enumerate(plans[:2]):
            assert plan.scheduled_time is not None
            scheduled = local_datetime(day, plan.scheduled_time.hour, plan.scheduled_time.minute)
            existing = session.scalar(select(MedicationEvent).where(MedicationEvent.medication_plan_id == plan.id, MedicationEvent.scheduled_at == scheduled))
            if existing is None:
                missed = (day_offset, plan_index) in {(11, 1), (21, 0), (22, 1)}
                session.add(MedicationEvent(patient_id=patient_id, medication_plan_id=plan.id, scheduled_at=scheduled, taken_at=None if missed else scheduled + timedelta(minutes=10), status="missed" if missed else "taken"))
                created += 1
    return created


def _ensure_encounters(session: Session, patient_id: object) -> dict[str, Encounter]:
    entries = {
        "cardiology": (18, 10, "consultation", "心内科", "演示心内科医生", "复核连续血压记录与测量流程。"),
        "endocrine": (21, 11, "consultation", "内分泌科", "演示内分泌科医生", "查看 CGM 时间序列与生活记录。"),
        "sleep": (23, 14, "follow_up", "睡眠相关咨询", "演示睡眠咨询医生", "讨论出差期间睡眠记录波动。"),
        "mdt": (27, 15, "multidisciplinary_review", "联合会诊", "演示多学科团队", "汇总多来源数据，形成待确认的统一管理计划。"),
    }
    result: dict[str, Encounter] = {}
    for key, (offset, hour, encounter_type, department, clinician, reason) in entries.items():
        at = local_datetime(DEMO_START_DATE + timedelta(days=offset), hour)
        encounter = session.scalar(select(Encounter).where(Encounter.patient_id == patient_id, Encounter.encounter_at == at, Encounter.department == department))
        if encounter is None:
            encounter = Encounter(patient_id=patient_id, encounter_at=at, encounter_type=encounter_type, department=department, clinician_name=clinician, reason=reason, summary="仅用于 Demo 的会诊记录；未产生自动诊断或处方调整。", status="completed")
            session.add(encounter)
            session.flush()
        result[key] = encounter
    return result


def _ensure_recommendations(session: Session, patient_id: object, encounters: dict[str, Encounter]) -> None:
    entries = [
        ("cardiology", "数据复核", "已确认：继续按既定流程规范记录血压，并在随访时共同查看时间序列。"),
        ("endocrine", "记录复核", "已确认：继续记录 CGM 与关键饮食/活动时间，供后续沟通使用。"),
        ("sleep", "生活节律", "已确认：继续记录睡眠时间与出差背景，供后续随访讨论。"),
    ]
    for key, recommendation_type, content in entries:
        encounter = encounters[key]
        exists = session.scalar(select(ClinicalRecommendation).where(ClinicalRecommendation.encounter_id == encounter.id, ClinicalRecommendation.recommendation_type == recommendation_type))
        if exists is None:
            session.add(ClinicalRecommendation(encounter_id=encounter.id, patient_id=patient_id, department=encounter.department, clinician_name=encounter.clinician_name, recommendation_type=recommendation_type, content=content, status="confirmed"))


def _ensure_care_plan(session: Session, patient_id: object) -> CarePlan:
    plan = session.scalar(select(CarePlan).where(CarePlan.patient_id == patient_id, CarePlan.title == "演示：连续健康管理计划"))
    if plan is None:
        plan = CarePlan(patient_id=patient_id, title="演示：连续健康管理计划", condition="慢病健康管理演示", goal="在同一时间轴中持续记录既定测量、用药与生活信息，供医生随访沟通。", start_date=DEMO_END_DATE, end_date=DEMO_END_DATE + timedelta(days=30), primary_clinician="演示多学科团队", status="active")
        session.add(plan)
        session.flush()
    return plan


def _ensure_care_tasks(session: Session, patient_id: object, plan: CarePlan) -> int:
    entries = [
        (7, 30, "measure_bp", "按既定流程完成晨间血压测量。"), (8, 0, "take_medication", "完成既定服药计划的记录。"),
        (19, 30, "walk", "晚饭后完成简单活动任务。"), (21, 0, "check_cgm", "检查 CGM 数据是否已正常同步。"),
        (22, 30, "sleep_preparation", "完成睡前准备并记录作息。"),
    ]
    created = 0
    for hour, minute, task_type, instruction in entries:
        scheduled = local_datetime(DEMO_END_DATE, hour, minute)
        exists = session.scalar(select(CareTask).where(CareTask.care_plan_id == plan.id, CareTask.scheduled_at == scheduled, CareTask.task_type == task_type))
        if exists is None:
            session.add(CareTask(care_plan_id=plan.id, patient_id=patient_id, task_type=task_type, instruction=instruction, scheduled_at=scheduled, due_at=scheduled + timedelta(hours=2), status="pending", source="clinician_confirmed_demo"))
            created += 1
    return created


def _ensure_rule_insights(session: Session, patient_id: object) -> None:
    narrator = DeterministicNarrator()
    for association in generate_possible_associations(session, patient_id):
        exists = session.scalar(select(AIInsight).where(AIInsight.patient_id == patient_id, AIInsight.title == association.title))
        if exists is None:
            session.add(AIInsight(patient_id=patient_id, insight_type=association.insight_type, title=association.title, content=narrator.narrate(association), confidence=Decimal(str(association.confidence)), status=association.status, needs_clinician_review=True, evidence_json={"evidence_count": association.evidence_count, "rule": "temporal_association_v0.1"}))


def _ensure_chronic_care_demo(session: Session, patient_id: object) -> HealthProgram | None:
    """Create the V0.2 continuous-management story using only synthetic facts."""

    existing = session.scalar(select(HealthProgram).where(HealthProgram.patient_id == patient_id, HealthProgram.program_type == "NINETY_DAY"))
    if existing is not None:
        return existing
    journey = create_assessment(
        session, patient_id, "体检与连续记录提示体重、糖代谢风险、血压波动及睡眠不足需要持续人工跟进。",
        "改善体重与代谢状态", "HIGH", ["改善睡眠", "提高运动量"],
        {"weight": "86 kg", "sleep": "5.8 h", "exercise": "1 次/周", "morning_bp": "146/94 mmHg"},
        "演示健康管理师", "演示心内科医生",
    )
    metabolic = HealthProblem(patient_id=patient_id, title="体重与糖代谢风险", description="合成体检与生活记录显示的管理优先事项；不构成疾病诊断。", severity="HIGH", responsible_role="health_manager", owner="演示健康管理师", source="synthetic_assessment")
    sleep = HealthProblem(patient_id=patient_id, title="长期睡眠不足", description="合成睡眠记录提示的管理优先事项；需要持续观察。", severity="MEDIUM", responsible_role="health_manager", owner="演示健康管理师", source="synthetic_assessment")
    session.add_all([metabolic, sleep])
    session.flush()
    program = create_program(session, journey, "NINETY_DAY", "2026 Q3 90-Day Metabolic Health Program", "改善体重与代谢状态", ["改善睡眠", "提高运动量"], date(2026, 5, 10), "演示健康管理师", "演示心内科医生", [metabolic, sleep], date(2026, 8, 7))
    metabolic.priority_rank, sleep.priority_rank = 2, 3
    task = create_program_task(session, program, "出差期间每天 20 分钟步行", "将原每周运动 4 次的安排调整为出差期间可执行的每日步行记录。", local_datetime(date(2026, 6, 17), 20), "Demo Executive A", "演示健康管理师", "MEDIUM", metabolic)
    task.status, task.completed_at = "COMPLETED", local_datetime(date(2026, 6, 17), 20, 10)
    barrier = record_execution_barrier(session, program, "TRAVEL", "连续 7 天出差导致运动下降、睡眠下降与任务完成率下降。", "演示健康管理师", task, "已降低出差期间运动门槛并调整为每日 20 分钟步行。")
    assert barrier.status == "RESOLVED"
    plan = ManagementPlan(patient_id=patient_id, program_id=program.id, health_problem_id=metabolic.id, title="代谢健康阶段管理计划", content="从可执行的步行、睡眠记录和复查安排开始；不含自动诊断或药物调整。", status="ACTIVE", owner="演示健康管理师", source="synthetic_program", start_date=program.start_date, end_date=program.end_date)
    session.add(plan)
    session.flush()
    adjust_management_plan(session, plan, "演示健康管理师", "出差期间执行受限（TRAVEL），降低任务难度。", "出差期间每天 20 分钟步行；返程后恢复每周运动安排并在周复盘核实。")
    record_weekly_review(session, program, 5, "2 / 4", "充分", "出差期间运动与睡眠记录下降，已联系成员核实。", "完成出差适配任务并恢复睡眠记录。", "演示健康管理师", "TRAVEL", "已记录中断原因。", "降低运动任务频率。")
    for metric, baseline, current, unit, direction, result in [
        ("体重", "86", "81", "kg", "DOWN", "IMPROVED"),
        ("平均睡眠", "5.8", "6.6", "h", "UP", "IMPROVED"),
        ("每周运动", "1", "3", "次/周", "UP", "IMPROVED"),
        ("晨间血压趋势", "146/94", "134/86", "mmHg", "DOWN", "IMPROVED"),
    ]:
        record_outcome_evaluation(session, program, metric, baseline, current, unit, direction, "演示健康管理师", "合成 Demo 的基线与阶段记录比较；不构成疾病治疗结论。", result, evaluation_date=program.end_date)
    stabilization = transition_to_stabilization(session, program, "演示健康管理师")
    stabilization.title = "半年稳定管理：代谢与生活节律"
    create_annual_account(session, journey, 2026, "维持代谢改善趋势，并持续完成复查与生活节律跟进。", "演示健康管理师", date(2026, 11, 7))
    return program


def _ensure_operations_demo(session: Session, patient_id: object, program: HealthProgram | None = None) -> None:
    """Seed one completed, auditable operational workflow for the synthetic member."""

    if session.scalar(select(HealthProblem).where(HealthProblem.patient_id == patient_id, HealthProblem.title == "血压记录模式待医生复核")) is not None:
        return
    alert = screen_member(session, patient_id)  # rule result; always requires human review
    if alert is None:
        return
    if program is not None:
        alert.program_id = program.id
    problem = confirm_alert_as_manager(
        session, alert, "演示健康管理师", "已核实来源与连续测量记录，转交医生复核。"
    )
    problem.priority_rank = 1
    _, _, task = record_doctor_review(
        session, problem, "演示心内科医生", "心内科",
        "已记录医生复核意见：请继续按既定记录与随访流程执行，后续由临床团队结合完整信息处理。",
        alert,
    )
    complete_follow_up(
        session, problem, "演示健康管理师",
        "已完成合成 Demo 复查记录与人工闭环；不代表真实临床结论。",
        task,
    )


def main() -> None:
    # PowerShell sessions can inherit a legacy code page; keep this synthetic
    # local-demo script readable without changing any system-wide setting.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    parser = argparse.ArgumentParser(description="Seed the synthetic Executive Health AI V0.1 demo.")
    parser.add_argument("--reset-demo", action="store_true", help="仅删除并重建 demo-executive-001 的合成数据")
    args = parser.parse_args()
    if engine.dialect.name != "sqlite":
        raise RuntimeError("本地 Demo 脚本要求 SQLite；PostgreSQL 迁移可在后续环境单独配置。")
    if args.reset_demo:
        print("已清理 demo-executive-001 的关联合成数据。" if reset_demo_data() else "未发现既有 Demo 数据，开始创建。")
    created = seed_full_demo()
    print("V0.1 合成 Demo 数据已就绪。")
    print(f"数据库：{engine.url}")
    print("新增：" + "，".join(f"{key}={value}" for key, value in created.items()))


if __name__ == "__main__":
    main()
