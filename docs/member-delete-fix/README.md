# Member directory filters and safe archive

## What the duplication investigation established

The source has one `directory → filter_bar` call. Fresh Chromium sessions also showed one stable filter bar on first entry. The user's reported persistent duplicate on first entry was not reproduced exactly.

A real rendering defect was reproduced: `workflow.flash()` conditionally inserted a success element above the filter bar. When it appeared/disappeared, Streamlit changed the positional delta path, temporarily retaining both the old and new filter blocks. The Chromium MutationObserver recorded a peak of **2** filter containers on the confirmation/feedback path. The unchanged script recorded a peak of **1** after the fix (including navigation, search, selection, cancellation and confirmation).

`render_members_workspace` now owns a stable keyed page container. `directory` always allocates a keyed feedback container, whether or not a message exists. The filter remains a single component invocation; no CSS hiding or second hidden set of widgets is used.

- Before evidence: `filter-render-before.json`.
- After evidence: `../images/member-delete-fix/filter-render-samples.json` and `browser-results.json`.
- Treat the first-entry report as a reproduction limitation, not proof of an independently verified second Python render call.

## Model and association audit

`Patient` / `Member` is one model, backed by `patients`. It had no inactive/archive field. Migration `0029_archive_members` adds only nullable indexed `archived_at`; existing rows remain active. No FK cascade or physical deletion was introduced.

| Existing data | Archive handling |
| --- | --- |
| Health records, Observation, documents/reports, extraction candidates, annual baseline | Retained |
| Annual program/journey, management/care plan, unfinished phases | Paused; original status recorded in audit |
| ManagementItem operational projection / Task, FollowUp, unfinished Recheck, ServiceRequest, legacy CareTask | Cancelled, never marked completed; completion evidence/timestamps not invented |
| DoctorReview, Consultation, Risk | Clinical state and records retained; unresolved issues require human handoff |
| AgentGoal, plans, pending steps/approvals/events | Active execution cancelled, automation paused, wake-up scheduling cleared; completed records retained |
| ManagementLog, Timeline source records, Audit, Agent Trace | Retained; archive audit and trace appended |

Recheck `COMPLETED` means examination performed with report/review still pending; it is not treated as a closed workflow. Cancelling the local service workflow does not assert that an external booking or fee was cancelled.

The archive transaction locks the member row and verifies stable member ID, current name, typed confirmation and permitted role. The ORM write guard rejects writes from stale sessions after archive. Supervisor/tool entry points block new execution, and late events are recorded as ignored. There is no restore, hard delete or alternative Member model.

## User interaction and retention

Selecting a row exposes the retained primary “查看会员 / 进入Member360” action and secondary red “删除成员”. A native dialog displays name, short member ID, active-work impact, retention/handoff explanation, name input, Cancel and Confirm. Every opening clears the previous confirmation input. Only the bound member ID is passed to the transaction.

After success the selection is reset and the member disappears from normal member, annual, daily-work, service, assistant and doctor queues. Member360 entry rejects archived members; its business content is unchanged. Administrator → 系统状态 → 操作记录 → 显示已归档成员 exposes audit plus read-only historical tables. Existing administrator automation views retain Agent Trace access.

## Verification and runtime

- Baseline: **730 passed / 0 failed** (`baseline/final-tests.txt`).
- Complete suite: **745 passed / 0 failed**, 13 existing warnings (`final-release/final-tests.txt`).
- Final event-replay refinement was subsequently verified against archive, post-checkup and profile-intake suites: **57 passed / 0 failed**, one UI-only test deselected because the refinement does not change UI (`agent-archive-regression.txt`). Replayed processed/cancelled events retain their historical state; ignored receipts retain their original receipt timestamp.
- Chromium 1440×900: one filter bar, normal table, secondary action, disabled empty/wrong-name confirmation, cancellation, confirmed archive, disappearance and administrator history.
- Screenshots: `docs/images/member-delete-fix/01-member-filter-fixed.png` through `05-admin-archived-history.png`, plus `06-live-first-open.png` from the normal running instance.
- Deletion acceptance runs only against `.runtime/member-delete/qa.db` and synthetic `Demo Archive QA`; no actual member is deleted/archived for acceptance.
- Existing local database backed up with SQLite backup to `.runtime/member-delete/pre-archive.db` before migration.
- Normal services use hidden managed instance `platform`, logs `.runtime/logs/platform/`, PID registry `.runtime/processes/platform.json`; no database reseeding.
- QA instance `member-delete` is separately managed and stopped after acceptance.
- No push.

The final regression exposed an existing Windows process-registry race: a concurrent reader occasionally prevented atomic PID-file replacement (`WinError 5`). `write_state` now retries the replacement for at most two seconds, retaining the previous complete registry and propagating persistent errors. Real Windows file-handle tests cover transient and persistent locks; the existing hidden-window, restart, PID-reuse and descendant-cleanup checks remain in place.

Skill read: `D:/executive_health_ai/.agents/skills/ui-ux-pro-max/SKILL.md`; local UX guidance on destructive confirmation, cancellation and feedback applied.
