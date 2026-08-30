"""Synthetic coverage for daily wellness data and deterministic routing."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.blood_pressure import TOKYO_TIMEZONE
from executive_health_ai.models import Base, ManagementRule, ManagementSignal, Observation, Patient, RiskEvent, RiskRule, SleepSession
from executive_health_ai.services.health_data_summary import HealthDataSummaryService
from executive_health_ai.services.longitudinal import HealthDataCategoryRegistry, ManagementRoutingService
from executive_health_ai.services.risk_triage import RiskEvaluationService


def _factory():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def _member(session: Session) -> Patient:
    member = Patient(external_id="daily-signals-synthetic", display_name="合成日常信号成员", timezone="Asia/Tokyo")
    session.add(member); session.flush()
    return member


def _observation(session: Session, member: Patient, metric: str, value: str, at: datetime, *, quality: str = "valid") -> Observation:
    units = {"steps": "count", "active_calories": "kcal", "exercise_minutes": "minutes", "sleep_duration": "minutes", "glucose": "mg/dL"}
    item = Observation(patient_id=member.id, observed_at=at, metric_code=metric, value_numeric=Decimal(value), unit=units[metric], source="synthetic_demo", quality_flag=quality)
    session.add(item); session.flush()
    return item


def _rule(code: str, metric: str, *, condition: str = "THRESHOLD", threshold: dict | None = None, window: dict | None = None, route: str = "HEALTH_MANAGER") -> ManagementRule:
    return ManagementRule(
        name=f"合成 {code}", code=code, canonical_code=metric, condition_type=condition,
        threshold_config=threshold or {"operator": "<", "value": "1000", "severity": "ACTION_NEEDED"},
        window_config=window or {}, recommended_route=route, review_status="APPROVED", is_active=True,
        source_reference="SYNTHETIC TEST ONLY — not a clinical threshold",
    )


def test_sleep_stage_intervals_preserve_source_order_and_deep_ratio() -> None:
    with _factory()() as session:
        member = _member(session)
        start = datetime(2026, 8, 20, 23, tzinfo=TOKYO_TIMEZONE)
        sleep = SleepSession(patient_id=member.id, sleep_start=start, sleep_end=start + timedelta(hours=8), total_sleep_minutes=420, deep_sleep_minutes=84, rem_sleep_minutes=92, awake_minutes=24, source="synthetic_demo", stage_segments_json=[
            {"stage": "LIGHT", "start_at": start.isoformat(), "end_at": (start + timedelta(minutes=90)).isoformat()},
            {"stage": "DEEP", "start_at": (start + timedelta(minutes=90)).isoformat(), "end_at": (start + timedelta(minutes=174)).isoformat()},
            {"stage": "REM", "start_at": (start + timedelta(minutes=174)).isoformat(), "end_at": (start + timedelta(minutes=266)).isoformat()},
            {"stage": "AWAKE", "start_at": (start + timedelta(minutes=266)).isoformat(), "end_at": (start + timedelta(minutes=290)).isoformat()},
        ])
        session.add(sleep); session.flush()
        service = HealthDataSummaryService()
        intervals = service.sleep_stage_intervals(sleep)
        assert [item.stage for item in intervals] == ["LIGHT", "DEEP", "REM", "AWAKE"]
        assert intervals[1].duration_minutes == 84
        summary = service.sleep_trend([sleep])
        assert summary.average_deep_minutes == 84 and summary.average_deep_ratio == 20


def test_missing_sleep_stage_data_never_creates_fake_stages() -> None:
    with _factory()() as session:
        member = _member(session)
        start = datetime(2026, 8, 20, 23, tzinfo=TOKYO_TIMEZONE)
        sleep = SleepSession(patient_id=member.id, sleep_start=start, sleep_end=start + timedelta(hours=7), total_sleep_minutes=420, source="synthetic_demo")
        session.add(sleep); session.flush()
        assert HealthDataSummaryService().sleep_stage_intervals(sleep) == []


def test_sleep_trends_cover_7_30_and_90_day_windows() -> None:
    with _factory()() as session:
        member = _member(session); now = datetime.now(TOKYO_TIMEZONE)
        sessions = []
        for days_ago in (2, 12, 50):
            end = now - timedelta(days=days_ago)
            sessions.append(SleepSession(patient_id=member.id, sleep_start=end - timedelta(hours=7), sleep_end=end, total_sleep_minutes=420 - days_ago, deep_sleep_minutes=80, rem_sleep_minutes=90, awake_minutes=20, source="synthetic_demo"))
        session.add_all(sessions); session.flush()
        service = HealthDataSummaryService()
        assert len(service.get_sleep_sessions(session, member.id, days=7)) == 1
        assert len(service.get_sleep_sessions(session, member.id, days=30)) == 2
        assert len(service.get_sleep_sessions(session, member.id, days=90)) == 3


def test_steps_activity_calories_and_exercise_remain_separate_device_measurements() -> None:
    with _factory()() as session:
        member = _member(session); now = datetime.now(TOKYO_TIMEZONE)
        for metric, value in (("steps", "8432"), ("active_calories", "436"), ("exercise_minutes", "47")):
            _observation(session, member, metric, value, now)
        summary = HealthDataSummaryService().get_lifestyle_summary(session, member.id)
        assert str(summary.latest["steps"].value_numeric) == "8432.000"
        assert str(summary.latest["active_calories"].value_numeric) == "436.000"
        assert str(summary.latest["exercise_minutes"].value_numeric) == "47.000"


def test_management_rules_support_window_repeats_trends_and_deduplicated_evidence() -> None:
    with _factory()() as session:
        member = _member(session); now = datetime.now(TOKYO_TIMEZONE)
        rule = _rule("SYNTHETIC_ACTIVITY_WINDOW", "steps", threshold={"operator": "<", "value": "1000", "severity": "ACTION_NEEDED"}, window={"lookback_days": 7, "minimum_samples": 3, "required_matches": 3})
        session.add(rule); session.flush()
        service = ManagementRoutingService()
        observations = [_observation(session, member, "steps", "500", now - timedelta(days=offset)) for offset in (2, 1, 0)]
        signal = service.evaluate_observation(session, observations[-1].id)
        assert signal and signal.recommended_route == "HEALTH_MANAGER" and signal.severity == "ACTION_NEEDED"
        _observation(session, member, "steps", "400", now + timedelta(minutes=1))
        updated = service.evaluate_observation(session, session.scalar(select(Observation).order_by(Observation.observed_at.desc())).id)
        assert updated and updated.id == signal.id and len(updated.evidence_json["history"]) == 2
        assert session.scalar(select(RiskEvent)) is None


def test_management_rule_excludes_invalid_and_suspect_and_never_auto_routes_doctors() -> None:
    with _factory()() as session:
        member = _member(session); now = datetime.now(TOKYO_TIMEZONE)
        session.add_all([
            _rule("SYNTHETIC_INVALID_EXCLUSION", "sleep_duration"),
            _rule("SYNTHETIC_NO_DOCTOR_ROUTE", "steps", route="INTERNAL_DOCTOR"),
        ]); session.flush()
        invalid = _observation(session, member, "sleep_duration", "1", now, quality="invalid")
        steps = _observation(session, member, "steps", "1", now)
        service = ManagementRoutingService()
        assert service.evaluate_observation(session, invalid.id) is None
        assert service.evaluate_observation(session, steps.id) is None
        assert session.scalar(select(ManagementSignal)) is None


def test_non_synthetic_wellness_rule_cannot_create_a_medical_risk_event() -> None:
    with _factory()() as session:
        member = _member(session); now = datetime.now(TOKYO_TIMEZONE)
        session.add(RiskRule(
            name="nonclinical wellness rule", code="WELLNESS_STEPS_NOT_MEDICAL", applicable_device_class="ANY",
            canonical_code="steps", risk_level="YELLOW", condition_type="THRESHOLD",
            threshold_config={"metric": "steps", "operator": "<", "value": "1000", "unit": "count"},
            window_config={}, requires_repeated_measurement=False, requires_symptom_confirmation=False,
            action_type="MANAGEMENT", source_reference="governed wellness management policy", review_status="APPROVED", is_active=True,
        ))
        observation = _observation(session, member, "steps", "1", now)
        session.flush()
        result = RiskEvaluationService().evaluate_observation(session, observation.id)
        assert result.evaluated_rule_count == 0 and session.scalar(select(RiskEvent)) is None


def test_synthetic_glucose_medical_monitoring_still_uses_existing_risk_engine() -> None:
    with _factory()() as session:
        member = _member(session); now = datetime.now(TOKYO_TIMEZONE)
        rule = RiskRule(
            name="synthetic glucose pipeline", code="SYNTHETIC_GLUCOSE_PIPELINE", applicable_device_class="ANY",
            canonical_code="glucose", risk_level="YELLOW", condition_type="SYNTHETIC_TEST_THRESHOLD",
            threshold_config={"metric": "glucose", "operator": ">=", "value": "999", "unit": "mg/dL"},
            window_config={}, requires_repeated_measurement=False, requires_symptom_confirmation=False,
            action_type="SYNTHETIC_TEST_ONLY", source_reference="SYNTHETIC TEST ONLY", review_status="APPROVED", is_active=True,
        )
        session.add(rule); session.flush()
        observation = _observation(session, member, "glucose", "999", now)
        result = RiskEvaluationService().evaluate_observation(session, observation.id)
        assert result.created_event_count == 1 and session.scalar(select(RiskEvent)) is not None


def test_percentage_decline_and_taxonomy_are_deterministic_and_not_llm_based() -> None:
    with _factory()() as session:
        member = _member(session); now = datetime.now(TOKYO_TIMEZONE)
        rule = _rule("SYNTHETIC_SLEEP_DECLINE", "sleep_duration", condition="PERCENTAGE_CHANGE", threshold={"operator": "<=", "value": "-20"}, window={"lookback_days": 14, "minimum_samples": 2, "required_matches": 1})
        session.add(rule); session.flush()
        service = ManagementRoutingService()
        first = _observation(session, member, "sleep_duration", "600", now - timedelta(days=5))
        last = _observation(session, member, "sleep_duration", "400", now)
        assert service.evaluate_observation(session, first.id) is None
        assert service.evaluate_observation(session, last.id) is not None
        assert HealthDataCategoryRegistry.classify_metric("deep_sleep_duration") == ("SLEEP", "睡眠")
        assert "LLM" not in ManagementRoutingService.__doc__
