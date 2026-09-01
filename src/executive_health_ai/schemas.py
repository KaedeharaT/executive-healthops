"""Pydantic input/output contracts for the V0.1 API."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MemberOut(APIModel):
    id: UUID
    external_id: str | None
    display_name: str | None
    birth_date: date | None
    sex: str | None
    timezone: str
    organization_id: UUID | None


class ObservationCreate(APIModel):
    member_id: UUID
    metric_code: str = Field(min_length=1, max_length=64)
    value: Decimal
    unit: str = Field(min_length=1, max_length=32)
    observed_at: datetime
    source: str = Field(default="manual_entry", min_length=1, max_length=128)
    source_device_id: UUID | None = None
    quality_flag: str = "valid"

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        return value


class DocumentCreate(APIModel):
    member_id: UUID
    document_type: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    storage_reference: str = Field(min_length=1, max_length=512)
    source: str = Field(default="manual_document_registration", min_length=1, max_length=128)


class DocumentOut(APIModel):
    id: UUID
    patient_id: UUID
    document_type: str
    title: str
    storage_reference: str
    source: str
    status: str
    created_at: datetime


class ReportUploadRequest(APIModel):
    member_id: UUID
    filename: str = Field(min_length=1, max_length=200)
    content_base64: str = Field(min_length=1)
    actor: str = Field(default="health_manager", min_length=1, max_length=128)


class ReportCandidateReview(APIModel):
    actor: str = Field(default="health_manager", min_length=1, max_length=128)
    reason: str = Field(default="已人工核对", min_length=1, max_length=1000)
    canonical_code: str | None = Field(default=None, max_length=100)
    normalized_value: str | None = Field(default=None, max_length=256)
    unit: str | None = Field(default=None, max_length=64)


class AlertOut(APIModel):
    id: UUID
    patient_id: UUID
    health_problem_id: UUID | None
    alert_type: str
    title: str
    finding: str
    status: str
    severity: str
    responsible_role: str
    owner: str | None
    due_at: datetime | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    source: str
    created_at: datetime


class ManagerConfirmation(APIModel):
    manager_name: str = Field(min_length=1, max_length=128)
    review_note: str = Field(min_length=1, max_length=2000)


class HealthProblemOut(APIModel):
    id: UUID
    patient_id: UUID
    title: str
    description: str
    status: str
    severity: str
    responsible_role: str
    owner: str | None
    source: str
    opened_at: datetime
    closed_at: datetime | None


class DoctorReviewCreate(APIModel):
    problem_id: UUID
    doctor_name: str = Field(min_length=1, max_length=128)
    department: str = Field(min_length=1, max_length=128)
    opinion: str = Field(min_length=1, max_length=4000)


class DoctorReviewOut(APIModel):
    id: UUID
    patient_id: UUID
    health_problem_id: UUID
    alert_id: UUID | None
    doctor_name: str
    department: str
    doctor_brief: str
    question_for_doctor: str
    opinion: str
    status: str
    reviewed_at: datetime


class TaskOut(APIModel):
    id: UUID
    patient_id: UUID
    health_problem_id: UUID | None
    management_plan_id: UUID | None
    alert_id: UUID | None
    title: str
    instruction: str
    status: str
    priority: str
    assignee: str | None
    responsible_role: str
    due_at: datetime | None
    completed_at: datetime | None
    source: str


class TaskCompletion(APIModel):
    actor: str = Field(default="health_manager", min_length=1, max_length=128)
    outcome: str = Field(default="任务已完成并记录。", min_length=1, max_length=4000)


class FollowUpCreate(APIModel):
    problem_id: UUID
    reviewer: str = Field(min_length=1, max_length=128)
    outcome: str = Field(min_length=1, max_length=4000)
    task_id: UUID | None = None


class FollowUpOut(APIModel):
    id: UUID
    patient_id: UUID
    health_problem_id: UUID
    task_id: UUID | None
    status: str
    completed_at: datetime | None
    outcome: str | None
    reviewed_by: str | None


class YellowAcknowledge(APIModel):
    actor: str = Field(min_length=1, max_length=128)
    note: str = Field(min_length=1, max_length=2000)


class YellowMonitoring(YellowAcknowledge):
    due_at: datetime


class YellowContact(YellowAcknowledge):
    method: str
    result: str
    due_at: datetime | None = None


class YellowManagementAdjustment(YellowAcknowledge):
    adjustment: str = Field(min_length=1, max_length=4000)
    due_at: datetime | None = None


class YellowDoctorEscalation(APIModel):
    actor: str = Field(min_length=1, max_length=128)
    question: str = Field(min_length=1, max_length=4000)
    department: str = Field(default="全科/健康管理", min_length=1, max_length=128)


class YellowDoctorCompletion(APIModel):
    doctor: str = Field(min_length=1, max_length=128)
    department: str = Field(min_length=1, max_length=128)
    opinion: str = Field(min_length=1, max_length=4000)
    follow_up_instruction: str = Field(min_length=1, max_length=4000)
    due_at: datetime | None = None


class YellowFollowUp(APIModel):
    actor: str = Field(min_length=1, max_length=128)
    outcome: str = Field(min_length=1, max_length=4000)
    task_id: UUID | None = None


class YellowClose(APIModel):
    actor: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=4000)


class DashboardOut(APIModel):
    high_priority_alerts: int
    waiting_manager_review: int
    waiting_doctor_review: int
    overdue_tasks: int
    open_problems: int
    upcoming_followups: int


class TimelineEventOut(APIModel):
    occurred_at: datetime
    event_type: str
    event_type_label: str
    title: str
    summary: str
    severity: str
    source: str
    expandable_details: dict[str, object]
    related_entity: str | None
    group_key: str
    related_entity_ids: tuple[str, ...]
    actions: tuple[str, ...]
    risk_level: str | None
    risk_label: str | None
    risk_indicator: str
    lane: str


class AssessmentCreate(APIModel):
    member_id: UUID
    assessment_summary: str = Field(min_length=1, max_length=4000)
    main_focus: str = Field(min_length=1, max_length=1000)
    risk_level: str
    supporting_goals: list[str] = Field(default_factory=list)
    baseline: dict[str, object] = Field(default_factory=dict)
    owner: str = Field(min_length=1, max_length=128)
    doctor: str | None = Field(default=None, max_length=128)


class ProgramCreate(APIModel):
    journey_id: UUID
    program_type: str
    title: str = Field(min_length=1, max_length=200)
    main_goal: str = Field(min_length=1, max_length=4000)
    supporting_goals: list[str] = Field(default_factory=list)
    start_date: date
    owner: str = Field(min_length=1, max_length=128)
    doctor: str | None = Field(default=None, max_length=128)
    priority_problem_ids: list[UUID] = Field(default_factory=list)
    end_date: date | None = None


class ProgramOut(APIModel):
    id: UUID
    patient_id: UUID
    journey_id: UUID
    program_type: str
    title: str
    main_goal: str
    supporting_goals_json: list[str]
    status: str
    current_phase: str | None
    owner: str | None
    doctor: str | None
    start_date: date
    end_date: date | None
    next_decision: str | None


class WeeklyReviewCreate(APIModel):
    week_number: int = Field(ge=1)
    task_completion: str = Field(min_length=1, max_length=40)
    data_completeness: str = Field(min_length=1, max_length=40)
    key_changes: str = Field(min_length=1, max_length=4000)
    next_week_focus: str = Field(min_length=1, max_length=4000)
    reviewed_by: str = Field(min_length=1, max_length=128)
    execution_barriers: str | None = None
    manager_notes: str | None = None
    adjustment: str | None = None


class BarrierCreate(APIModel):
    reason: str
    description: str = Field(min_length=1, max_length=4000)
    confirmed_by: str = Field(min_length=1, max_length=128)
    task_id: UUID | None = None
    resolution: str | None = None


class OutcomeCreate(APIModel):
    metric: str = Field(min_length=1, max_length=128)
    baseline_value: str = Field(min_length=1, max_length=128)
    current_value: str = Field(min_length=1, max_length=128)
    unit: str = Field(min_length=1, max_length=32)
    direction: str = Field(min_length=1, max_length=32)
    evaluator: str = Field(min_length=1, max_length=128)
    evidence: str = Field(min_length=1, max_length=4000)
    result: str
    target_value: str | None = None
    notes: str | None = None
    evaluation_date: date | None = None


class MedicalReferralCreate(APIModel):
    actor: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=4000)


class IngestionRequest(APIModel):
    provider: str = Field(min_length=1, max_length=128)
    member_external_id: str | None = Field(default=None, max_length=256)
    member_id: UUID | None = None
    records: list[dict[str, object]] = Field(default_factory=list)
    mapping: dict[str, str] | None = None
    dry_run: bool = False


class FileIngestionRequest(APIModel):
    provider: str
    filename: str = Field(min_length=1, max_length=256)
    content_base64: str = Field(min_length=1)
    member_external_id: str | None = None
    member_id: UUID | None = None
    mapping: dict[str, str] | None = None
    dry_run: bool = False


class AppleHealthSyncRequest(APIModel):
    external_member_id: str = Field(min_length=1, max_length=256)
    device_installation_id: str = Field(min_length=1, max_length=128)
    sync_id: str = Field(min_length=1, max_length=128)
    sync_started_at: datetime
    samples: list[dict[str, object]] = Field(default_factory=list)
    deleted_sample_ids: list[str] = Field(default_factory=list)
