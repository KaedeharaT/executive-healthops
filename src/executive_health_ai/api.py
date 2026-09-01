"""FastAPI surface for the human-reviewed HealthOps portfolio prototype."""

from __future__ import annotations

import base64
import os
import logging
from datetime import datetime, timezone
from typing import Callable, Iterator
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from executive_health_ai.database import SessionLocal
from executive_health_ai.models import Alert, Document, DoctorReview, ExecutionBarrier, FollowUp, HealthJourney, HealthProblem, HealthProgram, IngestionJob, Observation, OutcomeEvaluation, Patient, ProgramPhase, RawIngestionRecord, ReportExtractionCandidate, ReportExtractionRun, RiskEvent, Task, WeeklyReview
from executive_health_ai.schemas import (
    AlertOut, DashboardOut, DoctorReviewCreate, DoctorReviewOut, DocumentCreate, DocumentOut,
    FollowUpCreate, FollowUpOut, HealthProblemOut, ManagerConfirmation, MemberOut,
    AppleHealthSyncRequest, AssessmentCreate, BarrierCreate, FileIngestionRequest, IngestionRequest, MedicalReferralCreate, ObservationCreate, OutcomeCreate, ProgramCreate, ProgramOut,
    ReportCandidateReview, ReportUploadRequest, TaskCompletion, TaskOut, TimelineEventOut, WeeklyReviewCreate, YellowAcknowledge, YellowClose, YellowContact, YellowDoctorCompletion, YellowDoctorEscalation, YellowFollowUp, YellowManagementAdjustment, YellowMonitoring,
)
from executive_health_ai.services.chronic_care import (
    create_assessment, create_program, escalate_to_medical_care, record_execution_barrier,
    record_outcome_evaluation, record_weekly_review,
)
from executive_health_ai.services.ingestion import get_or_create_raw_data
from executive_health_ai.integrations.service import ingest, manually_correct_record, mark_source_deleted, match_member
from executive_health_ai.services.timeline import build_patient_timeline
from executive_health_ai.services.report_parsing import ReportParsingService
from executive_health_ai.services.risk_triage import RiskEvaluationService
from executive_health_ai.services.longitudinal import HealthTimelineService, ManagementRoutingService
from executive_health_ai.services.operational_worklist import OperationalWorklistService
from executive_health_ai.services.risk_operations import RiskOperationsService
from executive_health_ai.services.task_transitions import TaskTransitionService
from executive_health_ai.services.workflow import (
    complete_follow_up, confirm_alert_as_manager, record_doctor_review, screen_member,
)

logger = logging.getLogger(__name__)


def create_app(session_factory: Callable[[], Session] = SessionLocal) -> FastAPI:
    app = FastAPI(
        title="企业高管健康运营平台 API",
        version="0.9.0",
        description="健康管理与数据接入接口。系统不进行自动诊断、处方或药物调整，医疗决定须由医生确认。",
    )

    def get_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    def member_or_404(session: Session, member_id: UUID) -> Patient:
        member = session.get(Patient, member_id)
        if member is None:
            raise HTTPException(status_code=404, detail="Member not found")
        return member

    def require_apple_bridge_token(authorization: str | None = Header(default=None)) -> None:
        expected = os.getenv("APPLE_HEALTH_BRIDGE_TOKEN")
        if not expected:
            raise HTTPException(status_code=503, detail="Apple Health bridge token is not configured.")
        if authorization != f"Bearer {expected}":
            raise HTTPException(status_code=401, detail="Invalid bridge authorization.")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "medical_safety": "human_review_required"}

    @app.get("/members", response_model=list[MemberOut])
    def list_members(session: Session = Depends(get_session)) -> list[Patient]:
        return list(session.scalars(select(Patient).order_by(Patient.created_at.desc())))

    @app.get("/members/{member_id}", response_model=MemberOut)
    def get_member(member_id: UUID, session: Session = Depends(get_session)) -> Patient:
        return member_or_404(session, member_id)

    @app.get("/members/{member_id}/timeline", deprecated=True)
    def member_timeline(member_id: UUID, days: int = 30, session: Session = Depends(get_session)) -> list[dict[str, object]]:
        """Deprecated raw-event compatibility endpoint; product UI uses Longitudinal Timeline."""
        member_or_404(session, member_id)
        return [item.__dict__ for item in build_patient_timeline(session, member_id, days)]

    @app.get("/members/{member_id}/timeline/v2", response_model=list[TimelineEventOut])
    def member_timeline_v2(member_id: UUID, limit: int = 100, session: Session = Depends(get_session)) -> list[dict[str, object]]:
        """Current read-only projection assembled from source business entities."""
        member_or_404(session, member_id)
        bounded_limit = max(1, min(limit, 200))
        return [item.__dict__ for item in HealthTimelineService().get_timeline(session, member_id, limit=bounded_limit)]

    @app.post("/assessments", status_code=status.HTTP_201_CREATED)
    def create_member_assessment(payload: AssessmentCreate, session: Session = Depends(get_session)) -> dict[str, object]:
        member_or_404(session, payload.member_id)
        try:
            journey = create_assessment(session, payload.member_id, payload.assessment_summary, payload.main_focus, payload.risk_level, payload.supporting_goals, payload.baseline, payload.owner, payload.doctor)
            session.commit()
        except ValueError as error:
            session.rollback()
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"id": str(journey.id), "stage": journey.current_stage, "risk_level": journey.risk_level}

    @app.post("/programs", response_model=ProgramOut, status_code=status.HTTP_201_CREATED)
    def create_health_program(payload: ProgramCreate, session: Session = Depends(get_session)) -> HealthProgram:
        journey = session.get(HealthJourney, payload.journey_id)
        if journey is None:
            raise HTTPException(status_code=404, detail="Health journey not found")
        problems = list(session.scalars(select(HealthProblem).where(HealthProblem.id.in_(payload.priority_problem_ids)))) if payload.priority_problem_ids else []
        try:
            program = create_program(session, journey, payload.program_type, payload.title, payload.main_goal, payload.supporting_goals, payload.start_date, payload.owner, payload.doctor, problems, payload.end_date)
            session.commit()
        except ValueError as error:
            session.rollback()
            raise HTTPException(status_code=422, detail=str(error)) from error
        return program

    @app.get("/programs", response_model=list[ProgramOut])
    def list_programs(member_id: UUID | None = None, session: Session = Depends(get_session)) -> list[HealthProgram]:
        statement = select(HealthProgram).order_by(HealthProgram.start_date.desc())
        if member_id is not None:
            statement = statement.where(HealthProgram.patient_id == member_id)
        return list(session.scalars(statement))

    @app.get("/programs/{program_id}", response_model=ProgramOut)
    def get_program(program_id: UUID, session: Session = Depends(get_session)) -> HealthProgram:
        program = session.get(HealthProgram, program_id)
        if program is None:
            raise HTTPException(status_code=404, detail="Health program not found")
        return program

    @app.get("/programs/{program_id}/phases", response_model=None)
    def list_program_phases(program_id: UUID, session: Session = Depends(get_session)) -> list[ProgramPhase]:
        get_program(program_id, session)
        return list(session.scalars(select(ProgramPhase).where(ProgramPhase.program_id == program_id).order_by(ProgramPhase.sequence)))

    @app.get("/programs/{program_id}/reviews", response_model=None)
    def list_program_reviews(program_id: UUID, session: Session = Depends(get_session)) -> list[WeeklyReview]:
        get_program(program_id, session)
        return list(session.scalars(select(WeeklyReview).where(WeeklyReview.program_id == program_id).order_by(WeeklyReview.reviewed_at.desc())))

    @app.get("/programs/{program_id}/execution-barriers", response_model=None)
    def list_program_barriers(program_id: UUID, session: Session = Depends(get_session)) -> list[ExecutionBarrier]:
        get_program(program_id, session)
        return list(session.scalars(select(ExecutionBarrier).where(ExecutionBarrier.program_id == program_id).order_by(ExecutionBarrier.detected_at.desc())))

    @app.get("/programs/{program_id}/outcomes", response_model=None)
    def list_program_outcomes(program_id: UUID, session: Session = Depends(get_session)) -> list[OutcomeEvaluation]:
        get_program(program_id, session)
        return list(session.scalars(select(OutcomeEvaluation).where(OutcomeEvaluation.program_id == program_id).order_by(OutcomeEvaluation.evaluation_date.desc())))

    @app.post("/programs/{program_id}/reviews", status_code=status.HTTP_201_CREATED)
    def add_weekly_review(program_id: UUID, payload: WeeklyReviewCreate, session: Session = Depends(get_session)) -> dict[str, object]:
        program = session.get(HealthProgram, program_id)
        if program is None:
            raise HTTPException(status_code=404, detail="Health program not found")
        review = record_weekly_review(session, program, **payload.model_dump())
        session.commit()
        return {"id": str(review.id), "program_id": str(program.id), "week_number": review.week_number}

    @app.post("/programs/{program_id}/execution-barriers", status_code=status.HTTP_201_CREATED)
    def add_execution_barrier(program_id: UUID, payload: BarrierCreate, session: Session = Depends(get_session)) -> dict[str, object]:
        program = session.get(HealthProgram, program_id)
        if program is None:
            raise HTTPException(status_code=404, detail="Health program not found")
        task = session.get(Task, payload.task_id) if payload.task_id else None
        try:
            barrier = record_execution_barrier(session, program, payload.reason, payload.description, payload.confirmed_by, task, payload.resolution)
            session.commit()
        except ValueError as error:
            session.rollback()
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"id": str(barrier.id), "status": barrier.status, "reason": barrier.reason}

    @app.post("/programs/{program_id}/outcomes", status_code=status.HTTP_201_CREATED)
    def add_outcome(program_id: UUID, payload: OutcomeCreate, session: Session = Depends(get_session)) -> dict[str, object]:
        program = session.get(HealthProgram, program_id)
        if program is None:
            raise HTTPException(status_code=404, detail="Health program not found")
        try:
            outcome = record_outcome_evaluation(session, program, **payload.model_dump())
            session.commit()
        except ValueError as error:
            session.rollback()
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"id": str(outcome.id), "result": outcome.result, "metric": outcome.metric}

    @app.post("/programs/{program_id}/medical-referral")
    def create_medical_referral(program_id: UUID, payload: MedicalReferralCreate, session: Session = Depends(get_session)) -> dict[str, str]:
        program = session.get(HealthProgram, program_id)
        if program is None:
            raise HTTPException(status_code=404, detail="Health program not found")
        escalate_to_medical_care(session, program, payload.actor, payload.reason)
        session.commit()
        return {"status": program.status, "next_decision": program.next_decision or "MEDICAL_REFERRAL"}

    @app.post("/observations", status_code=status.HTTP_201_CREATED)
    def create_observation(payload: ObservationCreate, session: Session = Depends(get_session)) -> dict[str, object]:
        member_or_404(session, payload.member_id)
        raw, raw_created = get_or_create_raw_data(
            session, patient_id=payload.member_id, device_id=payload.source_device_id,
            source=payload.source, record_type="manual_observation",
            payload_json={"metric_code": payload.metric_code, "value": str(payload.value), "unit": payload.unit, "observed_at": payload.observed_at.isoformat()}, recorded_at=payload.observed_at,
        )
        observation = session.scalar(select(Observation).where(Observation.patient_id == payload.member_id, Observation.raw_record_id == raw.id, Observation.metric_code == payload.metric_code))
        if observation is None:
            observation = Observation(patient_id=payload.member_id, device_id=payload.source_device_id, observed_at=payload.observed_at, metric_code=payload.metric_code, value_numeric=payload.value, unit=payload.unit, source=payload.source, quality_flag=payload.quality_flag, raw_record_id=raw.id)
            session.add(observation)
        session.flush()
        risk_summary = RiskEvaluationService().evaluate_observation_safely(session, observation.id).summary()
        ManagementRoutingService().evaluate_observation(session, observation.id)
        session.commit()
        return {"id": str(observation.id), "raw_record_id": str(raw.id), "raw_created": raw_created, "risk_evaluation_summary": risk_summary}

    @app.post("/ingestion/observations", status_code=status.HTTP_201_CREATED)
    def ingest_observations(payload: IngestionRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        source_payload = {"records": payload.records}
        try:
            summary = ingest(session, payload.provider, source_payload, external_member_id=payload.member_external_id, member_id=payload.member_id, mapping=payload.mapping, dry_run=payload.dry_run)
            session.commit()
        except ValueError as error:
            session.rollback(); raise HTTPException(status_code=422, detail=str(error)) from error
        return summary.__dict__

    @app.post("/ingestion/files", status_code=status.HTTP_201_CREATED)
    def ingest_file(payload: FileIngestionRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        try:
            content = base64.b64decode(payload.content_base64, validate=True)
            if payload.provider == "pdf":
                if payload.member_id is None:
                    raise ValueError("PDF document registration requires a verified internal member_id.")
                member_or_404(session, payload.member_id)
                job = IngestionJob(source_system="pdf", source_type="file", patient_id=payload.member_id, status="PARTIAL_SUCCESS", records_received=1, records_valid=0, records_invalid=0, records_duplicate=0, records_created=0, error_count=0, created_by="file_upload", completed_at=datetime.now(timezone.utc))
                session.add(job); session.flush()
                document = Document(patient_id=payload.member_id, document_type="health_check_pdf", title=payload.filename, storage_reference=f"gateway-upload://{job.id}/{payload.filename}", source="pdf_gateway", status="WAITING_REVIEW")
                session.add(document)
                session.add(RawIngestionRecord(job_id=job.id, patient_id=payload.member_id, source_system="pdf", source_type="file", source_record_id=payload.filename, payload_json={"filename": payload.filename, "bytes": len(content), "synthetic_or_external": "unparsed"}, adapter_name="PDFParserInterface", adapter_version="v1", status="WAITING_REVIEW", normalization_json={"message": "DEMO / RULE-BASED EXTRACTION NOT RUN; human review required."}))
                session.commit()
                return {"job_id": str(job.id), "status": job.status, "filename": payload.filename, "document_id": str(document.id)}
            provider_payload: object = content if payload.provider in {"csv", "excel"} else content.decode("utf-8")
            summary = ingest(session, payload.provider, provider_payload, external_member_id=payload.member_external_id, member_id=payload.member_id, mapping=payload.mapping, dry_run=payload.dry_run)
            session.commit()
        except (ValueError, UnicodeDecodeError) as error:
            session.rollback(); raise HTTPException(status_code=422, detail=str(error)) from error
        return {**summary.__dict__, "filename": payload.filename}

    @app.get("/ingestion/jobs", response_model=None)
    def list_ingestion_jobs(member_id: UUID | None = None, session: Session = Depends(get_session)) -> list[IngestionJob]:
        statement = select(IngestionJob).order_by(IngestionJob.started_at.desc())
        if member_id: statement = statement.where(IngestionJob.patient_id == member_id)
        return list(session.scalars(statement))

    @app.get("/ingestion/jobs/{job_id}", response_model=None)
    def ingestion_job_detail(job_id: UUID, session: Session = Depends(get_session)) -> dict[str, object]:
        job = session.get(IngestionJob, job_id)
        if job is None: raise HTTPException(status_code=404, detail="Ingestion job not found")
        records = list(session.scalars(select(RawIngestionRecord).where(RawIngestionRecord.job_id == job_id).order_by(RawIngestionRecord.created_at)))
        return {"job": job, "records": records}

    @app.get("/ingestion/review-queue", response_model=None)
    def ingestion_review_queue(session: Session = Depends(get_session)) -> list[RawIngestionRecord]:
        return list(session.scalars(select(RawIngestionRecord).where(RawIngestionRecord.status.in_(["SUSPECT", "INVALID", "UNMATCHED", "WAITING_REVIEW"])).order_by(RawIngestionRecord.created_at.desc())))

    @app.post("/ingestion/review/{record_id}/correct")
    def correct_ingestion_record(record_id: UUID, value: str, reason: str, actor: str = "health_manager", session: Session = Depends(get_session)) -> dict[str, str]:
        record = session.get(RawIngestionRecord, record_id)
        if record is None: raise HTTPException(status_code=404, detail="Ingestion record not found")
        try:
            observation = manually_correct_record(session, record, value, reason, actor); session.commit()
        except ValueError as error:
            session.rollback(); raise HTTPException(status_code=422, detail=str(error)) from error
        return {"observation_id": str(observation.id), "quality_flag": observation.quality_flag}

    @app.post("/integrations/mock-yuwell/webhook", status_code=status.HTTP_201_CREATED)
    def mock_yuwell_webhook(payload: dict[str, object], session: Session = Depends(get_session)) -> dict[str, object]:
        summary = ingest(session, "mock_yuwell", payload, external_member_id=str(payload.get("user_id") or ""), created_by="mock_webhook")
        session.commit(); return summary.__dict__

    @app.post("/integrations/mock-oura/sync", status_code=status.HTTP_201_CREATED)
    def mock_oura_sync(payload: dict[str, object], session: Session = Depends(get_session)) -> dict[str, object]:
        summary = ingest(session, "mock_oura", payload, external_member_id=str(payload.get("user_id") or ""), created_by="mock_sync")
        session.commit(); return summary.__dict__

    @app.post("/integrations/mock-cgm/sync", status_code=status.HTTP_201_CREATED)
    def mock_cgm_sync(payload: dict[str, object], session: Session = Depends(get_session)) -> dict[str, object]:
        summary = ingest(session, "mock_cgm", payload, external_member_id=str(payload.get("user_id") or ""), created_by="mock_sync")
        session.commit(); return summary.__dict__

    @app.post("/integrations/apple-health/sync", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_apple_bridge_token)])
    def apple_health_sync(payload: AppleHealthSyncRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        member = match_member(session, "apple_health", payload.external_member_id)
        summary = ingest(session, "apple_health", {"samples": payload.samples}, external_member_id=payload.external_member_id, created_by="apple_health_bridge")
        job = session.get(IngestionJob, summary.job_id)
        assert job is not None
        job.installation_id, job.external_sync_id = payload.device_installation_id, payload.sync_id
        deleted = mark_source_deleted(session, "apple_health", member.id, payload.deleted_sample_ids, job) if member else 0
        session.commit()
        return {**summary.__dict__, "sync_id": payload.sync_id, "deleted_excluded": deleted}

    @app.post("/integrations/apple-health/mock-sync", status_code=status.HTTP_201_CREATED)
    def mock_apple_health_sync(payload: AppleHealthSyncRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        member = match_member(session, "apple_health", payload.external_member_id)
        summary = ingest(session, "apple_health", {"samples": payload.samples}, external_member_id=payload.external_member_id, created_by="mock_apple_health")
        job = session.get(IngestionJob, summary.job_id); assert job is not None
        job.installation_id, job.external_sync_id = payload.device_installation_id, payload.sync_id
        deleted = mark_source_deleted(session, "apple_health", member.id, payload.deleted_sample_ids, job) if member else 0
        session.commit()
        return {**summary.__dict__, "sync_id": payload.sync_id, "deleted_excluded": deleted}

    @app.get("/integrations/apple-health/status/{external_member_id}")
    def apple_health_status(external_member_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
        member = match_member(session, "apple_health", external_member_id)
        if member is None: raise HTTPException(status_code=404, detail="Apple Health identity not found")
        job = session.scalar(select(IngestionJob).where(IngestionJob.patient_id == member.id, IngestionJob.source_system == "apple_health").order_by(IngestionJob.completed_at.desc()))
        observations = list(session.scalars(select(Observation).where(Observation.patient_id == member.id, Observation.source == "apple_health", Observation.excluded_from_analysis.is_(False))))
        real_bridge_sync = bool(job and job.status == "SUCCESS" and job.created_by == "apple_health_bridge")
        return {
            "external_member_id": external_member_id,
            "status": "SYNCED" if job and job.status == "SUCCESS" else "NO_DATA" if job is None else job.status,
            "last_sync": job.completed_at if job else None,
            "records_last_sync": job.records_received if job else 0,
            "data_types_seen": sorted({item.metric_code for item in observations}),
            "latest_observation_at": max((item.observed_at for item in observations), default=None),
            "current_error": None if not job or job.status != "FAILED" else "See ingestion job",
            # Source readiness, authenticated bridge receipt and real-device
            # verification are intentionally separate claims.
            "provider_readiness": {
                "backend": "BACKEND_READY",
                "ios_bridge": "IOS_SOURCE_READY",
                "real_device": "REAL_DEVICE_VERIFIED" if real_bridge_sync else "REAL_DEVICE_NOT_VERIFIED",
            },
        }

    @app.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
    def register_document(payload: DocumentCreate, session: Session = Depends(get_session)) -> Document:
        """Register report/PDF provenance; the file itself stays in approved storage."""
        member_or_404(session, payload.member_id)
        document = Document(patient_id=payload.member_id, document_type=payload.document_type, title=payload.title, storage_reference=payload.storage_reference, source=payload.source)
        session.add(document)
        session.commit()
        return document

    @app.post("/reports/upload", status_code=status.HTTP_201_CREATED, tags=["体检报告"], summary="上传并本地解析体检报告")
    def upload_report(payload: ReportUploadRequest, session: Session = Depends(get_session)) -> dict[str, object]:
        member_or_404(session, payload.member_id)
        try:
            content = base64.b64decode(payload.content_base64, validate=True)
            document, run, duplicate = ReportParsingService().upload_and_parse(session, payload.member_id, payload.filename, content, payload.actor)
            session.commit()
        except (ValueError, UnicodeDecodeError) as error:
            session.rollback()
            raise HTTPException(status_code=422, detail="报告文件无法解析或格式不正确") from error
        return {"document_id": str(document.id), "run_id": str(run.id), "status": run.status, "duplicate": duplicate, "candidate_count": run.candidate_count}

    @app.get("/reports/{document_id}/extraction", response_model=None, tags=["体检报告"], summary="查看体检报告解析概览")
    def report_extraction(document_id: UUID, session: Session = Depends(get_session)) -> dict[str, object]:
        run = session.scalar(select(ReportExtractionRun).where(ReportExtractionRun.document_id == document_id).order_by(ReportExtractionRun.created_at.desc()))
        if run is None: raise HTTPException(status_code=404, detail="未找到报告解析记录")
        return {"document_id": str(run.document_id), "status": run.status, "parser_version": run.parser_version, "page_count": run.page_count, "candidate_count": run.candidate_count, "detected_hospital": run.detected_hospital, "detected_report_date": run.detected_report_date}

    @app.post("/reports/{document_id}/reparse", response_model=None, tags=["体检报告"], summary="使用当前解析器重新解析原始报告")
    def reparse_report(document_id: UUID, actor: str = "health_manager", session: Session = Depends(get_session)) -> dict[str, object]:
        try:
            run = ReportParsingService().reparse_document(session, document_id, actor)
            session.commit()
        except ValueError as error:
            session.rollback()
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"document_id": str(document_id), "run_id": str(run.id), "status": run.status, "candidate_count": run.candidate_count}

    @app.post("/reports/{document_id}/parse", response_model=None, tags=["体检报告"], summary="明确开始一次新的体检报告解析")
    def parse_report(document_id: UUID, actor: str = "health_manager", session: Session = Depends(get_session)) -> dict[str, object]:
        """Every POST is a new parse command; GET endpoints only read history."""
        try:
            run = ReportParsingService().reparse_document(session, document_id, actor)
            session.commit()
        except ValueError as error:
            session.rollback()
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"document_id": str(document_id), "run_id": str(run.id), "status": run.status, "candidate_count": run.candidate_count}

    @app.get("/reports/{document_id}/candidates", response_model=None, tags=["体检报告"], summary="查看待人工确认的报告候选资料")
    def report_candidates(document_id: UUID, session: Session = Depends(get_session)) -> list[dict[str, object]]:
        service = ReportParsingService()
        latest_run = service.runs(session, document_id)
        run_id = latest_run[0].id if latest_run else None
        return [{"id": str(item.id), "candidate_type": item.candidate_type, "canonical_code": item.canonical_code, "raw_name": item.raw_name, "raw_value": item.raw_value, "normalized_value": item.normalized_value, "unit": item.unit, "confidence": item.confidence, "status": item.status, "source_page": item.source_page, "evidence_text": item.evidence_text} for item in service.candidates(session, document_id, run_id)]

    @app.post("/report-candidates/{candidate_id}/confirm", tags=["体检报告"], summary="人工确认候选资料并写入健康档案")
    def confirm_report_candidate(candidate_id: UUID, payload: ReportCandidateReview, session: Session = Depends(get_session)) -> dict[str, object]:
        candidate = session.get(ReportExtractionCandidate, candidate_id)
        if candidate is None: raise HTTPException(status_code=404, detail="未找到报告候选资料")
        try:
            observation = ReportParsingService().confirm_candidate(session, candidate, payload.actor); session.commit()
        except ValueError as error:
            session.rollback(); raise HTTPException(status_code=422, detail=str(error)) from error
        return {"status": candidate.status, "observation_id": str(observation.id) if observation else None}

    @app.post("/report-candidates/{candidate_id}/correct", tags=["体检报告"], summary="人工修正报告候选资料")
    def correct_report_candidate(candidate_id: UUID, payload: ReportCandidateReview, session: Session = Depends(get_session)) -> dict[str, str]:
        candidate = session.get(ReportExtractionCandidate, candidate_id)
        if candidate is None: raise HTTPException(status_code=404, detail="未找到报告候选资料")
        ReportParsingService().correct_candidate(session, candidate, payload.actor, canonical=payload.canonical_code, value=payload.normalized_value, unit=payload.unit, reason=payload.reason)
        session.commit(); return {"status": candidate.status}

    @app.post("/report-candidates/{candidate_id}/reject", tags=["体检报告"], summary="忽略报告候选资料")
    def reject_report_candidate(candidate_id: UUID, payload: ReportCandidateReview, session: Session = Depends(get_session)) -> dict[str, str]:
        candidate = session.get(ReportExtractionCandidate, candidate_id)
        if candidate is None: raise HTTPException(status_code=404, detail="未找到报告候选资料")
        ReportParsingService().reject_candidate(session, candidate, payload.actor, payload.reason); session.commit(); return {"status": candidate.status}

    @app.get("/documents", response_model=list[DocumentOut])
    def list_documents(member_id: UUID, session: Session = Depends(get_session)) -> list[Document]:
        member_or_404(session, member_id)
        return list(session.scalars(select(Document).where(Document.patient_id == member_id).order_by(Document.created_at.desc())))

    @app.post("/members/{member_id}/screen", response_model=AlertOut | None, deprecated=True)
    def screen(member_id: UUID, session: Session = Depends(get_session)) -> Alert | None:
        """Deprecated V0.1 compatibility write; current risk evaluation creates RiskEvent."""
        member_or_404(session, member_id)
        alert = screen_member(session, member_id)
        session.commit()
        return alert

    @app.get("/alerts", response_model=list[AlertOut], deprecated=True)
    def list_alerts(member_id: UUID | None = None, session: Session = Depends(get_session)) -> list[Alert]:
        """Read historical V0.1 Alert rows; new risk workflows do not write here."""
        statement = select(Alert).order_by(Alert.created_at.desc())
        if member_id is not None:
            statement = statement.where(Alert.patient_id == member_id)
        return list(session.scalars(statement))

    @app.post("/alerts/{alert_id}/manager-confirm", response_model=HealthProblemOut, deprecated=True)
    def manager_confirm(alert_id: UUID, payload: ManagerConfirmation, session: Session = Depends(get_session)) -> HealthProblem:
        alert = session.get(Alert, alert_id)
        if alert is None:
            raise HTTPException(status_code=404, detail="Alert not found")
        try:
            problem = confirm_alert_as_manager(session, alert, payload.manager_name, payload.review_note)
            session.commit()
        except ValueError as error:
            session.rollback()
            raise HTTPException(status_code=409, detail=str(error)) from error
        return problem

    def yellow_event_or_404(event_id: UUID, session: Session) -> RiskEvent:
        event = session.get(RiskEvent, event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="RiskEvent not found")
        return event

    @app.post("/risk-events/{event_id}/acknowledge")
    def acknowledge_yellow(event_id: UUID, payload: YellowAcknowledge, session: Session = Depends(get_session)) -> dict[str, object]:
        yellow_event_or_404(event_id, session)
        try:
            event = RiskOperationsService().acknowledge(session, event_id, payload.actor, payload.note); session.commit()
        except ValueError as error:
            session.rollback(); raise HTTPException(status_code=409, detail=str(error)) from error
        return {"id": str(event.id), "status": event.status}

    @app.post("/risk-events/{event_id}/continue-monitoring")
    def monitor_yellow(event_id: UUID, payload: YellowMonitoring, session: Session = Depends(get_session)) -> dict[str, str]:
        try:
            task = RiskOperationsService().continue_monitoring(session, event_id, payload.actor, payload.note, payload.due_at); session.commit()
        except ValueError as error:
            session.rollback(); raise HTTPException(status_code=409, detail=str(error)) from error
        return {"task_id": str(task.id), "status": "MONITORING"}

    @app.post("/risk-events/{event_id}/contact")
    def contact_yellow(event_id: UUID, payload: YellowContact, session: Session = Depends(get_session)) -> dict[str, str]:
        try:
            event = RiskOperationsService().record_contact(session, event_id, payload.actor, payload.method, payload.result, payload.note, payload.due_at); session.commit()
        except ValueError as error:
            session.rollback(); raise HTTPException(status_code=409, detail=str(error)) from error
        return {"id": str(event.id), "status": event.status}

    @app.post("/risk-events/{event_id}/mark-data-issue")
    def data_issue_yellow(event_id: UUID, payload: YellowAcknowledge, session: Session = Depends(get_session)) -> dict[str, str]:
        try:
            event = RiskOperationsService().mark_data_issue(session, event_id, payload.actor, payload.note); session.commit()
        except ValueError as error:
            session.rollback(); raise HTTPException(status_code=409, detail=str(error)) from error
        return {"id": str(event.id), "status": event.status}

    @app.post("/risk-events/{event_id}/adjust-management")
    def adjust_yellow(event_id: UUID, payload: YellowManagementAdjustment, session: Session = Depends(get_session)) -> dict[str, str]:
        try:
            task = RiskOperationsService().adjust_management(session, event_id, payload.actor, payload.adjustment, payload.note, payload.due_at); session.commit()
        except ValueError as error:
            session.rollback(); raise HTTPException(status_code=409, detail=str(error)) from error
        return {"task_id": str(task.id)}

    @app.post("/risk-events/{event_id}/escalate-doctor")
    def escalate_yellow(event_id: UUID, payload: YellowDoctorEscalation, session: Session = Depends(get_session)) -> dict[str, str]:
        try:
            review = RiskOperationsService().escalate_to_doctor(session, event_id, payload.actor, payload.question, payload.department); session.commit()
        except ValueError as error:
            session.rollback(); raise HTTPException(status_code=409, detail=str(error)) from error
        return {"doctor_review_id": str(review.id), "status": review.status}

    @app.post("/yellow-doctor-reviews/{review_id}/complete")
    def complete_yellow_doctor_review(review_id: UUID, payload: YellowDoctorCompletion, session: Session = Depends(get_session)) -> dict[str, str]:
        try:
            review, task = RiskOperationsService().complete_doctor_review(session, review_id, payload.doctor, payload.department, payload.opinion, payload.follow_up_instruction, payload.due_at); session.commit()
        except ValueError as error:
            session.rollback(); raise HTTPException(status_code=409, detail=str(error)) from error
        return {"doctor_review_id": str(review.id), "task_id": str(task.id), "status": review.status}

    @app.post("/risk-events/{event_id}/follow-up")
    def follow_up_yellow(event_id: UUID, payload: YellowFollowUp, session: Session = Depends(get_session)) -> dict[str, str]:
        try:
            followup = RiskOperationsService().record_follow_up(session, event_id, payload.actor, payload.outcome, payload.task_id); session.commit()
        except ValueError as error:
            session.rollback(); raise HTTPException(status_code=409, detail=str(error)) from error
        return {"followup_id": str(followup.id)}

    @app.post("/risk-events/{event_id}/close")
    def close_yellow(event_id: UUID, payload: YellowClose, session: Session = Depends(get_session)) -> dict[str, str]:
        try:
            event = RiskOperationsService().close(session, event_id, payload.actor, payload.reason); session.commit()
        except ValueError as error:
            session.rollback(); raise HTTPException(status_code=409, detail=str(error)) from error
        return {"id": str(event.id), "status": event.status}

    @app.get("/problems", response_model=list[HealthProblemOut])
    def list_problems(member_id: UUID | None = None, session: Session = Depends(get_session)) -> list[HealthProblem]:
        statement = select(HealthProblem).order_by(HealthProblem.opened_at.desc())
        if member_id is not None:
            statement = statement.where(HealthProblem.patient_id == member_id)
        return list(session.scalars(statement))

    @app.post("/doctor-reviews", response_model=DoctorReviewOut, status_code=status.HTTP_201_CREATED)
    def create_doctor_review(payload: DoctorReviewCreate, session: Session = Depends(get_session)):
        problem = session.get(HealthProblem, payload.problem_id)
        if problem is None:
            raise HTTPException(status_code=404, detail="Health problem not found")
        review, _, _ = record_doctor_review(session, problem, payload.doctor_name, payload.department, payload.opinion)
        session.commit()
        return review

    @app.get("/tasks", response_model=list[TaskOut])
    def list_tasks(member_id: UUID | None = None, session: Session = Depends(get_session)) -> list[Task]:
        statement = select(Task).order_by(Task.created_at.desc())
        if member_id is not None:
            statement = statement.where(Task.patient_id == member_id)
        return list(session.scalars(statement))

    @app.post("/tasks/{task_id}/complete", response_model=TaskOut)
    def complete_task(task_id: UUID, payload: TaskCompletion | None = None, session: Session = Depends(get_session)) -> Task:
        completion = payload or TaskCompletion()
        try:
            task = TaskTransitionService().complete(
                session, task_id, actor=completion.actor, outcome=completion.outcome,
            )
            session.commit()
        except ValueError as error:
            session.rollback()
            status_code = 404 if str(error) == "Task not found." else 409
            raise HTTPException(status_code=status_code, detail=str(error)) from error
        return task

    @app.post("/followups", response_model=FollowUpOut, status_code=status.HTTP_201_CREATED)
    def create_followup(payload: FollowUpCreate, session: Session = Depends(get_session)) -> FollowUp:
        problem = session.get(HealthProblem, payload.problem_id)
        if problem is None:
            raise HTTPException(status_code=404, detail="Health problem not found")
        task = session.get(Task, payload.task_id) if payload.task_id else None
        follow_up = complete_follow_up(session, problem, payload.reviewer, payload.outcome, task)
        session.commit()
        return follow_up

    @app.get("/dashboard/manager", response_model=DashboardOut)
    def manager_dashboard(session: Session = Depends(get_session)) -> dict[str, int]:
        now = datetime.now(timezone.utc)
        worklist = OperationalWorklistService()
        counts = worklist.dashboard_counts(worklist.list_items(session, now))
        count = lambda statement: int(session.scalar(statement) or 0)
        return {
            **counts,
            "open_problems": count(select(func.count(HealthProblem.id)).where(HealthProblem.status != "CLOSED")),
        }

    return app


app = create_app()
