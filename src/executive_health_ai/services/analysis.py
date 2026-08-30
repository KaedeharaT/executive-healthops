"""Descriptive, non-diagnostic summaries for the V0.1 local demo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from statistics import mean, pstdev
from typing import Iterable

from executive_health_ai.blood_pressure import (
    BloodPressureRecord,
    SevenDayBloodPressureSummary,
    TOKYO_TIMEZONE,
    calculate_seven_day_summary,
    recent_seven_day_records,
)
from executive_health_ai.models import MedicationEvent, Observation, SleepSession


@dataclass(frozen=True)
class CGMSummary:
    count: int
    completeness_percent: float
    average_glucose: Decimal | None
    min_glucose: Decimal | None
    max_glucose: Decimal | None
    variability: float | None
    daily_means: dict[str, Decimal]
    daytime_average: Decimal | None
    nighttime_average: Decimal | None
    meal_associated_peak_count: int
    interpretation_status: str


@dataclass(frozen=True)
class SleepSummary:
    count: int
    average_sleep_minutes: float | None
    bedtime_consistency_minutes: float | None
    average_sleep_efficiency: float | None
    sleep_efficiency_trend: str
    resting_hr_trend: str
    hrv_trend: str
    interpretation_status: str


@dataclass(frozen=True)
class MedicationAdherenceSummary:
    scheduled_count: int
    taken_count: int
    missed_count: int
    adherence_percent: float | None
    interpretation_status: str


@dataclass(frozen=True)
class BloodPressurePeriodSummary:
    """A selectable 7- or 30-day descriptive BP summary."""

    days: int
    valid_measurement_count: int
    completeness_percent: float
    morning_average_systolic: Decimal | None
    morning_average_diastolic: Decimal | None
    evening_average_systolic: Decimal | None
    evening_average_diastolic: Decimal | None
    recent_period_average_systolic: Decimal | None
    previous_period_average_systolic: Decimal | None
    trend: str
    interpretation_status: str


def calculate_blood_pressure_summary(
    records: Iterable[BloodPressureRecord], days: int = 7
) -> BloodPressurePeriodSummary:
    """Summarize the latest local-calendar 7 or 30 day period without thresholds."""

    if days not in {7, 30}:
        raise ValueError("V0.1 仅支持 7 天或 30 天血压总结。")
    all_records = sorted(records, key=lambda record: record.observed_at)
    if not all_records:
        return BloodPressurePeriodSummary(days, 0, 0.0, None, None, None, None, None, None, "insufficient_data", "insufficient_data")
    latest_day = all_records[-1].observed_at.astimezone(TOKYO_TIMEZONE).date()
    first_day = latest_day - timedelta(days=days - 1)
    selected = [record for record in all_records if first_day <= record.observed_at.astimezone(TOKYO_TIMEZONE).date() <= latest_day]
    valid = [record for record in selected if record.is_complete]
    present = sum(value is not None for record in selected for value in (record.systolic_bp, record.diastolic_bp, record.heart_rate))
    completeness = present / (len(selected) * 3) * 100 if selected else 0.0
    morning = [record for record in valid if record.observed_at.astimezone(TOKYO_TIMEZONE).hour < 12]
    evening = [record for record in valid if record.observed_at.astimezone(TOKYO_TIMEZONE).hour >= 18]
    morning_sys, morning_dia = _blood_pressure_means(morning)
    evening_sys, evening_dia = _blood_pressure_means(evening)
    split_days = 3 if days == 7 else 15
    split_date = latest_day - timedelta(days=split_days - 1)
    recent = [record for record in valid if record.observed_at.astimezone(TOKYO_TIMEZONE).date() >= split_date]
    previous = [record for record in valid if record.observed_at.astimezone(TOKYO_TIMEZONE).date() < split_date]
    recent_sys, _ = _blood_pressure_means(recent)
    previous_sys, _ = _blood_pressure_means(previous)
    has_each_day = {record.observed_at.astimezone(TOKYO_TIMEZONE).date() for record in valid} >= {first_day + timedelta(days=index) for index in range(days)}
    trend = _compare_bp_means(previous_sys, recent_sys, has_each_day)
    status = "needs_clinician_review" if any(record.has_conflicting_metrics for record in selected) else "insufficient_data" if not has_each_day else "needs_remeasurement" if completeness < 100 else "normal"
    return BloodPressurePeriodSummary(days, len(valid), completeness, morning_sys, morning_dia, evening_sys, evening_dia, recent_sys, previous_sys, trend, status)


def calculate_cgm_summary(
    observations: Iterable[Observation], expected_interval_minutes: int = 15
) -> CGMSummary:
    """Describe CGM coverage and variation without setting clinical targets."""

    glucose = sorted(
        (item for item in observations if item.metric_code == "glucose"),
        key=lambda item: item.observed_at,
    )
    if not glucose:
        return CGMSummary(0, 0.0, None, None, None, None, {}, None, None, 0, "insufficient_data")
    values = [Decimal(item.value_numeric) for item in glucose]
    first, last = glucose[0].observed_at, glucose[-1].observed_at
    expected = max(1, int((last - first).total_seconds() / 60 / expected_interval_minutes) + 1)
    daily: dict[str, list[Decimal]] = {}
    daytime: list[Decimal] = []
    nighttime: list[Decimal] = []
    for item, value in zip(glucose, values, strict=True):
        local = item.observed_at.astimezone(TOKYO_TIMEZONE)
        daily.setdefault(local.date().isoformat(), []).append(value)
        if 6 <= local.hour < 22:
            daytime.append(value)
        else:
            nighttime.append(value)
    daily_means = {day: sum(items) / len(items) for day, items in daily.items()}
    variability = pstdev(float(value) for value in values) if len(values) > 1 else 0.0
    # A descriptive peak is a local point above that local day's mean; the UI
    # labels it only as a data pattern, never as a clinical target failure.
    peak_count = sum(value > daily_means[item.observed_at.astimezone(TOKYO_TIMEZONE).date().isoformat()] for item, value in zip(glucose, values, strict=True))
    completeness = min(100.0, len(glucose) / expected * 100)
    status = "normal" if completeness >= 80 and len(glucose) >= 8 else "insufficient_data"
    return CGMSummary(
        len(glucose), completeness, sum(values) / len(values), min(values), max(values),
        variability, daily_means, _decimal_mean(daytime), _decimal_mean(nighttime), peak_count, status,
    )


def calculate_sleep_summary(sessions: Iterable[SleepSession]) -> SleepSummary:
    """Describe sleep timing and device metrics; it does not diagnose sleep disease."""

    ordered = sorted(sessions, key=lambda item: item.sleep_end)
    if not ordered:
        return SleepSummary(0, None, None, None, "insufficient_data", "insufficient_data", "insufficient_data", "insufficient_data")
    durations = [item.total_sleep_minutes for item in ordered]
    bedtime_minutes = [
        item.sleep_start.astimezone(TOKYO_TIMEZONE).hour * 60 + item.sleep_start.astimezone(TOKYO_TIMEZONE).minute
        for item in ordered
    ]
    efficiencies = [float(item.sleep_efficiency) for item in ordered if item.sleep_efficiency is not None]
    hrs = [float(item.avg_heart_rate) for item in ordered if item.avg_heart_rate is not None]
    hrvs = [float(item.avg_hrv) for item in ordered if item.avg_hrv is not None]
    status = "normal" if len(ordered) >= 7 else "insufficient_data"
    return SleepSummary(
        count=len(ordered), average_sleep_minutes=mean(durations),
        bedtime_consistency_minutes=pstdev(bedtime_minutes) if len(bedtime_minutes) > 1 else 0.0,
        average_sleep_efficiency=mean(efficiencies) if efficiencies else None,
        sleep_efficiency_trend=_period_trend(efficiencies),
        resting_hr_trend=_period_trend(hrs), hrv_trend=_period_trend(hrvs),
        interpretation_status=status,
    )


def calculate_medication_adherence(events: Iterable[MedicationEvent]) -> MedicationAdherenceSummary:
    """Calculate reported execution only; never change a medication plan."""

    event_list = list(events)
    scheduled = len(event_list)
    taken = sum(event.status == "taken" for event in event_list)
    missed = sum(event.status == "missed" for event in event_list)
    rate = taken / scheduled * 100 if scheduled else None
    status = "normal" if scheduled else "insufficient_data"
    return MedicationAdherenceSummary(scheduled, taken, missed, rate, status)


def _decimal_mean(values: list[Decimal]) -> Decimal | None:
    return sum(values) / len(values) if values else None


def _blood_pressure_means(records: list[BloodPressureRecord]) -> tuple[Decimal | None, Decimal | None]:
    if not records:
        return None, None
    return (
        sum(record.systolic_bp for record in records if record.systolic_bp is not None) / len(records),
        sum(record.diastolic_bp for record in records if record.diastolic_bp is not None) / len(records),
    )


def _compare_bp_means(previous: Decimal | None, recent: Decimal | None, reliable: bool) -> str:
    if not reliable or previous is None or recent is None:
        return "insufficient_data"
    difference = recent - previous
    if difference > Decimal("0.5"):
        return "increasing"
    if difference < Decimal("-0.5"):
        return "decreasing"
    return "stable"


def _period_trend(values: list[float]) -> str:
    if len(values) < 6:
        return "insufficient_data"
    midpoint = len(values) // 2
    difference = mean(values[midpoint:]) - mean(values[:midpoint])
    if difference > 0.5:
        return "increasing"
    if difference < -0.5:
        return "decreasing"
    return "stable"
