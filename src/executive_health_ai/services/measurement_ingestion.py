"""Vendor-independent mobile/device adapter contract over unified ingestion."""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class MeasurementEnvelope(BaseModel):
    member_id: UUID
    source_type: Literal['MOBILE','DEVICE']
    source_id: str = Field(min_length=1,max_length=256)
    metric: str = Field(min_length=1,max_length=80)
    value: Decimal
    unit: str = Field(min_length=1,max_length=32)
    observed_at: datetime

    @field_validator('observed_at')
    @classmethod
    def timezone_required(cls,value):
        if value.tzinfo is None:raise ValueError('测量时间必须包含时区。')
        return value

    @field_validator('value')
    @classmethod
    def finite_value(cls,value):
        if not value.is_finite():raise ValueError('测量值必须是有限数值。')
        return value


def ingest_measurement(session,envelope:MeasurementEnvelope):
    """Adapters must authenticate/bind the member before invoking this service."""
    from executive_health_ai.services.health_events import ingest_health_event
    return ingest_health_event(session,member_id=envelope.member_id,source_type=envelope.source_type,
        source_id=envelope.source_id,event_type=envelope.source_type+'_RAW_MEASUREMENT',event_category='NEW_INFORMATION',
        occurred_at=envelope.observed_at,payload_ref={'measurement':{'metric':envelope.metric,
            'value':str(envelope.value),'unit':envelope.unit,'observed_at':envelope.observed_at.isoformat()}})
