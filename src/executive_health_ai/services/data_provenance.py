"""Append-only evidence and corrections; current facts never replace their origin."""
from sqlalchemy import select, func
from executive_health_ai.models import Observation, RawData
from executive_health_ai.models.goal_data import ReportCandidateRevision
from executive_health_ai.models.base import utc_now


def candidate_revision(session, candidate, author=None, reason=''):
    session.flush()
    values = {key: getattr(candidate, key) for key in
              ('raw_name', 'raw_value', 'canonical_code', 'normalized_value', 'unit', 'evidence_text', 'status')}
    prior = session.scalar(select(ReportCandidateRevision).where(
        ReportCandidateRevision.candidate_id == candidate.id).order_by(ReportCandidateRevision.version.desc()).limit(1))
    if prior and prior.values_json == values:
        return prior
    row = ReportCandidateRevision(candidate_id=candidate.id, version=prior.version+1 if prior else 1,
        values_json=values, author=author or 'parser', method=candidate.extraction_method,
        reason=reason)
    session.add(row)
    session.flush()
    return row


def report_raw(session, candidate, observed_at):
    from executive_health_ai.services.ingestion import get_or_create_raw_data
    first=session.scalar(select(ReportCandidateRevision).where(ReportCandidateRevision.candidate_id==candidate.id)
        .order_by(ReportCandidateRevision.version).limit(1))
    raw, _ = get_or_create_raw_data(session, patient_id=candidate.patient_id, device_id=None,
        source='REPORT', record_type='report_evidence', recorded_at=observed_at,
        payload_json={'source_id':str(candidate.id), 'source_document':str(candidate.document_id),
            'original_value':candidate.raw_value, 'original_unit':candidate.structured_data_json.get('raw_unit') or (first.values_json.get('unit') if first else None),
            'original_text':candidate.evidence_text, 'page':candidate.source_page,
            'timestamp':observed_at.isoformat()})
    return raw


def correct_observation(session, observation, *, value, unit, actor, reason):
    from decimal import Decimal
    from executive_health_ai.integrations.codes import canonical_code
    from executive_health_ai.integrations.normalization import normalize_unit, quality_for
    if not actor.strip() or not reason.strip():
        raise ValueError('修正需要确认人和原因。')
    if observation.excluded_from_analysis:
        raise ValueError('只能修正当前有效版本。')
    code = canonical_code(observation.metric_code)
    normalized, normalized_unit = normalize_unit(code, value, unit)
    if not normalized.is_finite(): raise ValueError('数值必须有限。')
    quality, notes = quality_for(code, normalized)
    if quality == 'invalid': raise ValueError('修正值未通过数据质量检查。')
    revised = Observation(patient_id=observation.patient_id, device_id=observation.device_id,
        metric_code=observation.metric_code, observed_at=observation.observed_at,
        value_numeric=normalized, unit=normalized_unit, source=observation.source,
        source_type=observation.source_type, quality_flag='manually_corrected', quality_notes=notes,
        raw_record_id=observation.raw_record_id, source_record_id=observation.source_record_id,
        confirmation_status='CONFIRMED', confirmed_by=actor, confirmed_at=utc_now(),
        version=observation.version+1, supersedes_id=observation.id, evidence_ref=observation.evidence_ref,
        provenance_json={**observation.provenance_json, 'correction_reason':reason,
                         'previous_observation_id':str(observation.id)})
    observation.excluded_from_analysis = True
    session.add(revised)
    session.flush()
    return revised


def detail(session, observation):
    raw = session.get(RawData, observation.raw_record_id) if observation.raw_record_id else None
    versions = []
    current = observation
    while current and len(versions) < 100:
        versions.append({'value':str(current.value_numeric), 'unit':current.unit,
            'version':current.version, 'confirmed_by':current.confirmed_by,
            'status':current.confirmation_status, 'reason':current.provenance_json.get('correction_reason')})
        current = session.get(Observation, current.supersedes_id) if current.supersedes_id else None
    candidates = []
    if observation.source == 'confirmed_health_check_report' and observation.source_record_id:
        from uuid import UUID
        candidates = [r.values_json for r in session.scalars(select(ReportCandidateRevision).where(
            ReportCandidateRevision.candidate_id==UUID(observation.source_record_id)).order_by(ReportCandidateRevision.version))]
    return {'source':observation.source, 'evidence':observation.evidence_ref,
        'occurred_at':observation.observed_at.isoformat(), 'raw':raw.payload_json if raw else None,
        'versions':versions, 'candidates':candidates, 'corrected':len(versions)>1 or len(candidates)>1}
