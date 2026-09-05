from __future__ import annotations

import argparse
import http.client
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMAGE_TAG = "agent-kb-runtime-smoke:local"
DEFAULT_INSTALL_PROFILE = "runtime"
DEFAULT_CONTAINER_PORT = 18080
DEFAULT_HEALTH_PATH = "/api/health"
DEFAULT_COMPLETION_TIMEOUT = 600.0
DOCKER_INFO_COMMAND = ["docker", "info", "--format", "{{.ServerVersion}}"]


TRANSIENT_HTTP_JSON_ERRORS = (
    urllib.error.URLError,
    TimeoutError,
    json.JSONDecodeError,
    http.client.RemoteDisconnected,
    ConnectionResetError,
)


def wait_for_http_json(url: str, *, timeout_seconds: float = 120.0) -> dict:
    """Poll a JSON endpoint until it responds or timeout expires."""
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                payload = response.read().decode("utf-8")
                return json.loads(payload)
        except TRANSIENT_HTTP_JSON_ERRORS as exc:
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"Timed out waiting for JSON response from {url}: {last_error}")


def normalize_runtime_mode(raw_mode: str | None) -> str:
    normalized = str(raw_mode or "api").strip().lower()
    return normalized or "api"


def infer_default_install_profile(*, app_runtime_mode: str) -> str:
    runtime_mode = normalize_runtime_mode(app_runtime_mode)
    if runtime_mode == "eval":
        return "eval"
    if runtime_mode == "prod":
        return "prod"
    return DEFAULT_INSTALL_PROFILE


def resolve_install_profile(raw_install_profile: str | None, *, app_runtime_mode: str) -> str:
    normalized = str(raw_install_profile or "").strip().lower()
    if normalized:
        return normalized
    return infer_default_install_profile(app_runtime_mode=app_runtime_mode)


def select_verification_strategy(*, app_runtime_mode: str, skip_healthcheck: bool) -> str:
    if skip_healthcheck:
        return "skip"
    return "container_exit" if normalize_runtime_mode(app_runtime_mode) == "eval" else "healthcheck"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build an agent-kb Docker image and smoke-test either the API health endpoint or non-server container completion.",
    )
    parser.add_argument("--tag", default=DEFAULT_IMAGE_TAG, help="Docker image tag to build and run.")
    parser.add_argument(
        "--install-profile",
        default=None,
        choices=("runtime", "smoke", "full", "dev", "prod", "eval"),
        help=(
            "INSTALL_PROFILE used during docker build. "
            "Defaults to runtime for api mode, eval for eval mode, and prod for prod mode."
        ),
    )
    parser.add_argument(
        "--app-runtime-mode",
        default="api",
        help="APP_RUNTIME_MODE to pass to the container. Defaults to api.",
    )
    parser.add_argument(
        "--host-port",
        type=int,
        default=None,
        help=(
            "Host port to publish the container API on. "
            "Defaults to a Docker-assigned loopback port to avoid host-side port races."
        ),
    )
    parser.add_argument(
        "--container-port",
        type=int,
        default=DEFAULT_CONTAINER_PORT,
        help="Container PORT env and published internal port. Defaults to 18080; host port stays Docker-assigned unless --host-port is provided.",
    )
    parser.add_argument(
        "--health-path",
        default=DEFAULT_HEALTH_PATH,
        help="HTTP JSON path to probe after startup. Defaults to /api/health.",
    )
    parser.add_argument(
        "--health-timeout",
        type=float,
        default=120.0,
        help="Seconds to wait for the health endpoint to respond.",
    )
    parser.add_argument(
        "--completion-timeout",
        type=float,
        default=DEFAULT_COMPLETION_TIMEOUT,
        help="Seconds to wait for non-server container modes such as eval to exit successfully.",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Skip docker build and reuse an existing image tag.",
    )
    parser.add_argument(
        "--keep-container",
        action="store_true",
        help="Do not remove the container after the smoke test finishes.",
    )
    parser.add_argument(
        "--keep-image",
        action="store_true",
        help="Do not remove the image tag after the smoke test finishes.",
    )
    parser.add_argument(
        "--skip-healthcheck",
        action="store_true",
        help="Start the container but skip HTTP health probing.",
    )
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Extra environment variable forwarded to docker run. Can be passed multiple times.",
    )
    return parser


def default_container_name(image_tag: str) -> str:
    sanitized = image_tag.replace(":", "-").replace("/", "-")
    return f"{sanitized}-smoke-{os.getpid()}-{int(time.time())}"


def _normalize_env_pairs(env_pairs: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    for pair in env_pairs:
        if "=" not in pair:
            raise ValueError(f"Invalid --env value {pair!r}; expected KEY=VALUE format.")
        normalized.append(pair)
    return normalized


def parse_published_port(raw_output: str, *, container_port: int) -> int:
    """Parse `docker port` output and return the resolved host port."""
    for line in [item.strip() for item in raw_output.splitlines() if item.strip()]:
        try:
            return int(line.rsplit(":", 1)[1])
        except (IndexError, ValueError) as exc:
            raise RuntimeError(
                f"Unable to parse published host port for {container_port}/tcp from docker port output: {raw_output!r}"
            ) from exc
    raise RuntimeError(f"docker port returned no published mapping for {container_port}/tcp")


def build_docker_build_command(*, tag: str, install_profile: str) -> list[str]:
    return [
        "docker",
        "build",
        "--progress",
        "plain",
        "-t",
        tag,
        "--build-arg",
        f"INSTALL_PROFILE={install_profile}",
        ".",
    ]


def build_docker_run_command(
    *,
    tag: str,
    container_name: str,
    host_port: int | None,
    container_port: int,
    app_runtime_mode: str,
    env_pairs: Sequence[str] = (),
) -> list[str]:
    published_port = f"127.0.0.1:{host_port}:{container_port}" if host_port is not None else f"127.0.0.1::{container_port}"
    runtime_mode = normalize_runtime_mode(app_runtime_mode)
    command = [
        "docker",
        "run",
        "-d",
        "--name",
        container_name,
        "-p",
        published_port,
        "-e",
        f"PORT={container_port}",
        "-e",
        f"APP_RUNTIME_MODE={runtime_mode}",
    ]
    for pair in _normalize_env_pairs(env_pairs):
        command.extend(["-e", pair])
    command.append(tag)
    return command


def run_subprocess(command: Sequence[str], *, capture_output: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=REPO_ROOT,
        check=True,
        capture_output=capture_output,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def ensure_docker_available() -> None:
    """Fail fast with an actionable error when Docker CLI/daemon is unavailable."""
    try:
        result = subprocess.run(
            DOCKER_INFO_COMMAND,
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Docker CLI is not installed or not on PATH. Install Docker Desktop (or another Docker CLI) before running scripts/docker_smoke.py."
        ) from exc

    raw_output = ((result.stdout or "") + (result.stderr or "")).strip()
    if result.returncode != 0:
        detail = raw_output or f"docker info exit={result.returncode}"
        raise RuntimeError(
            "Docker daemon is not available. Start Docker Desktop or dockerd and wait for `docker info` to succeed before running scripts/docker_smoke.py. "
            f"Raw output: {detail}"
        )


def parse_container_exit_code(raw_output: str, *, container_name: str) -> int:
    first_line = next((line.strip() for line in raw_output.splitlines() if line.strip()), "")
    if not first_line:
        raise RuntimeError(f"docker wait returned no exit code for {container_name}")
    try:
        return int(first_line)
    except ValueError as exc:
        raise RuntimeError(f"Unable to parse docker wait exit code for {container_name}: {raw_output!r}") from exc


def wait_for_container_exit(container_name: str, *, timeout_seconds: float) -> int:
    try:
        result = subprocess.run(
            ["docker", "wait", container_name],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Timed out waiting for container {container_name} to exit") from exc
    return parse_container_exit_code(result.stdout, container_name=container_name)


def resolve_published_port(container_name: str, container_port: int, *, timeout_seconds: float = 30.0) -> int:
    """Resolve the published host port for a started container.

    When `--host-port` is omitted we let Docker assign an available loopback port and
    inspect the published mapping instead of racing another local process for a free port.
    """
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        result = subprocess.run(
            ["docker", "port", container_name, f"{container_port}/tcp"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        raw_output = (result.stdout or "") + (result.stderr or "")
        if result.returncode == 0 and raw_output.strip():
            return parse_published_port(raw_output, container_port=container_port)
        last_error = RuntimeError(raw_output.strip() or f"docker port exit={result.returncode}")
        time.sleep(1)
    raise RuntimeError(f"Timed out resolving published host port for {container_name}: {last_error}")


def remove_container(container_name: str) -> None:
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def remove_image(tag: str) -> None:
    subprocess.run(
        ["docker", "image", "rm", "-f", tag],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def read_container_logs(container_name: str) -> str:
    result = subprocess.run(
        ["docker", "logs", container_name],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return (result.stdout or "") + (result.stderr or "")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    requested_host_port = args.host_port
    runtime_mode = normalize_runtime_mode(args.app_runtime_mode)
    install_profile = resolve_install_profile(args.install_profile, app_runtime_mode=runtime_mode)
    verification_strategy = select_verification_strategy(
        app_runtime_mode=runtime_mode,
        skip_healthcheck=args.skip_healthcheck,
    )
    container_name = default_container_name(args.tag)

    print(f"[docker-smoke] repo={REPO_ROOT}")
    print(f"[docker-smoke] image={args.tag} install_profile={install_profile}")
    print(
        "[docker-smoke] mode="
        f"{runtime_mode} host_port={requested_host_port or 'docker-assigned'} "
        f"container_port={args.container_port} strategy={verification_strategy}"
    )

    ensure_docker_available()

    image_available = bool(args.no_build)

    if not args.no_build:
        build_command = build_docker_build_command(tag=args.tag, install_profile=install_profile)
        print(f"[docker-smoke] build={' '.join(build_command)}")
        run_subprocess(build_command, capture_output=False)
        image_available = True

    run_command = build_docker_run_command(
        tag=args.tag,
        container_name=container_name,
        host_port=requested_host_port,
        container_port=args.container_port,
        app_runtime_mode=runtime_mode,
        env_pairs=args.env,
    )
    print(f"[docker-smoke] run={' '.join(run_command)}")

    container_started = False
    success = False
    try:
        result = run_subprocess(run_command)
        container_id = result.stdout.strip()
        container_started = True
        print(f"[docker-smoke] container_id={container_id}")

        if verification_strategy == "skip":
            print("[docker-smoke] verification skipped")
            success = True
            return 0

        if verification_strategy == "container_exit":
            exit_code = wait_for_container_exit(container_name, timeout_seconds=args.completion_timeout)
            print(f"[docker-smoke] container_exit_code={exit_code}")
            if exit_code != 0:
                raise RuntimeError(f"Container {container_name} exited with non-zero code: {exit_code}")
            success = True
            return 0

        resolved_host_port = requested_host_port or resolve_published_port(container_name, args.container_port)
        health_url = f"http://127.0.0.1:{resolved_host_port}{args.health_path}"
        payload = wait_for_http_json(health_url, timeout_seconds=args.health_timeout)
        print(f"[docker-smoke] health_url={health_url}")
        print(f"[docker-smoke] health_payload={json.dumps(payload, ensure_ascii=False)}")
        if payload.get("code") != 0:
            raise RuntimeError(f"Health payload returned non-zero code: {payload}")
        success = True
        return 0
    except Exception:
        if container_started:
            logs = read_container_logs(container_name)
            if logs.strip():
                print("[docker-smoke] container logs:", file=sys.stderr)
                print(logs, file=sys.stderr)
        raise
    finally:
        if container_started and not args.keep_container:
            remove_container(container_name)
        if image_available and not args.keep_image:
            remove_image(args.tag)


if __name__ == "__main__":
    raise SystemExit(main())

