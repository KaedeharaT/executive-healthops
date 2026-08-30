"""Read-only, windowed summaries for the member health-data presentation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.blood_pressure import TOKYO_TIMEZONE
from executive_health_ai.models import Observation, SleepSession


USABLE_QUALITY_FLAGS = ("valid", "VALID", "manually_corrected", "MANUALLY_CORRECTED")
LIFESTYLE_CODES = ("steps", "exercise_minutes", "sleep_duration", "active_calories", "resting_heart_rate", "spo2")
LONG_TERM_CODES = ("systolic_bp", "diastolic_bp", "glucose", "weight", "sleep_duration", "steps", "resting_heart_rate")


@dataclass(frozen=True)
class RealtimeHealthSummary:
    cgm_current: Observation | None
    latest_systolic: Observation | None
    latest_diastolic: Observation | None
    latest_heart_rate: Observation | None


@dataclass(frozen=True)
class LifestyleHealthSummary:
    latest: dict[str, Observation]
    daily_values: dict[str, list[Observation]]


@dataclass(frozen=True)
class SleepStageInterval:
    """A source-provided stage interval, normalized for display only."""

    stage: str
    start_at: datetime
    end_at: datetime
    duration_minutes: float


@dataclass(frozen=True)
class SleepTrendSummary:
    sessions: int
    average_total_minutes: float | None
    average_deep_minutes: float | None
    average_deep_ratio: float | None
    average_rem_minutes: float | None
    average_awake_minutes: float | None
    average_bedtime_minutes: float | None


class HealthDataSummaryService:
    """Window queries only. This service does not run risk rules or diagnose."""

    def _usable(self, statement):
        return statement.where(
            Observation.quality_flag.in_(USABLE_QUALITY_FLAGS),
            Observation.excluded_from_analysis.is_(False),
            Observation.source_deleted.is_(False),
        )

    def latest_for_codes(self, session: Session, patient_id: UUID, codes: Iterable[str]) -> dict[str, Observation]:
        records = list(session.scalars(self._usable(
            select(Observation).where(
                Observation.patient_id == patient_id,
                Observation.metric_code.in_(tuple(codes)),
            ).order_by(Observation.observed_at.desc()).limit(80)
        )))
        latest: dict[str, Observation] = {}
        for record in records:
            latest.setdefault(record.metric_code, record)
        return latest

    def get_realtime_summary(self, session: Session, patient_id: UUID) -> RealtimeHealthSummary:
        latest = self.latest_for_codes(session, patient_id, ("systolic_bp", "diastolic_bp", "heart_rate"))
        cgm = session.scalar(self._usable(
            select(Observation).where(
                Observation.patient_id == patient_id,
                Observation.metric_code == "glucose",
                Observation.source.ilike("%cgm%"),
            ).order_by(Observation.observed_at.desc()).limit(1)
        ))
        return RealtimeHealthSummary(
            cgm_current=cgm,
            latest_systolic=latest.get("systolic_bp"),
            latest_diastolic=latest.get("diastolic_bp"),
            latest_heart_rate=latest.get("heart_rate"),
        )

    def get_cgm_series(self, session: Session, patient_id: UUID, *, hours: int, limit: int = 2_000) -> list[Observation]:
        start_at = datetime.now(TOKYO_TIMEZONE) - timedelta(hours=hours)
        statement = self._usable(select(Observation).where(
            Observation.patient_id == patient_id,
            Observation.metric_code == "glucose",
            Observation.source.ilike("%cgm%"),
            Observation.observed_at >= start_at,
        ).order_by(Observation.observed_at.desc()).limit(limit))
        return list(reversed(list(session.scalars(statement))))

    def get_lifestyle_summary(self, session: Session, patient_id: UUID, *, days: int = 14) -> LifestyleHealthSummary:
        start_at = datetime.now(TOKYO_TIMEZONE) - timedelta(days=days)
        records = list(session.scalars(self._usable(select(Observation).where(
            Observation.patient_id == patient_id,
            Observation.metric_code.in_(LIFESTYLE_CODES),
            Observation.observed_at >= start_at,
        ).order_by(Observation.observed_at.desc()).limit(1_000))))
        latest: dict[str, Observation] = {}
        daily: dict[str, dict[object, Observation]] = defaultdict(dict)
        for record in records:
            latest.setdefault(record.metric_code, record)
            local_day = record.observed_at.astimezone(TOKYO_TIMEZONE).date()
            existing = daily[record.metric_code].get(local_day)
            # The gateway commonly sends daily aggregates; use the largest value for a day to avoid double counting.
            if existing is None or record.value_numeric > existing.value_numeric:
                daily[record.metric_code][local_day] = record
        return LifestyleHealthSummary(
            latest=latest,
            daily_values={code: list(sorted(by_day.values(), key=lambda item: item.observed_at)) for code, by_day in daily.items()},
        )

    def get_sleep_sessions(self, session: Session, patient_id: UUID, *, days: int = 90, limit: int = 100) -> list[SleepSession]:
        start_at = datetime.now(TOKYO_TIMEZONE) - timedelta(days=days)
        return list(session.scalars(select(SleepSession).where(
            SleepSession.patient_id == patient_id,
            SleepSession.sleep_end >= start_at,
        ).order_by(SleepSession.sleep_end.desc()).limit(limit)))

    @staticmethod
    def sleep_stage_intervals(session_item: SleepSession) -> list[SleepStageInterval]:
        """Return real source stages; an empty list is an explicit no-data state.

        Providers may supply ISO start/end values or ordered source durations.
        In the latter case only the time positions are derived from the sleep
        session's real start time; stage types and durations are never inferred.
        """
        accepted = {"AWAKE", "REM", "LIGHT", "DEEP"}
        intervals: list[SleepStageInterval] = []
        cursor = session_item.sleep_start
        for item in session_item.stage_segments_json or []:
            stage = str(item.get("stage") or "").upper()
            if stage not in accepted:
                return []
            start_raw, end_raw = item.get("start_at"), item.get("end_at")
            start: datetime | None = None
            end: datetime | None = None
            try:
                if start_raw and end_raw:
                    start = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
                    end = datetime.fromisoformat(str(end_raw).replace("Z", "+00:00"))
                    if start.tzinfo is None: start = start.replace(tzinfo=session_item.sleep_start.tzinfo)
                    if end.tzinfo is None: end = end.replace(tzinfo=session_item.sleep_end.tzinfo)
                else:
                    duration = float(item.get("duration_minutes", item.get("minutes", 0)) or 0)
                    if duration <= 0: return []
                    start, end = cursor, cursor + timedelta(minutes=duration)
                duration_minutes = (end - start).total_seconds() / 60
            except (TypeError, ValueError):
                return []
            if duration_minutes <= 0 or end <= start:
                return []
            intervals.append(SleepStageInterval(stage, start, end, duration_minutes))
            cursor = end
        return intervals

    @staticmethod
    def sleep_trend(sessions: list[SleepSession]) -> SleepTrendSummary:
        if not sessions:
            return SleepTrendSummary(0, None, None, None, None, None, None)
        total = [item.total_sleep_minutes for item in sessions]
        def stage_total(item: SleepSession, stage: str) -> float | None:
            value = {"DEEP": item.deep_sleep_minutes, "REM": item.rem_sleep_minutes, "AWAKE": item.awake_minutes}[stage]
            if value is not None:
                return float(value)
            intervals = HealthDataSummaryService.sleep_stage_intervals(item)
            total_minutes = sum(segment.duration_minutes for segment in intervals if segment.stage == stage)
            return total_minutes if total_minutes else None
        deep = [value for item in sessions if (value := stage_total(item, "DEEP")) is not None]
        rem = [value for item in sessions if (value := stage_total(item, "REM")) is not None]
        awake = [value for item in sessions if (value := stage_total(item, "AWAKE")) is not None]
        ratios = [deep_value / item.total_sleep_minutes * 100 for item in sessions if item.total_sleep_minutes and (deep_value := stage_total(item, "DEEP")) is not None]
        bedtime = [item.sleep_start.astimezone(TOKYO_TIMEZONE).hour * 60 + item.sleep_start.astimezone(TOKYO_TIMEZONE).minute for item in sessions]
        return SleepTrendSummary(
            len(sessions), mean(total), mean(deep) if deep else None,
            mean(ratios) if ratios else None, mean(rem) if rem else None,
            mean(awake) if awake else None, mean(bedtime) if bedtime else None,
        )

    def get_long_term_observations(
        self,
        session: Session,
        patient_id: UUID,
        *,
        days: int | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        per_metric_limit: int = 500,
    ) -> list[Observation]:
        """Bounded metric-window query; never an unbounded member history scan."""
        if start_at is None and days is not None:
            start_at = datetime.now(TOKYO_TIMEZONE) - timedelta(days=days)
        records: list[Observation] = []
        for code in LONG_TERM_CODES:
            statement = self._usable(select(Observation).where(
                Observation.patient_id == patient_id,
                Observation.metric_code == code,
            ))
            if start_at is not None:
                statement = statement.where(Observation.observed_at >= start_at)
            if end_at is not None:
                statement = statement.where(Observation.observed_at <= end_at)
            statement = statement.order_by(Observation.observed_at.desc()).limit(per_metric_limit)
            records.extend(session.scalars(statement))
        return sorted(records, key=lambda item: item.observed_at)
