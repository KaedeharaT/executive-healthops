# BP product alignment

Executive HealthOps is aligned to the product definition in *企业家主动式持续健康管理平台-BP-v06新版*: year-round, human-owned health operations for members, health managers, and licensed doctors. It is not an AI chat product, a developer console, or a training platform.

## Responsibility loop

| BP step | Product implementation | Owner | Status |
|---|---|---|---|
| 采集 | Reports, device adapters, medical records, and manual entry preserve raw evidence | Member / health manager | Implemented |
| 判断 | Confirmed observations feed rules; AI may prepare summaries or drafts | System assists; human verifies | Implemented |
| 分级 | Approved deterministic rules create Green / Yellow / Red / Gray outcomes | Risk Engine | Implemented |
| 确认 | Managers confirm operational facts; doctors retain medical judgement | Manager / doctor | Implemented |
| 行动 | Problems, plans, tasks, services, referrals, and follow-up have owners and due dates | Manager coordinates | Implemented |
| 回写 | Service evidence, doctor conclusions, follow-up, and outcomes return to business records | Responsible human | Implemented |
| 复盘 | Monthly execution, quarterly calibration, and annual review use plans, comparisons, and outcomes | Manager / doctor | Implemented |
| 下一轮 | Review results update the next plan and actionable queue | Manager | Implemented |

The Operational Worklist is the single current projection for manager priorities. The Timeline is a longitudinal projection. Neither is a source of truth: reports, observations, RiskEvents, problems, plans, tasks, doctor reviews, services, and outcomes remain authoritative.

## Role products

| Role | First question answered | Primary product surface |
|---|---|---|
| Member | What should I do now, what changed, and who is responsible? | Home, Health, Timeline, Plan, Service |
| Health manager | Who needs attention today, why, by when, and what is next? | Operational Worklist, Member Overview, Service Operations |
| Doctor | Why am I needed, what facts support the request, and who acts on my conclusion? | Medical Collaboration / Doctor Review |

Doctors retain diagnosis, prescription, medication adjustment, investigation, treatment, and referral decisions. AI may structure reports, summarize evidence, detect changes, and draft low-risk communication; it never determines medical risk or replaces a clinician.

## Annual operating cadence

- First month: confirm reports, history, medication, health data, lifestyle, goals, baseline, and initial plan.
- Monthly: monitor trends, follow tasks, reminders, services, and result writeback.
- Quarterly: compare key indicators, reassess risk, coordinate doctor review, and calibrate the plan.
- Annually: compare examinations, review major events, services, and outcomes, then prepare the next cycle.

## Offline service delivery

The service lifecycle is `REQUESTED → APPROVED → SCHEDULED → IN_SERVICE → COMPLETED`, with cancellation supported. Product views show the service, member, owner, delivery party where known, appointment, SLA, completion evidence, result, and next action. Completion writes a timeline event and creates a manager follow-up task so delivery cannot disappear after it is marked complete.

Schema revision `0024_align_service_delivery_with_bp` adds nullable, backward-compatible `service_provider`, `sla_due_at`, `completion_evidence`, and `next_action` fields to `service_requests`. Existing business records are preserved; historical `IN_PROGRESS` rows are interpreted as `IN_SERVICE`. Consent continues to use the existing `consents` table (`consent_type`, `granted_at`, `withdrawn_at`, and `source`) with BP-facing scope/revocation names in the application layer.

The catalogue is presented in four BP delivery families: assessment and record building, continuous management, professional collaboration, and medical coordination.

## Integration boundaries

- Device providers implement a translation adapter: external payload → raw ingestion → canonical observation → quality review. Devices do not diagnose or decide risk.
- External medical knowledge is consumed through the partner knowledge adapter. HealthOps retains citation validation, usage records, and no-source refusal; local approved SOPs remain available for workflow guidance and offline demo fallback.
- Human AI feedback is quality-governance data only. It cannot automatically train, deploy, modify RiskRules, or activate a model.

## Delivery status

Real device vendors, a real partner knowledge service, production authentication/RBAC, hospital integrations, and payment remain integration boundaries rather than simulated production capabilities.
