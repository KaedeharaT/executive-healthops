"""Dispatch the existing bounded executor without blocking Streamlit refresh.

The database claim still owns execution. These futures only prevent redundant
local submissions; a restart/worker uses the same goal and lease recovery.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import logging

_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='intake-display')
_lock=Lock()
_pending={}


def _execute(goal_id):
    from executive_health_ai.database import SessionLocal
    from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
    with SessionLocal() as session:
        HealthOpsAgentSupervisor().execute_next_step(session,goal_id,durable_profile=True)


def submit(goal_id):
    with _lock:
        for key,future in list(_pending.items()):
            if future.done():
                del _pending[key]
                if future.exception():
                    # Preserve actual operational failures in the server log.
                    logging.getLogger(__name__).error('Intake execution failed',exc_info=future.exception())
                    if key==goal_id:raise future.exception()
        if goal_id not in _pending:_pending[goal_id]=_pool.submit(_execute,goal_id)
