"""Raw measurements reuse existing normalization/Observation; never wake on a row."""
from datetime import datetime
from sqlalchemy import select
from executive_health_ai.models import Observation, RawData
from executive_health_ai.services.ingestion import get_or_create_raw_data
from executive_health_ai.integrations.codes import canonical_code
from executive_health_ai.integrations.normalization import normalize_unit, quality_for


def store_measurement(session,event):
    data=(event.payload_ref or {}).get('measurement')
    if not isinstance(data,dict):raise ValueError('原始测量缺少标准数据。')
    code=canonical_code(data.get('metric',''))
    if not code:raise ValueError('未知测量指标。')
    value,unit=normalize_unit(code,data.get('value'),data.get('unit'))
    if not value.is_finite():raise ValueError('测量值必须是有限数值。')
    quality,notes=quality_for(code,value)
    at=datetime.fromisoformat(data['observed_at']) if data.get('observed_at') else event.occurred_at
    if at.tzinfo is None:raise ValueError('测量时间必须包含时区。')
    raw,_=get_or_create_raw_data(session,patient_id=event.member_id,device_id=None,source=event.source_type,
        record_type='measurement',payload_json={'source_id':event.source_id,**data},recorded_at=at)
    existing=session.scalar(select(Observation).where(Observation.patient_id==event.member_id,
        Observation.raw_record_id==raw.id,Observation.metric_code==code.canonical_code))
    if not existing:
        session.add(Observation(patient_id=event.member_id,observed_at=at,metric_code=code.canonical_code,
            value_numeric=value,unit=unit,source=event.source_type,quality_flag=quality,quality_notes=notes,
            raw_record_id=raw.id,source_record_id=event.source_id))
        session.flush()


def evaluate_window(session,*,member_id,metric,threshold,minimum_count,window_start,window_end,rule_id):
    """Explicit fixed-window demo/business rule, not a diagnosis or risk grade.

    The same member/rule/window yields one event even after another 50 uploads.
    This must be invoked after normalization, never automatically for each row.
    """
    from decimal import Decimal
    from executive_health_ai.services.health_events import ingest_health_event
    if window_start.tzinfo is None or window_end.tzinfo is None:raise ValueError('规则窗口必须包含时区。')
    if not rule_id or len(rule_id)>100 or not canonical_code(metric):raise ValueError('规则或指标无效。')
    metric=canonical_code(metric).canonical_code
    if minimum_count<2 or minimum_count>1000 or window_end<=window_start:raise ValueError('规则窗口无效。')
    threshold=Decimal(str(threshold))
    if not threshold.is_finite():raise ValueError('规则阈值无效。')
    rows=list(session.scalars(select(Observation).where(Observation.patient_id==member_id,
        Observation.metric_code==metric,Observation.observed_at>=window_start,Observation.observed_at<window_end,
        Observation.quality_flag=='valid',Observation.source_deleted.is_(False),Observation.excluded_from_analysis.is_(False),
        Observation.source.in_(('DEVICE','MOBILE'))).order_by(Observation.observed_at.desc(),Observation.id).limit(minimum_count)))
    if len(rows)<minimum_count or not all(r.value_numeric>=threshold for r in rows):return None
    source=f'{rule_id}:{metric}:{window_start.isoformat()}:{window_end.isoformat()}'
    return ingest_health_event(session,member_id=member_id,event_type='MEANINGFUL_CHANGE',event_category='MEANINGFUL_CHANGE',
        source_type='SYSTEM',source_id=source,payload_ref={'rule_id':rule_id,'threshold':str(threshold),
            'observation_ids':[str(r.id) for r in rows],'window_start':window_start.isoformat(),'window_end':window_end.isoformat()})[0]
