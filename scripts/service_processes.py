"""Windows background service groups: no consoles, durable PIDs, owned-tree cleanup.

The supervisor owns a Windows Job Object with KILL_ON_JOB_CLOSE. Its services,
venv Python redirectors and all descendants die even if the supervisor crashes.
No database, API or worker behavior is implemented here.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import shutil
import signal
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
    # A controller can be reading the PID registry while the supervisor writes
    # it. Windows readers briefly deny rename/delete sharing. Keep the previous
    # complete registry until replacement succeeds; never truncate it in place.
    deadline = time.monotonic() + 2
    while True:
        try:
            os.replace(temp, path)
            return
        except PermissionError:
            if os.name != 'nt' or time.monotonic() >= deadline:
                raise
            time.sleep(.02)


def read_state(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def windows_snapshot():
    """Read command lines and listener owners, without inspecting environments."""
    script = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$processes = @(Get-CimInstance Win32_Process | ForEach-Object {
    @{pid=[int]$_.ProcessId; parent=[int]$_.ParentProcessId; name=$_.Name;
      command=$_.CommandLine; executable=$_.ExecutablePath;
      created=if ($_.CreationDate) { $_.CreationDate.ToFileTimeUtc() } else { 0 }}
})
$listeners = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { @{port=[int]$_.LocalPort; pid=[int]$_.OwningProcess} })
@{processes=$processes; listeners=$listeners} | ConvertTo-Json -Depth 4 -Compress
'''
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand",
         base64.b64encode(script.encode("utf-16le")).decode("ascii")],
        capture_output=True, encoding="utf-8", errors="replace", check=True, timeout=30,
        creationflags=NO_WINDOW)
    snapshot = json.loads(result.stdout.lstrip("\ufeff"))
    for process in snapshot["processes"]:
        created = process_identity(process["pid"])
        # CIM truncates the final 100ns digit. Do not attach a new identity to
        # an old command line if the PID was recycled during enumeration.
        process["created"] = created if created and created // 10 == process["created"] // 10 else None
    return snapshot


def command_args(command):
    if not command:
        return []
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    shell.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
    count = ctypes.c_int()
    pointer = shell.CommandLineToArgvW(command, ctypes.byref(count))
    if not pointer:
        return []
    try:
        return list(pointer[:count.value])
    finally:
        dll = kernel()
        dll.LocalFree.argtypes = [ctypes.c_void_p]
        dll.LocalFree(pointer)


def same_path(value, expected):
    # A relative argument is not proof of a process's working directory.
    return bool(value and Path(value).is_absolute() and
                os.path.normcase(os.path.normpath(value)) == os.path.normcase(str(expected)))


def python_call(process):
    """Return the interpreter arguments and actual Python entry point."""
    args = command_args(process.get("command"))
    if not args or Path(args[0]).name.lower() not in ("python.exe", "pythonw.exe"):
        return [], []
    # Parse the Python entry point; quoted paths in `python -c ...` are data,
    # not evidence of ownership.
    tail = args[1:]
    while tail and tail[0] in ("-u", "-B", "-E", "-s", "-I", "-X", "utf8"):
        tail = tail[1:]
    return args, tail


def project_supervisor(process, instance):
    _, tail = python_call(process)
    if len(tail) < 4 or not same_path(tail[0], ROOT / "scripts/service_processes.py") or tail[1] != "_supervise":
        return False
    return any(tail[index:index + 2] == ["--instance", instance] for index in range(2, len(tail) - 1))


def project_service(process):
    """Require an exact executable/script argument, never a substring match."""
    args, tail = python_call(process)
    if not tail:
        return False
    if same_path(tail[0], ROOT / "scripts/run_agent_worker.py"):
        return True
    if same_path(tail[0], ROOT / "scripts/service_processes.py"):
        return len(tail) > 1 and tail[1] == "_supervise" and "qa" not in tail
    if tail[:3] == ["-m", "streamlit", "run"]:
        return len(tail) > 3 and same_path(tail[3], ROOT / "streamlit_app.py")
    if tail[:3] == ["-m", "uvicorn", "executive_health_ai.api:app"]:
        if "--app-dir" in tail:
            index = tail.index("--app-dir") + 1
            return index < len(tail) and same_path(tail[index], ROOT / "src")
        return same_path(args[0], ROOT / ".venv/Scripts/python.exe")
    return False


def terminate_identity(record):
    """Check creation time on the same handle used for termination."""
    if not alive(record):
        return
    dll = kernel()
    handle = dll.OpenProcess(0x1001, False, record["pid"])
    if not handle:
        if not alive(record):
            return
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        times = [wintypes.FILETIME() for _ in range(4)]
        if not dll.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
            raise ctypes.WinError(ctypes.get_last_error())
        created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        if created == record["created"] and not dll.TerminateProcess(handle, 0):
            if alive(record):
                raise ctypes.WinError(ctypes.get_last_error())
    finally:
        dll.CloseHandle(handle)


def terminate_tree(root, processes):
    descendants = [root]
    for parent in descendants:
        descendants.extend(p for p in processes if p.get("created") and
                           p["parent"] == parent["pid"] and p["created"] >= parent["created"] and
                           p["pid"] not in {item["pid"] for item in descendants})
    for process in descendants:  # stop parents before they can spawn more children
        terminate_identity(process)
    return descendants


def occupied_message(port, snapshot):
    owners = {p["pid"] for p in snapshot["listeners"] if p["port"] == port}
    details = [f"PID: {p['pid']}; Process name: {p['name']}; Command line: {p.get('command') or '<unavailable>'}"
               for p in snapshot["processes"] if p["pid"] in owners]
    return f"Port {port} is occupied by an external process.\n" + "\n".join(details or ["Owner unavailable; no process was stopped."])


def wait_released(records, ports, timeout=15):
    deadline = time.monotonic() + timeout
    while any(alive(p) for p in records) or any(not port_free(port) for port in ports):
        if time.monotonic() >= deadline:
            snapshot = windows_snapshot()
            errors = [occupied_message(port, snapshot) for port in ports if not port_free(port)]
            raise RuntimeError("\n".join(errors) or "Owned process cleanup timed out.")
        time.sleep(.1)


def remove_registry(path, token):
    if read_state(path).get("token") == token:
        path.unlink(missing_ok=True)


def cleanup_project(args):
    """Reconcile both production profiles and positively identified legacy trees."""
    snapshot = windows_snapshot()
    processes = snapshot["processes"]
    ports = {args.api_port, args.ui_port}
    # Reject external owners before stopping any current HealthOps instance.
    for port in ports:
        for listener in (p for p in snapshot["listeners"] if p["port"] == port):
            owner = next((p for p in processes if p["pid"] == listener["pid"]), None)
            if not owner or not project_service(owner) or not owner.get("created"):
                raise RuntimeError(occupied_message(port, snapshot))
    records = []
    registries = []
    for path in (RUNTIME / "processes").glob("*.json"):
        state = read_state(path)
        # QA groups have their own explicitly scoped stop command.
        if state.get("profile") == "qa":
            continue
        if not (state.get("profile") in ("platform", "portfolio") or
                path.stem in ("platform", "portfolio", args.instance) or
                any(s.get("name") == "worker" and same_path(s.get("cwd"), ROOT)
                    for s in state.get("services", []))):
            continue
        owner = next((p for p in processes if p["pid"] == state.get("pid") and
                      p.get("created") == state.get("created")), None)
        if owner and project_service(owner):
            records.extend(terminate_tree(owner, processes))
        if owner:
            ports.update(s["port"] for s in state.get("services", []) if s.get("port") and s.get("name") != "ollama")
        registries.append((path, state.get("token")))
    for process in processes:
        if process.get("created") and project_service(process):
            records.extend(terminate_tree(process, processes))
    wait_released(records, ports)
    for path, token in registries:
        remove_registry(path, token)


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
        deadline = time.monotonic() + 90
        while True:
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"Another controller is managing {instance}; retry after it finishes.") from exc
                time.sleep(.1)
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
            raise RuntimeError(occupied_message(port, windows_snapshot()))


def stop(instance, token=None):
    path = state_path(instance)
    state = read_state(path)
    if token is not None and state.get("token") != token:
        return  # An older launcher's finally must never stop its replacement.
    records = state.get("services", []) + state.get("processes", [])
    snapshot = windows_snapshot() if alive(state) or any(alive(p) for p in records) else None
    if alive(state):
        owner = next((p for p in snapshot["processes"] if p["pid"] == state["pid"] and
                      p.get("created") == state["created"]), None)
        # The supervisor's exact script, action and instance are required, even
        # if a corrupt registry happens to contain an external process's PID.
        if not owner or not project_supervisor(owner, instance):
            raise RuntimeError(f"PID {state['pid']} is not this project's supervisor; no process was stopped.")
        terminate_identity(state)
    # A pre-Job-Object launcher may have died while its registered services
    # remained alive. Revalidate exact commands before reclaiming those trees.
    if snapshot:
        for service in state.get("services", []):
            process = next((p for p in snapshot["processes"] if p["pid"] == service.get("pid") and
                            p.get("created") == service.get("created")), None)
            if not process or not alive(process):
                continue
            matches_record = command_args(process.get("command")) == service.get("command")
            if matches_record and (project_service(process) or same_path(state.get("root"), ROOT)):
                records.extend(terminate_tree(process, snapshot["processes"]))
    ports = [s["port"] for s in state.get("services", []) if s.get("port")]
    wait_released(records, ports)
    remove_registry(path, state.get("token"))
    print(f"Stopped {instance}; owned process tree released.")


def supervise(args, entries):
    job = own_process_tree()
    path = state_path(args.instance)
    state = dict(instance=args.instance, pid=os.getpid(), created=process_identity(os.getpid()),
                 started_at=time.time(), status="starting", token=args.token, services=[],
                 profile=args.profile, root=str(ROOT),
                 launcher=dict(pid=args.launcher_pid, created=args.launcher_created),
                 controller=dict(pid=args.controller_pid, created=args.controller_created))
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
            if any(item.get("pid") and not alive(item) for item in (state["launcher"], state["controller"])):
                raise RuntimeError("Launcher exited during startup.")
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
        # In a Windows venv the Popen PID can be a redirector, not the actual
        # Python listener. Keep both the service root and every real descendant.
        snapshot = windows_snapshot()
        for service in state["services"]:
            family = {service["pid"]}
            for _ in range(len(snapshot["processes"])):
                found = {p["pid"] for p in snapshot["processes"] if p["parent"] in family}
                if found <= family:
                    break
                family.update(found)
            service["processes"] = [p for p in state["processes"] if p["pid"] in family]
            if service.get("port"):
                service["listener_pids"] = [p["pid"] for p in snapshot["listeners"] if p["port"] == service["port"]]
        write_state(path, state)
        print(f"Ready {args.instance}; supervisor={state['pid']}; local LLM is optional.", flush=True)
        refreshed = time.monotonic()
        while True:
            if any(item.get("pid") and not alive(item) for item in (state["launcher"], state["controller"])):
                break
            for child, entry in children:
                if child.poll() is not None and not entry.get("optional"):
                    raise RuntimeError(f"{entry['name']} exited ({child.returncode}); stopping the whole group.")
            if time.monotonic() - refreshed >= 2:
                current = job_processes(job)
                if current != state["processes"]:
                    state["processes"] = current
                    write_state(path, state)
                refreshed = time.monotonic()
            time.sleep(.5)
    except BaseException as exc:
        state.update(status="failed", error=str(exc))
        write_state(path, state)
        raise
    finally:
        # A hidden supervisor survives console close long enough to verify
        # cleanup. If it is itself killed, KILL_ON_JOB_CLOSE is the backstop.
        records = job_processes(job)
        for process in records:
            terminate_identity(process)
        wait_released(records, [entry["port"] for entry in entries if entry.get("port")])
        if state.get("status") != "failed":
            remove_registry(path, args.token)


def start(args, entries):
    preflight(args, entries)
    path = state_path(args.instance)
    logs = RUNTIME / "logs" / args.instance
    logs.mkdir(parents=True, exist_ok=True)
    token = args.token or uuid.uuid4().hex
    command = [sys.executable, "-u", str(Path(__file__).resolve()), "_supervise",
               "--instance", args.instance, "--profile", args.profile,
               "--api-port", str(args.api_port), "--ui-port", str(args.ui_port),
               "--manifest", args.manifest, "--timeout", str(args.timeout), "--token", token]
    for name in ("launcher_pid", "launcher_created", "controller_pid", "controller_created"):
        command.extend(["--" + name.replace("_", "-"), str(getattr(args, name))])
    with (logs / "supervisor.log").open("ab") as output:
        child = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                                 creationflags=NO_WINDOW)
    deadline = time.monotonic() + args.timeout + 10
    try:
        while time.monotonic() < deadline:
            state = read_state(path)
            # Windows venv python.exe redirects to a different actual Python PID.
            if state.get("token") == token and state.get("status") == "ready":
                if args.action != "launch":
                    print(json.dumps(state, indent=2))
                return state
            if child.poll() is not None:
                raise RuntimeError(state.get("error", f"Supervisor exited. See {logs / 'supervisor.log'}"))
            time.sleep(.2)
        raise RuntimeError(f"Startup timed out. See {logs}")
    except BaseException:
        state = read_state(path)
        if state.get("token") == token:
            stop(args.instance, token)
        if child.poll() is None:
            subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
        child.wait(timeout=15)
        raise


def launch(args):
    """Foreground lifecycle; never hold the controller lock while waiting."""
    args.token = args.token or uuid.uuid4().hex
    args.launcher_created = process_identity(args.launcher_pid) if args.launcher_pid else 0
    args.controller_pid = os.getpid()
    args.controller_created = process_identity(os.getpid())
    state = None
    try:
        with instance_lock("_healthops"):
            cleanup_project(args)
            state = start(args, specifications(args))
        print(f"Streamlit: http://127.0.0.1:{args.ui_port}", flush=True)
        print(f"FastAPI: http://127.0.0.1:{args.api_port}/docs; Agent worker: running", flush=True)
        print("HealthOps ready. Keep this launcher open; Ctrl+C stops the platform.", flush=True)
        if args.open_browser:
            os.startfile(f"http://127.0.0.1:{args.ui_port}")
        while alive(state):
            time.sleep(.25)
        latest = read_state(state_path(args.instance))
        if latest.get("token") == args.token and latest.get("status") == "failed":
            raise RuntimeError(latest.get("error", "HealthOps services failed."))
    except KeyboardInterrupt:
        pass
    finally:
        # A second Ctrl+C must not interrupt the teardown in progress.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, signal.SIG_IGN)
        if state or read_state(state_path(args.instance)).get("token") == args.token:
            print("Stopping HealthOps...", flush=True)
            with instance_lock("_healthops"):
                stop(args.instance, args.token)
            print("HealthOps stopped cleanly.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "launch", "cleanup", "stop", "status", "preflight", "_supervise"])
    parser.add_argument("--instance", default="platform")
    parser.add_argument("--profile", choices=["platform", "portfolio", "qa"], default="platform")
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--ui-port", type=int, default=8501)
    parser.add_argument("--manifest", default=str(RUNTIME / "neumorphism-v2/manifest.json"))
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--token", default="", help=argparse.SUPPRESS)
    parser.add_argument("--launcher-pid", type=int, default=0)
    parser.add_argument("--launcher-created", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--controller-pid", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--controller-created", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    state_path(args.instance)  # Validate even before opening log paths.
    if args.action == "_supervise":
        supervise(args, specifications(args))
        return
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal.default_int_handler)
    if args.action == "launch":
        launch(args)
        return
    with instance_lock("_healthops"):
        control(args)


def control(args):
    if args.action == "stop":
        stop(args.instance, args.token or None)
    elif args.action == "cleanup":
        cleanup_project(args)
        print(f"Stopped {args.instance}; owned process tree released.")
    elif args.action == "status":
        state = read_state(state_path(args.instance))
        state["running"] = alive(state)
        print(json.dumps(state, indent=2))
    else:
        entries = specifications(args)
        if args.action == "preflight":
            preflight(args, entries)
        else:
            if args.profile != "qa":
                cleanup_project(args)
            if args.launcher_pid:
                args.launcher_created = process_identity(args.launcher_pid)
            start(args, entries)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
