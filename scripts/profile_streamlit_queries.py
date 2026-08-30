"""Read-only local profiling for Streamlit navigation query shapes.

It reports durations and row-free counts only. It never emits member names,
health values, report text, or other PHI, and it does not call LLM, parsing,
risk evaluation, migration, or seed routines.
"""
from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

# Executing ``python scripts/profile_streamlit_queries.py`` puts ``scripts``
# first on sys.path; add the repository root without changing global Python.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit_app as app


def _measure(label: str, callback) -> None:
    started = perf_counter()
    callback()
    print(f"{label:<28} {(perf_counter() - started) * 1000:7.1f} ms")


def main() -> None:
    members = app._members()
    member_ids = [member.id for member in members]
    print(f"members={len(member_ids)}")
    _measure("member list", app._members)
    _measure("member card summaries", lambda: app._member_list_summaries(member_ids))
    _measure("workbench summaries", app._dashboard_context)
    _measure("more root", lambda: None)
    print("No Observation full scan, LLM, parser, risk evaluation, seed, or migration was run.")


if __name__ == "__main__":
    main()
