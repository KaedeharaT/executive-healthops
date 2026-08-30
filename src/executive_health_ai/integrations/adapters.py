"""Provider adapters only translate payload shape; no HealthOps rules live here."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

import pandas as pd

from executive_health_ai.blood_pressure import coerce_observed_at


@dataclass(frozen=True)
class IncomingRecord:
    source_record_id: str
    metric: str
    value: object
    unit: str | None
    observed_at: datetime
    payload: dict[str, Any]
    device_id: str | None = None


class BaseHealthAdapter(Protocol):
    provider_name: str
    adapter_version: str
    source_type: str
    def parse(self, payload: Any, mapping: dict[str, str] | None = None) -> list[IncomingRecord]: ...


def _bp_records(payload: dict[str, Any], user_key: str, time_key: str, sys_key: str, dia_key: str, pulse_key: str) -> list[IncomingRecord]:
    observed = coerce_observed_at(payload[time_key])
    base = str(payload.get("id") or f"{payload.get(user_key, 'unknown')}-{observed.isoformat()}")
    return [IncomingRecord(f"{base}-sys", "systolic_bp", payload[sys_key], "mmHg", observed, payload, str(payload.get("device_id") or "")), IncomingRecord(f"{base}-dia", "diastolic_bp", payload[dia_key], "mmHg", observed, payload, str(payload.get("device_id") or "")), IncomingRecord(f"{base}-pulse", "heart_rate", payload[pulse_key], "bpm", observed, payload, str(payload.get("device_id") or ""))]


@dataclass(frozen=True)
class MockYuwellAdapter:
    provider_name: str = "mock_yuwell"
    adapter_version: str = "v1"
    source_type: str = "device_api"
    def parse(self, payload: dict[str, Any], mapping: dict[str, str] | None = None) -> list[IncomingRecord]: return _bp_records(payload, "user_id", "measure_time", "sys", "dia", "pulse")


@dataclass(frozen=True)
class MockOuraAdapter:
    provider_name: str = "mock_oura"
    adapter_version: str = "v1"
    source_type: str = "wearable_api"
    def parse(self, payload: dict[str, Any], mapping: dict[str, str] | None = None) -> list[IncomingRecord]:
        observed = coerce_observed_at(f"{payload['day']}T12:00:00+09:00")
        base = str(payload.get("id") or f"{payload.get('user_id')}-{payload['day']}")
        return [IncomingRecord(f"{base}-sleep", "sleep_duration", int(payload["total_sleep_duration"]) / 60, "minutes", observed, payload), IncomingRecord(f"{base}-score", "sleep_score", payload["score"], "score", observed, payload), IncomingRecord(f"{base}-rhr", "resting_heart_rate", payload["resting_heart_rate"], "bpm", observed, payload)]


@dataclass(frozen=True)
class MockCGMAdapter:
    provider_name: str = "mock_cgm"
    adapter_version: str = "v1"
    source_type: str = "device_api"
    def parse(self, payload: dict[str, Any], mapping: dict[str, str] | None = None) -> list[IncomingRecord]:
        rows = payload.get("records", [payload])
        return [IncomingRecord(str(row.get("id") or f"{payload.get('user_id', 'unknown')}-{row['timestamp']}"), "glucose", row["glucose"], row.get("unit", "mg/dL"), coerce_observed_at(row["timestamp"]), row, str(payload.get("device_id") or "")) for row in rows]


@dataclass(frozen=True)
class JSONAdapter:
    provider_name: str = "json"
    adapter_version: str = "v1"
    source_type: str = "json"
    def parse(self, payload: dict[str, Any], mapping: dict[str, str] | None = None) -> list[IncomingRecord]:
        return [IncomingRecord(str(row.get("id") or f"row-{index}"), str(row["metric"]), row["value"], row.get("unit"), coerce_observed_at(row["observed_at"]), row) for index, row in enumerate(payload.get("records", []), 1)]


@dataclass(frozen=True)
class CSVAdapter:
    provider_name: str = "csv"
    adapter_version: str = "v1"
    source_type: str = "file"
    def parse(self, payload: str | bytes, mapping: dict[str, str] | None = None) -> list[IncomingRecord]:
        if not mapping or "observed_at" not in mapping.values(): raise ValueError("column mapping must include observed_at")
        text = payload.decode("utf-8-sig") if isinstance(payload, bytes) else payload
        rows = list(csv.DictReader(io.StringIO(text)))
        reverse = {canonical: source for source, canonical in mapping.items()}
        records: list[IncomingRecord] = []
        for row_index, row in enumerate(rows, 1):
            observed = coerce_observed_at(row[reverse["observed_at"]])
            for canonical, source_column in reverse.items():
                if canonical in {"observed_at", "unit"} or not row.get(source_column): continue
                records.append(IncomingRecord(f"csv-{row_index}-{canonical}", canonical, row[source_column], row.get(reverse.get("unit", "")) or None, observed, row))
        return records


@dataclass(frozen=True)
class ExcelAdapter(CSVAdapter):
    provider_name: str = "excel"
    def parse(self, payload: bytes, mapping: dict[str, str] | None = None) -> list[IncomingRecord]:
        frame = pd.read_excel(io.BytesIO(payload))
        return CSVAdapter.parse(self, frame.to_csv(index=False), mapping)


from executive_health_ai.integrations.apple_health import AppleHealthAdapter
PROVIDERS: dict[str, BaseHealthAdapter] = {item.provider_name: item for item in (MockYuwellAdapter(), MockOuraAdapter(), MockCGMAdapter(), JSONAdapter(), CSVAdapter(), ExcelAdapter(), AppleHealthAdapter())}
def get_adapter(provider: str) -> BaseHealthAdapter:
    try: return PROVIDERS[provider]
    except KeyError as error: raise ValueError(f"unsupported provider: {provider}") from error
