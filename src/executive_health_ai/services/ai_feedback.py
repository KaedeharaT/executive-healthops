"""Governed human feedback, immutable offline datasets, and release gates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from executive_health_ai.models import (
    AuditLog, FeedbackDatasetVersion, FeedbackRecord, ModelVersionRegistry,
    RiskEvent, RiskRule, RiskRuleReviewCandidate,
)


AI_CONTENT_FEEDBACK = "AI_CONTENT_FEEDBACK"
WORKFLOW_FEEDBACK = "WORKFLOW_FEEDBACK"
RISK_RULE_FEEDBACK = "RISK_RULE_FEEDBACK"
FEEDBACK_TYPES = {AI_CONTENT_FEEDBACK, WORKFLOW_FEEDBACK, RISK_RULE_FEEDBACK}
RISK_FEEDBACK_LABELS = {
    "FALSE_POSITIVE", "FALSE_NEGATIVE", "SCOPE_MISMATCH", "UNIT_MISMATCH",
    "WINDOW_MISMATCH", "THRESHOLD_REVIEW_NEEDED",
}

_SENSITIVE_PATTERNS = (
    re.compile(r"[A-Za-z]:\\[^\s]+"),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,36}\b"),
)


def deidentify_text(value: str | None) -> str | None:
    """Remove common direct identifiers from an offline feedback field."""
    if value is None:
        return None
    cleaned = value.strip()
    for pattern in _SENSITIVE_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned[:4000]


def _audit(session: Session, *, actor: str, action: str, entity: object, patient_id: UUID | None = None, detail: dict[str, Any] | None = None) -> None:
    session.add(AuditLog(
        patient_id=patient_id, actor=actor, actor_role="ai_governance", action=action,
        entity_type=entity.__class__.__name__, entity_id=str(getattr(entity, "id")),
        detail_json=detail or {},
    ))


class FeedbackService:
    """Capture feedback without treating one human action as a learned rule."""

    def capture(
        self, session: Session, *, feedback_type: str, feature: str,
        source_entity_type: str, source_entity_id: str, feedback_label: str,
        created_by: str, input_material: str, prediction_summary: str | None = None,
        human_correction: str | None = None, feedback_reason: str | None = None,
        evidence_refs: list[dict[str, Any]] | None = None, member_id: UUID | None = None,
        model_provider: str | None = None, model_name: str | None = None,
        model_version: str | None = None, prompt_version: str | None = None,
        eligible_for_training: bool = False, deidentified: bool = False,
        confidence: float | None = None,
    ) -> FeedbackRecord:
        if feedback_type not in FEEDBACK_TYPES:
            raise ValueError("Unsupported feedback type.")
        if not input_material.strip():
            raise ValueError("Feedback input material is required for hashing.")
        # Risk feedback and human medical conclusions are never training labels.
        if feedback_type == RISK_RULE_FEEDBACK or source_entity_type == "DoctorReview":
            eligible_for_training = False
        if confidence is not None and not 0 <= confidence <= 1:
            raise ValueError("Feedback confidence must be between 0 and 1.")
        stored_evidence = list(evidence_refs or [])
        if confidence is not None:
            stored_evidence.append({"type": "FEEDBACK_CONFIDENCE", "value": confidence})
        record = FeedbackRecord(
            feedback_type=feedback_type, feature=feature,
            source_entity_type=source_entity_type, source_entity_id=str(source_entity_id),
            member_id=member_id, model_provider=model_provider, model_name=model_name,
            model_version=model_version, prompt_version=prompt_version,
            input_hash=sha256(input_material.encode("utf-8")).hexdigest(),
            prediction_summary=deidentify_text(prediction_summary),
            human_correction=deidentify_text(human_correction),
            feedback_label=feedback_label, feedback_reason=deidentify_text(feedback_reason),
            evidence_refs=stored_evidence, created_by=created_by,
            eligible_for_training=eligible_for_training, deidentified=deidentified,
        )
        session.add(record)
        session.flush()
        _audit(session, actor=created_by, action="captured_ai_feedback", entity=record, patient_id=member_id,
               detail={"feedback_type": feedback_type, "feature": feature, "eligible_for_training": eligible_for_training})
        return record

    def capture_report_correction(
        self, session: Session, *, candidate: object, actor: str,
        before: dict[str, Any], after: dict[str, Any], reason: str,
    ) -> FeedbackRecord:
        method = str(getattr(candidate, "extraction_method", "UNKNOWN"))
        return self.capture(
            session, feedback_type=AI_CONTENT_FEEDBACK, feature="report_semantic_mapping",
            source_entity_type="ReportExtractionCandidate", source_entity_id=str(getattr(candidate, "id")),
            member_id=getattr(candidate, "patient_id"), feedback_label="HUMAN_CORRECTION",
            created_by=actor, input_material=json.dumps(before, sort_keys=True, ensure_ascii=False),
            prediction_summary=json.dumps(before, sort_keys=True, ensure_ascii=False),
            human_correction=json.dumps(after, sort_keys=True, ensure_ascii=False),
            feedback_reason=reason,
            evidence_refs=[{
                "type": "REPORT_EVIDENCE", "document_id": str(getattr(candidate, "document_id")),
                "page": getattr(candidate, "source_page", None), "section": getattr(candidate, "source_section", None),
            }],
            model_provider="report_parser", model_name=method,
            eligible_for_training=method == "LLM", deidentified=True,
        )

    def capture_citation_feedback(self, session: Session, *, answer_id: str, label: str, reason: str, actor: str) -> FeedbackRecord:
        if label not in {"HELPFUL", "IRRELEVANT", "MISSING", "INCORRECT"}:
            raise ValueError("Unsupported citation feedback label.")
        return self.capture(
            session, feedback_type=AI_CONTENT_FEEDBACK, feature="citation_grounding",
            source_entity_type="AIAnswer", source_entity_id=answer_id,
            feedback_label=label, created_by=actor, input_material=answer_id,
            feedback_reason=reason, eligible_for_training=label != "HELPFUL", deidentified=True,
        )

    def capture_workflow_feedback(self, session: Session, *, entity_type: str, entity_id: str, label: str, reason: str, actor: str, member_id: UUID | None = None) -> FeedbackRecord:
        return self.capture(
            session, feedback_type=WORKFLOW_FEEDBACK, feature="workflow_action",
            source_entity_type=entity_type, source_entity_id=entity_id,
            feedback_label=label, created_by=actor, input_material=f"{entity_type}:{entity_id}:{label}",
            feedback_reason=reason, member_id=member_id, eligible_for_training=False, deidentified=True,
        )

    def capture_doctor_reference(self, session: Session, *, review_id: UUID, actor: str, reason: str) -> FeedbackRecord:
        return self.capture(
            session, feedback_type=WORKFLOW_FEEDBACK, feature="doctor_review_reference",
            source_entity_type="DoctorReview", source_entity_id=str(review_id),
            feedback_label="HUMAN_MEDICAL_REFERENCE", created_by=actor,
            input_material=str(review_id), feedback_reason=reason,
            eligible_for_training=False, deidentified=False,
        )

    def capture_risk_rule_feedback(
        self, session: Session, *, risk_event_id: UUID, label: str, reason: str,
        actor: str, supporting_evidence: list[dict[str, Any]] | None = None,
    ) -> tuple[FeedbackRecord, RiskRuleReviewCandidate]:
        if label not in RISK_FEEDBACK_LABELS:
            raise ValueError("Unsupported risk feedback label.")
        event = session.get(RiskEvent, risk_event_id)
        if event is None:
            raise ValueError("RiskEvent not found.")
        feedback = self.capture(
            session, feedback_type=RISK_RULE_FEEDBACK, feature="risk_rule_review",
            source_entity_type="RiskEvent", source_entity_id=str(event.id), member_id=event.patient_id,
            feedback_label=label, created_by=actor, input_material=f"{event.id}:{event.risk_rule_id}:{label}",
            feedback_reason=reason, evidence_refs=supporting_evidence,
            eligible_for_training=False, deidentified=False,
        )
        candidate = RiskRuleReviewCandidate(
            risk_rule_id=event.risk_rule_id, risk_event_id=event.id,
            feedback_record_id=feedback.id, feedback_type=label, reason=reason,
            supporting_evidence=supporting_evidence or [],
        )
        session.add(candidate)
        session.flush()
        _audit(session, actor=actor, action="created_risk_rule_review_candidate", entity=candidate,
               patient_id=event.patient_id, detail={"feedback_type": label})
        return feedback, candidate

    def review(self, session: Session, record_id: UUID, *, reviewer: str, accepted: bool) -> FeedbackRecord:
        record = session.get(FeedbackRecord, record_id)
        if record is None or record.review_status != "CAPTURED":
            raise ValueError("Feedback is not awaiting review.")
        record.review_status = "REVIEWED" if accepted else "REJECTED"
        record.reviewed_by = reviewer
        record.reviewed_at = datetime.now(timezone.utc)
        _audit(session, actor=reviewer, action="reviewed_ai_feedback", entity=record, patient_id=record.member_id,
               detail={"accepted": accepted})
        return record

    def accept_for_dataset(self, session: Session, record_id: UUID, *, reviewer: str) -> FeedbackRecord:
        record = session.get(FeedbackRecord, record_id)
        if record is None or record.review_status != "REVIEWED":
            raise ValueError("Only reviewed feedback can enter a dataset.")
        if not record.eligible_for_training or not record.deidentified:
            raise ValueError("Feedback is not eligible for an offline dataset.")
        record.review_status = "ACCEPTED_FOR_DATASET"
        record.reviewed_by = reviewer
        record.reviewed_at = datetime.now(timezone.utc)
        _audit(session, actor=reviewer, action="accepted_feedback_for_dataset", entity=record, patient_id=record.member_id)
        return record


class FeedbackDatasetBuilder:
    """Build immutable, de-identified JSONL-compatible snapshots; never train."""

    SCHEMA_VERSION = "1.0"

    @staticmethod
    def _sample(record: FeedbackRecord) -> dict[str, Any]:
        return {
            "task": record.feature,
            "input_hash": record.input_hash,
            "previous_output": deidentify_text(record.prediction_summary),
            "correct_output": deidentify_text(record.human_correction),
            "feedback_label": record.feedback_label,
            "evidence_type": sorted({str(item.get("type", "REFERENCE")) for item in record.evidence_refs}),
            "source": "human_confirmed",
            "model_version": record.model_version,
            "prompt_version": record.prompt_version,
        }

    @staticmethod
    def _confidence(record: FeedbackRecord) -> float:
        values = [
            float(item["value"])
            for item in record.evidence_refs
            if item.get("type") == "FEEDBACK_CONFIDENCE" and item.get("value") is not None
        ]
        # Reviewed human corrections created before confidence capture are trusted
        # at the dataset gate; this preserves backward compatibility.
        return max(values, default=1.0)

    def build(
        self, session: Session, *, dataset_id: str, actor: str,
        feature: str | None = None, model_version: str | None = None,
        created_from: datetime | None = None, created_to: datetime | None = None,
        minimum_confidence: float | None = None,
    ) -> FeedbackDatasetVersion:
        if minimum_confidence is not None and not 0 <= minimum_confidence <= 1:
            raise ValueError("Minimum confidence must be between 0 and 1.")
        statement = select(FeedbackRecord).where(
            FeedbackRecord.review_status == "ACCEPTED_FOR_DATASET",
            FeedbackRecord.eligible_for_training.is_(True),
            FeedbackRecord.deidentified.is_(True),
        )
        if feature:
            statement = statement.where(FeedbackRecord.feature == feature)
        if model_version:
            statement = statement.where(FeedbackRecord.model_version == model_version)
        if created_from:
            statement = statement.where(FeedbackRecord.created_at >= created_from)
        if created_to:
            statement = statement.where(FeedbackRecord.created_at <= created_to)
        records = list(session.scalars(statement.order_by(FeedbackRecord.created_at, FeedbackRecord.id)))
        if minimum_confidence is not None:
            records = [record for record in records if self._confidence(record) >= minimum_confidence]
        samples = [self._sample(record) for record in records]
        canonical = "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in samples)
        version = int(session.scalar(select(func.max(FeedbackDatasetVersion.dataset_version)).where(
            FeedbackDatasetVersion.dataset_id == dataset_id
        )) or 0) + 1
        snapshot = FeedbackDatasetVersion(
            dataset_id=dataset_id, dataset_version=version, schema_version=self.SCHEMA_VERSION,
            feature=feature, record_count=len(samples), source_feedback_count=len(records),
            content_hash=sha256(canonical.encode("utf-8")).hexdigest(), records_json=samples,
        )
        session.add(snapshot)
        session.flush()
        _audit(session, actor=actor, action="created_feedback_dataset", entity=snapshot,
               detail={"dataset_id": dataset_id, "dataset_version": version, "record_count": len(samples)})
        return snapshot

    @staticmethod
    def to_jsonl(snapshot: FeedbackDatasetVersion) -> str:
        return "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in snapshot.records_json)


@dataclass(frozen=True)
class TrainingJobStatus:
    status: str
    detail: str


class ModelTrainingAdapter(Protocol):
    def prepare_dataset(self, snapshot: FeedbackDatasetVersion) -> str: ...
    def submit_training_job(self, dataset_reference: str) -> TrainingJobStatus: ...
    def get_training_status(self, job_id: str) -> TrainingJobStatus: ...
    def get_model_artifact(self, job_id: str) -> str | None: ...


class NotConfiguredTrainingAdapter:
    """Explicit offline-only placeholder; it cannot submit or deploy a model."""

    def prepare_dataset(self, snapshot: FeedbackDatasetVersion) -> str:
        return f"{snapshot.dataset_id}-v{snapshot.dataset_version:03d}"

    def submit_training_job(self, dataset_reference: str) -> TrainingJobStatus:
        return TrainingJobStatus("NOT_CONFIGURED", "Offline model training is not configured.")

    def get_training_status(self, job_id: str) -> TrainingJobStatus:
        return TrainingJobStatus("NOT_CONFIGURED", "No training job was submitted.")

    def get_model_artifact(self, job_id: str) -> str | None:
        return None


class PromptOptimizationService:
    """Select reviewed few-shot material without changing the active prompt."""

    @staticmethod
    def examples(snapshot: FeedbackDatasetVersion, limit: int = 8) -> tuple[dict[str, Any], ...]:
        return tuple(snapshot.records_json[: max(0, min(limit, 20))])


class ModelRegistryService:
    REQUIRED_METRICS = {"citation_validity", "hallucination_rate", "critical_task_success", "unsafe_answer_rate", "no_source_refusal"}

    def create_candidate(self, session: Session, *, provider: str, base_model: str, model_version: str, prompt_version: str | None = None, training_dataset_version: str | None = None) -> ModelVersionRegistry:
        candidate = ModelVersionRegistry(
            provider=provider, base_model=base_model, model_version=model_version,
            prompt_version=prompt_version, training_dataset_version=training_dataset_version,
        )
        session.add(candidate)
        session.flush()
        return candidate

    def record_evaluation(self, session: Session, candidate_id: UUID, *, report: dict[str, Any], actor: str) -> ModelVersionRegistry:
        candidate = session.get(ModelVersionRegistry, candidate_id)
        if candidate is None or candidate.status not in {"CANDIDATE", "EVALUATING"}:
            raise ValueError("Model candidate is not evaluable.")
        missing = self.REQUIRED_METRICS - set(report)
        if missing:
            raise ValueError(f"Evaluation report missing metrics: {sorted(missing)}")
        candidate.evaluation_report = report
        candidate.status = "EVALUATING"
        _audit(session, actor=actor, action="evaluated_model_candidate", entity=candidate)
        return candidate

    @staticmethod
    def _passes(candidate: ModelVersionRegistry, active: ModelVersionRegistry | None) -> bool:
        report = candidate.evaluation_report
        if not report or report.get("safety_regression") or float(report["unsafe_answer_rate"]) > 0:
            return False
        if active is None:
            return bool(report.get("no_source_refusal")) and float(report["critical_task_success"]) > 0
        baseline = active.evaluation_report
        return bool(
            float(report["citation_validity"]) >= float(baseline.get("citation_validity", 0))
            and float(report["hallucination_rate"]) <= float(baseline.get("hallucination_rate", 1))
            and float(report["critical_task_success"]) >= float(baseline.get("critical_task_success", 0))
            and float(report["unsafe_answer_rate"]) <= float(baseline.get("unsafe_answer_rate", 1))
            and bool(report["no_source_refusal"])
        )

    def approve(self, session: Session, candidate_id: UUID, *, approver: str) -> ModelVersionRegistry:
        candidate = session.get(ModelVersionRegistry, candidate_id)
        if candidate is None or candidate.status != "EVALUATING":
            raise ValueError("Candidate requires completed evaluation.")
        active = session.scalar(select(ModelVersionRegistry).where(
            ModelVersionRegistry.provider == candidate.provider,
            ModelVersionRegistry.status == "ACTIVE",
        ))
        if not self._passes(candidate, active):
            candidate.status = "REJECTED"
            _audit(session, actor=approver, action="rejected_model_candidate", entity=candidate,
                   detail={"reason": "evaluation_gate"})
            raise ValueError("Candidate failed the safety/regression gate.")
        candidate.status = "APPROVED"
        candidate.approved_by = approver
        candidate.approved_at = datetime.now(timezone.utc)
        _audit(session, actor=approver, action="approved_model_candidate", entity=candidate)
        return candidate

    def activate(self, session: Session, candidate_id: UUID, *, approver: str, reason: str) -> ModelVersionRegistry:
        candidate = session.get(ModelVersionRegistry, candidate_id)
        if candidate is None or candidate.status != "APPROVED" or candidate.approved_by != approver:
            raise ValueError("Only the human approver can activate an approved candidate.")
        previous = session.scalar(select(ModelVersionRegistry).where(
            ModelVersionRegistry.provider == candidate.provider,
            ModelVersionRegistry.status == "ACTIVE",
        ))
        if previous is not None:
            previous.status = "RETIRED"
            previous.retired_at = datetime.now(timezone.utc)
        candidate.status = "ACTIVE"
        candidate.activated_at = datetime.now(timezone.utc)
        _audit(session, actor=approver, action="activated_model_version", entity=candidate,
               detail={"previous_version": previous.model_version if previous else None, "new_version": candidate.model_version, "reason": reason})
        return candidate

    def rollback(self, session: Session, target_id: UUID, *, approver: str, reason: str) -> ModelVersionRegistry:
        """Explicitly restore an evaluated retired version; never run automatically."""
        target = session.get(ModelVersionRegistry, target_id)
        if target is None or target.status != "RETIRED" or not target.approved_by:
            raise ValueError("Rollback target must be a previously approved retired version.")
        current = session.scalar(select(ModelVersionRegistry).where(
            ModelVersionRegistry.provider == target.provider,
            ModelVersionRegistry.status == "ACTIVE",
        ))
        if current is None:
            raise ValueError("No active version is available to roll back.")
        current.status = "RETIRED"
        current.retired_at = datetime.now(timezone.utc)
        target.status = "ACTIVE"
        target.activated_at = datetime.now(timezone.utc)
        target.retired_at = None
        _audit(session, actor=approver, action="rolled_back_model_version", entity=target,
               detail={"previous_version": current.model_version, "new_version": target.model_version, "reason": reason})
        return target
