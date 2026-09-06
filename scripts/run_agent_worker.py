"""Run the replaceable DB-backed wake-up worker for Agent Supervisor V1."""

from __future__ import annotations

import argparse
import logging
import os
import time

from executive_health_ai.agent.scheduler import AgentSchedulerService
from executive_health_ai.database import SessionLocal
from executive_health_ai.models.base import utc_now


logger = logging.getLogger("healthops.agent_worker")


def run_once() -> int:
    with SessionLocal() as session:
        count = AgentSchedulerService().run_due(session, now=utc_now())
        session.commit()
        return count


def main() -> None:
    parser = argparse.ArgumentParser(description="HealthOps bounded automation wake-up worker")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    interval = max(1, min(int(os.getenv("AGENT_WORKER_INTERVAL_SECONDS", "30")), 300))
    while True:
        try:
            run_once()
        except Exception:
            logger.exception("agent_worker_cycle_failed")
        if args.once:
            return
        time.sleep(interval)


if __name__ == "__main__":
    main()
