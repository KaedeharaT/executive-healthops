"""Small, non-diagnostic helpers for the internal blood-pressure demo."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid5

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.models import Device, Observation, Patient

DEMO_PATIENT_EXTERNAL_ID = "demo-executive-001"
BP_METRIC_CODES = ("systolic_bp", "diastolic_bp", "heart_rate")
CSV_REQUIRED_COLUMNS = ("datetime", "systolic", "diastolic", "heart_rate")
TOKYO_TIMEZONE = timezone(timedelta(hours=9), name="Asia/Tokyo")
MEASUREMENT_NAMESPACE = UUID("ad4f6101-260b-4b6e-b610-0ac3a35c2bbc")


@dataclass(frozen=True)
class BloodPressureMeasurement:
    """Values from one blood-pressure measurement event."""

    observed_at: datetime
    systolic_bp: Decimal
    diastolic_bp: Decimal
    heart_rate: Decimal


@dataclass(frozen=True)
class BloodPressureRecord:
    """A grouped view of up to three standardized observations."""

    observed_at: datetime
    systolic_bp: Decimal | None
    diastolic_bp: Decimal | None
    heart_rate: Decimal | None
    has_conflicting_metrics: bool = False

    @property
    def is_complete(self) -> bool:
        return (
            not self.has_conflicting_metrics
            and self.systolic_bp is not None
            and self.diastolic_bp is not None
            and self.heart_rate is not None
        )


@dataclass(frozen=True)
class HealthFeedback:
    """Descriptive data-quality and trend feedback, not clinical advice."""

    valid_measurement_count: int
    completeness_percent: float
    recent_average_systolic: Decimal | None
    recent_average_diastolic: Decimal | None
    morning_measurement_count: int
    evening_measurement_count: int
    trend: str
    interpretation_status: str


@dataclass(frozen=True)
class SevenDayBloodPressureSummary:
    """A structured, non-diagnostic summary of the latest seven local dates."""

    records: tuple[BloodPressureRecord, ...]
    valid_measurement_count: int
    completeness_percent: float
    morning_average_systolic: Decimal | None
    morning_average_diastolic: Decimal | None
    evening_average_systolic: Decimal | None
    evening_average_diastolic: Decimal | None
    recent_three_day_average_systolic: Decimal | None
    recent_three_day_average_diastolic: Decimal | None
    previous_four_day_average_systolic: Decimal | None
    previous_four_day_average_diastolic: Decimal | None
    trend: str
    interpretation_status: str


def get_demo_patient(session: Session) -> Patient | None:
    """Return the synthetic patient used by the local demo."""
    return session.scalar(
        select(Patient).where(Patient.external_id == DEMO_PATIENT_EXTERNAL_ID)
    )


def get_patient_bp_device(session: Session, patient_id: UUID) -> Device | None:
    """Return the first blood-pressure monitor associated with the patient."""
    return session.scalar(
        select(Device)
        .where(Device.patient_id == patient_id, Device.device_type == "bp_monitor")
        .order_by(Device.created_at)
    )


def coerce_observed_at(value: object) -> datetime:
    """Parse a timestamp and assign Asia/Tokyo to timezone-naive CSV values."""
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = pd.to_datetime(value, errors="raise").to_pydatetime()

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=TOKYO_TIMEZONE)
    return parsed


def coerce_decimal(value: object, field_name: str) -> Decimal:
    """Validate one required numeric CSV or form value."""
    if pd.isna(value):
        raise ValueError(f"{field_name} is required")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{field_name} must be numeric") from error
    if not result.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return result


def measurement_from_values(
    observed_at: object,
    systolic_bp: object,
    diastolic_bp: object,
    heart_rate: object,
) -> BloodPressureMeasurement:
    """Create one validated measurement using explicit units supplied by the UI."""
    return BloodPressureMeasurement(
        observed_at=coerce_observed_at(observed_at),
        systolic_bp=coerce_decimal(systolic_bp, "systolic"),
        diastolic_bp=coerce_decimal(diastolic_bp, "diastolic"),
        heart_rate=coerce_decimal(heart_rate, "heart_rate"),
    )


def validate_csv_columns(dataframe: pd.DataFrame) -> list[str]:
    """Require exactly the four columns supported by this first CSV version."""
    actual_columns = {str(column) for column in dataframe.columns}
    required_columns = set(CSV_REQUIRED_COLUMNS)
    errors: list[str] = []
    missing = sorted(required_columns - actual_columns)
    unexpected = sorted(actual_columns - required_columns)
    if missing:
        errors.append(f"Missing columns: {', '.join(missing)}")
    if unexpected:
        errors.append(f"Unsupported columns: {', '.join(unexpected)}")
    return errors


def parse_csv_measurements(
    dataframe: pd.DataFrame,
) -> tuple[list[BloodPressureMeasurement], list[str]]:
    """Parse all CSV rows, returning errors rather than writing partial input."""
    errors = validate_csv_columns(dataframe)
    if errors:
        return [], errors

    measurements: list[BloodPressureMeasurement] = []
    for row_index, row in dataframe.iterrows():
        try:
            measurements.append(
                measurement_from_values(
                    row["datetime"],
                    row["systolic"],
                    row["diastolic"],
                    row["heart_rate"],
                )
            )
        except (TypeError, ValueError) as error:
            errors.append(f"Row {row_index + 2}: {error}")
    return measurements, errors


def measurement_raw_record_id(
    patient_id: UUID, measurement: BloodPressureMeasurement
) -> UUID:
    """Generate a stable identifier that prevents duplicate imports of a row."""
    observed_at_utc = measurement.observed_at.astimezone(timezone.utc).isoformat()
    fingerprint = "|".join(
        (
            str(patient_id),
            observed_at_utc,
            format(measurement.systolic_bp, "f"),
            format(measurement.diastolic_bp, "f"),
            format(measurement.heart_rate, "f"),
        )
    )
    return uuid5(MEASUREMENT_NAMESPACE, fingerprint)


def persist_measurement(
    session: Session,
    patient_id: UUID,
    device_id: UUID,
    measurement: BloodPressureMeasurement,
    source: str,
) -> tuple[int, UUID]:
    """Persist only missing metrics for a measurement and return the write count."""
    # Imported device content is retained first; observations remain a separate
    # standardized layer.  The UUID remains stable for backwards-compatible CSV
    # deduplication and all three metrics share it.
    from executive_health_ai.services.ingestion import get_or_create_raw_data

    raw_record_id = measurement_raw_record_id(patient_id, measurement)
    raw_data, _ = get_or_create_raw_data(
        session,
        patient_id=patient_id,
        device_id=device_id,
        source=source,
        record_type="blood_pressure",
        payload_json={
            "datetime": measurement.observed_at.astimezone(timezone.utc).isoformat(),
            "systolic": str(measurement.systolic_bp),
            "diastolic": str(measurement.diastolic_bp),
            "heart_rate": str(measurement.heart_rate),
        },
        recorded_at=measurement.observed_at,
        raw_id=raw_record_id,
    )
    raw_record_id = raw_data.id
    existing_metrics = set(
        session.scalars(
            select(Observation.metric_code).where(
                Observation.patient_id == patient_id,
                Observation.raw_record_id == raw_record_id,
            )
        )
    )
    values = (
        ("systolic_bp", measurement.systolic_bp, "mmHg"),
        ("diastolic_bp", measurement.diastolic_bp, "mmHg"),
        ("heart_rate", measurement.heart_rate, "bpm"),
    )
    created = 0
    for metric_code, value_numeric, unit in values:
        if metric_code in existing_metrics:
            continue
        session.add(
            Observation(
                patient_id=patient_id,
                device_id=device_id,
                observed_at=measurement.observed_at,
                metric_code=metric_code,
                value_numeric=value_numeric,
                unit=unit,
                source=source,
                quality_flag="valid",
                raw_record_id=raw_record_id,
            )
        )
        created += 1
    session.flush()
    return created, raw_record_id


def build_blood_pressure_records(
    observations: Iterable[Observation],
) -> list[BloodPressureRecord]:
    """Group standardized observations into displayable measurement records."""
    grouped: dict[tuple[UUID | None, UUID | datetime], dict[str, object]] = {}
    for observation in observations:
        if observation.metric_code not in BP_METRIC_CODES:
            continue
        record_identifier: UUID | datetime = observation.raw_record_id or observation.observed_at
        key = (observation.device_id, record_identifier)
        group = grouped.setdefault(
            key,
            {
                "observed_at": observation.observed_at,
                "values": {},
                "conflict": False,
            },
        )
        values = group["values"]
        assert isinstance(values, dict)
        previous = values.get(observation.metric_code)
        if previous is not None and previous != observation.value_numeric:
            group["conflict"] = True
        values[observation.metric_code] = observation.value_numeric

    records = [
        BloodPressureRecord(
            observed_at=group["observed_at"],  # type: ignore[arg-type]
            systolic_bp=group["values"].get("systolic_bp"),  # type: ignore[union-attr,arg-type]
            diastolic_bp=group["values"].get("diastolic_bp"),  # type: ignore[union-attr,arg-type]
            heart_rate=group["values"].get("heart_rate"),  # type: ignore[union-attr,arg-type]
            has_conflicting_metrics=bool(group["conflict"]),
        )
        for group in grouped.values()
    ]
    return sorted(records, key=lambda record: record.observed_at)


def calculate_health_feedback(records: Iterable[BloodPressureRecord]) -> HealthFeedback:
    """Calculate descriptive statistics without applying clinical diagnosis rules."""
    record_list = list(records)
    valid_records = [record for record in record_list if record.is_complete]
    present_values = sum(
        value is not None
        for record in record_list
        for value in (record.systolic_bp, record.diastolic_bp, record.heart_rate)
    )
    expected_values = len(record_list) * len(BP_METRIC_CODES)
    completeness_percent = (present_values / expected_values * 100) if expected_values else 0.0

    recent_records = valid_records[-7:]
    if recent_records:
        average_systolic = sum(record.systolic_bp for record in recent_records) / len(recent_records)  # type: ignore[arg-type]
        average_diastolic = sum(record.diastolic_bp for record in recent_records) / len(recent_records)  # type: ignore[arg-type]
    else:
        average_systolic = None
        average_diastolic = None

    morning_count = sum(
        record.observed_at.astimezone(TOKYO_TIMEZONE).hour < 12 for record in valid_records
    )
    evening_count = sum(
        record.observed_at.astimezone(TOKYO_TIMEZONE).hour >= 18 for record in valid_records
    )
    trend = _calculate_systolic_trend(valid_records)

    if any(record.has_conflicting_metrics for record in record_list):
        interpretation_status = "needs_clinician_review"
    elif len(valid_records) < 3:
        interpretation_status = "insufficient_data"
    elif completeness_percent < 100:
        interpretation_status = "needs_remeasurement"
    else:
        interpretation_status = "normal"

    return HealthFeedback(
        valid_measurement_count=len(valid_records),
        completeness_percent=completeness_percent,
        recent_average_systolic=average_systolic,
        recent_average_diastolic=average_diastolic,
        morning_measurement_count=morning_count,
        evening_measurement_count=evening_count,
        trend=trend,
        interpretation_status=interpretation_status,
    )


def recent_seven_day_records(
    records: Iterable[BloodPressureRecord],
) -> list[BloodPressureRecord]:
    """Return records from the seven local calendar dates ending at the latest record."""
    ordered_records = sorted(records, key=lambda record: record.observed_at)
    if not ordered_records:
        return []

    latest_date = ordered_records[-1].observed_at.astimezone(TOKYO_TIMEZONE).date()
    first_date = latest_date - timedelta(days=6)
    return [
        record
        for record in ordered_records
        if first_date <= record.observed_at.astimezone(TOKYO_TIMEZONE).date() <= latest_date
    ]


def calculate_seven_day_summary(
    records: Iterable[BloodPressureRecord],
) -> SevenDayBloodPressureSummary:
    """Calculate data-quality and descriptive trend statistics for seven local dates."""
    weekly_records = recent_seven_day_records(records)
    valid_records = [record for record in weekly_records if record.is_complete]
    present_values = sum(
        value is not None
        for record in weekly_records
        for value in (record.systolic_bp, record.diastolic_bp, record.heart_rate)
    )
    expected_values = len(weekly_records) * len(BP_METRIC_CODES)
    completeness_percent = (present_values / expected_values * 100) if expected_values else 0.0

    morning_records = [
        record
        for record in valid_records
        if record.observed_at.astimezone(TOKYO_TIMEZONE).hour < 12
    ]
    evening_records = [
        record
        for record in valid_records
        if record.observed_at.astimezone(TOKYO_TIMEZONE).hour >= 18
    ]
    morning_systolic, morning_diastolic = _average_blood_pressure(morning_records)
    evening_systolic, evening_diastolic = _average_blood_pressure(evening_records)

    if weekly_records:
        latest_date = weekly_records[-1].observed_at.astimezone(TOKYO_TIMEZONE).date()
        dates = [latest_date - timedelta(days=offset) for offset in range(6, -1, -1)]
    else:
        dates = []
    records_by_date = _records_by_local_date(valid_records)
    previous_four_records = [
        record for day in dates[:4] for record in records_by_date.get(day, [])
    ]
    recent_three_records = [
        record for day in dates[4:] for record in records_by_date.get(day, [])
    ]
    previous_systolic, previous_diastolic = _average_blood_pressure(previous_four_records)
    recent_systolic, recent_diastolic = _average_blood_pressure(recent_three_records)

    trend_reliable = len(dates) == 7 and all(records_by_date.get(day) for day in dates)
    trend = _compare_period_averages(
        previous_systolic, recent_systolic, trend_reliable
    )
    if any(record.has_conflicting_metrics for record in weekly_records):
        interpretation_status = "needs_clinician_review"
    elif not trend_reliable:
        interpretation_status = "insufficient_data"
    elif completeness_percent < 100:
        interpretation_status = "needs_remeasurement"
    else:
        interpretation_status = "normal"

    return SevenDayBloodPressureSummary(
        records=tuple(weekly_records),
        valid_measurement_count=len(valid_records),
        completeness_percent=completeness_percent,
        morning_average_systolic=morning_systolic,
        morning_average_diastolic=morning_diastolic,
        evening_average_systolic=evening_systolic,
        evening_average_diastolic=evening_diastolic,
        recent_three_day_average_systolic=recent_systolic,
        recent_three_day_average_diastolic=recent_diastolic,
        previous_four_day_average_systolic=previous_systolic,
        previous_four_day_average_diastolic=previous_diastolic,
        trend=trend,
        interpretation_status=interpretation_status,
    )


def _records_by_local_date(
    records: Iterable[BloodPressureRecord],
) -> dict[date, list[BloodPressureRecord]]:
    grouped: dict[date, list[BloodPressureRecord]] = {}
    for record in records:
        local_date = record.observed_at.astimezone(TOKYO_TIMEZONE).date()
        grouped.setdefault(local_date, []).append(record)
    return grouped


def _average_blood_pressure(
    records: Iterable[BloodPressureRecord],
) -> tuple[Decimal | None, Decimal | None]:
    record_list = list(records)
    if not record_list:
        return None, None
    systolic = sum(record.systolic_bp for record in record_list) / len(record_list)  # type: ignore[arg-type]
    diastolic = sum(record.diastolic_bp for record in record_list) / len(record_list)  # type: ignore[arg-type]
    return systolic, diastolic


def _compare_period_averages(
    previous_systolic: Decimal | None,
    recent_systolic: Decimal | None,
    trend_reliable: bool,
) -> str:
    """Describe change between periods without applying a clinical threshold."""
    if not trend_reliable or previous_systolic is None or recent_systolic is None:
        return "insufficient_data"
    difference = recent_systolic - previous_systolic
    if difference > Decimal("0.5"):
        return "increasing"
    if difference < Decimal("-0.5"):
        return "decreasing"
    return "stable"


def _calculate_systolic_trend(records: list[BloodPressureRecord]) -> str:
    """Return a descriptive linear trend; this is not a clinical interpretation."""
    if len(records) < 3:
        return "insufficient_data"
    values = [float(record.systolic_bp) for record in records if record.systolic_bp is not None]
    indices = list(range(len(values)))
    mean_index = sum(indices) / len(indices)
    mean_value = sum(values) / len(values)
    denominator = sum((index - mean_index) ** 2 for index in indices)
    slope = sum(
        (index - mean_index) * (value - mean_value)
        for index, value in zip(indices, values, strict=True)
    ) / denominator
    if slope > 0.5:
        return "increasing"
    if slope < -0.5:
        return "decreasing"
    return "stable"
