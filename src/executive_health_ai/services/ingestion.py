"""Small, explicit import helpers for local demo device adapters."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.blood_pressure import TOKYO_TIMEZONE, coerce_observed_at
from executive_health_ai.models import Device, Observation, RawData, SleepSession

CGM_REQUIRED_COLUMNS = ("datetime", "glucose")
SLEEP_REQUIRED_COLUMNS = (
    "sleep_start", "sleep_end", "total_sleep_minutes", "deep_sleep_minutes",
    "rem_sleep_minutes", "awake_minutes", "sleep_efficiency", "avg_heart_rate",
    "lowest_heart_rate", "avg_hrv",
)


def canonical_checksum(payload: dict[str, Any]) -> str:
    """Create a reproducible payload checksum for idempotent raw-data ingest."""

    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def get_or_create_raw_data(
    session: Session,
    *,
    patient_id: object,
    device_id: object | None,
    source: str,
    record_type: str,
    payload_json: dict[str, Any],
    recorded_at: datetime,
    raw_id: object | None = None,
) -> tuple[RawData, bool]:
    """Persist one immutable payload exactly once for a patient/checksum pair."""

    checksum = canonical_checksum(payload_json)
    existing = session.scalar(
        select(RawData).where(RawData.patient_id == patient_id, RawData.checksum == checksum)
    )
    if existing is not None:
        return existing, False
    values: dict[str, Any] = {
        "patient_id": patient_id,
        "device_id": device_id,
        "source": source,
        "record_type": record_type,
        "payload_json": payload_json,
        "recorded_at": recorded_at,
        "checksum": checksum,
    }
    if raw_id is not None:
        values["id"] = raw_id
    raw_data = RawData(**values)
    session.add(raw_data)
    session.flush()
    return raw_data, True


def normalize_glucose(value: object, unit: str = "mg/dL") -> Decimal:
    """Normalize a glucose value explicitly; no unit conversion is implicit."""

    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("glucose 必须是数值") from error
    normalized_unit = unit.strip().lower()
    if normalized_unit == "mg/dl":
        return amount
    if normalized_unit == "mmol/l":
        return (amount * Decimal("18.0182")).quantize(Decimal("0.001"))
    raise ValueError("仅支持 mg/dL 或 mmol/L 血糖单位，转换必须明确指定。")


def validate_columns(dataframe: pd.DataFrame, required: Iterable[str]) -> list[str]:
    """Return user-readable shape errors without writing any data."""

    actual = {str(column) for column in dataframe.columns}
    required_set = set(required)
    errors: list[str] = []
    missing = sorted(required_set - actual)
    unexpected = sorted(actual - required_set)
    if missing:
        errors.append(f"缺少字段：{', '.join(missing)}")
    if unexpected:
        errors.append(f"不支持的字段：{', '.join(unexpected)}")
    return errors


def parse_cgm_csv(dataframe: pd.DataFrame, unit: str = "mg/dL") -> tuple[list[tuple[datetime, Decimal]], list[str]]:
    """Validate the V0.1 CGM CSV (`datetime,glucose`) before import."""

    errors = validate_columns(dataframe, CGM_REQUIRED_COLUMNS)
    if errors:
        return [], errors
    parsed: list[tuple[datetime, Decimal]] = []
    for index, row in dataframe.iterrows():
        try:
            parsed.append((coerce_observed_at(row["datetime"]), normalize_glucose(row["glucose"], unit)))
        except (TypeError, ValueError) as error:
            errors.append(f"第 {index + 2} 行：{error}")
    return parsed, errors


def import_cgm_rows(
    session: Session,
    patient_id: object,
    device_id: object | None,
    rows: Iterable[tuple[datetime, Decimal]],
    source: str = "cgm_csv_import",
) -> int:
    """Normalize idempotent CGM rows into immutable raw records and observations."""

    created = 0
    for observed_at, glucose in rows:
        payload = {"datetime": observed_at.astimezone(TOKYO_TIMEZONE).isoformat(), "glucose": str(glucose), "unit": "mg/dL"}
        raw, _ = get_or_create_raw_data(
            session, patient_id=patient_id, device_id=device_id, source=source,
            record_type="cgm_reading", payload_json=payload, recorded_at=observed_at,
        )
        existing = session.scalar(
            select(Observation).where(
                Observation.patient_id == patient_id,
                Observation.raw_record_id == raw.id,
                Observation.metric_code == "glucose",
            )
        )
        if existing is None:
            session.add(Observation(
                patient_id=patient_id, device_id=device_id, observed_at=observed_at,
                metric_code="glucose", value_numeric=glucose, unit="mg/dL", source=source,
                quality_flag="valid", raw_record_id=raw.id,
            ))
            created += 1
    session.flush()
    return created


def parse_sleep_csv(dataframe: pd.DataFrame) -> tuple[list[dict[str, Any]], list[str]]:
    """Validate V0.1 sleep rows before they become raw and normalized records."""

    errors = validate_columns(dataframe, SLEEP_REQUIRED_COLUMNS)
    if errors:
        return [], errors
    parsed: list[dict[str, Any]] = []
    for index, row in dataframe.iterrows():
        try:
            parsed.append({
                "sleep_start": coerce_observed_at(row["sleep_start"]),
                "sleep_end": coerce_observed_at(row["sleep_end"]),
                "total_sleep_minutes": int(row["total_sleep_minutes"]),
                "deep_sleep_minutes": int(row["deep_sleep_minutes"]),
                "rem_sleep_minutes": int(row["rem_sleep_minutes"]),
                "awake_minutes": int(row["awake_minutes"]),
                "sleep_efficiency": Decimal(str(row["sleep_efficiency"])),
                "avg_heart_rate": Decimal(str(row["avg_heart_rate"])),
                "lowest_heart_rate": Decimal(str(row["lowest_heart_rate"])),
                "avg_hrv": Decimal(str(row["avg_hrv"])),
            })
        except (TypeError, ValueError, InvalidOperation) as error:
            errors.append(f"第 {index + 2} 行：睡眠字段无效（{error}）")
    return parsed, errors


def import_sleep_rows(
    session: Session,
    patient_id: object,
    device_id: object | None,
    rows: Iterable[dict[str, Any]],
    source: str = "sleep_csv_import",
) -> int:
    """Idempotently write sleep raw payloads and sessions."""

    created = 0
    for row in rows:
        payload = {
            key: (value.isoformat() if isinstance(value, datetime) else str(value))
            for key, value in row.items()
        }
        raw, _ = get_or_create_raw_data(
            session, patient_id=patient_id, device_id=device_id, source=source,
            record_type="sleep_session", payload_json=payload, recorded_at=row["sleep_end"],
        )
        existing = session.scalar(select(SleepSession).where(SleepSession.raw_record_id == raw.id))
        if existing is None:
            session.add(SleepSession(patient_id=patient_id, device_id=device_id, source=source, raw_record_id=raw.id, **row))
            created += 1
        elif row.get("stage_segments_json") and not existing.stage_segments_json:
            # A later provider payload may add real stage metadata to the same
            # immutable raw sleep record.  Preserve the session identity while
            # filling only previously absent source-provided stages.
            existing.stage_segments_json = list(row["stage_segments_json"])
    session.flush()
    return created


def device_for_type(session: Session, patient_id: object, device_type: str) -> Device | None:
    """Return the first registered local-demo adapter/device for a type."""

    return session.scalar(select(Device).where(Device.patient_id == patient_id, Device.device_type == device_type))
