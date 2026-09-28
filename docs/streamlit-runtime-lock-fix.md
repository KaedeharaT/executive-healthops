# Streamlit intake runtime lock regression — 2026-09-28

The production Streamlit log at 17:50:33 recorded
`sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) database is locked`.
The application stack was `ui/pages/manager/intake_workspace.py:144` →
`agent/supervisor.py:116` → `agent/profile_intake.py:82` (lines before this fix).
The worker log reported the same failed claim. FastAPI had started normally.

The intake policy changed RUNNING to PROCESSING inside the caller's transaction,
then made a potentially long local model request before committing. SQLite kept
the write lock throughout the request. Another browser refresh or worker still
read the uncommitted old RUNNING state, tried to claim it and timed out.

Runtime UI/worker calls now publish the claim in a short transaction, execute the
same existing policy without a write lock during extraction/model I/O, and commit
candidate results together with the plan transition. Candidate persistence is
deferred until semantic extraction finishes. Actual worker progress is published
to the same goal for the foreground board and spinner. Claims have renewable
deadlines based on the existing model timeout; stale results are fenced, expired
claims can resume, and unexpected failures roll back and propagate their original
exception. The caller-owned transaction interface remains available for commands.

No model/provider, Agent policy, database table or medical confirmation boundary
was replaced. Source validation, prefill, exceptions and the eleven-step editor
remain in place.

Verification:

- File-backed SQLite with independent connections: while a model request is held
  open, a second executor does not duplicate it and another business write commits.
- Published progress and spinner remain visible; result persistence, matching and
  WAITING_MANAGER complete normally.
- Expired claims resume the same goal; failed work rolls back without swallowing
  the exception; superseded work cannot persist candidates.
- Targeted tests: 45 passed, 0 failed.
- Full suite: 845 passed, 0 failed (13 existing dependency deprecation warnings).
- Restarted the platform service group. Chromium 151.0.7922.34 navigated from
  `http://127.0.0.1:8501` through 会员 → Member360 → 健康档案 to the original
  affected member while the worker was executing the real local model request.
  The assistant, current semantic extraction stage and spinner were visible;
  no Streamlit exception appeared. Runtime screenshots and page text remain under
  ignored `.runtime/streamlit-runtime-fix/` because they contain member data.
- A later Chromium revisit while the same model request was outstanding also
  showed zero page exceptions. Streamlit returned HTTP 200, its health endpoint
  returned `ok`, and the post-restart Streamlit log contained no new traceback.
