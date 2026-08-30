# Executive HealthOps Usage Logic Audit

> Closure updated: 2026-08-31
> Scope: Portfolio Demo's existing report, risk, plan, doctor, service, timeline and knowledge flows.

## 1. Overall Verdict

**DEMO LOGIC: STRONG**
**DEMO READY: YES**

The Portfolio Demo now tells one accountable, human-in-the-loop story for the anonymous **Demo Executive A**:

`Report → manager review / baseline → demo yellow risk → manager hand-off → doctor review → manager follow-up → plan and outcome decision → service → timeline → approved medical reference.`

The closure work did not add Clinical RiskRules, change medical thresholds, let AI determine risk, or create automated emergency action.

## 2. Closed Loops

| Loop | Status | Closure now visible in the product |
|---|---|---|
| Report | COMPLETE | Member-facing received/processing/review/baseline-complete status; manager review and baseline route are explicit. |
| Risk | COMPLETE | Active yellow risks remain in one work item through waiting-member, waiting-doctor and follow-up states; only explicit closure removes them from active work. |
| Plan | COMPLETE | Member accept/adjust/pause changes plan state or creates a manager-owned next action. |
| Doctor | COMPLETE | A demo pending review is present; the doctor sees context and evidence, then completion returns one manager follow-up rather than duplicate work. |
| Service | COMPLETE | Request → approval → schedule → in service → result → completed is visible to both member and operator; completion remains traceable in the timeline. |
| Timeline | COMPLETE | The existing longitudinal timeline aggregates the major report, risk, plan-choice, service and outcome decisions with an Inspector. |
| Knowledge | COMPLETE | The knowledge Inspector key is stable; report / doctor contexts can retrieve approved, non-archived references without changing risk or medical decisions. |
| Medical / External | PARTIAL | Records and referrals remain traceable. Full external appointment and feedback operations are deliberately outside the five-minute Portfolio story. |

## 3. Closure Outcomes

### Member journey

- A report has clear human language progress: received, being organized, waiting for review, health record being established, or review complete.
- An existing baseline is not presented as a new baseline action; baseline work opens the actual baseline view.
- Plan choices are no longer button-only history. They update the plan and/or create an accountable next action.
- Health-data cards distinguish recent, ageing, stale and absent data. No data is not presented as normal or green.
- Member service requests show their current stage, scheduled time, next action and completion result.

### Health Manager journey

- `Today` uses one operational worklist contract across risks, report review tasks, doctor work, program/plan actions and service requests.
- Each active item presents its owner, meaningful status, next action and due date when one exists; unassigned work is explicitly labelled `待分配`.
- A risk-to-doctor escalation is one primary risk work item (`等待医生`), not three duplicate items.
- Yellow workflow: `待处理 → 已接手 / 处理中 → 等待成员 / 等待医生 / 待随访 → 已关闭`.

### Doctor and knowledge journey

- The seeded demo has a pending doctor review linked to the yellow demo risk, with member, manager question, relevant risk context, report evidence and approved-reference retrieval.
- Completing a doctor review returns responsibility to a manager follow-up rather than silently removing the case.
- Related knowledge is explanatory only. Retrieval returns approved, valid documents/chunks and shows source attribution; it cannot create a RiskRule, diagnosis, prescription or risk decision.

### Service and outcome journey

- Service delivery has a minimal auditable lifecycle: requested, approved, scheduled, in service, completed (or cancelled), with owner, schedule, next action and result summary.
- An outcome is not an endpoint: the manager can continue, adjust, enter a stable phase or request a doctor review. The decision creates the corresponding program state or next work item and is eligible for timeline aggregation.

## 4. Demo Seed Contract

`scripts/build_portfolio_demo.py --rebuild` produces an isolated, anonymous story with:

- Demo Executive A and an already processed demo report / baseline;
- one active **demo yellow risk** already handed to a pending doctor review;
- a small closed demo red record that does not obscure the main yellow workflow;
- an active health plan and one unfinished member task (a reminder, not a medical risk);
- a service workflow and outcome data;
- approved knowledge documents with retrievable chunks.

All risk rules in the story remain clearly **TEST / demo rules**, not Clinical RiskRules.

## 5. Remaining Non-blocking Boundaries

These are deliberately outside this Portfolio closure and do not block the five-minute story:

1. External medical coordination does not implement a production hospital booking/feedback integration.
2. Platform-internal reminders are not SMS, email, WeChat or push notifications.
3. There is no production RBAC, clinical rule-governance program, real-device verification or production deployment claim.
4. The demo intentionally uses synthetic, anonymous data and does not assert clinical validation.

## 6. Verification

- Rebuilt the isolated Portfolio database from `scripts/build_portfolio_demo.py --rebuild`.
- Exercised the Streamlit `更多 → 知识库` and `今日` paths with `AppTest`; no duplicate widget-key exception occurred.
- Added regression coverage for active-risk continuity, worklist de-duplication, plan choice hand-off, service lifecycle, outcome decisions, baseline routing, knowledge key scopes and freshness copy.
- Full regression suite: **321 passed, 0 failed**.

## 7. Top 10 Audit Fixes

| # | Audit finding | Status |
|---|---|---|
| 1 | Today risk statistics and worklist semantics diverged | FIXED |
| 2 | Taken yellow risk could disappear before closure | FIXED |
| 3 | Knowledge Center Inspector duplicate key | FIXED |
| 4 | Member plan choice had no responsible next action | FIXED |
| 5 | Report member progress and comparison next-step wording | FIXED |
| 6 | Worklist owner, due, next action and risk/doctor de-duplication | FIXED |
| 7 | Demo lacked pending doctor review and incomplete member task | FIXED |
| 8 | Service skipped schedule, execution and result | FIXED |
| 9 | Outcome ended without a management decision | FIXED |
| 10 | Stale/no health data could read as current/normal | FIXED |
