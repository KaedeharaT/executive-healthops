# UI and runtime change rules

## One action per business context

Before adding an action, compare its page/context, target, side effects, bound
member/item/goal identity and user purpose with existing controls. Only actions
matching all five are duplicates. Keep distinct clinical/management actions and
distinct entry contexts such as the member directory and annual portfolio.

- Use one primary CTA per active task. A selected table row opens its detail;
  do not add another button solely to open that same detail.
- Reuse the current detail renderer and persisted identity. Never create another
  Agent to satisfy navigation, and never implement a duplicate progress page.
- Preserve evidence, source files, timestamps and human confirmation gates.
- Remove duplicate render calls/code, not with CSS hiding. Preserve a clear return
  path and invalidate old table selection when leaving a detail.
- Verify real Chromium interaction in every affected role, including empty and
  completed states. Source presence and passing tests do not prove visibility.

## No long I/O inside database write transactions

LLM calls, network requests, file parsing and long computations must not execute
while holding a database write transaction. This includes implicit ORM autoflush
and task-claim UPDATE statements.

Use a short transaction to claim work and publish its real state; commit it before
external I/O. Extract/compute without pending database writes. Then persist validated
results and the business transition atomically in a short transaction. Runtime
intake callers use `durable_profile=True` with a dedicated session and the existing
`profile_execution` boundary. Keep renewable ownership and stale-result fencing.

Do not put `session.commit()` in the LLM client or loosen medical confirmation.
Increasing SQLite timeout, swallowing `OperationalError`, or showing fabricated
progress does not solve write-lock contention. Add a file-backed, two-connection
regression check proving another business write succeeds during a held model
request; unexpected failures must retain their traceback.
