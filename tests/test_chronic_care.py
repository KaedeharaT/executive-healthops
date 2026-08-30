"""Synthetic regression coverage for the V0.2 chronic-care operating loop."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from executive_health_ai.blood_pressure import TOKYO_TIMEZONE
from executive_health_ai.models import (
    AuditLog, Base, ExecutionBarrier, HealthProblem, ManagementPlan, OutcomeEvaluation,
    Patient, ProgramPhase, ServiceEvent, WeeklyReview,
)
from executive_health_ai.services.chronic_care import (
    adjust_management_plan, create_assessment, create_program, create_program_task,
    escalate_to_medical_care, progress_program_phase, record_execution_barrier,
    record_outcome_evaluation, record_weekly_review, transition_to_stabilization,
)
from executive_health_ai.api import create_app


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)()


def test_assessment_enrolls_one_main_goal_program_with_priority_problems_and_phases() -> None:
    with _session() as session:
        member = Patient(external_id="synthetic-v02-journey", timezone="Asia/Tokyo")
        session.add(member)
        session.flush()
        problems = [
            HealthProblem(patient_id=member.id, title="Weight and metabolic risk", description="Synthetic operational priority.", source="synthetic"),
            HealthProblem(patient_id=member.id, title="Sleep insufficiency", description="Synthetic operational priority.", source="synthetic"),
        ]
        session.add_all(problems)
        session.flush()
        journey = create_assessment(session, member.id, "Synthetic assessment", "Improve metabolic state", "HIGH", ["Improve sleep"], {"weight": "86 kg"}, "synthetic manager")
        program = create_program(session, journey, "NINETY_DAY", "Synthetic 90-Day Program", "Improve metabolic state", ["Improve sleep"], date(2026, 8, 1), "synthetic manager", priority_problems=problems)
        session.commit()

        assert journey.current_stage == "90_DAY_PROGRAM"
        assert program.main_goal == "Improve metabolic state"
        assert [p.priority_rank for p in problems] == [1, 2]
        phases = list(session.scalars(select(ProgramPhase).where(ProgramPhase.program_id == program.id).order_by(ProgramPhase.sequence)))
        assert [phase.phase_code for phase in phases] == ["STARTUP", "EXECUTION", "STABILIZATION", "REASSESSMENT"]
        assert phases[0].status == "ACTIVE"
        progress_program_phase(session, program, "EXECUTION", "synthetic manager")
        assert phases[0].status == "COMPLETED"
        assert session.get(ProgramPhase, phases[1].id).status == "ACTIVE"


def test_barrier_adjustment_weekly_review_and_outcome_are_audited() -> None:
    with _session() as session:
        member = Patient(external_id="synthetic-v02-execution", timezone="Asia/Tokyo")
        session.add(member)
        session.flush()
        problem = HealthProblem(patient_id=member.id, title="Synthetic priority", description="Synthetic.", source="synthetic")
        session.add(problem)
        session.flush()
        journey = create_assessment(session, member.id, "Synthetic assessment", "Sustainable movement", "MODERATE", [], {}, "manager")
        program = create_program(session, journey, "NINETY_DAY", "Synthetic 90-Day", "Sustainable movement", [], date(2026, 8, 1), "manager", priority_problems=[problem])
        task = create_program_task(session, program, "Walk during travel", "Synthetic non-clinical task.", datetime(2026, 8, 9, 18, tzinfo=TOKYO_TIMEZONE), "member", "manager", problem=problem)
        barrier = record_execution_barrier(session, program, "TRAVEL", "Seven days of synthetic travel disrupted activity.", "manager", task, "Use a short walking task during travel.")
        plan = ManagementPlan(patient_id=member.id, program_id=program.id, health_problem_id=problem.id, title="Synthetic plan", content="Original agreed activity.", source="synthetic", start_date=date(2026, 8, 1))
        session.add(plan)
        session.flush()
        adjust_management_plan(session, plan, "manager", "Travel barrier", "Adjusted non-clinical walking activity.")
        review = record_weekly_review(session, program, 3, "2 / 4", "sufficient", "Travel interruption", "Resume a feasible activity", "manager", "TRAVEL", adjustment="Reduced task frequency")
        outcome = record_outcome_evaluation(session, program, "Weight", "86", "81", "kg", "DOWN", "manager", "Synthetic baseline/current comparison.", "IMPROVED")
        session.commit()

        assert session.get(ExecutionBarrier, barrier.id).reason == "TRAVEL"
        assert plan.status == "ADJUSTED" and plan.adjusted_by == "manager"
        assert session.get(WeeklyReview, review.id).week_number == 3
        assert session.get(OutcomeEvaluation, outcome.id).result == "IMPROVED"
        actions = set(session.scalars(select(AuditLog.action).where(AuditLog.patient_id == member.id)))
        assert {"recorded_execution_barrier", "adjusted_management_plan", "recorded_weekly_review", "recorded_outcome_evaluation"} <= actions


def test_medical_escalation_and_stabilization_are_explicit_program_decisions() -> None:
    with _session() as session:
        member = Patient(external_id="synthetic-v02-transition", timezone="Asia/Tokyo")
        session.add(member)
        session.flush()
        journey = create_assessment(session, member.id, "Synthetic assessment", "Sustainable change", "HIGH", [], {}, "manager")
        referral_program = create_program(session, journey, "NINETY_DAY", "Referral candidate", "Sustainable change", [], date(2026, 8, 1), "manager")
        escalate_to_medical_care(session, referral_program, "manager", "Synthetic high-risk signal needs a doctor review.")
        completed_program = create_program(session, journey, "NINETY_DAY", "Completed candidate", "Sustainable change", [], date(2026, 5, 1), "manager", end_date=date(2026, 7, 29))
        stabilization = transition_to_stabilization(session, completed_program, "manager")
        session.commit()

        assert referral_program.status == "ESCALATED_TO_MEDICAL_CARE"
        assert referral_program.next_decision == "MEDICAL_REFERRAL"
        assert stabilization.program_type == "STABILIZATION"
        assert journey.current_stage == "STABILIZATION"
        assert session.scalar(select(ServiceEvent).where(ServiceEvent.patient_id == member.id, ServiceEvent.event_type == "medical_referral")) is not None


def test_program_api_supports_assessment_program_review_barrier_outcome_and_referral() -> None:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with factory() as session:
        member = Patient(external_id="synthetic-v02-api", timezone="Asia/Tokyo")
        session.add(member)
        session.commit()
        member_id = member.id
    client = TestClient(create_app(factory))
    assessment = client.post("/assessments", json={"member_id": str(member_id), "assessment_summary": "Synthetic assessment", "main_focus": "Improve sleep", "risk_level": "MODERATE", "owner": "manager", "baseline": {}})
    assert assessment.status_code == 201
    program = client.post("/programs", json={"journey_id": assessment.json()["id"], "program_type": "NINETY_DAY", "title": "Synthetic Program", "main_goal": "Improve sleep", "supporting_goals": [], "start_date": "2026-08-01", "owner": "manager"})
    assert program.status_code == 201
    program_id = program.json()["id"]
    assert len(client.get(f"/programs/{program_id}/phases").json()) == 4
    assert client.post(f"/programs/{program_id}/reviews", json={"week_number": 1, "task_completion": "1 / 1", "data_completeness": "sufficient", "key_changes": "Synthetic", "next_week_focus": "Continue", "reviewed_by": "manager"}).status_code == 201
    assert client.post(f"/programs/{program_id}/execution-barriers", json={"reason": "TRAVEL", "description": "Synthetic travel", "confirmed_by": "manager"}).status_code == 201
    assert client.post(f"/programs/{program_id}/outcomes", json={"metric": "Sleep", "baseline_value": "5.8", "current_value": "6.6", "unit": "h", "direction": "UP", "evaluator": "manager", "evidence": "Synthetic", "result": "IMPROVED"}).status_code == 201
    assert client.post(f"/programs/{program_id}/medical-referral", json={"actor": "manager", "reason": "Synthetic physician review required"}).json()["status"] == "ESCALATED_TO_MEDICAL_CARE"
