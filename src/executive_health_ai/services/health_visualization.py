"""Read-only, role-independent series for health charts. No medical scoring."""
from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from sqlalchemy import select

from executive_health_ai.integrations.codes import canonical_code, canonical_metric_key
from executive_health_ai.integrations.normalization import normalize_unit
from executive_health_ai.models import Observation, ReportExtractionCandidate, ReportExtractionRun, RiskEvent, SleepSession
from executive_health_ai.services.longitudinal import USABLE_QUALITY
from executive_health_ai.services.baseline_visualization import comparison_change, number_text, METRIC_LABELS

LOCAL = ZoneInfo("Asia/Tokyo")
PERIODS = {"7天": 7, "30天": 30, "3个月": 90, "6个月": 180, "1年": 365, "全部": None}
DISPLAY_LABELS = {**METRIC_LABELS, "resting_heart_rate": "静息心率", "spo2": "血氧", "steps": "步数", "active_calories": "活动消耗", "rem_sleep_duration": "快速眼动睡眠时长", "sleep_score": "来源设备睡眠评分"}


def metric_label(code):
    definition = canonical_code(code)
    chinese = next((a for a in definition.aliases if any('\u4e00' <= c <= '\u9fff' for c in a)), None) if definition else None
    return DISPLAY_LABELS.get(code, chinese or "健康指标")


@dataclass(frozen=True)
class HealthPoint:
    at: datetime
    value: Decimal
    source: str


@dataclass(frozen=True)
class HealthSeries:
    code: str
    label: str
    unit: str
    points: tuple[HealthPoint, ...]

    @property
    def has_trend(self):
        return len({p.at for p in self.points}) >= 2

    @property
    def comparison(self):
        if not self.points:
            return "暂无数据"
        first, last = self.points[0], self.points[-1]
        if not self.has_trend:
            return f"当前 {number_text(last.value)} {self.unit}"
        delta, _, direction = comparison_change(first.value, last.value, self.code, self.unit)
        delta_unit = "个百分点" if self.unit == "%" else self.unit
        return f"{number_text(first.value)} → {number_text(last.value)} {self.unit} · {direction} {number_text(abs(delta))} {delta_unit}"


def filter_period(series, period="3个月", *, now=None, start=None, end=None):
    now = now or datetime.now(timezone.utc)
    days = PERIODS.get(period)
    cutoff = start or (now - timedelta(days=days) if days else None)
    return tuple(replace(s, points=tuple(p for p in s.points if (cutoff is None or p.at >= cutoff) and (end is None or p.at <= end))) for s in series)


def default_period(series, *, now=None):
    # Sparse lab tests should not look empty merely because the default is short.
    return "3个月" if any(s.has_trend for s in filter_period(series, "3个月", now=now)) else "全部"


def series_options(series):
    by_code = {s.code: s for s in series}
    options = {}
    if all(c in by_code for c in ("systolic_bp", "diastolic_bp")) and by_code["systolic_bp"].unit == by_code["diastolic_bp"].unit:
        options["blood_pressure"] = (by_code.pop("systolic_bp"), by_code.pop("diastolic_bp"))
    for code in ("weight", "bmi", "glucose", "hba1c", "ldl_c", "sleep_duration", "steps", "exercise_minutes"):
        if code in by_code:
            options[code] = (by_code.pop(code),)
    options.update({code: (s,) for code, s in by_code.items()})
    return options


def option_label(code, group):
    return "血压（收缩压 / 舒张压）" if code == "blood_pressure" else group[0].label


class HealthVisualizationService:
    def _normalized(self, code, value, unit):
        try:
            number = Decimal(str(value))
            if not number.is_finite():
                return None
            definition = canonical_code(code)
            if definition:
                # Stored same-unit numbers are already normalized (notably SpO2).
                if (unit or "").lower() != definition.default_unit.lower():
                    number, unit = normalize_unit(definition, number, unit)
                else:
                    unit = definition.default_unit
            elif not unit:
                return None
            return number, unit
        except (ValueError, InvalidOperation, TypeError):
            return None

    def build(self, session, patient_id):
        rows = session.scalars(select(Observation).where(
            Observation.patient_id == patient_id, Observation.quality_flag.in_(USABLE_QUALITY),
            Observation.source_deleted.is_(False), Observation.excluded_from_analysis.is_(False),
            Observation.value_numeric.is_not(None),
        ).order_by(Observation.observed_at, Observation.created_at))
        grouped = {}
        sources = {"manual": "人工记录", "device": "设备数据", "confirmed_health_check_report": "已确认体检报告", "confirmed_report": "已确认体检报告"}
        for row in rows:
            code = canonical_metric_key(row.metric_code)
            normalized = self._normalized(code, row.value_numeric, row.unit)
            if normalized is None:
                continue
            value, unit = normalized
            grouped.setdefault((code, unit), {})[row.observed_at] = HealthPoint(row.observed_at, value, sources.get(row.source, "健康数据"))
        # Some existing imports provide SleepSession only. Fill missing nights;
        # never add a second point for a night already represented by Observation.
        nights = {(code, p.at.astimezone(LOCAL).date()) for (code, _), points in grouped.items() for p in points.values()}
        for row in session.scalars(select(SleepSession).where(SleepSession.patient_id == patient_id).order_by(SleepSession.sleep_end)):
            for code, value in (("sleep_duration", row.total_sleep_minutes), ("deep_sleep_duration", row.deep_sleep_minutes), ("rem_sleep_duration", row.rem_sleep_minutes), ("awake_duration", row.awake_minutes)):
                night = (code, row.sleep_end.astimezone(LOCAL).date())
                if value is not None and night not in nights:
                    grouped.setdefault((code, "minutes"), {})[row.sleep_end] = HealthPoint(row.sleep_end, Decimal(value), "睡眠记录")
                    nights.add(night)
        result = []
        for (code, unit), points in grouped.items():
            ordered = tuple(sorted(points.values(), key=lambda p: p.at))
            # Display units only; the original observations remain immutable.
            if code.endswith("sleep_duration") or code in {"sleep_duration", "awake_duration", "rem_sleep_duration"}:
                if unit == "minutes":
                    ordered = tuple(replace(p, value=p.value / 60) for p in ordered)
                    unit = "小时"
            unit = {"count": "步" if code == "steps" else "次", "minutes": "分钟", "bpm": "次/分"}.get(unit, unit)
            result.append(HealthSeries(code, metric_label(code), unit, ordered))
        return tuple(result)

    def previews(self, series, limit=2):
        options = series_options(series)
        order = ["weight", "blood_pressure", "glucose", "hba1c", "sleep_duration", "steps"]
        return tuple((c, options[c]) for c in [*order, *[k for k in options if k not in order]] if c in options and any(s.has_trend for s in options[c]))[:limit]

    def for_review(self, session, patient_id, review):
        codes = []
        if review.risk_event_id:
            risk = session.get(RiskEvent, review.risk_event_id)
            if risk and risk.patient_id == patient_id and risk.canonical_code:
                codes.append(canonical_metric_key(risk.canonical_code))
        question = (review.question_for_doctor or "").lower()
        terms = {"血压": ["systolic_bp", "diastolic_bp"], "blood pressure": ["systolic_bp", "diastolic_bp"], "血糖": ["glucose", "fasting_glucose"], "hba1c": ["hba1c"], "糖化": ["hba1c"], "体重": ["weight"], "ldl": ["ldl_c"], "血氧": ["spo2"], "心率": ["heart_rate"]}
        for term, matches in terms.items():
            if term in question:
                codes.extend(matches)
        if {"systolic_bp", "diastolic_bp"} & set(codes):
            codes.extend(["systolic_bp", "diastolic_bp"])
        return tuple(s for s in self.build(session, patient_id) if s.code in codes)

    def report_series(self, session, patient_id):
        # Only the latest parse of each report, and only human-confirmed numbers.
        runs = list(session.scalars(select(ReportExtractionRun).where(ReportExtractionRun.patient_id == patient_id).order_by(ReportExtractionRun.created_at.desc())))
        latest = {}
        for run in runs:
            latest.setdefault(run.document_id, run)
        by_id = {r.id: r for r in latest.values() if r.detected_report_date is not None}
        if not by_id:
            return ()
        grouped = {}
        for row in session.scalars(select(ReportExtractionCandidate).where(ReportExtractionCandidate.patient_id == patient_id, ReportExtractionCandidate.extraction_run_id.in_(by_id), ReportExtractionCandidate.status == "CONFIRMED", ReportExtractionCandidate.candidate_type == "OBSERVATION")):
            code = canonical_metric_key(row.canonical_code or "")
            normalized = self._normalized(code, row.normalized_value, row.unit)
            if normalized is None:
                continue
            value, unit = normalized
            at = datetime.combine(by_id[row.extraction_run_id].detected_report_date, time(9), LOCAL)
            grouped.setdefault((code, unit), {})[at] = HealthPoint(at, value, "已确认体检报告")
        return tuple(HealthSeries(code, metric_label(code), unit, tuple(sorted(points.values(), key=lambda p:p.at))) for (code, unit), points in grouped.items())
