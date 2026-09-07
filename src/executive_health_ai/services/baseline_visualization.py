"""Read-only projections for annual health-baseline visualizations.

The projection never writes health facts, infers medical risk, or invents a
reference interval.  Reference semantics are accepted only from the confirmed
report candidate captured by the baseline.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from executive_health_ai.models import HealthAssessment, Observation, ReportExtractionCandidate
from executive_health_ai.integrations.codes import canonical_code, canonical_metric_key, storage_aliases
from executive_health_ai.integrations.normalization import normalize_unit
from executive_health_ai.services.longitudinal import HealthAssessmentService, USABLE_QUALITY


METRIC_LABELS = {
    "ldl_c": "LDL-C", "hdl_c": "HDL-C", "triglycerides": "甘油三酯", "hba1c": "糖化血红蛋白",
    "bmi": "BMI", "weight": "体重", "waist_circumference": "腰围",
    "systolic_bp": "收缩压", "diastolic_bp": "舒张压", "alt": "ALT", "ast": "AST",
    "glucose": "血糖", "steps": "步数", "exercise_minutes": "运动时间",
    "sleep_duration": "睡眠时长",
}
SUPPORTED_REFERENCE_METRICS = {"ldl_c", "hdl_c", "triglycerides", "hba1c", "bmi", "weight", "waist_circumference", "systolic_bp", "diastolic_bp", "alt", "ast"}
DOMAIN_METRICS = {
    "代谢健康": {"ldl_c", "hdl_c", "triglycerides", "hba1c", "glucose"},
    "心血管": {"systolic_bp", "diastolic_bp", "heart_rate"},
    "肝脏": {"alt", "ast"},
    "体重与体成分": {"weight", "bmi", "waist_circumference"},
    "生活方式": {"steps", "exercise_minutes", "sleep_duration", "deep_sleep_duration"},
}
DOMAIN_FINDING_TERMS = {
    "肝脏": ("肝",), "肺部": ("肺", "胸部"), "甲状腺": ("甲状腺",),
}


@dataclass(frozen=True)
class ReferenceInterval:
    text: str
    lower: Decimal | None
    upper: Decimal | None
    kind: str


@dataclass(frozen=True)
class BaselineMetricView:
    code: str
    label: str
    value: Decimal | None
    value_text: str
    unit: str
    observed_at: datetime | None
    source_candidate_id: UUID | None
    reference: ReferenceInterval | None
    explicit_status: str
    current_value: Decimal | None = None
    current_date: datetime | None = None

    @property
    def metric_name(self) -> str:
        return self.label

    @property
    def canonical_code(self) -> str:
        return self.code

    @property
    def baseline_value(self) -> Decimal | None:
        return self.value

    @property
    def baseline_date(self) -> datetime | None:
        return self.observed_at

    @property
    def evidence(self) -> UUID | None:
        return self.source_candidate_id


@dataclass(frozen=True)
class TrendPoint:
    observed_at: datetime
    value: Decimal
    series: str
    point_type: str


@dataclass(frozen=True)
class BaselineTrendView:
    code: str
    label: str
    unit: str
    baseline_value: Decimal
    points: tuple[TrendPoint, ...]

    @property
    def has_follow_up(self) -> bool:
        return any(point.point_type == "FOLLOW_UP" for point in self.points)


@dataclass(frozen=True)
class CoverageItem:
    label: str
    status: str


@dataclass(frozen=True)
class HealthDomainView:
    label: str
    status: str
    summary: str


@dataclass(frozen=True)
class BaselineComparisonView:
    code: str
    label: str
    baseline: str
    current: str
    unit: str
    status: str


@dataclass(frozen=True)
class AmendmentView:
    reason: str
    changed_at: datetime
    confirmed_by: str
    changes: tuple[str, ...]
    evidence: str


@dataclass(frozen=True)
class BaselineVisualization:
    assessment: HealthAssessment
    metrics: tuple[BaselineMetricView, ...]
    trends: tuple[BaselineTrendView, ...]
    coverage: tuple[CoverageItem, ...]
    domains: tuple[HealthDomainView, ...]
    comparisons: tuple[BaselineComparisonView, ...]
    amendments: tuple[AmendmentView, ...]

    @property
    def covered_count(self) -> int:
        return sum(item.status == "已覆盖" for item in self.coverage)


def _decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value)) if value not in {None, ""} else None
    except (InvalidOperation, ValueError):
        return None


def parse_reference_interval(text: str | None) -> ReferenceInterval | None:
    """Parse only explicit report interval/threshold notation."""
    raw = (text or "").strip().replace("，", ",")
    if not raw:
        return None
    normalized = raw.replace("－", "-").replace("—", "-").replace("–", "-").replace("～", "~")
    number = r"[-+]?\d+(?:\.\d+)?"
    match = re.search(fr"({number})\s*(?:-|~|至)\s*({number})", normalized)
    if match:
        lower, upper = _decimal(match.group(1)), _decimal(match.group(2))
        if lower is not None and upper is not None and lower <= upper:
            return ReferenceInterval(raw, lower, upper, "RANGE")
    match = re.search(fr"(?:<=|≤|<)\s*({number})", normalized)
    if match:
        return ReferenceInterval(raw, None, _decimal(match.group(1)), "UPPER")
    match = re.search(fr"(?:>=|≥|>)\s*({number})", normalized)
    if match:
        return ReferenceInterval(raw, _decimal(match.group(1)), None, "LOWER")
    return None


def _uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except (TypeError, ValueError):
        return None


def _datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value)) if value else None
    except (TypeError, ValueError):
        return None


def _explicit_status(flag: str | None) -> str:
    value = (flag or "").strip().upper()
    if value in {"H", "HIGH", "↑"}:
        return "报告标记偏高"
    if value in {"L", "LOW", "↓"}:
        return "报告标记偏低"
    return "已记录"


def _comparable_value(metric: BaselineMetricView, observation: Observation) -> Decimal | None:
    """Return a safely comparable value, using only explicit unit normalization."""
    if observation.value_numeric is None:
        return None
    if (observation.unit or "").strip().lower() == (metric.unit or "").strip().lower():
        return observation.value_numeric
    definition = canonical_code(metric.code)
    if definition is None or (metric.unit or "").strip().lower() != definition.default_unit.lower():
        return None
    try:
        value, unit = normalize_unit(definition, observation.value_numeric, observation.unit)
    except ValueError:
        return None
    return value if unit.lower() == metric.unit.lower() else None


class BaselineVisualizationService:
    """Build one bounded query projection for member/manager/doctor views."""

    def available_years(self, session: Session, member_id: UUID) -> tuple[int, ...]:
        rows = session.scalars(select(HealthAssessment).where(
            HealthAssessment.patient_id == member_id,
            HealthAssessment.assessment_type == "BASELINE",
            HealthAssessment.status.in_(("CONFIRMED", "AMENDED")),
            HealthAssessment.cycle_year.is_not(None),
        ).order_by(HealthAssessment.cycle_year.desc())).all()
        return tuple(dict.fromkeys(int(row.cycle_year) for row in rows if row.cycle_year is not None))

    def build(self, session: Session, member_id: UUID, *, cycle_year: int | None = None) -> BaselineVisualization:
        baseline = HealthAssessmentService().latest_baseline(
            session, member_id, include_draft=False, cycle_year=cycle_year,
        )
        if baseline is None:
            raise ValueError("该年度尚无已确认健康基线。")
        snapshot = baseline.baseline_json or {}
        raw_metrics = [row for row in snapshot.get("key_metrics", []) if isinstance(row, dict)]
        candidate_ids = [candidate_id for row in raw_metrics if (candidate_id := _uuid(row.get("source_candidate_id")))]
        candidates = {
            row.id: row for row in session.scalars(select(ReportExtractionCandidate).where(
                ReportExtractionCandidate.patient_id == member_id,
                ReportExtractionCandidate.id.in_(candidate_ids),
                ReportExtractionCandidate.status == "CONFIRMED",
            ))
        } if candidate_ids else {}
        metrics: list[BaselineMetricView] = []
        for row in raw_metrics:
            code = canonical_metric_key(str(row.get("metric") or ""))
            candidate_id = _uuid(row.get("source_candidate_id"))
            candidate = candidates.get(candidate_id)
            value = _decimal(row.get("value"))
            reference = parse_reference_interval(candidate.reference_range if candidate else None)
            metrics.append(BaselineMetricView(
                code=code, label=METRIC_LABELS.get(code, code.upper() or "健康指标"),
                value=value, value_text=str(row.get("value") or "未记录"), unit=str(row.get("unit") or ""),
                observed_at=_datetime(row.get("observed_at")), source_candidate_id=candidate_id,
                reference=reference if code in SUPPORTED_REFERENCE_METRICS else None,
                explicit_status=_explicit_status(candidate.abnormal_flag if candidate else None),
            ))

        metric_codes = {metric.code for metric in metrics if metric.value is not None}
        query_codes = {alias for code in metric_codes for alias in storage_aliases(code)}
        observations = list(session.scalars(select(Observation).where(
            Observation.patient_id == member_id,
            func.lower(Observation.metric_code).in_(query_codes),
            Observation.quality_flag.in_(USABLE_QUALITY),
            Observation.excluded_from_analysis.is_(False),
            Observation.source_deleted.is_(False),
        ).order_by(Observation.observed_at))) if metric_codes else []
        by_code: dict[str, list[Observation]] = {}
        for observation in observations:
            by_code.setdefault(canonical_metric_key(observation.metric_code), []).append(observation)
        trends: list[BaselineTrendView] = []
        comparisons: list[BaselineComparisonView] = []
        finalized_metrics: list[BaselineMetricView] = []
        for metric in metrics:
            if metric.value is None:
                finalized_metrics.append(metric)
                continue
            baseline_at = metric.observed_at or baseline.confirmed_at or baseline.assessed_at
            points = [TrendPoint(baseline_at, metric.value, metric.label, "BASELINE")]
            comparable = [
                (row, value) for row in by_code.get(metric.code, [])
                if row.observed_at > baseline_at and (value := _comparable_value(metric, row)) is not None
            ]
            points.extend(TrendPoint(row.observed_at, value, metric.label, "FOLLOW_UP") for row, value in comparable)
            trends.append(BaselineTrendView(metric.code, metric.label, metric.unit, metric.value, tuple(points)))
            current = comparable[-1] if comparable else None
            finalized_metrics.append(replace(
                metric,
                current_value=current[1] if current else None,
                current_date=current[0].observed_at if current else None,
            ))
            comparisons.append(BaselineComparisonView(
                metric.code, metric.label, metric.value_text,
                str(current[1]) if current else "暂无后续数据", metric.unit,
                "发生变化" if current and current[1] != metric.value else "已记录" if current else "未复查",
            ))

        coverage = self._coverage(snapshot)
        domains = self._domains(snapshot, metrics, coverage)
        amendments = self._amendments(session, baseline)
        return BaselineVisualization(baseline, tuple(finalized_metrics), tuple(trends), coverage, domains, tuple(comparisons), amendments)

    @staticmethod
    def _coverage(snapshot: dict[str, Any]) -> tuple[CoverageItem, ...]:
        pending = set((snapshot.get("completeness") or {}).get("pending") or [])
        data = snapshot.get("data_coverage") or {}
        medications = snapshot.get("current_medications")
        medication_covered = (isinstance(medications, list) and bool(medications)) or (isinstance(medications, dict) and medications.get("status") == "CONFIRMED_NONE")
        history_covered = bool(snapshot.get("health_problems")) or isinstance(snapshot.get("procedures_or_hospitalizations"), list)
        vital_codes = {canonical_metric_key(str(row.get("metric") or "")) for row in snapshot.get("key_metrics", []) if isinstance(row, dict)}
        vitals_covered = bool(vital_codes & {"weight", "bmi", "systolic_bp", "diastolic_bp"})
        continuous_statuses = [str(value) for value in data.values()]
        continuous = "部分" if continuous_statuses else "暂无数据"
        if continuous_statuses and all(value in {"暂无数据", "待补充"} for value in continuous_statuses):
            continuous = "暂无数据"
        lifestyle = snapshot.get("member_reported") or {}
        fields = lifestyle.get("fields") if isinstance(lifestyle, dict) else {}
        lifestyle_status = "已覆盖" if isinstance(fields, dict) and fields.get("生活方式资料") else "待补充"
        return (
            CoverageItem("年度体检", "已覆盖" if snapshot.get("source_reports") else "待补充" if "缺少年度体检" in pending else "暂无数据"),
            CoverageItem("既往史", "已覆盖" if history_covered else "待补充"),
            CoverageItem("当前用药", "已覆盖" if medication_covered else "待补充" if "当前用药" in pending else "暂无数据"),
            CoverageItem("生命体征", "已覆盖" if vitals_covered else "暂无数据"),
            CoverageItem("连续健康数据", continuous),
            CoverageItem("生活方式", lifestyle_status),
        )

    @staticmethod
    def _domains(snapshot: dict[str, Any], metrics: list[BaselineMetricView], _coverage: tuple[CoverageItem, ...]) -> tuple[HealthDomainView, ...]:
        findings = [str(row.get("summary") or "") for row in snapshot.get("important_findings", []) if isinstance(row, dict)]
        rows: list[HealthDomainView] = []
        for label, domain_codes in DOMAIN_METRICS.items():
            matching = [metric for metric in metrics if metric.code in domain_codes]
            matching_findings = [text for text in findings if any(term in text for term in DOMAIN_FINDING_TERMS.get(label, ()))]
            if matching_findings:
                status, summary = "需要持续关注", "；".join(matching_findings[:2])
            elif not matching:
                status, summary = "资料不足", "当前基线中暂无该领域的可展示指标。"
            elif any(metric.explicit_status != "已记录" for metric in matching):
                status = "需要持续关注"
                summary = "、".join(f"{metric.label}{metric.explicit_status.replace('报告标记', '')}" for metric in matching if metric.explicit_status != "已记录")
            else:
                status, summary = "已建立", "已记录" + "、".join(metric.label for metric in matching) + "作为年度参考。"
            rows.append(HealthDomainView(label, status, summary))
        for label in ("肺部", "甲状腺"):
            matching_findings = [text for text in findings if any(term in text for term in DOMAIN_FINDING_TERMS[label])]
            rows.append(HealthDomainView(
                label, "需要持续关注" if matching_findings else "资料不足",
                "；".join(matching_findings[:2]) if matching_findings else "当前基线中暂无该领域的可展示资料。",
            ))
        medications = snapshot.get("current_medications")
        rows.append(HealthDomainView("用药", "已建立" if isinstance(medications, list) and medications else "资料不足", "已记录基线建立时的当前用药。" if isinstance(medications, list) and medications else "当前用药资料待补充。"))
        return tuple(rows)

    @staticmethod
    def _amendments(session: Session, baseline: HealthAssessment) -> tuple[AmendmentView, ...]:
        rows = list(session.scalars(select(HealthAssessment).where(
            HealthAssessment.patient_id == baseline.patient_id,
            HealthAssessment.assessment_type == "BASELINE",
            HealthAssessment.cycle_year == baseline.cycle_year,
            HealthAssessment.amendment_type == "CORRECTION",
        ).order_by(HealthAssessment.confirmed_at.desc())))
        result = []
        for row in rows:
            correction = (row.baseline_json or {}).get("confirmed_correction") or {}
            changes = tuple(filter(None, [str(correction.get("content") or "").strip()]))
            evidence = str(correction.get("evidence") or (row.source_references_json or {}).get("amendment_evidence") or "已关联修订依据")
            result.append(AmendmentView(
                row.amendment_reason or "资料纠正", row.confirmed_at or row.assessed_at,
                row.amended_by or row.reviewed_by or "健康管理团队", changes, evidence,
            ))
        return tuple(result)
