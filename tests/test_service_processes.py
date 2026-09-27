"""Real Windows process tests, including grandchild cleanup and PID reuse safety."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "scripts/service_processes.py"
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows Job Object lifecycle")
spec = importlib.util.spec_from_file_location("service_processes", MANAGER)
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)


def unused_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_until(predicate):
    deadline = time.monotonic() + 15
    while not predicate():
        assert time.monotonic() < deadline, "Process/port did not settle"
        time.sleep(.1)


@pytest.fixture
def group(tmp_path):
    instance = "test-" + uuid.uuid4().hex[:12]
    source = tmp_path / "source with spaces"
    module = source / "src/streamlit"
    module.mkdir(parents=True)
    (module / "__init__.py").touch()
    (source / "streamlit_app.py").touch()
    (source / "qa.db").touch()
    child_port = unused_port()
    port = unused_port()
    # A subprocess with default flags mimics a venv redirector's additional child.
    (module / "__main__.py").write_text('''
import ctypes, json, os, subprocess, sys, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
child = subprocess.Popen([sys.executable, '-c', "import socket,time; s=socket.socket(); s.bind(('127.0.0.1', CHILD_PORT)); s.listen(); time.sleep(300)"])
Path('probe.json').write_text(json.dumps({'console': int(ctypes.windll.kernel32.GetConsoleWindow()), 'pid': os.getpid(), 'child': child.pid}))
print('stdout captured', flush=True)
print('stderr captured', file=sys.stderr, flush=True)
if Path('crash').exists():
    time.sleep(1)
    sys.exit(9)
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b'ok')
    def log_message(self, *args): pass
port = int(sys.argv[sys.argv.index('--server.port')+1])
HTTPServer(('127.0.0.1', port), Handler).serve_forever()
'''.replace("CHILD_PORT", str(child_port)), encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"old": dict(source=str(source), database=str(source / "qa.db"), port=port)}))
    args = ["--instance", instance, "--profile", "qa", "--manifest", str(manifest), "--timeout", "8"]

    def command(action):
        return subprocess.run([sys.executable, str(MANAGER), action, *args], capture_output=True,
                              text=True, timeout=35, creationflags=manager.NO_WINDOW)
    yield instance, source, port, child_port, command
    command("stop")


def test_start_hidden_logs_stop_entire_tree_and_restart(group):
    instance, source, port, child_port, command = group
    for _ in range(2):
        result = command("start")
        assert result.returncode == 0, result.stderr
        state = json.loads(result.stdout)
        probe = json.loads((source / "probe.json").read_text())
        assert probe["console"] == 0
        assert manager.url_ready(f"http://127.0.0.1:{port}/_stcore/health")
        assert not manager.port_free(child_port)
        assert "stdout captured" in Path(state["services"][0]["stdout"]).read_text()
        assert "stderr captured" in Path(state["services"][0]["stderr"]).read_text()
        assert command("stop").returncode == 0
        wait_until(lambda: manager.port_free(port) and manager.port_free(child_port))
        assert manager.process_identity(probe["pid"]) is None
        assert manager.process_identity(probe["child"]) is None


def test_start_failure_releases_grandchild_port(group):
    _, source, port, child_port, command = group
    (source / "crash").touch()
    result = command("start")
    assert result.returncode != 0
    assert "Service exited" in result.stderr
    wait_until(lambda: manager.port_free(port) and manager.port_free(child_port))


def test_supervisor_crash_releases_every_child(group):
    _, _, port, child_port, command = group
    result = command("start")
    assert result.returncode == 0, result.stderr
    state = json.loads(result.stdout)
    dll = manager.kernel()
    handle = dll.OpenProcess(1, False, state["pid"])
    try:
        assert dll.TerminateProcess(handle, 17)
    finally:
        dll.CloseHandle(handle)
    wait_until(lambda: manager.port_free(port) and manager.port_free(child_port))


def test_duplicate_start_keeps_existing_registry_and_service(group):
    _, _, port, _, command = group
    first = command("start")
    assert first.returncode == 0, first.stderr
    before = json.loads(first.stdout)
    assert command("start").returncode != 0
    after = json.loads(command("status").stdout)
    assert after["pid"] == before["pid"] and after["running"]
    assert manager.url_ready(f"http://127.0.0.1:{port}")


def test_occupied_unowned_port_is_not_stopped(group):
    _, _, port, _, command = group
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))
        sock.listen()
        result = command("start")
        assert result.returncode != 0 and "occupied" in result.stderr
        assert not manager.port_free(port)


def test_stale_pid_record_never_terminates_reused_process(group):
    instance, _, _, _, command = group
    manager.write_state(manager.state_path(instance), dict(pid=os.getpid(), created=1, services=[]))
    assert command("stop").returncode == 0
    assert manager.process_identity(os.getpid()) is not None


def test_instance_name_cannot_escape_runtime_directory():
    with pytest.raises(ValueError):
        manager.state_path("../outside")


def test_pid_registry_replacement_waits_for_windows_reader(tmp_path):
    from threading import Timer
    path=tmp_path/'process.json'
    manager.write_state(path,{'pid':1})
    reader=path.open('r',encoding='utf-8')
    release=Timer(.15,reader.close)
    release.start()
    try:
        manager.write_state(path,{'pid':2})
        assert manager.read_state(path)=={'pid':2}
    finally:
        release.cancel();reader.close()


def test_pid_registry_persistent_lock_preserves_previous_state(tmp_path):
    path=tmp_path/'process.json'
    manager.write_state(path,{'pid':1})
    with path.open('r',encoding='utf-8'):
        with pytest.raises(PermissionError):
            manager.write_state(path,{'pid':2})
    assert manager.read_state(path)=={'pid':1}
