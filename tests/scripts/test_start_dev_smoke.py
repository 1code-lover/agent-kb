from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from tests.scripts._startup_smoke_lock import acquire_startup_smoke_lock

REPO_ROOT = Path(__file__).resolve().parents[2]
START_DEV_SCRIPT = REPO_ROOT / "start_dev.ps1"


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


def _wait_for_http_text(url: str, *, timeout_seconds: float = 60.0) -> str:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                return response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            time.sleep(1)
    raise AssertionError(f"Timed out waiting for text response from {url}: {last_error}")


def _wait_for_port_closed(port: int, *, timeout_seconds: float = 30.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return
        time.sleep(1)
    raise AssertionError(f"Port {port} did not close within {timeout_seconds} seconds")


@pytest.mark.slow
@pytest.mark.skipif(sys.platform != "win32", reason="start_dev.ps1 smoke is Windows-specific")
def test_start_dev_smoke_uses_custom_ports_without_clobbering_default_runtime_files() -> None:
    with acquire_startup_smoke_lock(REPO_ROOT):
        backend_port = _find_free_port(20000, 29999)
        frontend_port = _find_free_port(30000, 39999)

        backend_pid_file = REPO_ROOT / ".dev-runtime" / f"backend-{backend_port}.pid"
        frontend_pid_file = REPO_ROOT / ".dev-runtime" / f"frontend-{frontend_port}.pid"
        backend_log = REPO_ROOT / "logs" / f"backend_out-{backend_port}.log"
        frontend_log = REPO_ROOT / "logs" / f"frontend_out-{frontend_port}.log"

        start_cmd = [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(START_DEV_SCRIPT),
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
            str(START_DEV_SCRIPT),
            "-Stop",
            "-BackendPort",
            str(backend_port),
            "-FrontendPort",
            str(frontend_port),
        ]

        launcher = subprocess.Popen(
            start_cmd,
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        try:
            health = _wait_for_http_json(f"http://127.0.0.1:{backend_port}/api/health")
            assert health.get("code") == 0

            index_html = _wait_for_http_text(f"http://127.0.0.1:{frontend_port}/")
            assert '<div id="root"></div>' in index_html
            assert '/src/main.jsx' in index_html

            main_module = _wait_for_http_text(f"http://127.0.0.1:{frontend_port}/src/main.jsx")
            assert 'from "/node_modules/react/jsx-dev-runtime.js"' in main_module
            assert 'from "/node_modules/react/index.js"' in main_module
            assert 'from "/node_modules/react-dom/client.js"' in main_module
            assert 'from "/node_modules/@tanstack/react-query/build/modern/index.js"' in main_module

            assert backend_pid_file.exists(), f"missing backend pid file: {backend_pid_file}"
            assert frontend_pid_file.exists(), f"missing frontend pid file: {frontend_pid_file}"
            assert int(backend_pid_file.read_text(encoding="utf-8").strip()) > 0
            assert int(frontend_pid_file.read_text(encoding="utf-8").strip()) > 0
            assert backend_log.exists(), f"missing backend log: {backend_log}"
            assert frontend_log.exists(), f"missing frontend log: {frontend_log}"

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
                timeout=120,
                check=False,
            )
            assert stopped.returncode == 0, stopped.stdout + "\n" + stopped.stderr
            _wait_for_port_closed(backend_port)
            _wait_for_port_closed(frontend_port)
            assert not backend_pid_file.exists(), f"backend pid file should be removed: {backend_pid_file}"
            assert not frontend_pid_file.exists(), f"frontend pid file should be removed: {frontend_pid_file}"
