"""Database models exposed by the V0.1 demo."""

from executive_health_ai.models.ai_insight import AIInsight
from executive_health_ai.models.base import Base
from executive_health_ai.models.care import CarePlan, CareTask
from executive_health_ai.models.gateway import ExternalIdentity, IngestionJob, RawIngestionRecord
from executive_health_ai.models.clinical import ClinicalRecommendation, Encounter
from executive_health_ai.models.device import Device
from executive_health_ai.models.health_event import HealthEvent
from executive_health_ai.models.knowledge import KnowledgeChunk, KnowledgeDocument, KnowledgeReviewAudit, KnowledgeSourceRegistry, KnowledgeUseRecord
from executive_health_ai.models.medication import MedicationEvent, MedicationPlan
from executive_health_ai.models.observation import Observation
from executive_health_ai.models.operations import (
    AgentRun, Alert, AuditLog, Consent, DoctorReview, Document, FollowUp,
    HealthProblem, ManagementPlan, Organization, ServiceEvent, Task,
)
from executive_health_ai.models.patient import Member, Patient
from executive_health_ai.models.program import (
    AnnualHealthAccount, ExecutionBarrier, HealthJourney, HealthProgram,
    OutcomeEvaluation, ProgramPhase, WeeklyReview,
)
from executive_health_ai.models.raw_data import RawData
from executive_health_ai.models.risk import EmergencyContact, RiskEvent, RiskRule
from executive_health_ai.models.report_parsing import ReportExtractionCandidate, ReportExtractionRun
from executive_health_ai.models.sleep_session import SleepSession
from executive_health_ai.models.training import TrainingSession
from executive_health_ai.models.ai_governance import FeedbackDatasetVersion, FeedbackRecord, ModelVersionRegistry, RiskRuleReviewCandidate
from executive_health_ai.models.longitudinal import (
    ExternalReferral, HealthAssessment, ManagementRule, ManagementSignal,
    MemberDeviceAssignment,
)
from executive_health_ai.models.member_service import ServiceCatalogItem, ServicePlan, ServicePlanItem, MemberEntitlement, ServiceRequest, MemberPlanChoice

__all__ = [
    "AIInsight", "Base", "CarePlan", "CareTask", "ClinicalRecommendation", "Device",
    "Encounter", "HealthEvent", "MedicationEvent", "MedicationPlan", "Observation",
    "Patient", "Member", "RawData", "SleepSession", "Organization", "Consent", "Document", "KnowledgeDocument", "KnowledgeChunk", "KnowledgeReviewAudit", "KnowledgeSourceRegistry", "KnowledgeUseRecord",
    "HealthProblem", "Alert", "ManagementPlan", "Task", "DoctorReview", "FollowUp",
    "ServiceEvent", "AgentRun", "AuditLog",
    "HealthJourney", "HealthProgram", "ProgramPhase", "ExecutionBarrier",
    "WeeklyReview", "OutcomeEvaluation", "AnnualHealthAccount",
    "IngestionJob", "RawIngestionRecord", "ExternalIdentity",
    "RiskRule", "RiskEvent", "EmergencyContact",
    "ReportExtractionRun", "ReportExtractionCandidate",
    "HealthAssessment", "ManagementRule", "ManagementSignal", "MemberDeviceAssignment", "ExternalReferral",
    "ServiceCatalogItem", "ServicePlan", "ServicePlanItem", "MemberEntitlement", "ServiceRequest", "MemberPlanChoice", "TrainingSession",
    "FeedbackRecord", "FeedbackDatasetVersion", "ModelVersionRegistry", "RiskRuleReviewCandidate",
]
