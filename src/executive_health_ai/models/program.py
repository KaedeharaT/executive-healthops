"""Longitudinal health-management entities for Executive HealthOps V0.2.

These records describe a human-managed service journey.  They intentionally
record goals, execution and observable outcomes rather than diagnoses,
prescriptions, or autonomous medical decisions.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from executive_health_ai.models.base import Base, UTCDateTime, utc_now


class HealthJourney(Base):
    """A member's enrollment and assessment-to-annual-management journey."""

    __tablename__ = "health_journeys"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    current_stage: Mapped[str] = mapped_column(String(32), nullable=False, default="ASSESSMENT", index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default="MODERATE")
    assessment_summary: Mapped[str] = mapped_column(Text, nullable=False)
    main_focus: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_goals_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    baseline_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    doctor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)


class HealthProgram(Base):
    """A time-bounded 90-day, stabilization, or annual management program."""

    __tablename__ = "health_programs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    journey_id: Mapped[UUID] = mapped_column(ForeignKey("health_journeys.id"), nullable=False, index=True)
    program_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    main_goal: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_goals_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="PLANNED", index=True)
    current_phase: Mapped[str | None] = mapped_column(String(32), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    doctor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    start_date: Mapped[date] = mapped_column(nullable=False)
    end_date: Mapped[date | None] = mapped_column(nullable=True)
    next_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)


class ProgramPhase(Base):
    """A deliberately finite phase within a program, not a repeating reminder."""

    __tablename__ = "program_phases"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    program_id: Mapped[UUID] = mapped_column(ForeignKey("health_programs.id"), nullable=False, index=True)
    phase_code: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    sequence: Mapped[int] = mapped_column(nullable=False)
    start_date: Mapped[date] = mapped_column(nullable=False)
    end_date: Mapped[date] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PLANNED")
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)


class ExecutionBarrier(Base):
    """A human-confirmed reason an agreed activity did not happen."""

    __tablename__ = "execution_barriers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    program_id: Mapped[UUID] = mapped_column(ForeignKey("health_programs.id"), nullable=False, index=True)
    task_id: Mapped[UUID | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    confirmed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class WeeklyReview(Base):
    __tablename__ = "weekly_reviews"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    program_id: Mapped[UUID] = mapped_column(ForeignKey("health_programs.id"), nullable=False, index=True)
    week_number: Mapped[int] = mapped_column(nullable=False)
    task_completion: Mapped[str] = mapped_column(String(40), nullable=False)
    data_completeness: Mapped[str] = mapped_column(String(40), nullable=False)
    key_changes: Mapped[str] = mapped_column(Text, nullable=False)
    execution_barriers: Mapped[str | None] = mapped_column(Text, nullable=True)
    manager_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    adjustment: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_week_focus: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)


class OutcomeEvaluation(Base):
    __tablename__ = "outcome_evaluations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    program_id: Mapped[UUID] = mapped_column(ForeignKey("health_programs.id"), nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(128), nullable=False)
    baseline_value: Mapped[str] = mapped_column(String(128), nullable=False)
    current_value: Mapped[str] = mapped_column(String(128), nullable=False)
    target_value: Mapped[str | None] = mapped_column(String(128), nullable=True)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    evaluation_date: Mapped[date] = mapped_column(nullable=False)
    evaluator: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(String(40), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)


class AnnualHealthAccount(Base):
    """A year-long responsibility account, not a benefits package."""

    __tablename__ = "annual_health_accounts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    journey_id: Mapped[UUID] = mapped_column(ForeignKey("health_journeys.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(nullable=False)
    annual_goal: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    next_review_date: Mapped[date | None] = mapped_column(nullable=True)
    next_year_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now)
