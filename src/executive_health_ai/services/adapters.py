"""Explicit local adapter boundary; V0.1 does not call any vendor API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from executive_health_ai.blood_pressure import parse_csv_measurements
from executive_health_ai.services.ingestion import parse_cgm_csv, parse_sleep_csv


class DeviceAdapter(Protocol):
    """Future vendor adapters normalize input before RawData/clinical persistence."""

    source: str
    record_type: str

    def preview(self, dataframe: pd.DataFrame) -> tuple[object, list[str]]: ...


@dataclass(frozen=True)
class YuwellCSVAdapter:
    source: str = "yuwell_csv_import"
    record_type: str = "blood_pressure"

    def preview(self, dataframe: pd.DataFrame) -> tuple[object, list[str]]:
        return parse_csv_measurements(dataframe)


@dataclass(frozen=True)
class CGMCSVAdapter:
    source: str = "cgm_csv_import"
    record_type: str = "cgm_reading"

    def preview(self, dataframe: pd.DataFrame) -> tuple[object, list[str]]:
        return parse_cgm_csv(dataframe)


@dataclass(frozen=True)
class OuraCSVAdapter:
    source: str = "sleep_csv_import"
    record_type: str = "sleep_session"

    def preview(self, dataframe: pd.DataFrame) -> tuple[object, list[str]]:
        return parse_sleep_csv(dataframe)
