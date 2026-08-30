"""Explicit unit conversion and non-clinical data-quality checks."""

from decimal import Decimal, InvalidOperation

from executive_health_ai.integrations.codes import ObservationCode


def normalize_unit(code: ObservationCode, value: object, unit: str | None) -> tuple[Decimal, str]:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("value is not numeric") from error
    source_unit = (unit or code.default_unit).strip().lower()
    target = code.default_unit
    if code.canonical_code == "glucose" and source_unit == "mmol/l":
        return (amount * Decimal("18.0182")).quantize(Decimal("0.001")), target
    if code.canonical_code == "weight" and source_unit in {"lb", "lbs"}:
        return (amount * Decimal("0.45359237")).quantize(Decimal("0.001")), target
    if code.canonical_code == "height" and source_unit == "m":
        return (amount * Decimal("100")).quantize(Decimal("0.001")), target
    if code.canonical_code == "body_temperature" and source_unit in {"f", "°f"}:
        return ((amount - Decimal("32")) * Decimal("5") / Decimal("9")).quantize(Decimal("0.001")), "°C"
    if code.canonical_code in {"heart_rate", "resting_heart_rate"} and source_unit in {"count/min", "count/minute"}:
        return amount, target
    if code.canonical_code == "spo2" and source_unit in {"percent", "%"}:
        return (amount * Decimal("100") if amount <= 1 else amount), target
    if source_unit != target.lower():
        raise ValueError(f"unsupported unit {unit!r} for {code.canonical_code}")
    return amount, target


def quality_for(code: ObservationCode, value: Decimal) -> tuple[str, str | None]:
    if code.minimum is not None and (value < Decimal(str(code.minimum)) or value > Decimal(str(code.maximum))):
        return "invalid", f"outside supported data-quality range for {code.canonical_code}"
    if code.minimum is not None and (value < Decimal(str(code.minimum)) * Decimal("1.15") or value > Decimal(str(code.maximum)) * Decimal("0.85")):
        return "suspect", "near data-quality boundary; requires human review"
    return "valid", None
