# HealthOps Agent Supervisor V1

## Purpose and boundary

V1 is **bounded autonomous HealthOps orchestration** for one workflow: post-checkup management. It is event-driven, goal-driven, durable across human and time waits, and independent of LLM availability. It coordinates existing services; it does not diagnose, prescribe, change medication, assign clinical risk, edit `RiskRule`, or bypass a health manager or doctor.

Business entities remain authoritative. `Report`, `Observation`, `RiskEvent`, `Task`, `DoctorReview`, `ServiceRequest`, `OutcomeEvaluation`, and timeline source entities are the facts. Agent tables contain orchestration and audit state only.

## Architecture

```text
Business event
  → EventService (dedup)
  → AgentGoal
  → template-guided AgentPlan / PlanStep
  → permissioned Tool Registry
  → existing HealthOps services
  → wait for person / event / time
  → resume, bounded retry, or operational replan
  → trace
```

V1 uses a database-backed scheduler. Production deployments can replace the worker loop without changing the plan, event, approval, or tool contracts.

## State machines

- Goal: `ACTIVE → WAITING ↔ ACTIVE → COMPLETED`; exceptional paths use `BLOCKED`, `FAILED`, or `CANCELLED`.
- Approval: `PENDING → APPROVED | REJECTED | CANCELLED`.
- Step: `PENDING → RUNNING → COMPLETED`; it may enter `WAITING_EVENT`, `WAITING_MEMBER`, `WAITING_MANAGER`, `WAITING_DOCTOR`, `WAITING_SERVICE`, `WAITING_TIME`, `WAITING_APPROVAL`, `RETRY_WAIT`, `BLOCKED`, or `SKIPPED`.
- Retry is bounded by `max_retries` with backoff. Replanning creates a new immutable plan version and preserves the prior plan.

## Post-checkup Golden Path

```text
REPORT_UPLOADED → goal → wait for report confirmation
REPORT_CONFIRMED → deterministic baseline/risk/worklist checks
manager approval → ownership → optional DoctorReview
DOCTOR_REVIEW_COMPLETED → follow-up → timed wait
REVIEW_DUE → outcome wait
OUTCOME_RECORDED → timeline check → success criteria → COMPLETED
```

Clinical questions are routed to the existing `DoctorReview` workflow. `AgentApprovalRequest` records only why orchestration is waiting and who released the gate.

## Product entry points

- Member: Member Health Center → Home → **持续管理状态**.
- Health manager: Operations → Today, or Operations → Members → member detail → **自动跟进状态**.
- Doctor: Operations → Medical Collaboration → Internal Doctor; a review shows its post-checkup workflow origin.
- Administrator: Operations → More → System → **自动化运营**. Manual takeover, resume, cancellation, and a folded trace are available there.

The FastAPI surface is under `/agent/events`, `/agent/goals`, and `/agent/approvals`. The migration is `0025_add_agent_supervisor_v1`.
