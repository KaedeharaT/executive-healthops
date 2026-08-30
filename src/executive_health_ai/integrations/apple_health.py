"""Apple Health payload adapter; parses data only, never makes health decisions."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from executive_health_ai.blood_pressure import coerce_observed_at
from executive_health_ai.integrations.adapters import IncomingRecord

TYPE_MAPPING = {
    "stepCount": ("steps", "count"), "appleExerciseTime": ("exercise_minutes", "minutes"),
    "activeEnergyBurned": ("active_calories", "kcal"), "heartRate": ("heart_rate", "bpm"),
    "restingHeartRate": ("resting_heart_rate", "bpm"), "oxygenSaturation": ("spo2", "%"),
    "bodyMass": ("weight", "kg"),
}
ASLEEP = {"asleep", "asleepCore", "asleepDeep", "asleepREM", "asleepUnspecified"}
SLEEP_STAGES = {
    "asleepDeep": "DEEP", "asleepCore": "LIGHT", "asleepREM": "REM",
    "awake": "AWAKE",
}


def _sleep_records(samples: list[dict[str, Any]]) -> list[IncomingRecord]:
    by_day: dict[str, list[tuple[datetime, datetime, dict[str, Any]]]] = defaultdict(list)
    for sample in samples:
        if sample.get("value") not in ASLEEP | {"awake"}: continue
        start, end = coerce_observed_at(sample["start_date"]), coerce_observed_at(sample["end_date"])
        # Attribute an overnight session to its wake date so stages either side
        # of midnight remain one real sleep period rather than separate rows.
        if end > start: by_day[end.date().isoformat()].append((start, end, sample))
    records: list[IncomingRecord] = []
    for day, intervals in by_day.items():
        intervals.sort(key=lambda item: item[0]); merged: list[tuple[datetime, datetime]] = []
        asleep_intervals = [item for item in intervals if item[2].get("value") in ASLEEP]
        for start, end, _ in asleep_intervals:
            if merged and start <= merged[-1][1]: merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else: merged.append((start, end))
        if not merged:
            continue
        minutes = sum((end - start).total_seconds() / 60 for start, end in merged)
        first = intervals[0][2]
        stage_segments = [
            {
                "stage": SLEEP_STAGES[str(sample.get("value"))],
                "start_at": start.isoformat(),
                "end_at": end.isoformat(),
                "duration_minutes": str((end - start).total_seconds() / 60),
            }
            for start, end, sample in intervals if str(sample.get("value")) in SLEEP_STAGES
        ]
        records.append(IncomingRecord(
            f"apple-sleep-{day}", "sleep_duration", minutes, "minutes", merged[-1][1],
            {
                "type": "sleepAnalysis", "day": day, "samples": [item[2] for item in intervals],
                "source_sample_ids": [str(item[2].get("sample_id") or "") for item in intervals if item[2].get("sample_id")],
                "aggregation": "merged_asleep_intervals", "sleep_start": intervals[0][0].isoformat(),
                "sleep_end": intervals[-1][1].isoformat(), "stage_segments": stage_segments,
            }, str(first.get("device", {}).get("model") or ""),
        ))
    return records


@dataclass(frozen=True)
class AppleHealthAdapter:
    provider_name: str = "apple_health"
    adapter_version: str = "v1"
    source_type: str = "healthkit_bridge"
    def parse(self, payload: dict[str, Any], mapping: dict[str, str] | None = None) -> list[IncomingRecord]:
        records: list[IncomingRecord] = []
        sleep: list[dict[str, Any]] = []
        for sample in payload.get("samples", []):
            type_name = sample.get("type")
            if type_name == "sleepAnalysis": sleep.append(sample); continue
            mapped = TYPE_MAPPING.get(str(type_name))
            if mapped is None: continue
            code, default_unit = mapped
            records.append(IncomingRecord(str(sample["sample_id"]), code, sample["value"], sample.get("unit", default_unit), coerce_observed_at(sample.get("end_date") or sample["start_date"]), sample, str(sample.get("device", {}).get("model") or "")))
        return records + _sleep_records(sleep)
