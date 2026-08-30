"""Deterministic longitudinal HealthOps services.

The module centralizes taxonomy, assessment history, management routing,
report comparison, timeline assembly and before/after observation summaries.
It never calls an LLM and does not create a medical diagnosis.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from executive_health_ai.blood_pressure import TOKYO_TIMEZONE
from executive_health_ai.models import (
    AuditLog, DoctorReview, Document, ExternalReferral, FollowUp, HealthAssessment,
    HealthEvent, HealthProblem, HealthProgram, ManagementRule,
    ManagementSignal, MedicationPlan, Observation, Patient, ReportExtractionCandidate,
    ReportExtractionRun, RiskEvent, Task, OutcomeEvaluation, WeeklyReview, ServiceCatalogItem, ServiceRequest,
)


USABLE_QUALITY = ("valid", "VALID", "manually_corrected", "MANUALLY_CORRECTED")
ROUTES = {"SELF_MANAGEMENT", "HEALTH_MANAGER", "INTERNAL_DOCTOR", "EXTERNAL_DOCTOR", "EMERGENCY_MANUAL_ACTION"}
LIFESTYLE_ROUTES = {"SELF_MANAGEMENT", "HEALTH_MANAGER"}
LIFESTYLE_METRICS = {"steps", "exercise_minutes", "active_calories", "sleep_duration", "deep_sleep_duration", "light_sleep_duration", "rem_sleep_duration", "awake_duration"}


def _member_facing_report_title(document: Document) -> str:
    """Hide synthetic/test storage names from normal longitudinal summaries."""
    title = (document.title or "").strip()
    if title.lower().startswith(("synthetic_", "synthetic-", "test_", "test-")):
        return "演示资料 · 体检报告"
    return title or "体检报告"


TIMELINE_EVENT_TYPE_LABELS = {
    "report": "体检",
    "assessment": "健康基线",
    "health_data_summary": "健康数据",
    "risk": "风险",
    "major_problem": "医疗",
    "doctor_review": "医生",
    "external_referral": "外部医疗",
    "medication_change": "用药",
    "procedure": "医疗",
    "surgery": "手术",
    "hospitalization": "住院",
    "program_start": "健康管理",
    "program_adjustment": "健康管理",
    "intervention": "健康管理",
    "service": "服务",
    "outcome": "阶段结果",
}
TIMELINE_RISK_LABELS = {
    "GREEN": "低风险",
    "YELLOW": "中风险",
    "RED": "高风险",
    "UNKNOWN": "暂无正式风险评估",
}


def get_timeline_event_type_display(event_type: str | None) -> str:
    """Return the product label for an event category, never an internal enum."""
    return TIMELINE_EVENT_TYPE_LABELS.get((event_type or "").lower(), "健康记录")


def get_timeline_risk_display(risk_level: str | None) -> str:
    """Return the accessible text accompanying a risk indicator."""
    normalized = _normalize_timeline_risk_level(risk_level)
    return TIMELINE_RISK_LABELS[normalized]


def _normalize_timeline_risk_level(risk_level: str | None) -> str:
    value = (risk_level or "").upper()
    if value in {"RED", "HIGH"}:
        return "RED"
    if value in {"YELLOW", "MEDIUM", "AMBER"}:
        return "YELLOW"
    if value in {"GREEN", "LOW"}:
        return "GREEN"
    return "UNKNOWN"


class HealthDataCategoryRegistry:
    """One canonical UI/timeline category per metric or entity type."""

    _METRICS = {
        "systolic_bp": ("VITALS", "生命体征"), "diastolic_bp": ("VITALS", "生命体征"),
        "heart_rate": ("VITALS", "生命体征"), "resting_heart_rate": ("VITALS", "生命体征"),
        "spo2": ("VITALS", "生命体征"), "temperature": ("VITALS", "生命体征"),
        "glucose": ("GLUCOSE_METABOLIC", "血糖代谢"), "hba1c": ("GLUCOSE_METABOLIC", "血糖代谢"),
        "weight": ("BODY_COMPOSITION", "体成分"), "bmi": ("BODY_COMPOSITION", "体成分"), "waist": ("BODY_COMPOSITION", "体成分"),
        "steps": ("ACTIVITY", "活动"), "exercise_minutes": ("ACTIVITY", "活动"), "active_calories": ("ACTIVITY", "活动"),
        "sleep_duration": ("SLEEP", "睡眠"), "deep_sleep_duration": ("SLEEP", "睡眠"),
        "light_sleep_duration": ("SLEEP", "睡眠"), "rem_sleep_duration": ("SLEEP", "睡眠"),
        "awake_duration": ("SLEEP", "睡眠"),
        "ldl": ("LABORATORY", "实验室检查"), "hdl": ("LABORATORY", "实验室检查"), "alt": ("LABORATORY", "实验室检查"),
        "ast": ("LABORATORY", "实验室检查"), "creatinine": ("LABORATORY", "实验室检查"),
    }
    _ENTITY = {
        "FINDING": ("IMAGING_DIAGNOSTIC", "影像与检查"), "HealthProblem": ("PROBLEMS", "疾病与健康问题"),
        "MedicationPlan": ("MEDICATION", "用药"), "HealthEvent": ("PROCEDURE_HOSPITALIZATION", "手术 / 住院"),
        "HealthProgram": ("INTERVENTION", "健康管理干预"), "DoctorReview": ("CLINICAL_REVIEW", "医生意见"),
    }

    @classmethod
    def classify_metric(cls, metric_code: str | None) -> tuple[str, str]:
        return cls._METRICS.get((metric_code or "").lower(), ("OTHER", "其他健康数据"))

    @classmethod
    def classify_entity(cls, entity_name: str) -> tuple[str, str]:
        return cls._ENTITY.get(entity_name, ("OTHER", "其他健康记录"))


class HealthAssessmentService:
    def create_assessment(self, session: Session, patient_id: UUID, *, title: str, summary: str, baseline: dict[str, Any], created_by: str, assessment_type: str = "BASELINE", source_references: dict[str, Any] | None = None, confirmed: bool = False) -> HealthAssessment:
        version = int(session.scalar(select(func.count(HealthAssessment.id)).where(HealthAssessment.patient_id == patient_id)) or 0) + 1
        now = datetime.now(timezone.utc)
        item = HealthAssessment(patient_id=patient_id, assessment_type=assessment_type, version=version, title=title.strip(), summary=summary.strip(), baseline_json=baseline, created_by=created_by.strip(), status="CONFIRMED" if confirmed else "DRAFT", reviewed_by=created_by.strip() if confirmed else None, confirmed_at=now if confirmed else None, source_references_json=source_references or {})
        session.add(item); session.flush()
        return item

    def create_initial_baseline(self, session: Session, patient_id: UUID, *, summary: str, baseline: dict[str, Any], created_by: str) -> HealthAssessment:
        return self.create_assessment(session, patient_id, title="初始健康评估", summary=summary, baseline=baseline, created_by=created_by, assessment_type="BASELINE", confirmed=True)

    def create_reassessment(self, session: Session, patient_id: UUID, *, summary: str, baseline: dict[str, Any], created_by: str) -> HealthAssessment:
        return self.create_assessment(session, patient_id, title="阶段健康复评", summary=summary, baseline=baseline, created_by=created_by, assessment_type="REASSESSMENT", confirmed=True)

    def confirm(self, session: Session, assessment_id: UUID, reviewed_by: str) -> HealthAssessment:
        item = session.get(HealthAssessment, assessment_id)
        if item is None: raise ValueError("健康评估不存在。")
        if item.status != "DRAFT":
            raise ValueError("只有待确认的健康基线初稿可以确认。")
        if item.assessment_type == "BASELINE":
            existing = session.scalar(select(HealthAssessment.id).where(
                HealthAssessment.patient_id == item.patient_id,
                HealthAssessment.assessment_type == "BASELINE",
                HealthAssessment.status == "CONFIRMED",
            ))
            if existing is not None:
                raise ValueError("该成员已有正式健康基线；请建立阶段复评，不会覆盖历史基线。")
        item.status, item.reviewed_by, item.confirmed_at = "CONFIRMED", reviewed_by, datetime.now(timezone.utc)
        session.flush(); return item

    def history(self, session: Session, patient_id: UUID) -> list[HealthAssessment]:
        return list(session.scalars(select(HealthAssessment).where(HealthAssessment.patient_id == patient_id).order_by(HealthAssessment.assessed_at.desc())))

    def compare_assessments(self, previous: HealthAssessment, current: HealthAssessment) -> dict[str, dict[str, Any]]:
        keys = set(previous.baseline_json) | set(current.baseline_json)
        return {key: {"previous": previous.baseline_json.get(key), "current": current.baseline_json.get(key)} for key in keys if previous.baseline_json.get(key) != current.baseline_json.get(key)}

    def latest_baseline(self, session: Session, patient_id: UUID, *, include_draft: bool = True) -> HealthAssessment | None:
        statuses = ("CONFIRMED", "DRAFT") if include_draft else ("CONFIRMED",)
        return session.scalar(select(HealthAssessment).where(
            HealthAssessment.patient_id == patient_id,
            HealthAssessment.assessment_type == "BASELINE",
            HealthAssessment.status.in_(statuses),
        ).order_by(HealthAssessment.version.desc()))

    def create_draft_from_report(self, session: Session, patient_id: UUID, document_id: UUID, *, created_by: str) -> HealthAssessment:
        """Build a reviewable baseline draft from confirmed facts only.

        This service deliberately reads neither Qwen output nor unconfirmed
        candidates.  It snapshots concise, traceable references instead of
        copying the member's time-series history.
        """
        document = session.get(Document, document_id)
        if document is None or document.patient_id != patient_id:
            raise ValueError("体检报告不存在或不属于当前成员。")
        patient = session.get(Patient, patient_id)
        confirmed_baseline = self.latest_baseline(session, patient_id, include_draft=False)
        if confirmed_baseline is not None:
            raise ValueError("该成员已有正式健康基线；新报告应进入长期比较，不会覆盖初始基线。")
        existing_draft = session.scalar(select(HealthAssessment).where(
            HealthAssessment.patient_id == patient_id,
            HealthAssessment.assessment_type == "BASELINE",
            HealthAssessment.status == "DRAFT",
        ).order_by(HealthAssessment.version.desc()))
        if existing_draft is not None:
            return existing_draft

        run = session.scalar(select(ReportExtractionRun).where(
            ReportExtractionRun.document_id == document_id,
            ReportExtractionRun.patient_id == patient_id,
            ReportExtractionRun.status.in_(("COMPLETED", "PARTIAL_SUCCESS")),
        ).order_by(ReportExtractionRun.created_at.desc()))
        if run is None:
            raise ValueError("报告尚未完成整理，不能建立健康基线初稿。")
        candidates = list(session.scalars(select(ReportExtractionCandidate).where(
            ReportExtractionCandidate.document_id == document_id,
            ReportExtractionCandidate.extraction_run_id == run.id,
            ReportExtractionCandidate.patient_id == patient_id,
            ReportExtractionCandidate.status == "CONFIRMED",
        ).order_by(ReportExtractionCandidate.source_page, ReportExtractionCandidate.created_at)))
        if not candidates:
            raise ValueError("尚无人工确认的报告资料，不能建立健康基线初稿。")

        observations = list(session.scalars(select(Observation).where(
            Observation.patient_id == patient_id,
            Observation.source == "confirmed_health_check_report",
            Observation.source_record_id.in_([str(item.id) for item in candidates if item.candidate_type == "OBSERVATION"]),
        ).order_by(Observation.observed_at.desc()).limit(80)))
        problems = list(session.scalars(select(HealthProblem).where(
            HealthProblem.patient_id == patient_id,
            HealthProblem.status != "CLOSED",
        ).order_by(HealthProblem.priority_rank, HealthProblem.opened_at.desc()).limit(12)))
        medications = list(session.scalars(select(MedicationPlan).where(
            MedicationPlan.patient_id == patient_id,
            MedicationPlan.status.not_in(("STOPPED", "CANCELLED")),
        ).order_by(MedicationPlan.created_at.desc()).limit(12)))
        procedures = list(session.scalars(select(HealthEvent).where(
            HealthEvent.patient_id == patient_id,
            HealthEvent.event_type.in_(("surgery", "hospitalization")),
        ).order_by(HealthEvent.start_at.desc()).limit(12)))
        recent = list(session.scalars(select(Observation).where(
            Observation.patient_id == patient_id,
            Observation.quality_flag.in_(USABLE_QUALITY),
            Observation.excluded_from_analysis.is_(False),
            Observation.source_deleted.is_(False),
        ).order_by(Observation.observed_at.desc()).limit(80)))
        latest_by_metric: dict[str, Observation] = {}
        for item in recent:
            latest_by_metric.setdefault(item.metric_code, item)
        risk = ReportRiskSummaryService().summarize(session, patient_id, document_id)

        metric_rows = [
            {"metric": item.metric_code, "value": str(item.value_numeric), "unit": item.unit, "observed_at": item.observed_at.isoformat(), "source_candidate_id": item.source_record_id}
            for item in observations
        ]
        metric_values = {item.metric_code: f"{item.value_numeric} {item.unit}" for item in observations}
        today = datetime.now(timezone.utc).date()
        age = None
        if patient and patient.birth_date:
            age = today.year - patient.birth_date.year - ((today.month, today.day) < (patient.birth_date.month, patient.birth_date.day))
        finding_rows = [
            {"summary": item.summary or item.raw_name or "已确认检查结果", "source_page": item.source_page, "source_candidate_id": str(item.id)}
            for item in candidates if item.candidate_type == "FINDING"
        ]
        followup_rows = [
            {"summary": item.summary or "已确认复查建议", "source_page": item.source_page, "source_candidate_id": str(item.id)}
            for item in candidates if item.candidate_type == "FOLLOWUP"
        ]
        lifestyle_codes = {"sleep_duration", "deep_sleep_duration", "steps", "active_calories", "exercise_minutes", "weight", "systolic_bp", "glucose"}
        recent_rows = [
            {"metric": item.metric_code, "value": str(item.value_numeric), "unit": item.unit, "observed_at": item.observed_at.isoformat(), "source": item.source}
            for code, item in latest_by_metric.items() if code in lifestyle_codes
        ]
        pending: list[str] = []
        if not problems: pending.append("既往健康史")
        if not medications: pending.append("当前用药")
        if not procedures: pending.append("手术 / 住院史")
        if not recent_rows: pending.append("近期日常健康数据")
        pending.append("家族史")
        baseline = {
            "source_report": {"document_id": str(document.id), "title": _member_facing_report_title(document)},
            "basic_information": {
                "age": age if age is not None else "待补充",
                "sex": patient.sex if patient and patient.sex else "待补充",
                "height": metric_values.get("height", "待补充"),
                "weight": metric_values.get("weight", "待补充"),
                "bmi": metric_values.get("bmi", "待补充"),
            },
            "key_metrics": metric_rows,
            "important_findings": finding_rows,
            "follow_up_recommendations": followup_rows,
            "health_problems": [{"title": item.title, "status": item.status, "source": item.source} for item in problems],
            "current_medications": [{"name": item.drug_name, "status": item.status} for item in medications] or {"status": "PENDING_SUPPLEMENT", "label": "待补充"},
            "procedures_or_hospitalizations": [{"type": item.event_type, "description": item.description, "occurred_at": item.start_at.isoformat()} for item in procedures] or {"status": "PENDING_SUPPLEMENT", "label": "待补充"},
            "recent_health_data": recent_rows or {"status": "PENDING_SUPPLEMENT", "label": "待补充"},
            "risk_summary": {"level": risk["level"], "reason": risk["reason"], "source": "formal_risk_events_and_approved_rules"},
            "management_focus": [row["summary"] for row in finding_rows[:3]] or ["待健康管理师结合已确认资料确认"],
            "member_reported": {"source": "MEMBER_REPORTED", "status": "PENDING_SUPPLEMENT"},
            "completeness": {"organized": ["最近体检", "主要指标", "检查结果"], "pending": pending},
        }
        source_references = {
            "source_report_ids": [str(document.id)],
            "source_observation_ids": [str(item.id) for item in observations],
            "source_candidate_ids": [str(item.id) for item in candidates],
            "source_problem_ids": [str(item.id) for item in problems],
            "source_medication_ids": [str(item.id) for item in medications],
            "source_procedure_ids": [str(item.id) for item in procedures],
            "member_reported_fields": [],
        }
        return self.create_assessment(
            session, patient_id, title="健康基线 · 待确认",
            summary=f"基于《{_member_facing_report_title(document)}》及已确认健康档案整理的初稿，仍需健康管理师补充与确认。",
            baseline=baseline, created_by=created_by, assessment_type="BASELINE",
            source_references=source_references, confirmed=False,
        )

    def update_member_reported(self, session: Session, assessment_id: UUID, fields: dict[str, str], *, reported_by: str = "member") -> HealthAssessment:
        item = session.get(HealthAssessment, assessment_id)
        if item is None or item.status != "DRAFT":
            raise ValueError("只能为待确认的健康基线初稿补充资料。")
        allowed = {"既往史", "当前用药", "手术 / 住院史", "家族史", "生活方式资料"}
        submitted = {key: value.strip() for key, value in fields.items() if key in allowed and value and value.strip()}
        if not submitted:
            return item
        baseline = dict(item.baseline_json or {})
        reported = dict(baseline.get("member_reported") or {})
        reported.update({"source": "MEMBER_REPORTED", "reported_by": reported_by, "fields": submitted})
        baseline["member_reported"] = reported
        completeness = dict(baseline.get("completeness") or {})
        pending = [label for label in completeness.get("pending", []) if label not in submitted]
        completeness["pending"] = pending
        baseline["completeness"] = completeness
        item.baseline_json = baseline
        refs = dict(item.source_references_json or {})
        refs["member_reported_fields"] = sorted(submitted)
        item.source_references_json = refs
        session.flush()
        return item

    def ensure_report_review_task(self, session: Session, patient_id: UUID, document: Document) -> Task:
        source = f"member_report_upload:{document.id}"
        existing = session.scalar(select(Task).where(
            Task.patient_id == patient_id,
            Task.source == source,
            Task.status.not_in(("COMPLETED", "CANCELLED")),
        ).order_by(Task.created_at.desc()))
        if existing is not None:
            return existing
        confirmed_baseline = self.latest_baseline(session, patient_id, include_draft=False)
        next_step = "审核报告并进入长期比较" if confirmed_baseline is not None else "审核报告并建立健康基线初稿"
        task = Task(
            patient_id=patient_id, title="新体检报告待确认",
            instruction=f"《{_member_facing_report_title(document)}》已完成自动整理。请{next_step}。",
            status="PENDING", priority="HIGH", assignee="health_manager",
            responsible_role="health_manager", source=source,
        )
        session.add(task); session.flush()
        return task

    def complete_report_review_task(self, session: Session, patient_id: UUID, document_id: UUID) -> None:
        source = f"member_report_upload:{document_id}"
        for task in session.scalars(select(Task).where(Task.patient_id == patient_id, Task.source == source, Task.status.not_in(("COMPLETED", "CANCELLED")))):
            task.status = "COMPLETED"
            task.completed_at = datetime.now(timezone.utc)


class ManagementRoutingService:
    """Evaluate approved wellness rules separately from medical risk triage.

    The evaluator deliberately has no LLM, clinical severity or escalation
    behaviour.  It creates at most one open signal per member/rule and keeps a
    bounded provenance trail as new source observations arrive.
    """

    def evaluate_observation(self, session: Session, observation_id: UUID) -> ManagementSignal | None:
        observation = session.get(Observation, observation_id)
        if not self._eligible(observation) or observation.metric_code not in LIFESTYLE_METRICS:
            return None
        rules = list(session.scalars(select(ManagementRule).where(
            ManagementRule.canonical_code == observation.metric_code,
            ManagementRule.review_status == "APPROVED",
            ManagementRule.is_active.is_(True),
        )))
        for rule in rules:
            if rule.recommended_route not in LIFESTYLE_ROUTES:
                # A wellness rule is never allowed to automatically route to a
                # doctor or emergency action.  Such escalation remains human
                # work in the existing Yellow workflow.
                continue
            result = self._evaluate_rule(session, observation, rule)
            if result is None:
                continue
            return self._upsert_signal(session, observation, rule, result)
        return None

    @staticmethod
    def _eligible(observation: Observation | None) -> bool:
        return bool(
            observation
            and observation.quality_flag in USABLE_QUALITY
            and not observation.excluded_from_analysis
            and not observation.source_deleted
        )

    @staticmethod
    def _compare(value: Decimal, operator: str, target: Decimal) -> bool:
        return {
            ">=": value >= target, ">": value > target,
            "<=": value <= target, "<": value < target, "==": value == target,
        }.get(operator, False)

    @staticmethod
    def _integer(config: dict[str, Any], key: str, default: int) -> int:
        try:
            return max(1, int(config.get(key, default)))
        except (TypeError, ValueError):
            return default

    def _window_records(self, session: Session, observation: Observation, config: dict[str, Any]) -> list[Observation]:
        lookback_days = self._integer(config, "lookback_days", 1)
        lookback_minutes = self._integer(config, "lookback_minutes", lookback_days * 24 * 60)
        start = observation.observed_at - timedelta(minutes=lookback_minutes)
        return list(session.scalars(select(Observation).where(
            Observation.patient_id == observation.patient_id,
            Observation.metric_code == observation.metric_code,
            Observation.quality_flag.in_(USABLE_QUALITY),
            Observation.excluded_from_analysis.is_(False),
            Observation.source_deleted.is_(False),
            Observation.observed_at >= start,
            Observation.observed_at <= observation.observed_at,
        ).order_by(Observation.observed_at)))

    def _evaluate_rule(self, session: Session, observation: Observation, rule: ManagementRule) -> dict[str, Any] | None:
        config = rule.threshold_config or {}
        window = rule.window_config or {}
        if str(config.get("metric") or rule.canonical_code) != observation.metric_code:
            return None
        expected_unit = str(config.get("unit") or "")
        if expected_unit and expected_unit.lower() != observation.unit.lower():
            return None
        try:
            target = Decimal(str(config["value"]))
        except (KeyError, ArithmeticError, ValueError):
            return None
        operator = str(config.get("operator") or "")
        records = self._window_records(session, observation, window)
        minimum_samples = self._integer(window, "minimum_samples", 1)
        required_matches = self._integer(window, "required_matches", minimum_samples)
        if len(records) < minimum_samples:
            return None
        values = [Decimal(str(item.value_numeric)) for item in records]
        condition = str(rule.condition_type or "THRESHOLD").upper()
        matched_records: list[Observation] = []
        evaluated_value: Decimal | None = None

        if condition in {"THRESHOLD", "SINGLE_THRESHOLD"}:
            matched_records = [item for item in records if self._compare(Decimal(str(item.value_numeric)), operator, target)]
            if len(matched_records) < required_matches:
                return None
            evaluated_value = Decimal(str(observation.value_numeric))
        elif condition in {"AVERAGE_THRESHOLD", "AVERAGE"}:
            evaluated_value = sum(values) / Decimal(len(values))
            if not self._compare(evaluated_value, operator, target):
                return None
            matched_records = records
        elif condition in {"PERCENTAGE_CHANGE", "PERCENTAGE_DECLINE", "TREND"}:
            midpoint = len(values) // 2
            if midpoint == 0:
                return None
            before = sum(values[:midpoint]) / Decimal(midpoint)
            after = sum(values[midpoint:]) / Decimal(len(values[midpoint:]))
            if before == 0:
                return None
            evaluated_value = (after - before) / before * Decimal("100")
            if not self._compare(evaluated_value, operator, target):
                return None
            matched_records = records[midpoint:]
        elif condition in {"CONSECUTIVE_DAYS", "REPEATED_DAYS"}:
            daily: dict[object, Observation] = {}
            for item in records:
                daily[item.observed_at.astimezone(timezone.utc).date()] = item
            ordered = [daily[key] for key in sorted(daily)]
            matched_records = [item for item in ordered if self._compare(Decimal(str(item.value_numeric)), operator, target)]
            if len(matched_records) < required_matches or ordered[-required_matches:] != matched_records[-required_matches:]:
                return None
            evaluated_value = Decimal(str(observation.value_numeric))
        else:
            return None

        return {
            "metric": observation.metric_code,
            "unit": observation.unit,
            "condition_type": condition,
            "evaluated_value": str(evaluated_value),
            "threshold": str(target),
            "operator": operator,
            "window": {"lookback_days": window.get("lookback_days"), "lookback_minutes": window.get("lookback_minutes"), "minimum_samples": minimum_samples, "required_matches": required_matches},
            "matched_count": len(matched_records),
            "sample_count": len(records),
            "observation_ids": [str(item.id) for item in records],
            "matched_observation_ids": [str(item.id) for item in matched_records],
            "rule_version": rule.version,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _upsert_signal(self, session: Session, observation: Observation, rule: ManagementRule, evidence: dict[str, Any]) -> ManagementSignal:
        now = datetime.now(timezone.utc)
        existing = session.scalar(select(ManagementSignal).where(
            ManagementSignal.patient_id == observation.patient_id,
            ManagementSignal.management_rule_id == rule.id,
            ManagementSignal.metric_code == observation.metric_code,
            ManagementSignal.status == "OPEN",
        ).order_by(ManagementSignal.created_at.desc()))
        if existing:
            history = list((existing.evidence_json or {}).get("history", []))[-9:]
            history.append(evidence)
            existing.observation_id = observation.id
            existing.last_detected_at = now
            existing.evidence_json = {"latest": evidence, "history": history}
            session.add(AuditLog(patient_id=observation.patient_id, actor="system", actor_role="system", action="management_signal_evidence_appended", entity_type="ManagementSignal", entity_id=str(existing.id), detail_json={"rule_id": str(rule.id), "metric": observation.metric_code, "matched_count": evidence["matched_count"]}))
            session.flush()
            return existing
        severity = str((rule.threshold_config or {}).get("severity") or "WATCH").upper()
        if severity not in {"NORMAL", "WATCH", "ACTION_NEEDED"}:
            severity = "WATCH"
        signal = ManagementSignal(
            patient_id=observation.patient_id,
            management_rule_id=rule.id,
            observation_id=observation.id,
            signal_category="LIFESTYLE_MANAGEMENT",
            metric_code=observation.metric_code,
            severity=severity,
            recommended_route=rule.recommended_route,
            summary=f"健康管理信号：{rule.name}；需要人工持续管理，不构成诊断。",
            evidence_json={"latest": evidence, "history": [evidence]},
            first_detected_at=now,
            last_detected_at=now,
        )
        session.add(signal)
        session.flush()
        session.add(AuditLog(patient_id=observation.patient_id, actor="system", actor_role="system", action="management_signal_created", entity_type="ManagementSignal", entity_id=str(signal.id), detail_json={"rule_id": str(rule.id), "metric": observation.metric_code, "route": rule.recommended_route, "severity": severity}))
        return signal


class ReportComparisonService:
    """Compare two already human-confirmed report records without inferring diagnoses."""

    def compare(self, session: Session, member_id: UUID, old_document_id: UUID, new_document_id: UUID) -> dict[str, Any]:
        def latest_run(document_id: UUID) -> ReportExtractionRun | None:
            return session.scalar(select(ReportExtractionRun).where(ReportExtractionRun.document_id == document_id, ReportExtractionRun.patient_id == member_id).order_by(ReportExtractionRun.completed_at.desc(), ReportExtractionRun.created_at.desc()))
        old_run, new_run = latest_run(old_document_id), latest_run(new_document_id)
        if old_run is None or new_run is None:
            raise ValueError("两份报告均需已有解析记录。")
        def candidates(run: ReportExtractionRun) -> list[ReportExtractionCandidate]:
            return list(session.scalars(select(ReportExtractionCandidate).where(ReportExtractionCandidate.extraction_run_id == run.id, ReportExtractionCandidate.status == "CONFIRMED")))
        old, new = candidates(old_run), candidates(new_run)
        old_obs = {item.canonical_code: item for item in old if item.candidate_type == "OBSERVATION" and item.canonical_code}
        new_obs = {item.canonical_code: item for item in new if item.candidate_type == "OBSERVATION" and item.canonical_code}
        changes = []
        for code in sorted(set(old_obs) | set(new_obs)):
            before, after = old_obs.get(code), new_obs.get(code)
            if before and after:
                try: delta = float(after.normalized_value or 0) - float(before.normalized_value or 0)
                except ValueError: delta = None
                changes.append({"metric": code, "previous": before.normalized_value, "current": after.normalized_value, "unit": after.unit or before.unit, "delta": delta, "status": "INCREASED" if delta and delta > 0 else "DECREASED" if delta and delta < 0 else "UNCHANGED", "trend": "提高" if delta and delta > 0 else "降低" if delta and delta < 0 else "稳定", "previous_candidate_id": str(before.id), "current_candidate_id": str(after.id)})
            elif after:
                changes.append({"metric": code, "previous": None, "current": after.normalized_value, "unit": after.unit, "delta": None, "status": "NEW_RESULT", "trend": "新增检查", "previous_candidate_id": None, "current_candidate_id": str(after.id)})
            else:
                changes.append({"metric": code, "previous": before.normalized_value, "current": None, "unit": before.unit, "delta": None, "status": "NOT_RECHECKED", "trend": "未复查", "previous_candidate_id": str(before.id), "current_candidate_id": None})
        old_finding_items = {item.summary: item for item in old if item.candidate_type == "FINDING" and item.summary}
        new_finding_items = {item.summary: item for item in new if item.candidate_type == "FINDING" and item.summary}
        old_findings, new_findings = set(old_finding_items), set(new_finding_items)
        followups = [item.summary for item in new if item.candidate_type == "FOLLOWUP" and item.summary]
        return {"metric_changes": changes, "new_findings": sorted(new_findings - old_findings), "persistent_findings": sorted(new_findings & old_findings), "resolved_findings": [], "not_rechecked_findings": sorted(old_findings - new_findings), "changed_findings": [], "needs_review_findings": [], "followup_changes": followups, "finding_evidence": {"old": {title: str(item.id) for title, item in old_finding_items.items()}, "new": {title: str(item.id) for title, item in new_finding_items.items()}}, "risk_summary": "仅汇总已人工确认资料；风险等级由已审核规则及人工处理决定。"}


@dataclass(frozen=True)
class TimelineEvent:
    occurred_at: datetime
    event_type: str
    title: str
    summary: str
    severity: str
    source: str
    expandable_details: dict[str, Any]
    related_entity: str | None = None
    group_key: str = ""
    related_entity_ids: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    # Display dimensions are intentionally distinct.  ``event_type_label``
    # describes what happened; ``risk_*`` is populated only for a formal risk
    # event and must never be inferred from an ordinary event's severity.
    event_type_label: str = ""
    risk_level: str | None = None
    risk_label: str | None = None
    risk_indicator: str = "NONE"  # TRAFFIC_LIGHT / NEUTRAL / NONE
    # This is a presentation grouping only.  It never replaces event_type or
    # changes the underlying medical/workflow record.
    lane: str = "MEDICAL"


@dataclass(frozen=True)
class MetricSeries:
    """A bounded, display-ready continuous health metric series."""

    metric_code: str
    display_name: str
    unit: str
    points: tuple[dict[str, Any], ...]
    aggregation: str
    source: str
    time_range: tuple[datetime | None, datetime | None]


@dataclass(frozen=True)
class TimelineWindowSummary:
    """Objective window totals and observed changes, never causal claims."""

    health_changes: tuple[dict[str, Any], ...]
    risk_counts: dict[str, int]
    medical_counts: dict[str, int]
    management_counts: dict[str, int]
    service_counts: dict[str, int]


@dataclass(frozen=True)
class TimelineViewport:
    """UI-only semantic-zoom window; it does not persist health data."""

    start: datetime
    end: datetime
    zoom_level: str  # YEAR / QUARTER / MONTH / WEEK


@dataclass(frozen=True)
class TimelineCluster:
    """A compact lifecycle node for a month or same-day event group."""

    cluster_id: str
    period_start: datetime
    period_end: datetime
    zoom_level: str
    event_count: int
    event_type_counts: dict[str, int]
    highest_risk: str | None
    main_events: tuple[TimelineEvent, ...]
    zoom_target: TimelineViewport | None = None

    @property
    def occurred_at(self) -> datetime:
        return self.period_start


@dataclass(frozen=True)
class TimelineViewModel:
    """Read-only V4 projection joining continuous data with major events."""

    start: datetime | None
    end: datetime | None
    metric_series: tuple[MetricSeries, ...]
    events: tuple[TimelineEvent, ...]
    summary: TimelineWindowSummary
    viewport: TimelineViewport | None = None
    lifecycle_items: tuple[TimelineCluster, ...] = ()


class MonthlyTimelineSummaryService:
    """Bounded monthly health-data summaries for the longitudinal story.

    This deliberately reads only a short, explicitly selected metric set.  It
    does not evaluate medical risk, infer a diagnosis, or create records.
    """

    _METRICS = {
        "sleep_duration": "睡眠",
        "steps": "活动",
        "systolic_bp": "血压",
        "glucose": "血糖",
        "weight": "体重",
        "resting_heart_rate": "静息心率",
    }

    def monthly_summaries(
        self,
        session: Session,
        member_id: UUID,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        per_metric_limit: int = 500,
    ) -> list[TimelineEvent]:
        """Return at most one non-clinical summary node per calendar month."""
        records_by_month: dict[tuple[int, int], dict[str, list[Observation]]] = defaultdict(lambda: defaultdict(list))
        for metric in self._METRICS:
            statement = select(Observation).where(
                Observation.patient_id == member_id,
                Observation.metric_code == metric,
                Observation.quality_flag.in_(USABLE_QUALITY),
                Observation.excluded_from_analysis.is_(False),
                Observation.source_deleted.is_(False),
            )
            if start is not None:
                statement = statement.where(Observation.observed_at >= start)
            if end is not None:
                statement = statement.where(Observation.observed_at <= end)
            for record in session.scalars(statement.order_by(Observation.observed_at.desc()).limit(per_metric_limit)):
                local = record.observed_at.astimezone(TOKYO_TIMEZONE)
                records_by_month[(local.year, local.month)][metric].append(record)

        summaries: list[TimelineEvent] = []
        for (year, month), per_metric in records_by_month.items():
            metrics: list[dict[str, Any]] = []
            short_parts: list[str] = []
            for metric in self._METRICS:
                records = sorted(per_metric.get(metric, []), key=lambda item: item.observed_at)
                if not records:
                    continue
                values = [float(item.value_numeric) for item in records]
                average = sum(values) / len(values)
                delta = values[-1] - values[0] if len(values) >= 2 else None
                direction = "稳定" if delta is None or abs(delta) < 0.001 else ("上升" if delta > 0 else "下降")
                metrics.append({
                    "metric": metric,
                    "label": self._METRICS[metric],
                    "average": round(average, 2),
                    "unit": records[-1].unit,
                    "samples": len(records),
                    "direction": direction,
                    "start": records[0].observed_at.isoformat(),
                    "end": records[-1].observed_at.isoformat(),
                })
                if len(short_parts) < 4:
                    short_parts.append(f"{self._METRICS[metric]}：{direction}")
            if not metrics:
                continue
            # A partial current month must not be placed in the future at the
            # calendar month-end.  Anchor the summary to the real cutoff: the
            # latest usable observation included in this exact window.
            occurred_at = max(
                record.observed_at
                for records in per_metric.values()
                for record in records
            )
            summaries.append(TimelineEvent(
                occurred_at=occurred_at,
                event_type="health_data_summary",
                title=f"{year}年{month}月健康数据总结",
                summary=" · ".join(short_parts),
                severity="AMBER" if any(item["direction"] != "稳定" for item in metrics) else "GRAY",
                source="health_data_summary",
                expandable_details={"window_start": f"{year:04d}-{month:02d}-01", "window_end": occurred_at.astimezone(TOKYO_TIMEZONE).date().isoformat(), "metrics": metrics},
                group_key=f"HEALTH_DATA_SUMMARY:{member_id}:{year:04d}-{month:02d}",
                actions=("view_health_data",),
            ))
        return summaries


class HealthTimelineService:
    """Build a bounded, major-event health story; no copied timeline table."""

    @staticmethod
    def _lane_for_event_type(event_type: str) -> str:
        """Return one of the five V4 lifecycle lanes for a major event."""
        normalized = (event_type or "").lower()
        if normalized == "medication_change":
            return "MEDICATION"
        if normalized in {"program_start", "program_adjustment", "intervention", "service"}:
            return "MANAGEMENT"
        if normalized == "risk":
            return "RISK"
        return "MEDICAL"

    @staticmethod
    def _display_event(event: TimelineEvent) -> TimelineEvent:
        """Attach UI-only labels without letting event category imply risk.

        Existing ``severity`` remains available for historical business data,
        but it is deliberately not converted into a traffic-light indicator
        unless the event itself is a formal deterministic risk event.
        """
        event_type_label = get_timeline_event_type_display(event.event_type)
        lane = HealthTimelineService._lane_for_event_type(event.event_type)
        if event.event_type != "risk":
            return replace(event, event_type_label=event_type_label, lane=lane)
        risk_level = _normalize_timeline_risk_level(event.risk_level or event.severity)
        return replace(
            event,
            event_type_label=event_type_label,
            risk_level=risk_level,
            risk_label=get_timeline_risk_display(risk_level),
            risk_indicator="TRAFFIC_LIGHT" if risk_level in {"GREEN", "YELLOW", "RED"} else "NEUTRAL",
            lane=lane,
        )

    @staticmethod
    def _program_display_title(program: HealthProgram) -> str:
        """Prevent synthetic/storage program identifiers from reaching members."""
        raw_title = (program.title or "").strip()
        normalized = raw_title.lower()
        is_storage_or_demo_name = normalized.startswith(("synthetic_", "synthetic-", "demo_", "demo-", "test_", "test-"))
        is_legacy_demo_name = "90-day metabolic" in normalized or normalized == "synthetic_prog"
        if raw_title and not (is_storage_or_demo_name or is_legacy_demo_name):
            return raw_title
        if program.program_type == "NINETY_DAY":
            return "90天代谢健康计划"
        return "健康管理计划"

    @staticmethod
    def _report_display_title(document: Document | None) -> str:
        """Keep synthetic storage filenames out of the member-facing story."""
        return _member_facing_report_title(document) if document is not None else "年度体检"

    def get_timeline(self, session: Session, member_id: UUID, *, start: datetime | None = None, end: datetime | None = None, limit: int = 100) -> list[TimelineEvent]:
        events: list[TimelineEvent] = []
        assessment_query = select(HealthAssessment).where(HealthAssessment.patient_id == member_id, HealthAssessment.status == "CONFIRMED")
        risk_query = select(RiskEvent).where(RiskEvent.patient_id == member_id)
        problem_query = select(HealthProblem).where(HealthProblem.patient_id == member_id)
        medication_query = select(MedicationPlan).where(MedicationPlan.patient_id == member_id)
        health_event_query = select(HealthEvent).where(HealthEvent.patient_id == member_id)
        review_query = select(DoctorReview).where(DoctorReview.patient_id == member_id)
        program_query = select(HealthProgram).where(HealthProgram.patient_id == member_id)
        referral_query = select(ExternalReferral).where(ExternalReferral.patient_id == member_id)
        outcome_query = select(OutcomeEvaluation).where(OutcomeEvaluation.patient_id == member_id)
        service_query = select(ServiceRequest).where(ServiceRequest.patient_id == member_id, ServiceRequest.status.in_(("SCHEDULED", "IN_PROGRESS", "COMPLETED")))
        adjustment_query = select(WeeklyReview).join(HealthProgram, WeeklyReview.program_id == HealthProgram.id).where(HealthProgram.patient_id == member_id, WeeklyReview.adjustment.is_not(None))
        report_query = select(ReportExtractionRun).where(ReportExtractionRun.patient_id == member_id, ReportExtractionRun.status.in_(("COMPLETED", "PARTIAL_SUCCESS")))
        if start is not None:
            assessment_query = assessment_query.where(HealthAssessment.assessed_at >= start); risk_query = risk_query.where(RiskEvent.created_at >= start)
            problem_query = problem_query.where(HealthProblem.opened_at >= start); medication_query = medication_query.where(MedicationPlan.created_at >= start)
            health_event_query = health_event_query.where(HealthEvent.start_at >= start); review_query = review_query.where(DoctorReview.reviewed_at >= start)
            program_query = program_query.where(HealthProgram.created_at >= start); referral_query = referral_query.where(ExternalReferral.created_at >= start)
            report_query = report_query.where(ReportExtractionRun.created_at >= start)
            outcome_query = outcome_query.where(OutcomeEvaluation.created_at >= start)
            adjustment_query = adjustment_query.where(WeeklyReview.reviewed_at >= start)
            service_query = service_query.where(ServiceRequest.requested_at >= start)
        if end is not None:
            assessment_query = assessment_query.where(HealthAssessment.assessed_at <= end); risk_query = risk_query.where(RiskEvent.created_at <= end)
            problem_query = problem_query.where(HealthProblem.opened_at <= end); medication_query = medication_query.where(MedicationPlan.created_at <= end)
            health_event_query = health_event_query.where(HealthEvent.start_at <= end); review_query = review_query.where(DoctorReview.reviewed_at <= end)
            program_query = program_query.where(HealthProgram.created_at <= end); referral_query = referral_query.where(ExternalReferral.created_at <= end)
            report_query = report_query.where(ReportExtractionRun.created_at <= end)
            outcome_query = outcome_query.where(OutcomeEvaluation.created_at <= end)
            adjustment_query = adjustment_query.where(WeeklyReview.reviewed_at <= end)
            service_query = service_query.where(ServiceRequest.requested_at <= end)
        for assessment in session.scalars(assessment_query.order_by(HealthAssessment.assessed_at.desc()).limit(limit)):
            kind = {"BASELINE": "健康基线", "REASSESSMENT": "阶段健康复评", "ANNUAL": "年度健康评估"}.get(assessment.assessment_type, assessment.title)
            details = {**(assessment.baseline_json or {}), "status": assessment.status, "reviewed_by": assessment.reviewed_by, "source_references": assessment.source_references_json}
            events.append(TimelineEvent(assessment.confirmed_at or assessment.assessed_at, "assessment", kind, assessment.summary, "BLUE", "health_assessment", details, str(assessment.id), f"ASSESSMENT:{assessment.id}", (str(assessment.id),)))
        for event in session.scalars(risk_query.order_by(RiskEvent.created_at.desc()).limit(limit)):
            risk_level = _normalize_timeline_risk_level(event.risk_level)
            events.append(TimelineEvent(event.created_at, "risk", get_timeline_risk_display(risk_level), event.summary, risk_level, "risk_event", event.evidence_json, str(event.id), f"RISK:{event.id}", (str(event.id),), ("view_risk",), risk_level=risk_level))
        for problem in session.scalars(problem_query.order_by(HealthProblem.opened_at.desc()).limit(limit)):
            events.append(TimelineEvent(problem.opened_at, "major_problem", problem.title, problem.description, problem.severity, problem.source, {"status": problem.status, "owner": problem.owner or problem.responsible_role}, str(problem.id), f"PROBLEM:{problem.id}", (str(problem.id),)))
        for plan in session.scalars(medication_query.order_by(MedicationPlan.created_at.desc()).limit(limit)):
            medication_at = datetime.combine(plan.start_date, datetime.min.time(), tzinfo=timezone.utc)
            change = "停止用药记录" if plan.status.lower() in {"stopped", "inactive", "discontinued"} else "开始用药记录"
            drug_name = (plan.drug_name or "").strip()
            if drug_name.lower().startswith(("demo ", "synthetic_", "synthetic-", "test_", "test-")):
                drug_name = "演示用药记录"
            events.append(TimelineEvent(medication_at, "medication_change", f"{change}：{drug_name or '用药记录'}", f"状态：{plan.status}", "BLUE", "medication_plan", {"frequency": plan.frequency, "route": plan.route, "prescriber": plan.prescriber_name, "department": plan.department, "change_type": change, "record_source": "正式用药记录"}, str(plan.id), f"MEDICATION:{plan.id}", (str(plan.id),)))
        for item in session.scalars(health_event_query.order_by(HealthEvent.start_at.desc()).limit(limit)):
            event_type = item.event_type.lower()
            if event_type not in {"procedure", "surgery", "hospitalization"}:
                continue
            title = {"surgery": "手术", "hospitalization": "住院", "procedure": "医疗处置"}.get(event_type, "医疗事件")
            events.append(TimelineEvent(item.start_at, event_type, title, item.description, item.severity or "GRAY", item.source, {"event_type": event_type, "end_at": item.end_at.isoformat() if item.end_at else None, "record_source": item.source}, str(item.id), f"{event_type.upper()}:{item.id}", (str(item.id),), ("view_procedure",)))
        for review in session.scalars(review_query.order_by(DoctorReview.reviewed_at.desc()).limit(limit)):
            related_risk = session.get(RiskEvent, review.risk_event_id) if review.risk_event_id else None
            events.append(TimelineEvent(review.reviewed_at, "doctor_review", "内部医生复核", review.opinion, "BLUE", "doctor_review", {"department": review.department, "question": review.question_for_doctor, "doctor": review.doctor_name, "status": review.status, "related_risk_level": related_risk.risk_level if related_risk else None}, str(review.id), f"DOCTOR_REVIEW:{review.id}", (str(review.id),), ("view_doctor_review",)))
        for program in session.scalars(program_query.order_by(HealthProgram.created_at.desc()).limit(limit)):
            title = self._program_display_title(program)
            events.append(TimelineEvent(program.created_at, "program_start", title, program.main_goal, "BLUE", "health_program", {"status": program.status, "start_date": str(program.start_date), "end_date": str(program.end_date or ""), "owner": program.owner, "goal": program.main_goal}, str(program.id), f"PROGRAM:{program.id}", (str(program.id),), ("view_program",)))
        for review in session.scalars(adjustment_query.order_by(WeeklyReview.reviewed_at.desc()).limit(limit)):
            events.append(TimelineEvent(review.reviewed_at, "program_adjustment", "调整健康管理计划", review.adjustment or "已完成阶段性管理调整。", "BLUE", "weekly_review", {"program_id": str(review.program_id), "next_focus": review.next_week_focus, "reviewed_by": review.reviewed_by}, str(review.id), f"PROGRAM_ADJUSTMENT:{review.id}", (str(review.id),), ("view_program",)))
        for referral in session.scalars(referral_query.order_by(ExternalReferral.created_at.desc()).limit(limit)):
            events.append(TimelineEvent(referral.created_at, "external_referral", "外部医疗协同", referral.reason, "BLUE", "external_referral", {"specialty": referral.specialty, "organization": referral.organization, "status": referral.status, "question": referral.question, "feedback": referral.feedback}, str(referral.id), f"EXTERNAL_REFERRAL:{referral.id}", (str(referral.id),)))
        for outcome in session.scalars(outcome_query.order_by(OutcomeEvaluation.created_at.desc()).limit(limit)):
            events.append(TimelineEvent(datetime.combine(outcome.evaluation_date, datetime.min.time(), tzinfo=timezone.utc), "outcome", "阶段健康评估", f"{outcome.metric}：{outcome.baseline_value}{outcome.unit} → {outcome.current_value}{outcome.unit}；观察到的前后变化。", "GREEN" if outcome.result == "IMPROVED" else "BLUE", "outcome_evaluation", {"metric": outcome.metric, "before": outcome.baseline_value, "after": outcome.current_value, "unit": outcome.unit, "status": outcome.result, "program_id": str(outcome.program_id)}, str(outcome.id), f"OUTCOME:{outcome.id}", (str(outcome.id),), ("view_outcome",)))
        for request in session.scalars(service_query.order_by(ServiceRequest.completed_at.desc(), ServiceRequest.requested_at.desc()).limit(limit)):
            item = session.get(ServiceCatalogItem, request.service_item_id)
            if not item or not item.is_major_timeline_service:
                continue
            occurred_at = request.completed_at or request.scheduled_at or request.requested_at
            summary = request.result_summary or "服务已安排，等待执行。"
            related_risk = session.get(RiskEvent, request.related_risk_event_id) if request.related_risk_event_id else None
            events.append(TimelineEvent(occurred_at, "service", item.name, summary, "BLUE", "service_request", {"status": request.status, "manager": request.assigned_manager, "requested_by": request.requested_by, "related_risk_level": related_risk.risk_level if related_risk else None}, str(request.id), f"SERVICE:{request.id}", (str(request.id),), ()))

        # A document is the health-story source.  Re-parsing it creates a new
        # run, never a second timeline node.
        latest_by_document: dict[UUID, ReportExtractionRun] = {}
        for run in session.scalars(report_query.order_by(ReportExtractionRun.completed_at.desc(), ReportExtractionRun.created_at.desc()).limit(limit * 4)):
            latest_by_document.setdefault(run.document_id, run)
        report_rows: list[tuple[datetime, TimelineEvent]] = []
        for document_id, run in latest_by_document.items():
            document = session.get(Document, document_id)
            candidates = list(session.scalars(select(ReportExtractionCandidate).where(
                ReportExtractionCandidate.extraction_run_id == run.id,
                ReportExtractionCandidate.status == "CONFIRMED",
            )))
            finding_count = sum(item.candidate_type == "FINDING" for item in candidates)
            followup_count = sum(item.candidate_type == "FOLLOWUP" for item in candidates)
            observation_count = sum(item.candidate_type == "OBSERVATION" for item in candidates)
            # The report's examination date is the health-story date.  Upload
            # and parsing timestamps remain audit metadata, not the main axis.
            at = datetime.combine(run.detected_report_date, datetime.min.time(), tzinfo=timezone.utc) if run.detected_report_date else (run.completed_at or run.created_at)
            report_date = run.detected_report_date.isoformat() if run.detected_report_date else at.date().isoformat()
            title = self._report_display_title(document)
            summary = f"主要发现 {finding_count} 项 · 指标 {observation_count} 项" if candidates else "报告已整理，等待人工确认。"
            details = {"document_id": str(document_id), "report_date": report_date, "hospital": run.detected_hospital, "findings": finding_count, "metrics": observation_count, "followups": followup_count, "review_state": "已确认" if candidates else "等待确认", "system_recorded_at": (run.completed_at or run.created_at).isoformat(), "event_date_source": "report_date" if run.detected_report_date else "system_recorded_at"}
            report_rows.append((at, TimelineEvent(at, "report", title, summary, "BLUE", "report", details, str(document_id), f"REPORT:{document_id}", (str(document_id), str(run.id)), ("view_report", "view_report_comparison"))))
        # The comparison is deterministic and only reads human-confirmed
        # candidates.  It never asks the parser or an LLM to compare PDFs.
        ordered_reports = sorted(report_rows, key=lambda item: item[0])
        for index, (_, report_event) in enumerate(ordered_reports):
            if index == 0:
                continue
            previous = ordered_reports[index - 1][1]
            try:
                comparison = ReportComparisonService().compare(
                    session,
                    member_id,
                    UUID(previous.expandable_details["document_id"]),
                    UUID(report_event.expandable_details["document_id"]),
                )
                report_event.expandable_details["comparison"] = {
                    "new": len(comparison["new_findings"]),
                    "persistent": len(comparison["persistent_findings"]),
                    "changed": len(comparison["changed_findings"]),
                    "not_rechecked": len(comparison["not_rechecked_findings"]),
                    "metric_changes": len(comparison["metric_changes"]),
                }
            except ValueError:
                report_event.expandable_details["comparison"] = None
        events.extend(item for _, item in report_rows)
        events.extend(MonthlyTimelineSummaryService().monthly_summaries(session, member_id, start=start, end=end))
        # group_key is the final guard against duplicate source-derived nodes.
        grouped: dict[str, TimelineEvent] = {}
        for event in sorted(events, key=lambda item: item.occurred_at, reverse=True):
            grouped.setdefault(event.group_key or f"{event.event_type}:{event.related_entity}", event)
        return [self._display_event(event) for event in list(grouped.values())[:limit]]


class TimelineV4Service:
    """Build the correlated lifecycle projection without persisting copies.

    Continuous observations are queried only for selected metrics and a bounded
    time window.  Discrete lifecycle events continue to come from
    :class:`HealthTimelineService`, which retains the report aggregation and
    formal-risk safety rules.
    """

    _METRICS: dict[str, tuple[str, tuple[str, ...]]] = {
        "glucose": ("血糖", ("glucose", "cgm_glucose", "blood_glucose")),
        "systolic_bp": ("血压", ("systolic_bp",)),
        "sleep_duration": ("睡眠时长", ("sleep_duration",)),
        "deep_sleep_duration": ("深度睡眠", ("deep_sleep_duration",)),
        # Keep physical units separate.  A trend must never combine steps,
        # minutes and kilocalories merely because they are all activity data.
        "steps": ("步数", ("steps",)),
        "exercise_minutes": ("活动时长", ("exercise_minutes",)),
        "active_calories": ("活动消耗", ("active_calories",)),
        "weight": ("体重", ("weight",)),
        "resting_heart_rate": ("静息心率", ("resting_heart_rate",)),
    }
    _MEDICAL_TYPES = {"assessment", "report", "health_data_summary", "major_problem", "doctor_review", "external_referral", "procedure", "surgery", "hospitalization", "outcome"}
    _MANAGEMENT_TYPES = {"program_start", "program_adjustment", "intervention"}
    _YEAR_MAJOR_TYPES = {
        "assessment", "report", "risk", "doctor_review", "medication_change",
        "procedure", "surgery", "hospitalization", "service", "outcome",
        "health_data_summary",
    }

    @staticmethod
    def _usable(statement):
        return statement.where(
            Observation.quality_flag.in_(USABLE_QUALITY),
            Observation.excluded_from_analysis.is_(False),
            Observation.source_deleted.is_(False),
        )

    @classmethod
    def available_metric_codes(
        cls, session: Session, member_id: UUID, *, start: datetime | None, end: datetime | None
    ) -> list[str]:
        """Return display metrics that have usable data in this window."""
        available_statement = cls._usable(select(Observation.metric_code).where(
            Observation.patient_id == member_id,
        ))
        if start is not None:
            available_statement = available_statement.where(Observation.observed_at >= start)
        if end is not None:
            available_statement = available_statement.where(Observation.observed_at <= end)
        available = set(session.scalars(available_statement.distinct()))
        result: list[str] = []
        for canonical, (_, aliases) in cls._METRICS.items():
            statement = cls._usable(select(Observation.id).where(
                Observation.patient_id == member_id,
                Observation.metric_code.in_(aliases),
            ))
            if start is not None:
                statement = statement.where(Observation.observed_at >= start)
            if end is not None:
                statement = statement.where(Observation.observed_at <= end)
            if any(alias in available for alias in aliases) and session.scalar(statement.limit(1)) is not None:
                result.append(canonical)
        return result

    def available_history_bounds(self, session: Session, member_id: UUID) -> tuple[datetime, datetime] | None:
        """Return bounded timeline limits without loading raw observations.

        Observation bounds are aggregate SQL queries.  Major-event dates are
        read through the existing timeline assembler with a fixed cap, so the
        range slider never invokes parsing, risk evaluation, or device sync.
        """
        observation_bounds = session.execute(
            self._usable(select(func.min(Observation.observed_at), func.max(Observation.observed_at)).where(
                Observation.patient_id == member_id,
            ))
        ).one()
        candidates = [value for value in observation_bounds if value is not None]
        events = HealthTimelineService().get_timeline(session, member_id, limit=200)
        candidates.extend(event.occurred_at for event in events if event.occurred_at is not None)
        if not candidates:
            return None
        normalized = [
            value.replace(tzinfo=TOKYO_TIMEZONE) if value.tzinfo is None else value.astimezone(TOKYO_TIMEZONE)
            for value in candidates
        ]
        return min(normalized), max(normalized)

    @staticmethod
    def _bucket_at(at: datetime, aggregation: str) -> datetime:
        local = at.astimezone(TOKYO_TIMEZONE)
        if aggregation == "小时":
            return local.replace(minute=0, second=0, microsecond=0)
        if aggregation == "日":
            return local.replace(hour=0, minute=0, second=0, microsecond=0)
        if aggregation == "周":
            day = local - timedelta(days=local.weekday())
            return day.replace(hour=0, minute=0, second=0, microsecond=0)
        if aggregation == "月":
            return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return local

    @staticmethod
    def _aggregation_for(start: datetime | None, end: datetime | None) -> str:
        if start is None or end is None:
            return "月"
        days = max((end - start).total_seconds() / 86_400, 0)
        if days <= 7:
            return "小时"
        if days <= 90:
            return "日"
        if days <= 365 * 3:
            return "周"
        return "月"

    def _series(
        self,
        session: Session,
        member_id: UUID,
        metric_code: str,
        *,
        start: datetime | None,
        end: datetime | None,
        raw_point_limit: int,
    ) -> MetricSeries | None:
        label, aliases = self._METRICS[metric_code]
        statement = self._usable(select(Observation).where(
            Observation.patient_id == member_id,
            Observation.metric_code.in_(aliases),
        ))
        if start is not None:
            statement = statement.where(Observation.observed_at >= start)
        if end is not None:
            statement = statement.where(Observation.observed_at <= end)
        # The hard cap is intentional: a long CGM history must never turn a
        # member page into an unbounded raw-observation load.
        records = list(reversed(list(session.scalars(
            statement.order_by(Observation.observed_at.desc()).limit(raw_point_limit)
        ))))
        if not records:
            return None
        aggregation = self._aggregation_for(start, end)
        buckets: dict[datetime, list[Observation]] = defaultdict(list)
        for record in records:
            buckets[self._bucket_at(record.observed_at, aggregation)].append(record)
        points: list[dict[str, Any]] = []
        for at, rows in sorted(buckets.items(), key=lambda item: item[0]):
            points.append({
                "at": at,
                "value": round(sum(float(row.value_numeric) for row in rows) / len(rows), 3),
                "samples": len(rows),
            })
        return MetricSeries(
            metric_code=metric_code,
            display_name=label,
            unit=records[-1].unit,
            points=tuple(points),
            aggregation=aggregation,
            source=records[-1].source,
            time_range=(start, end),
        )

    @staticmethod
    def _summary(series: tuple[MetricSeries, ...], events: tuple[TimelineEvent, ...]) -> TimelineWindowSummary:
        changes: list[dict[str, Any]] = []
        for item in series:
            if not item.points:
                continue
            first, last = item.points[0]["value"], item.points[-1]["value"]
            changes.append({
                "metric": item.metric_code,
                "label": item.display_name,
                "unit": item.unit,
                "before": first,
                "after": last,
                "delta": round(float(last) - float(first), 3),
            })
        risk_counts = {
            "low": sum(event.risk_level == "GREEN" for event in events if event.event_type == "risk"),
            "medium": sum(event.risk_level == "YELLOW" for event in events if event.event_type == "risk"),
            "high": sum(event.risk_level == "RED" for event in events if event.event_type == "risk"),
        }
        return TimelineWindowSummary(
            health_changes=tuple(changes[:4]),
            risk_counts=risk_counts,
            medical_counts={"医生复核": sum(event.event_type == "doctor_review" for event in events), "医疗事件": sum(event.event_type in {"procedure", "surgery", "hospitalization"} for event in events), "体检与检查": sum(event.event_type == "report" for event in events)},
            management_counts={"健康管理": sum(event.event_type in TimelineV4Service._MANAGEMENT_TYPES for event in events), "阶段结果": sum(event.event_type == "outcome" for event in events)},
            service_counts={"服务": sum(event.event_type == "service" for event in events)},
        )

    @staticmethod
    def _period_end(year: int, month: int, tzinfo) -> datetime:
        next_month = datetime(year + 1, 1, 1, tzinfo=tzinfo) if month == 12 else datetime(year, month + 1, 1, tzinfo=tzinfo)
        return next_month - timedelta(microseconds=1)

    @staticmethod
    def _highest_risk(events: list[TimelineEvent]) -> str | None:
        levels = {event.risk_level for event in events if event.event_type == "risk"}
        for level in ("RED", "YELLOW", "GREEN"):
            if level in levels:
                return level
        return None

    @classmethod
    def _cluster_title(cls, events: list[TimelineEvent], *, zoom_level: str, local_at: datetime) -> str:
        if zoom_level == "YEAR":
            if len(events) == 1:
                return events[0].title
            return f"{local_at.month}月健康事件"
        if len(events) == 1:
            return events[0].title
        labels = "、".join(sorted({event.event_type_label or get_timeline_event_type_display(event.event_type) for event in events})[:3])
        return f"{labels} · {len(events)} 项事件"

    def _semantic_clusters(self, events: tuple[TimelineEvent, ...], viewport: TimelineViewport) -> tuple[TimelineCluster, ...]:
        """Collapse the lifecycle to months or same days for the zoom level.

        The aggregate is strictly a ViewModel; source events and their evidence
        remain untouched.  Continuous observations never enter this method.
        """
        source = list(events)
        if viewport.zoom_level == "YEAR":
            major = [event for event in source if event.event_type in self._YEAR_MAJOR_TYPES]
            source = major or source
        buckets: dict[tuple[int, ...], list[TimelineEvent]] = defaultdict(list)
        for event in source:
            local = event.occurred_at.astimezone(TOKYO_TIMEZONE)
            key = (local.year, local.month) if viewport.zoom_level == "YEAR" else (local.year, local.month, local.day)
            buckets[key].append(event)
        clusters: list[TimelineCluster] = []
        for key, items in sorted(buckets.items()):
            items.sort(key=lambda event: (event.occurred_at, event.group_key))
            local_at = items[0].occurred_at.astimezone(TOKYO_TIMEZONE)
            if viewport.zoom_level == "YEAR":
                period_start = datetime(key[0], key[1], 1, tzinfo=TOKYO_TIMEZONE)
                period_end = self._period_end(key[0], key[1], TOKYO_TIMEZONE)
                target = TimelineViewport(period_start, period_end, "MONTH")
                cluster_id = f"MONTH:{key[0]:04d}-{key[1]:02d}"
            else:
                period_start = datetime(key[0], key[1], key[2], tzinfo=TOKYO_TIMEZONE)
                period_end = period_start + timedelta(days=1) - timedelta(microseconds=1)
                target = None
                cluster_id = f"DAY:{key[0]:04d}-{key[1]:02d}-{key[2]:02d}"
            counts: dict[str, int] = defaultdict(int)
            for event in items:
                counts[event.event_type_label or get_timeline_event_type_display(event.event_type)] += 1
            clusters.append(TimelineCluster(
                cluster_id=cluster_id,
                period_start=period_start,
                period_end=period_end,
                zoom_level=viewport.zoom_level,
                event_count=len(items),
                event_type_counts=dict(counts),
                highest_risk=self._highest_risk(items),
                main_events=tuple(items[:6]),
                zoom_target=target,
            ))
        return tuple(clusters)

    def build_view(
        self,
        session: Session,
        member_id: UUID,
        *,
        start: datetime | None,
        end: datetime | None,
        metric_codes: tuple[str, ...],
        events: list[TimelineEvent] | None = None,
        raw_point_limit: int = 1_200,
        event_limit: int = 100,
    ) -> TimelineViewModel:
        # The UI permits four user-selected trend categories; sleep and
        # activity may add one companion series each for clear paired charts.
        selected = tuple(code for code in metric_codes if code in self._METRICS)[:6]
        metric_series = tuple(
            series for code in selected
            if (series := self._series(session, member_id, code, start=start, end=end, raw_point_limit=raw_point_limit)) is not None
        )
        major_events = events if events is not None else HealthTimelineService().get_timeline(
            session, member_id, start=start, end=end, limit=event_limit,
        )
        if events is not None:
            major_events = [
                event for event in major_events
                if (start is None or event.occurred_at >= start) and (end is None or event.occurred_at <= end)
            ]
        bounded_events = tuple(sorted(major_events[:event_limit], key=lambda item: (item.occurred_at, item.group_key)))
        return TimelineViewModel(
            start=start,
            end=end,
            metric_series=metric_series,
            events=bounded_events,
            summary=self._summary(metric_series, bounded_events),
        )

    def get_timeline_view(
        self,
        session: Session,
        member_id: UUID,
        *,
        viewport: TimelineViewport,
        metric_codes: tuple[str, ...],
        event_types: set[str] | None = None,
        raw_point_limit: int = 1_200,
        event_limit: int = 100,
    ) -> TimelineViewModel:
        """Return one synchronized semantic-zoom projection for the renderer."""
        events = HealthTimelineService().get_timeline(
            session, member_id, start=viewport.start, end=viewport.end, limit=event_limit,
        )
        if event_types is not None:
            events = [event for event in events if event.event_type in event_types]
        base = self.build_view(
            session, member_id, start=viewport.start, end=viewport.end,
            metric_codes=metric_codes, events=events,
            raw_point_limit=raw_point_limit, event_limit=event_limit,
        )
        return replace(base, viewport=viewport, lifecycle_items=self._semantic_clusters(base.events, viewport))


class RiskSummaryService:
    """Minimal, privacy-aware operational risk summary without raw report data."""

    def for_member(self, session: Session, member_id: UUID) -> dict[str, Any]:
        active = list(session.scalars(select(RiskEvent).where(RiskEvent.patient_id == member_id, RiskEvent.status.not_in(("CLOSED", "DISMISSED_DATA_ISSUE"))).order_by(RiskEvent.created_at.desc()).limit(20)))
        level = "UNKNOWN"
        if any(item.risk_level == "RED" for item in active): level = "RED"
        elif any(item.risk_level == "YELLOW" for item in active): level = "YELLOW"
        return {"member_id": str(member_id), "current_risk_level": level, "primary_categories": sorted({item.canonical_code or "other" for item in active}), "updated_at": max((item.updated_at for item in active), default=None), "processing_status": active[0].status if active else "STABLE", "recommended_routes": sorted({item.recommended_route for item in active})}


class ReportRiskSummaryService:
    """Report risk is derived only from confirmed data and existing RiskEvents."""
    def summarize(self, session: Session, member_id: UUID, document_id: UUID) -> dict[str, Any]:
        run = session.scalar(select(ReportExtractionRun).where(ReportExtractionRun.patient_id == member_id, ReportExtractionRun.document_id == document_id).order_by(ReportExtractionRun.created_at.desc()))
        if run is None: return {"level": "UNKNOWN", "reason": "暂无解析记录。", "rules": []}
        candidates = list(session.scalars(select(ReportExtractionCandidate).where(ReportExtractionCandidate.extraction_run_id == run.id)))
        if any(item.status in {"PENDING_REVIEW", "NEEDS_MANUAL_REVIEW"} for item in candidates):
            return {"level": "NEEDS_REVIEW", "reason": "报告仍有需要人工确认的内容。", "rules": []}
        confirmed = [item for item in candidates if item.status == "CONFIRMED" and item.candidate_type == "OBSERVATION"]
        if not confirmed: return {"level": "UNKNOWN", "reason": "暂无可用于正式规则判断的已确认指标。", "rules": []}
        codes = {item.canonical_code for item in confirmed if item.canonical_code}
        events = list(session.scalars(select(RiskEvent).where(RiskEvent.patient_id == member_id, RiskEvent.canonical_code.in_(codes), RiskEvent.status.not_in(("CLOSED", "DISMISSED_DATA_ISSUE"))).order_by(RiskEvent.updated_at.desc()).limit(30))) if codes else []
        if any(event.risk_level == "RED" for event in events): level = "RED"
        elif any(event.risk_level == "YELLOW" for event in events): level = "YELLOW"
        else: level = "UNKNOWN"
        return {"level": level, "reason": "已审核规则触发的正式风险事件。" if events else "已确认数据暂无适用的正式风险规则覆盖。", "rules": [str(event.risk_rule_id) for event in events], "event_ids": [str(event.id) for event in events]}


class OversightRiskSummaryService:
    """Aggregate-only oversight view; intentionally never returns member clinical data."""
    def summarize(self, session: Session) -> dict[str, Any]:
        active = list(session.scalars(select(RiskEvent).where(RiskEvent.status.not_in(("CLOSED", "DISMISSED_DATA_ISSUE"))).limit(500)))
        return {"member_coverage": int(session.scalar(select(func.count(HealthAssessment.id)).where(HealthAssessment.status == "CONFIRMED")) or 0), "red": sum(item.risk_level == "RED" for item in active), "yellow": sum(item.risk_level == "YELLOW" for item in active), "unhandled": sum(item.status == "OPEN" for item in active), "doctor_pending": sum(item.status == "ESCALATED_TO_DOCTOR" for item in active), "closed_rate": 0, "clinical_details_included": False}


class InterventionOutcomeService:
    """Descriptive before/after comparison; no causal statement is made."""

    def compare(self, session: Session, member_id: UUID, metric_code: str, intervention_started_at: datetime, *, days: int = 30) -> dict[str, Any] | None:
        before_start = intervention_started_at - timedelta(days=days)
        after_end = intervention_started_at + timedelta(days=days)
        records = list(session.scalars(select(Observation).where(Observation.patient_id == member_id, Observation.metric_code == metric_code, Observation.quality_flag.in_(USABLE_QUALITY), Observation.excluded_from_analysis.is_(False), Observation.source_deleted.is_(False), Observation.observed_at >= before_start, Observation.observed_at <= after_end).order_by(Observation.observed_at)))
        before = [float(item.value_numeric) for item in records if item.observed_at < intervention_started_at]
        after = [float(item.value_numeric) for item in records if item.observed_at >= intervention_started_at]
        if len(before) < 2 or len(after) < 2:
            return {"status": "INSUFFICIENT_DATA", "label": "数据不足，暂不能比较。"}
        return {"status": "READY", "metric": metric_code, "before_window_days": days, "after_window_days": days, "before_summary": sum(before) / len(before), "after_summary": sum(after) / len(after), "difference": (sum(after) / len(after)) - (sum(before) / len(before)), "unit": records[-1].unit, "before_samples": len(before), "after_samples": len(after), "label": "观察到的干预前后变化，不代表因果结论。"}
