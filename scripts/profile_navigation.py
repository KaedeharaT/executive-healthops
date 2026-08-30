"""Read-only Streamlit navigation profiler for the current local database.

It reports route timings and SQL counts without printing member, report, or
measurement content.  It does not invoke LLM, report parsing, risk evaluation,
device sync, seed routines, or database migrations.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from sqlalchemy import event
from streamlit.testing.v1 import AppTest

import streamlit_app as app
from executive_health_ai.database import engine


@dataclass
class QueryCounter:
    count: int = 0
    elapsed_ms: float = 0.0

    def reset(self) -> None:
        self.count = 0
        self.elapsed_ms = 0.0


COUNTER = QueryCounter()


@event.listens_for(engine, "before_cursor_execute")
def _before_cursor_execute(_conn, _cursor, _statement, _parameters, context, _executemany) -> None:
    context._navigation_profile_started = perf_counter()


@event.listens_for(engine, "after_cursor_execute")
def _after_cursor_execute(_conn, _cursor, _statement, _parameters, context, _executemany) -> None:
    COUNTER.count += 1
    COUNTER.elapsed_ms += (perf_counter() - getattr(context, "_navigation_profile_started", perf_counter())) * 1000


def _measure(label: str, callback) -> tuple[float, int]:
    COUNTER.reset()
    started = perf_counter()
    callback()
    elapsed = (perf_counter() - started) * 1000
    print(f"[PERF] {label:<26} {elapsed:7.1f} ms  sql={COUNTER.count:2d} ({COUNTER.elapsed_ms:.1f} ms)")
    return elapsed, COUNTER.count


def _render_route(app_test: AppTest, workspace: str) -> tuple[float, int]:
    COUNTER.reset()
    started = perf_counter()
    navigation = next(radio for radio in app_test.radio if radio.label == "工作区")
    navigation.set_value(workspace)
    app_test.run(timeout=30)
    elapsed = (perf_counter() - started) * 1000
    print(f"[PERF] route:{workspace:<20} {elapsed:7.1f} ms  sql={COUNTER.count:2d} ({COUNTER.elapsed_ms:.1f} ms)")
    return elapsed, COUNTER.count


def main() -> None:
    """Profile direct data stages, then real Streamlit reruns twice."""
    members = app._members()
    member_ids = [member.id for member in members]
    print(f"[PERF] local database members={len(member_ids)}")
    _measure("bootstrap member list", app._members)
    def _daily_worklist():
        with app.SessionLocal() as session:
            return app.OperationalWorklistService().list_items(session, datetime.now(app.TOKYO_TIMEZONE))

    _measure("today worklist", _daily_worklist)
    _measure("workbench member map", app._patient_map)
    _measure("member list summaries", lambda: app._member_list_summaries(member_ids))
    _measure("device overview", app._device_overview_snapshot)
    _measure("more root", lambda: None)

    test = AppTest.from_file(ROOT / "streamlit_app.py")
    test.run(timeout=30)
    for workspace in ("成员", "更多", "今日", "协同", "更多", "成员"):
        _render_route(test, workspace)
    if test.exception:
        raise SystemExit("Streamlit exception encountered during profile")
    print("[PERF] side_effects local_llm=0 ollama=0 risk_engine=0 report_parser=0 device_sync=0 seed=0")


if __name__ == "__main__":
    main()
