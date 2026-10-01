"""Real Windows launcher acceptance, using a disposable copy of the Demo DB.

Run with .venv/Scripts/python.exe scripts/verify_launcher_lifecycle.py.
Requires free 8000/8501 and an existing data/portfolio_demo.db. Never seeds,
migrates or opens the formal database for writing. Console windows are hidden.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time

import service_processes as manager

ROOT = manager.ROOT
OUTPUT = ROOT / ".runtime/launcher-validation"
INSTANCE = "launcher-validation"
PYTHON = ROOT / ".venv/Scripts/python.exe"
POWERSHELL = shutil.which("pwsh.exe")


def wait(predicate, seconds=45):
    deadline = time.monotonic() + seconds
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("Timed out waiting for lifecycle transition")
        time.sleep(.1)


def command(*args):
    return subprocess.run([str(PYTHON), str(ROOT / "scripts/service_processes.py"), *args],
                          capture_output=True, text=True, timeout=90, creationflags=manager.NO_WINDOW)


def launch(label, shell, profile="portfolio"):
    log = OUTPUT / f"{label}.log"
    hwnd = OUTPUT / f"{label}.hwnd"
    hwnd.unlink(missing_ok=True)
    script = ROOT / f"scripts/start_{'portfolio_demo' if profile == 'portfolio' else 'platform'}.ps1"
    extra = f"-DatabasePath '{OUTPUT / 'demo.db'}'" if profile == "portfolio" else ""
    # A real (hidden) console allows actual CTRL_C_EVENT and WM_CLOSE testing.
    code = f'''
Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class ConsoleProbe {{ [DllImport("kernel32.dll")] public static extern IntPtr GetConsoleWindow(); }}'
[IO.File]::WriteAllText('{hwnd}', [ConsoleProbe]::GetConsoleWindow().ToInt64().ToString())
& '{script}' -NoBrowser -Instance {INSTANCE} {extra}
'''
    env = os.environ.copy()
    env.update(DATABASE_URL="sqlite:///" + (OUTPUT / "demo.db").as_posix(),
               LOCAL_LLM_ENABLED="false", PORTFOLIO_DEMO="true", AGENT_SUPERVISOR_ENABLED="true")
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    with log.open("wb") as out:
        proc = subprocess.Popen([shell, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", code],
                                cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                                creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup)
    try:
        wait(lambda: proc.poll() is not None or (
            manager.read_state(manager.state_path(INSTANCE)).get("status") == "ready" and
            "HealthOps ready" in log.read_text(errors="replace")), seconds=75)
        assert proc.poll() is None, log.read_text(errors="replace")
        state = manager.read_state(manager.state_path(INSTANCE))
        assert state["launcher"]["pid"] == proc.pid
        assert manager.url_ready("http://127.0.0.1:8501/_stcore/health")
        assert manager.url_ready("http://127.0.0.1:8000/docs")
        worker = next(s for s in state["services"] if s["name"] == "worker")
        assert manager.alive(worker) and worker["processes"]
        return proc, state, log, int(hwnd.read_text())
    except BaseException:
        proc.terminate()
        command("stop", "--instance", INSTANCE)
        raise


def released(proc, state):
    wait(lambda: manager.port_free(8501) and manager.port_free(8000))
    wait(lambda: not any(manager.alive(p) for p in state["processes"]))
    wait(lambda: not manager.state_path(INSTANCE).exists())
    proc.wait(timeout=30)


def ctrl_c(proc):
    # Isolate console attachment so the test runner can never signal its own
    # console. Generate a real CTRL_C_EVENT, not a simulated KeyboardInterrupt.
    code = f'''
import ctypes,time
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.FreeConsole()
assert k.AttachConsole({proc.pid}), ctypes.get_last_error()
assert k.SetConsoleCtrlHandler(None,True)
assert k.GenerateConsoleCtrlEvent(0,0), ctypes.get_last_error()
time.sleep(.5)
k.FreeConsole()
'''
    subprocess.run([sys._base_executable, "-c", code], check=True, timeout=10, creationflags=manager.NO_WINDOW)


def report(name, results):
    results[name] = "PASS"
    print(name + ": PASS", flush=True)
    (OUTPUT / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


def main():
    assert os.name == "nt" and POWERSHELL, "Windows with pwsh is required for acceptance"
    assert manager.port_free(8000) and manager.port_free(8501), "Stop the current platform before acceptance"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    formal = ROOT / "data/portfolio_demo.db"
    before = hashlib.sha256(formal.read_bytes()).hexdigest()
    with sqlite3.connect(formal.as_uri() + "?mode=ro", uri=True) as src, sqlite3.connect(OUTPUT / "demo.db") as dst:
        src.backup(dst)
    results = {}
    active = None
    try:
        # A, B, C and G: both PowerShell families, Ctrl+C, real close, stop.
        for index, (shell, mode, profile) in enumerate([
            (POWERSHELL, "ctrl_c", "portfolio"),
            ("powershell.exe", "window_close", "platform"),
            (POWERSHELL, "stop_script", "portfolio"),
        ], 1):
            active, state, log, hwnd = launch(f"cycle-{index}-{mode}", shell, profile)
            if mode == "ctrl_c":
                ctrl_c(active)
            elif mode == "window_close":
                user = ctypes.WinDLL("user32", use_last_error=True)
                user.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
                assert hwnd and user.PostMessageW(hwnd, 0x0010, 0, 0), "WM_CLOSE failed"
            else:
                result = subprocess.run([shell, "-NoProfile", "-File", str(ROOT / "scripts/stop_platform.ps1"),
                                         "-Instance", INSTANCE], capture_output=True, text=True, timeout=60,
                                        creationflags=manager.NO_WINDOW)
                assert result.returncode == 0, result.stderr
            released(active, state)
            active = None
            if mode == "ctrl_c":
                assert "HealthOps stopped cleanly." in log.read_text(errors="replace"), log.read_text(errors="replace")
            report(f"cycle_{index}_{mode}", results)

        # D: a real orphan FastAPI (no supervisor/PID record), with its venv
        # redirector and real listener, must be reclaimed by the next launch.
        env = os.environ.copy()
        env.update(DATABASE_URL="sqlite:///" + (OUTPUT / "demo.db").as_posix(), LOCAL_LLM_ENABLED="false")
        with (OUTPUT / "legacy-api.log").open("wb") as out:
            legacy = subprocess.Popen([str(PYTHON), "-m", "uvicorn", "executive_health_ai.api:app",
                                       "--app-dir", str(ROOT / "src"), "--host", "127.0.0.1", "--port", "8000"],
                                      cwd=ROOT, env=env, stdout=out, stderr=out, creationflags=manager.NO_WINDOW)
        try:
            wait(lambda: manager.url_ready("http://127.0.0.1:8000/docs"))
            active, state, _, _ = launch("orphan-recovery", POWERSHELL)
            assert legacy.poll() is not None, "Legacy FastAPI survived replacement"
            result = command("stop", "--instance", INSTANCE)
            assert result.returncode == 0, result.stderr
            released(active, state)
            active = None
        finally:
            if legacy.poll() is None:
                # Exact process ownership is already known from Popen.
                snapshot = manager.windows_snapshot()
                owner = next(p for p in snapshot["processes"] if p["pid"] == legacy.pid)
                manager.terminate_tree(owner, snapshot["processes"])
        report("orphan_fastapi_recovered", results)

        # E: a stale record deliberately names this live test PID with the wrong
        # creation time. Cleanup must remove the record without touching us.
        manager.write_state(manager.state_path(INSTANCE), dict(pid=os.getpid(), created=1, services=[]))
        result = command("cleanup", "--instance", INSTANCE)
        assert result.returncode == 0, result.stderr
        assert not manager.state_path(INSTANCE).exists()
        assert manager.process_identity(os.getpid())
        report("stale_pid_removed", results)

        # F: use the project interpreter AND put project-looking text inside
        # python -c. Neither is proof that an external port owner is HealthOps.
        marker = str(ROOT / "scripts/run_agent_worker.py")
        external = subprocess.Popen([str(PYTHON), "-c",
            "import socket,time; s=socket.socket(); s.bind(('127.0.0.1',8000)); s.listen(); time.sleep(180)", marker],
            creationflags=manager.NO_WINDOW)
        try:
            wait(lambda: not manager.port_free(8000))
            for action in ("launch", "cleanup"):
                result = command(action, "--instance", INSTANCE, "--profile", "portfolio")
                assert result.returncode != 0
                assert "Port 8000 is occupied by an external process." in result.stderr, result.stderr
                assert all(label in result.stderr for label in ("PID:", "Process name:", "Command line:"))
                assert external.poll() is None and not manager.port_free(8000)
                assert "Stopped" not in result.stdout
        finally:
            snapshot = manager.windows_snapshot()
            owner = next(p for p in snapshot["processes"] if p["pid"] == external.pid)
            manager.terminate_tree(owner, snapshot["processes"])
            external.wait(timeout=15)
        wait(lambda: manager.port_free(8000))
        report("external_process_protected", results)
    finally:
        if active and active.poll() is None:
            active.terminate()
        command("stop", "--instance", INSTANCE)
        assert hashlib.sha256(formal.read_bytes()).hexdigest() == before, "Formal database changed"
    report("formal_database_unchanged", results)


if __name__ == "__main__":
    main()
