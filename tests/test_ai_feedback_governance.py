from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from executive_health_ai.models import (
    AuditLog, Base, DoctorReview, FeedbackDatasetVersion, FeedbackRecord,
    HealthProblem, ModelVersionRegistry, Patient, ReportExtractionCandidate,
    ReportExtractionRun, RiskEvent, RiskRule, RiskRuleReviewCandidate,
)
from executive_health_ai.services.ai_feedback import (
    AI_CONTENT_FEEDBACK, WORKFLOW_FEEDBACK, FeedbackDatasetBuilder, FeedbackService,
    ModelRegistryService, NotConfiguredTrainingAdapter, PromptOptimizationService,
)
from executive_health_ai.services.report_parsing import ReportParsingService


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def member(db: Session) -> Patient:
    item = Patient(external_id="synthetic-feedback-member", display_name="Synthetic Member", timezone="Asia/Tokyo")
    db.add(item); db.flush()
    return item


def report_candidate(db: Session, patient: Patient, *, method: str = "LLM") -> ReportExtractionCandidate:
    from executive_health_ai.models import Document
    document = Document(patient_id=patient.id, document_type="health_report", title="Synthetic report", storage_reference="synthetic", source="synthetic")
    db.add(document); db.flush()
    run = ReportExtractionRun(document_id=document.id, patient_id=patient.id, parser_version="v1", canonical_registry_version="v1", file_hash="a" * 64, file_type="txt")
    db.add(run); db.flush()
    candidate = ReportExtractionCandidate(
        extraction_run_id=run.id, document_id=document.id, patient_id=patient.id,
        candidate_type="OBSERVATION", canonical_code="hba1c", raw_name="合成指标",
        raw_value="5", normalized_value="5", unit="mmol/L", confidence="MEDIUM",
        extraction_method=method, evidence_text="合成证据", source_page=1,
    )
    db.add(candidate); db.flush()
    return candidate


def eligible_feedback(db: Session, *, feature: str = "report_semantic_mapping") -> FeedbackRecord:
    record = FeedbackService().capture(
        db, feedback_type=AI_CONTENT_FEEDBACK, feature=feature,
        source_entity_type="ReportExtractionCandidate", source_entity_id="synthetic",
        feedback_label="HUMAN_CORRECTION", created_by="reviewer",
        input_material="deidentified input", prediction_summary="old@example.com old",
        human_correction="correct", eligible_for_training=True, deidentified=True,
    )
    FeedbackService().review(db, record.id, reviewer="governor", accepted=True)
    FeedbackService().accept_for_dataset(db, record.id, reviewer="governor")
    return record


def test_report_correction_creates_deidentified_feedback(db):
    candidate = report_candidate(db, member(db))
    ReportParsingService().correct_candidate(db, candidate, "manager", canonical="glucose", value="5", unit="mmol/L", reason="语义映射纠正")
    feedback = db.scalar(select(FeedbackRecord))
    assert feedback and feedback.feature == "report_semantic_mapping"
    assert feedback.eligible_for_training is True and feedback.deidentified is True
    assert feedback.input_hash and "合成证据" not in (feedback.prediction_summary or "")


def test_semantic_correction_preserves_previous_and_correct_output(db):
    candidate = report_candidate(db, member(db))
    ReportParsingService().correct_candidate(db, candidate, "manager", canonical="fasting_glucose", value="5", unit="mmol/L", reason="人工确认")
    feedback = db.scalar(select(FeedbackRecord))
    assert '"canonical_code": "hba1c"' in feedback.prediction_summary
    assert '"canonical_code": "fasting_glucose"' in feedback.human_correction


def test_citation_feedback_is_captured_for_offline_review(db):
    record = FeedbackService().capture_citation_feedback(db, answer_id="answer-1", label="INCORRECT", reason="引用不支持正文", actor="reviewer")
    assert record.feature == "citation_grounding" and record.review_status == "CAPTURED"
    assert record.eligible_for_training and record.deidentified


def risk_fixture(db: Session) -> tuple[RiskRule, RiskEvent]:
    patient = member(db)
    rule = RiskRule(
        name="Synthetic rule", code="FEEDBACK_TEST", applicable_device_class="ANY",
        canonical_code="glucose", risk_level="YELLOW", condition_type="SYNTHETIC_TEST_THRESHOLD",
        threshold_config={"value": "10", "unit": "mmol/L"}, window_config={},
        requires_repeated_measurement=False, requires_symptom_confirmation=False,
        action_type="SYNTHETIC_TEST_ONLY", source_reference="synthetic", scope="TEST",
        review_status="APPROVED", is_active=True,
    )
    db.add(rule); db.flush()
    event = RiskEvent(
        patient_id=patient.id, risk_rule_id=rule.id, risk_level="YELLOW", status="NEW",
        device_class="ANY", canonical_code="glucose", evidence_json={"synthetic": True},
        summary="Synthetic risk", requires_manager_review=True,
    )
    db.add(event); db.flush()
    return rule, event


def test_risk_feedback_creates_review_candidate_without_changing_rule(db):
    rule, event = risk_fixture(db)
    original = deepcopy(rule.threshold_config)
    feedback, review = FeedbackService().capture_risk_rule_feedback(
        db, risk_event_id=event.id, label="THRESHOLD_REVIEW_NEEDED",
        reason="请由临床治理复核适用范围", actor="manager",
    )
    assert feedback.eligible_for_training is False
    assert review.review_status == "PENDING_REVIEW"
    assert db.scalar(select(func.count()).select_from(RiskRuleReviewCandidate)) == 1
    assert rule.threshold_config == original and rule.review_status == "APPROVED"


def test_doctor_review_reference_is_not_training_eligible(db):
    record = FeedbackService().capture_doctor_reference(db, review_id=uuid4(), actor="doctor", reason="仅作为人工参考")
    assert record.eligible_for_training is False and record.deidentified is False


def test_workflow_feedback_is_captured_but_not_used_as_a_training_label(db):
    record = FeedbackService().capture_workflow_feedback(
        db, entity_type="Task", entity_id="synthetic-task", label="CONTACT_MEMBER",
        reason="人工选择下一步动作", actor="manager",
    )
    assert record.feedback_type == WORKFLOW_FEEDBACK
    assert record.eligible_for_training is False


def test_dataset_includes_only_reviewed_accepted_deidentified_feedback_and_excludes_phi(db):
    accepted = eligible_feedback(db)
    captured = FeedbackService().capture(
        db, feedback_type=AI_CONTENT_FEEDBACK, feature="report_semantic_mapping",
        source_entity_type="AIAnswer", source_entity_id="pending", feedback_label="MISSING",
        created_by="reviewer", input_material="pending", human_correction="pending",
        eligible_for_training=True, deidentified=True,
    )
    snapshot = FeedbackDatasetBuilder().build(db, dataset_id="feedback-report", actor="governor")
    payload = FeedbackDatasetBuilder.to_jsonl(snapshot)
    assert snapshot.record_count == 1 and accepted.input_hash in payload
    assert captured.input_hash not in payload
    assert "old@example.com" not in payload and "member_id" not in payload and "source_entity_id" not in payload


def test_dataset_versions_are_immutable_snapshots(db):
    eligible_feedback(db)
    builder = FeedbackDatasetBuilder()
    first = builder.build(db, dataset_id="feedback-report", actor="governor")
    second = builder.build(db, dataset_id="feedback-report", actor="governor")
    assert (first.dataset_version, second.dataset_version) == (1, 2)
    assert first.id != second.id and first.content_hash == second.content_hash
    first.record_count = 99
    with pytest.raises(ValueError, match="immutable"):
        db.flush()


def test_dataset_minimum_confidence_filters_accepted_records(db):
    service = FeedbackService()
    for entity_id, confidence in (("high", 0.9), ("low", 0.4)):
        record = service.capture(
            db, feedback_type=AI_CONTENT_FEEDBACK, feature="report_semantic_mapping",
            source_entity_type="ReportExtractionCandidate", source_entity_id=entity_id,
            feedback_label="HUMAN_CORRECTION", created_by="reviewer",
            input_material=entity_id, human_correction=f"correct-{entity_id}",
            eligible_for_training=True, deidentified=True, confidence=confidence,
        )
        service.review(db, record.id, reviewer="governor", accepted=True)
        service.accept_for_dataset(db, record.id, reviewer="governor")
    snapshot = FeedbackDatasetBuilder().build(
        db, dataset_id="confidence-filtered", actor="governor", minimum_confidence=0.8,
    )
    assert snapshot.record_count == 1
    assert snapshot.records_json[0]["correct_output"] == "correct-high"


def evaluation(*, safety_regression: bool = False, citation: float = 1.0) -> dict[str, object]:
    return {
        "citation_validity": citation, "hallucination_rate": 0.0,
        "critical_task_success": 1.0, "unsafe_answer_rate": 0.0,
        "no_source_refusal": True, "safety_regression": safety_regression,
    }


def test_model_candidate_cannot_activate_without_evaluation_and_human_approval(db):
    service = ModelRegistryService()
    candidate = service.create_candidate(db, provider="local", base_model="base", model_version="candidate-v1")
    with pytest.raises(ValueError):
        service.activate(db, candidate.id, approver="governor", reason="not approved")


def test_candidate_with_safety_regression_is_rejected(db):
    service = ModelRegistryService()
    candidate = service.create_candidate(db, provider="local", base_model="base", model_version="unsafe-v1")
    service.record_evaluation(db, candidate.id, report=evaluation(safety_regression=True), actor="evaluator")
    with pytest.raises(ValueError, match="failed"):
        service.approve(db, candidate.id, approver="governor")
    assert candidate.status == "REJECTED"


def test_model_activation_is_human_approved_and_audited(db):
    service = ModelRegistryService()
    candidate = service.create_candidate(db, provider="local", base_model="base", model_version="safe-v1", prompt_version="prompt-v2")
    service.record_evaluation(db, candidate.id, report=evaluation(), actor="evaluator")
    service.approve(db, candidate.id, approver="governor")
    service.activate(db, candidate.id, approver="governor", reason="fixed suite passed")
    assert candidate.status == "ACTIVE"
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "activated_model_version"))
    assert audit and audit.detail_json["new_version"] == "safe-v1"


def test_model_rollback_is_explicit_and_audited(db):
    service = ModelRegistryService()
    first = service.create_candidate(db, provider="local", base_model="base", model_version="stable-v1")
    service.record_evaluation(db, first.id, report=evaluation(), actor="evaluator")
    service.approve(db, first.id, approver="governor")
    service.activate(db, first.id, approver="governor", reason="initial release")
    second = service.create_candidate(db, provider="local", base_model="base", model_version="stable-v2")
    service.record_evaluation(db, second.id, report=evaluation(), actor="evaluator")
    service.approve(db, second.id, approver="governor")
    service.activate(db, second.id, approver="governor", reason="next release")

    restored = service.rollback(db, first.id, approver="governor", reason="operator rollback")
    assert restored.status == "ACTIVE" and second.status == "RETIRED"
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "rolled_back_model_version"))
    assert audit and audit.detail_json["previous_version"] == "stable-v2"


def test_prompt_optimization_and_training_adapter_remain_offline(db):
    eligible_feedback(db)
    snapshot = FeedbackDatasetBuilder().build(db, dataset_id="feedback-report", actor="governor")
    assert len(PromptOptimizationService.examples(snapshot)) == 1
    adapter = NotConfiguredTrainingAdapter()
    status = adapter.submit_training_job(adapter.prepare_dataset(snapshot))
    assert status.status == "NOT_CONFIGURED" and adapter.get_model_artifact("none") is None
