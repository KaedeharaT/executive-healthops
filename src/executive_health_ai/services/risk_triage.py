"""Deterministic, human-governed risk operations.

The observation path deliberately executes only approved, active rules.  It
does not contain clinical thresholds, call an LLM, diagnose, prescribe, or
contact emergency services.  Clinical rule content remains a separately
governed responsibility; this module only executes its explicit configuration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.integrations.codes import canonical_code
from executive_health_ai.integrations.normalization import normalize_unit
from executive_health_ai.models import AuditLog, HealthProgram, Observation, Patient, RiskEvent, RiskRule


logger = logging.getLogger(__name__)

DEVICE_CLASS = {
    "apple_health": "WELLNESS",
    "mock_oura": "WELLNESS",
    "mock_yuwell": "MEDICAL_MONITOR",
    "mock_cgm": "MEDICAL_MONITOR",
    "confirmed_health_check_report": "REPORT",
}
USABLE_QUALITY_FLAGS = {"valid", "manually_corrected"}
ACTIVE_EVENT_STATUSES = {
    "NEW", "ACKNOWLEDGED", "IN_REVIEW", "MONITORING",
    "ESCALATED_TO_DOCTOR", "WAITING_MEMBER", "FOLLOW_UP", "ESCALATED",
}
EXECUTABLE_CONDITION_TYPES = {"THRESHOLD", "SYNTHETIC_TEST_THRESHOLD"}
# Wellness metrics are routed by ManagementRule.  The exception preserves the
# explicitly labelled synthetic rules that exercise the generic engine in the
# test/demo suite; they never represent clinical configuration.
WELLNESS_MANAGEMENT_METRICS = {
    "steps", "exercise_minutes", "active_calories", "sleep_duration",
    "deep_sleep_duration", "light_sleep_duration", "rem_sleep_duration", "awake_duration",
}


@dataclass(frozen=True)
class RiskEvaluationResult:
    """Compatibility result for the retained synthetic demo entrypoint."""

    risk_level: str
    rule: RiskRule | None
    summary: str
    requires_review: bool
    emergency: bool


@dataclass(frozen=True)
class ObservationRiskEvaluation:
    """Outcome of one idempotent observation-driven evaluation command."""

    observation_id: UUID
    eligible: bool
    skipped_reason: str | None
    evaluated_rule_count: int
    matched_rule_count: int
    created_event_count: int
    updated_event_count: int
    events: tuple[RiskEvent, ...]

    def summary(self) -> dict[str, object]:
        return {
            "eligible": self.eligible,
            "skipped_reason": self.skipped_reason,
            "evaluated_rules": self.evaluated_rule_count,
            "matched_rules": self.matched_rule_count,
            "created_events": self.created_event_count,
            "updated_events": self.updated_event_count,
            "risk_event_ids": [str(event.id) for event in self.events],
        }


class RiskEvaluationService:
    """Evaluate a persisted Observation against deterministic governed rules."""

    def classify_provider(self, provider: str) -> str:
        source = (provider or "").lower()
        if source.startswith("manual_correction:"):
            source = source.split(":", 1)[1]
        return DEVICE_CLASS.get(source, "ANY")

    @staticmethod
    def _audit(session: Session, observation: Observation, action: str, detail: dict[str, object]) -> None:
        session.add(AuditLog(
            patient_id=observation.patient_id,
            actor="risk_engine",
            actor_role="system",
            action=action,
            entity_type="Observation",
            entity_id=str(observation.id),
            detail_json=detail,
        ))

    @staticmethod
    def _is_usable(observation: Observation) -> tuple[bool, str | None]:
        if observation.quality_flag.lower() not in USABLE_QUALITY_FLAGS:
            return False, "quality_not_usable"
        if observation.excluded_from_analysis:
            return False, "excluded_from_analysis"
        if observation.source_deleted:
            return False, "source_deleted"
        return True, None

    def evaluate_observation(self, session: Session, observation_id: UUID) -> ObservationRiskEvaluation:
        """Evaluate one saved Observation without ever reading report candidates.

        The method is idempotent for an active event: repeat evaluation appends
        bounded evidence to that event instead of creating another event.
        """
        observation = session.get(Observation, observation_id)
        if observation is None:
            raise ValueError("Observation not found for risk evaluation.")
        usable, reason = self._is_usable(observation)
        if not usable:
            self._audit(session, observation, "risk_evaluation_skipped_quality", {"reason": reason})
            session.flush()
            return ObservationRiskEvaluation(observation.id, False, reason, 0, 0, 0, 0, ())

        self._audit(session, observation, "risk_evaluation_started", {
            "metric_code": observation.metric_code,
            "source": observation.source,
        })
        device_class = self.classify_provider(observation.source)
        rules = list(session.scalars(select(RiskRule).where(
            RiskRule.review_status == "APPROVED",
            RiskRule.is_active.is_(True),
            RiskRule.canonical_code == observation.metric_code,
        ).order_by(RiskRule.updated_at.desc())))
        member = session.get(Patient, observation.patient_id)
        rules = [rule for rule in rules if self._scope_allows_member(rule, member)]
        if observation.metric_code in WELLNESS_MANAGEMENT_METRICS:
            rules = [rule for rule in rules if self._is_explicit_synthetic_test_rule(rule)]

        evaluated = matched = created = updated = 0
        events: list[RiskEvent] = []
        for rule in rules:
            if rule.condition_type not in EXECUTABLE_CONDITION_TYPES:
                continue
            if rule.applicable_device_class not in {"ANY", device_class}:
                continue
            evaluated += 1
            result = self._evaluate_rule(session, observation, rule, device_class)
            if result is None:
                continue
            matched += 1
            self._audit(session, observation, "risk_rule_matched", {
                "risk_rule_id": str(rule.id),
                "rule_code": rule.code,
                "risk_level": rule.risk_level,
            })
            event, was_created, was_updated = self._create_or_update_event(session, observation, rule, device_class, result)
            if event is not None:
                events.append(event)
            created += int(was_created)
            updated += int(was_updated)

        session.flush()
        return ObservationRiskEvaluation(observation.id, True, None, evaluated, matched, created, updated, tuple(events))

    @staticmethod
    def _is_explicit_synthetic_test_rule(rule: RiskRule) -> bool:
        marker = f"{rule.code} {rule.condition_type} {rule.action_type} {rule.source_reference}".upper()
        return "SYNTHETIC" in marker and "TEST" in marker

    @staticmethod
    def _scope_allows_member(rule: RiskRule, member: Patient | None) -> bool:
        """Keep demo/test rules out of non-demo UAT members by default."""
        scope = (getattr(rule, "scope", "TEST") or "TEST").upper()
        if scope == "CLINICAL":
            return bool(rule.reviewed_by and rule.source_reference and rule.review_status == "APPROVED" and rule.is_active)
        identifier = " ".join(filter(None, ((member.external_id if member else None), (member.display_name if member else None)))).lower()
        return scope in {"DEMO", "TEST"} and any(marker in identifier for marker in ("demo", "synthetic", "test"))

    def evaluate_observation_safely(self, session: Session, observation_id: UUID) -> ObservationRiskEvaluation:
        """Never let a deterministic risk failure discard a health observation.

        Normal configuration/unit failures are handled per-rule.  This final
        guard keeps ingestion and report-confirmation usable if an unexpected
        evaluator failure occurs; it logs only identifiers and error class.
        """
        try:
            return self.evaluate_observation(session, observation_id)
        except Exception as error:  # pragma: no cover - defensive integration guard
            observation = session.get(Observation, observation_id)
            if observation is not None:
                self._audit(session, observation, "risk_evaluation_failed", {"error_type": type(error).__name__})
            logger.exception("risk_evaluation_failed observation_id=%s error_type=%s", observation_id, type(error).__name__)
            return ObservationRiskEvaluation(observation_id, False, "evaluation_failed", 0, 0, 0, 0, ())

    def _evaluate_rule(
        self,
        session: Session,
        observation: Observation,
        rule: RiskRule,
        device_class: str,
    ) -> dict[str, object] | None:
        config = rule.threshold_config or {}
        configured_metric = str(config.get("metric") or rule.canonical_code or "")
        if configured_metric != observation.metric_code:
            self._audit(session, observation, "risk_rule_skipped_metric", {"risk_rule_id": str(rule.id)})
            return None
        code = canonical_code(observation.metric_code)
        if code is None:
            self._audit(session, observation, "risk_rule_skipped_unit", {"risk_rule_id": str(rule.id), "reason": "unknown_metric"})
            return None
        try:
            threshold_value, threshold_unit = normalize_unit(code, config["value"], str(config.get("unit") or code.default_unit))
        except (KeyError, TypeError, ValueError, InvalidOperation):
            self._audit(session, observation, "risk_rule_skipped_unit", {"risk_rule_id": str(rule.id), "reason": "invalid_threshold_config"})
            return None

        window = rule.window_config or {}
        lookback_minutes = self._positive_int(window.get("lookback_minutes"), default=0)
        minimum_samples = self._positive_int(
            window.get("minimum_samples"), default=2 if rule.requires_repeated_measurement else 1
        )
        required_matches = self._positive_int(window.get("required_matches"), default=minimum_samples if rule.requires_repeated_measurement else 1)
        records = self._window_observations(session, observation, lookback_minutes)
        comparable: list[tuple[Observation, Decimal]] = []
        for item in records:
            try:
                amount, unit = normalize_unit(code, item.value_numeric, item.unit)
            except ValueError:
                continue
            if unit != threshold_unit:
                continue
            comparable.append((item, amount))
        operator = str(config.get("operator") or "")
        matching = [(item, amount) for item, amount in comparable if self._compare(amount, threshold_value, operator)]
        if len(comparable) < minimum_samples or len(matching) < required_matches:
            return None

        return {
            "source": "observation_driven",
            "rule_id": str(rule.id),
            "rule_code": rule.code,
            "rule_version": rule.version,
            "metric": observation.metric_code,
            "threshold_operator": operator,
            "threshold_value": str(threshold_value),
            "threshold_unit": threshold_unit,
            "window": {
                "lookback_minutes": lookback_minutes,
                "minimum_samples": minimum_samples,
                "required_matches": required_matches,
            },
            "matched_count": len(matching),
            "sample_count": len(comparable),
            "observation_ids": [str(item.id) for item, _ in matching],
            "matches": [
                {
                    "observation_id": str(item.id),
                    "value": str(amount),
                    "unit": threshold_unit,
                    "observed_at": item.observed_at.isoformat(),
                    "source": item.source,
                }
                for item, amount in matching
            ],
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "device_class": device_class,
            "recommended_route": rule.recommended_route,
        }

    @staticmethod
    def _positive_int(value: object, *, default: int) -> int:
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _nonnegative_int(value: object, *, default: int) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _compare(value: Decimal, threshold: Decimal, operator: str) -> bool:
        return {
            ">=": value >= threshold,
            ">": value > threshold,
            "<=": value <= threshold,
            "<": value < threshold,
            "==": value == threshold,
            "!=": value != threshold,
        }.get(operator, False)

    def _window_observations(self, session: Session, observation: Observation, lookback_minutes: int) -> list[Observation]:
        if lookback_minutes <= 0:
            return [observation]
        start = observation.observed_at - timedelta(minutes=lookback_minutes)
        return list(session.scalars(select(Observation).where(
            Observation.patient_id == observation.patient_id,
            Observation.metric_code == observation.metric_code,
            Observation.observed_at >= start,
            Observation.observed_at <= observation.observed_at,
            Observation.quality_flag.in_(("valid", "VALID", "manually_corrected", "MANUALLY_CORRECTED")),
            Observation.excluded_from_analysis.is_(False),
            Observation.source_deleted.is_(False),
        ).order_by(Observation.observed_at.asc(), Observation.created_at.asc())))

    def _create_or_update_event(
        self,
        session: Session,
        observation: Observation,
        rule: RiskRule,
        device_class: str,
        evidence: dict[str, object],
    ) -> tuple[RiskEvent | None, bool, bool]:
        active = session.scalar(select(RiskEvent).where(
            RiskEvent.patient_id == observation.patient_id,
            RiskEvent.risk_rule_id == rule.id,
            RiskEvent.status.in_(tuple(ACTIVE_EVENT_STATUSES)),
        ).order_by(RiskEvent.created_at.desc()))
        if active is not None:
            self._append_evidence(active, evidence)
            self._audit(session, observation, "risk_event_evidence_appended", {"risk_event_id": str(active.id), "risk_rule_id": str(rule.id)})
            self._audit(session, observation, "risk_event_not_created_duplicate", {"risk_event_id": str(active.id), "risk_rule_id": str(rule.id)})
            return active, False, True

        cooldown_minutes = self._nonnegative_int((rule.window_config or {}).get("cooldown_minutes"), default=0)
        if cooldown_minutes:
            previous = session.scalar(select(RiskEvent).where(
                RiskEvent.patient_id == observation.patient_id,
                RiskEvent.risk_rule_id == rule.id,
            ).order_by(RiskEvent.created_at.desc()))
            if previous is not None:
                anchor = previous.resolved_at or previous.created_at
                if anchor >= datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes):
                    self._audit(session, observation, "risk_event_not_created_cooldown", {"risk_rule_id": str(rule.id), "cooldown_minutes": cooldown_minutes})
                    return None, False, False

        event = RiskEvent(
            patient_id=observation.patient_id,
            risk_rule_id=rule.id,
            risk_level=rule.risk_level,
            status="NEW",
            device_class=device_class,
            canonical_code=observation.metric_code,
            recommended_route=rule.recommended_route,
            evidence_json={**evidence, "trigger_count": 1, "last_triggered_at": evidence["evaluated_at"], "recent_evaluations": [evidence]},
            summary=self._summary(rule, observation.metric_code),
            requires_manager_review=rule.risk_level == "YELLOW",
            requires_doctor_review=False,
            requires_emergency_action=rule.risk_level == "RED",
        )
        session.add(event)
        session.flush()
        self._audit(session, observation, "risk_event_created", {
            "risk_event_id": str(event.id),
            "risk_rule_id": str(rule.id),
            "risk_level": rule.risk_level,
            "source": "observation_driven",
        })
        return event, True, False

    @staticmethod
    def _append_evidence(event: RiskEvent, evidence: dict[str, object]) -> None:
        existing = dict(event.evidence_json or {})
        history = list(existing.get("recent_evaluations", []))
        history.append(evidence)
        existing.update(evidence)
        existing["trigger_count"] = int(existing.get("trigger_count", 1)) + 1
        existing["last_triggered_at"] = evidence["evaluated_at"]
        existing["recent_evaluations"] = history[-20:]
        event.evidence_json = existing

    @staticmethod
    def _summary(rule: RiskRule, metric_code: str) -> str:
        return f"健康数据自动监测触发规则“{rule.name}”（{metric_code}）；需要人工核实，不构成诊断。"

    # The retained demo API is intentionally isolated.  It is never used by
    # ingestion, manual observations, report confirmation, or corrections.
    def evaluate_demo(self, session: Session, patient_id: UUID, *, demo_flag: str | None, provider: str, canonical_code: str | None = None) -> RiskEvaluationResult:
        level = {"SYNTHETIC_EMERGENCY": "RED", "SYNTHETIC_YELLOW": "YELLOW"}.get(demo_flag or "", "GREEN")
        rules = list(session.scalars(select(RiskRule).where(
            RiskRule.review_status == "APPROVED",
            RiskRule.is_active.is_(True),
            RiskRule.risk_level == level,
        )))
        rule = next((item for item in rules if item.condition_type == "SYNTHETIC_DEMO_FLAG" and item.applicable_device_class in {self.classify_provider(provider), "ANY"}), None)
        summary = {
            "GREEN": "近期数据稳定，继续当前健康管理计划。",
            "YELLOW": "演示风险规则提示需要健康管理师人工核实。",
            "RED": "演示紧急风险：请立即进行人工处置并优先完成医疗评估。",
        }[level]
        if rule and level != "GREEN":
            self._demo_event(session, patient_id, rule, provider, canonical_code, summary)
        return RiskEvaluationResult(level, rule, summary, level == "YELLOW", level == "RED")

    def _demo_event(self, session: Session, patient_id: UUID, rule: RiskRule, provider: str, code: str | None, summary: str) -> RiskEvent:
        existing = session.scalar(select(RiskEvent).where(
            RiskEvent.patient_id == patient_id,
            RiskEvent.risk_rule_id == rule.id,
            RiskEvent.status.in_(tuple(ACTIVE_EVENT_STATUSES)),
        ))
        if existing:
            existing.evidence_json = {**existing.evidence_json, "last_seen": datetime.now(timezone.utc).isoformat()}
            return existing
        event = RiskEvent(
            patient_id=patient_id, risk_rule_id=rule.id, risk_level=rule.risk_level,
            status="NEW", device_class=self.classify_provider(provider), canonical_code=code,
            evidence_json={"demo_flag": True, "source": "synthetic_demo"}, summary=summary,
            requires_manager_review=rule.risk_level == "YELLOW", requires_doctor_review=False,
            requires_emergency_action=rule.risk_level == "RED",
        )
        session.add(event)
        session.flush()
        session.add(AuditLog(
            patient_id=patient_id, actor="risk_engine", actor_role="system", action="generated_risk_event",
            entity_type="RiskEvent", entity_id=str(event.id), detail_json={"level": event.risk_level, "demo": True},
        ))
        return event

    def acknowledge(self, session: Session, event: RiskEvent, actor: str) -> None:
        event.status = "ACKNOWLEDGED"
        event.acknowledged_by = actor
        event.acknowledged_at = datetime.now(timezone.utc)
        session.add(AuditLog(patient_id=event.patient_id, actor=actor, actor_role="health_manager", action="acknowledged_risk_event", entity_type="RiskEvent", entity_id=str(event.id), detail_json={}))
        session.flush()

    def emergency_action(self, session: Session, event: RiskEvent, actor: str, action: str) -> None:
        event.status = "ESCALATED"
        event.acknowledged_by = event.acknowledged_by or actor
        event.acknowledged_at = event.acknowledged_at or datetime.now(timezone.utc)
        session.add(AuditLog(patient_id=event.patient_id, actor=actor, actor_role="health_manager", action="recorded_emergency_action", entity_type="RiskEvent", entity_id=str(event.id), detail_json={"action": action, "manual_confirmation_required": True}))
        for program in session.scalars(select(HealthProgram).where(HealthProgram.patient_id == event.patient_id, HealthProgram.status == "ACTIVE")):
            program.status = "ESCALATED_TO_MEDICAL_CARE"
        session.flush()

    def close_manual_event(self, session: Session, event: RiskEvent, actor: str, reason: str, final_action: str) -> RiskEvent:
        """Close a non-Yellow event only after a named human records why.

        This does not change any rule threshold or make a medical decision; it
        merely preserves the human closure rationale for the timeline/audit.
        """
        if event.risk_level != "RED":
            raise ValueError("Use the Yellow risk workflow to close this event.")
        if event.status not in ACTIVE_EVENT_STATUSES:
            raise ValueError("该风险事项已关闭。")
        if not reason.strip() or not final_action.strip():
            raise ValueError("请填写关闭原因和最终人工处置。")
        event.status, event.resolved_at = "CLOSED", datetime.now(timezone.utc)
        session.add(AuditLog(
            patient_id=event.patient_id, actor=actor, actor_role="health_manager", action="closed_red_risk_event",
            entity_type="RiskEvent", entity_id=str(event.id), detail_json={"reason": reason.strip(), "final_action": final_action.strip()},
        ))
        session.flush()
        return event
