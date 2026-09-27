"""Windows background service groups: no consoles, durable PIDs, owned-tree cleanup.

The supervisor owns a Windows Job Object with KILL_ON_JOB_CLOSE. Its services,
venv Python redirectors and all descendants die even if the supervisor crashes.
No database, API or worker behavior is implemented here.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def kernel():
    if os.name != "nt":
        raise RuntimeError("This launcher requires Windows; use the existing CLI services on other systems.")
    dll = ctypes.WinDLL("kernel32", use_last_error=True)
    dll.OpenProcess.restype = wintypes.HANDLE
    dll.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    dll.CloseHandle.argtypes = [wintypes.HANDLE]
    dll.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    dll.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    dll.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    return dll


def process_identity(pid):
    """Creation time guards against recycled PIDs; exit code excludes dead handles."""
    dll = kernel()
    handle = dll.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        times = [wintypes.FILETIME() for _ in range(4)]
        code = wintypes.DWORD()
        if not dll.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
            return None
        if not dll.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:
            return None
        return (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
    finally:
        dll.CloseHandle(handle)


def own_process_tree():
    """Assign ourselves before spawning anything, so descendants inherit ownership."""
    class BasicLimit(ctypes.Structure):
        _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                    ("flags", wintypes.DWORD), ("min_ws", ctypes.c_size_t),
                    ("max_ws", ctypes.c_size_t), ("active", wintypes.DWORD),
                    ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                    ("scheduling", wintypes.DWORD)]

    class ExtendedLimit(ctypes.Structure):
        _fields_ = [("basic", BasicLimit), ("io", ctypes.c_uint64 * 6),
                    ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                    ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]

    dll = kernel()
    dll.CreateJobObjectW.restype = wintypes.HANDLE
    dll.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    dll.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    dll.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    dll.GetCurrentProcess.restype = wintypes.HANDLE
    job = dll.CreateJobObjectW(None, None)
    limits = ExtendedLimit()
    limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not job or not dll.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not dll.AssignProcessToJobObject(job, dll.GetCurrentProcess()):
        dll.CloseHandle(job)
        raise ctypes.WinError(ctypes.get_last_error())
    # Deliberately keep the non-inheritable handle open until supervisor exit.
    return job


def state_path(instance):
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", instance):
        raise ValueError("Instance must contain only letters, digits, '-' or '_'.")
    return RUNTIME / "processes" / f"{instance}.json"


def job_processes(job):
    dll = kernel()
    dll.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                              wintypes.DWORD, ctypes.c_void_p]
    buffer = ctypes.create_string_buffer(8 + ctypes.sizeof(ctypes.c_size_t) * 1024)
    if not dll.QueryInformationJobObject(job, 3, buffer, len(buffer), None):
        raise ctypes.WinError(ctypes.get_last_error())
    count = wintypes.DWORD.from_buffer(buffer, 4).value
    ids = (ctypes.c_size_t * count).from_buffer(buffer, 8)
    return [dict(pid=pid, created=process_identity(pid)) for pid in ids if pid != os.getpid()]


def write_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(temp, path)


def read_state(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@contextmanager
def instance_lock(instance):
    """Serialize controllers; a second start must not replace a live PID registry."""
    import msvcrt
    path = state_path(instance).with_suffix(".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0, 2)
        if not handle.tell():
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError(f"Another controller is managing {instance}; retry after it finishes.") from exc
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def alive(state):
    return bool(state.get("pid") and state.get("created") and
                process_identity(state["pid"]) == state["created"])


def url_ready(url):
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            return response.status == 200
    except (OSError, ValueError):
        return False


def port_free(port):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def specifications(args):
    python = sys.executable
    if args.profile == "qa":
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        entries = []
        for name, version in manifest.items():
            if not re.fullmatch(r"[a-zA-Z0-9_-]+", name):
                raise ValueError("Invalid QA version name")
            source = Path(version["source"]).resolve()
            database = Path(version["database"]).resolve()
            if not database.is_file() or not (source / "streamlit_app.py").is_file():
                raise ValueError(f"Missing prepared QA source/database: {name}")
            entries.append(dict(name=name, cwd=str(source), port=int(version["port"]),
                command=[python, "-m", "streamlit", "run", str(source / "streamlit_app.py"),
                         "--server.address", "127.0.0.1", "--server.port", str(version["port"]),
                         "--server.headless", "true", "--browser.gatherUsageStats", "false"],
                url=f"http://127.0.0.1:{version['port']}/_stcore/health",
                env={"DATABASE_URL": "sqlite:///" + database.as_posix(), "PORTFOLIO_DEMO": "true",
                     "AGENT_SUPERVISOR_ENABLED": "true", "PYTHONPATH": str(source / "src")}))
        return entries
    entries = [
        dict(name="api", port=args.api_port, url=f"http://127.0.0.1:{args.api_port}/health",
             command=[python, "-m", "uvicorn", "executive_health_ai.api:app", "--app-dir", str(ROOT / "src"),
                      "--host", "127.0.0.1", "--port", str(args.api_port)]),
        dict(name="streamlit", port=args.ui_port, url=f"http://127.0.0.1:{args.ui_port}/_stcore/health",
             command=[python, "-m", "streamlit", "run", str(ROOT / "streamlit_app.py"),
                      "--server.address", "127.0.0.1", "--server.port", str(args.ui_port),
                      "--server.headless", "true", "--browser.gatherUsageStats", "false"]),
        dict(name="worker", command=[python, "-u", str(ROOT / "scripts/run_agent_worker.py")]),
    ]
    for item in entries:
        item["cwd"] = str(ROOT)
    return entries


def preflight(args, entries):
    previous = read_state(state_path(args.instance))
    if alive(previous):
        raise RuntimeError(f"{args.instance} is already running. Stop it first with stop_platform.ps1 -Instance {args.instance}.")
    ports = [entry["port"] for entry in entries if entry.get("port")]
    if len(ports) != len(set(ports)):
        raise RuntimeError("Service ports must be distinct.")
    for port in ports:
        if not port_free(port):
            raise RuntimeError(f"Port {port} is occupied. No unowned process was stopped; release it before startup.")


def stop(instance):
    path = state_path(instance)
    state = read_state(path)
    if alive(state):
        # Open and recheck the same process handle: never terminate a recycled PID.
        dll = kernel()
        handle = dll.OpenProcess(0x1001, False, state["pid"])
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            times = [wintypes.FILETIME() for _ in range(4)]
            if not dll.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
                raise ctypes.WinError(ctypes.get_last_error())
            created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            if created == state["created"] and not dll.TerminateProcess(handle, 0):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            dll.CloseHandle(handle)
    # Children hold process handles briefly while Windows tears down their job.
    deadline = time.monotonic() + 15
    while any(alive(item) for item in state.get("services", []) + state.get("processes", [])):
        if time.monotonic() > deadline:
            raise RuntimeError("Service cleanup timed out; inspect PID registry and logs.")
        time.sleep(.1)
    if state:
        state.update(status="stopped", stopped_at=time.time())
        write_state(path, state)
    print(f"Stopped {instance}; owned process tree released.")


def supervise(args, entries):
    job = own_process_tree()
    path = state_path(args.instance)
    state = dict(instance=args.instance, pid=os.getpid(), created=process_identity(os.getpid()),
                 started_at=time.time(), status="starting", token=args.token, services=[])
    write_state(path, state)
    children = []
    logs = RUNTIME / "logs" / args.instance
    logs.mkdir(parents=True, exist_ok=True)
    try:
        # Ollama is optional. An already-running Ollama is neither adopted nor stopped.
        if args.profile == "platform" and not url_ready("http://127.0.0.1:11434/api/tags"):
            executable = shutil.which("ollama")
            if executable and port_free(11434):
                entries = [dict(name="ollama", cwd=str(ROOT), command=[executable, "serve"],
                                port=11434, optional=True, url="http://127.0.0.1:11434/api/tags")] + entries
        for entry in entries:
            env = os.environ.copy()
            env.update(PYTHONPATH=str(ROOT / "src"), PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
            env.update(entry.get("env", {}))
            out, err = logs / f"{entry['name']}.stdout.log", logs / f"{entry['name']}.stderr.log"
            with out.open("ab") as stdout, err.open("ab") as stderr:
                child = subprocess.Popen(entry["command"], cwd=entry["cwd"], env=env,
                    stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, creationflags=NO_WINDOW)
            children.append((child, entry))
            state["services"].append(dict(name=entry["name"], pid=child.pid, created=process_identity(child.pid),
                command=entry["command"], cwd=entry["cwd"], port=entry.get("port"), stdout=str(out), stderr=str(err)))
            write_state(path, state)
        deadline = time.monotonic() + args.timeout
        while True:
            failed = [entry["name"] for child, entry in children if child.poll() is not None and not entry.get("optional")]
            if failed:
                raise RuntimeError(f"Service exited: {', '.join(failed)}. See {logs}")
            ready = all(not entry.get("url") or entry.get("optional") or url_ready(entry["url"]) for _, entry in children)
            if ready and time.time() - state["started_at"] >= 2:
                break
            if time.monotonic() > deadline:
                raise RuntimeError(f"Service readiness timeout. See {logs}")
            time.sleep(.25)
        state["status"] = "ready"
        state["processes"] = job_processes(job)
        write_state(path, state)
        print(f"Ready {args.instance}; supervisor={state['pid']}; local LLM is optional.", flush=True)
        while True:
            for child, entry in children:
                if child.poll() is not None and not entry.get("optional"):
                    raise RuntimeError(f"{entry['name']} exited ({child.returncode}); stopping the whole group.")
            time.sleep(.5)
    except BaseException as exc:
        state.update(status="failed", error=str(exc))
        write_state(path, state)
        raise
    # Process exit closes job (including on uncaught errors), killing descendants.


def start(args, entries):
    preflight(args, entries)
    path = state_path(args.instance)
    logs = RUNTIME / "logs" / args.instance
    logs.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    command = [sys.executable, "-u", str(Path(__file__).resolve()), "_supervise", *sys.argv[2:], "--token", token]
    with (logs / "supervisor.log").open("ab") as output:
        child = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                                 creationflags=NO_WINDOW)
    deadline = time.monotonic() + args.timeout + 10
    try:
        while time.monotonic() < deadline:
            state = read_state(path)
            # Windows venv python.exe redirects to a different actual Python PID.
            if state.get("token") == token and state.get("status") == "ready":
                print(json.dumps(state, indent=2))
                return
            if child.poll() is not None:
                raise RuntimeError(state.get("error", f"Supervisor exited. See {logs / 'supervisor.log'}"))
            time.sleep(.2)
        raise RuntimeError(f"Startup timed out. See {logs}")
    except BaseException:
        state = read_state(path)
        if state.get("token") == token:
            stop(args.instance)
        if child.poll() is None:
            subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
        child.wait(timeout=15)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status", "preflight", "_supervise"])
    parser.add_argument("--instance", default="platform")
    parser.add_argument("--profile", choices=["platform", "portfolio", "qa"], default="platform")
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--ui-port", type=int, default=8501)
    parser.add_argument("--manifest", default=str(RUNTIME / "neumorphism-v2/manifest.json"))
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--token", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()
    state_path(args.instance)  # Validate even before opening log paths.
    if args.action == "_supervise":
        supervise(args, specifications(args))
        return
    with instance_lock(args.instance):
        control(args)


def control(args):
    if args.action == "stop":
        stop(args.instance)
    elif args.action == "status":
        state = read_state(state_path(args.instance))
        state["running"] = alive(state)
        print(json.dumps(state, indent=2))
    else:
        entries = specifications(args)
        if args.action == "preflight":
            preflight(args, entries)
        else:
            start(args, entries)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
