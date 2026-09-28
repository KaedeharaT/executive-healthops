"""Request-scoped safe telemetry. No prompts, response bodies or hidden reasoning."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from time import perf_counter

_collector = ContextVar('healthops_llm_activity', default=None)
_current = ContextVar('healthops_current_llm_call', default=None)
_progress = ContextVar('healthops_business_progress', default=None)


@contextmanager
def observe_progress(callback, *, chain=False):
    """Transient UI notifications; never a second workflow or persisted state."""
    previous=_progress.get()
    def combined(event):
        callback(event)
        if previous:previous(event)
    token=_progress.set(combined if chain else callback)
    try:
        yield
    finally:
        _progress.reset(token)


def notify_progress(event):
    if callback:=_progress.get():
        callback(event)


@contextmanager
def collect_calls():
    calls = []
    token = _collector.set(calls)
    try:
        yield calls
    finally:
        _collector.reset(token)


@contextmanager
def observe_call(task, provider):
    collector = _collector.get()
    if collector is None:
        yield
        return
    row = {'kind': 'LLM', 'task': task, 'provider': provider, 'request_sent': False,
           'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'RUNNING'}
    collector.append(row)
    token = _current.set(row)
    started = perf_counter()
    try:
        yield
        row['status'] = 'SUCCESS'
    except Exception:
        row['status'] = 'UNAVAILABLE'
        raise
    finally:
        row.update(completed_at=datetime.now(timezone.utc).isoformat(), latency_ms=round((perf_counter()-started)*1000))
        _current.reset(token)


def request_started():
    if (row := _current.get()) is not None:
        row['request_sent'] = True
        notify_progress('AI_REQUEST_STARTED')


def result_checked(task, count):
    """Attach only a validated count to this collector's most recent request."""
    calls = _collector.get()
    if calls and calls[-1]['task'] == task and calls[-1]['status'] == 'SUCCESS':
        calls[-1].update(accepted=count > 0, result_count=count)
