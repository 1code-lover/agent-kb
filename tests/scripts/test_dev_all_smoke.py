from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from tests.scripts._startup_smoke_lock import acquire_startup_smoke_lock

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV_ALL_SCRIPT = REPO_ROOT / "scripts" / "dev-all.ps1"


def _find_free_port(start: int, end: int) -> int:
    """Pick a free loopback port from a stable non-ephemeral range."""
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            sock.listen(1)
            return port
    raise AssertionError(f"No free loopback port in range {start}-{end}")


def _wait_for_http_json(url: str, *, timeout_seconds: float = 60.0) -> dict:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                payload = response.read().decode("utf-8")
                return json.loads(payload)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(1)
    raise AssertionError(f"Timed out waiting for JSON response from {url}: {last_error}")


def _wait_for_port_closed(port: int, *, timeout_seconds: float = 30.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return
        time.sleep(1)
    raise AssertionError(f"Port {port} did not close within {timeout_seconds} seconds")


def _wait_for_file(path: Path, *, timeout_seconds: float = 60.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if path.exists():
            return
        time.sleep(1)
    raise AssertionError(f"Timed out waiting for file: {path}")


def _wait_for_runtime_event(log_path: Path, event: str, *, timeout_seconds: float = 90.0) -> dict:
    deadline = time.time() + timeout_seconds
    last_payload = ""
    while time.time() < deadline:
        if log_path.exists():
            content = log_path.read_text(encoding="utf-8", errors="replace")
            last_payload = content
            for line in reversed([item for item in content.splitlines() if item.strip()]):
                data = json.loads(line)
                if data.get("event") == event:
                    return data
        time.sleep(1)
    raise AssertionError(f"Timed out waiting for desktop runtime event {event} in {log_path}: {last_payload[-1000:]}")


@pytest.mark.slow
@pytest.mark.skipif(sys.platform != "win32", reason="dev-all.ps1 smoke is Windows-specific")
def test_dev_all_smoke_starts_headless_desktop_with_isolated_runtime_root() -> None:
    with acquire_startup_smoke_lock(REPO_ROOT):
        backend_port = _find_free_port(20000, 29999)
        frontend_port = _find_free_port(30000, 39999)

        desktop_pid_file = REPO_ROOT / ".dev-runtime" / f"desktop-{backend_port}-{frontend_port}.pid"
        desktop_log = REPO_ROOT / "logs" / f"desktop_out-{backend_port}-{frontend_port}.log"
        temp_runtime_root = Path(tempfile.mkdtemp(prefix="agent-kb-desktop-smoke-"))
        runtime_log = temp_runtime_root / "storage" / "logs" / "desktop_runtime.log"

        start_cmd = [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(DEV_ALL_SCRIPT),
            "-BackendPort",
            str(backend_port),
            "-FrontendPort",
            str(frontend_port),
        ]
        stop_cmd = [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(DEV_ALL_SCRIPT),
            "-Stop",
            "-BackendPort",
            str(backend_port),
            "-FrontendPort",
            str(frontend_port),
        ]

        env = os.environ.copy()
        env["KB_DESKTOP_HEADLESS"] = "1"
        env["KB_RUNTIME_ROOT"] = str(temp_runtime_root)

        launcher = subprocess.Popen(
            start_cmd,
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

        try:
            health = _wait_for_http_json(f"http://127.0.0.1:{backend_port}/api/health")
            assert health.get("code") == 0

            _wait_for_file(desktop_pid_file)
            assert int(desktop_pid_file.read_text(encoding="utf-8").strip()) > 0
            _wait_for_file(desktop_log)
            _wait_for_file(runtime_log)

            ready_event = _wait_for_runtime_event(runtime_log, "desktop_app_ready")
            assert str(runtime_log) in ready_event.get("log_file", "")

            resolved_event = _wait_for_runtime_event(runtime_log, "renderer_resolved")
            assert resolved_event.get("headless") is True
            assert resolved_event.get("value") == f"http://127.0.0.1:{frontend_port}"
            assert resolved_event.get("source") in {"kb-env", "northagent-env", "thinkrag-env", "foxglove-env", "legacy-env"}

            loaded_event = _wait_for_runtime_event(runtime_log, "renderer_loaded")
            assert loaded_event.get("headless") is True
            assert loaded_event.get("url", "").startswith(f"http://127.0.0.1:{frontend_port}")

        finally:
            if launcher.poll() is None:
                launcher.kill()
                launcher.wait(timeout=10)

            stopped = subprocess.run(
                stop_cmd,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
                check=False,
            )
            assert stopped.returncode == 0, stopped.stdout + "\n" + stopped.stderr
            _wait_for_port_closed(backend_port)
            _wait_for_port_closed(frontend_port)
            assert not desktop_pid_file.exists(), f"desktop pid file should be removed: {desktop_pid_file}"
            shutil.rmtree(temp_runtime_root, ignore_errors=True)


