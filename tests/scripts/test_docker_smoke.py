from __future__ import annotations

import http.client
from types import SimpleNamespace

import pytest

from scripts.docker_smoke import (
    DEFAULT_COMPLETION_TIMEOUT,
    DEFAULT_CONTAINER_PORT,
    DEFAULT_HEALTH_PATH,
    DOCKER_INFO_COMMAND,
    build_docker_build_command,
    build_docker_run_command,
    build_parser,
    ensure_docker_available,
    parse_container_exit_code,
    parse_published_port,
    resolve_install_profile,
    select_verification_strategy,
    wait_for_http_json,
)


def test_build_parser_defaults_to_runtime_api_smoke() -> None:
    args = build_parser().parse_args([])

    assert args.tag == "agent-kb-runtime-smoke:local"
    assert args.install_profile is None
    assert resolve_install_profile(args.install_profile, app_runtime_mode=args.app_runtime_mode) == "runtime"
    assert args.app_runtime_mode == "api"
    assert args.host_port is None
    assert args.container_port == DEFAULT_CONTAINER_PORT
    assert args.health_path == DEFAULT_HEALTH_PATH
    assert args.completion_timeout == DEFAULT_COMPLETION_TIMEOUT
    assert args.skip_healthcheck is False


def test_resolve_install_profile_infers_eval_for_eval_mode() -> None:
    args = build_parser().parse_args(["--app-runtime-mode", "eval"])

    assert args.install_profile is None
    assert resolve_install_profile(args.install_profile, app_runtime_mode=args.app_runtime_mode) == "eval"


def test_resolve_install_profile_infers_prod_for_prod_mode() -> None:
    args = build_parser().parse_args(["--app-runtime-mode", "prod"])

    assert args.install_profile is None
    assert resolve_install_profile(args.install_profile, app_runtime_mode=args.app_runtime_mode) == "prod"


def test_build_parser_accepts_smoke_install_profile() -> None:
    args = build_parser().parse_args(["--install-profile", "smoke"])

    assert args.install_profile == "smoke"


def test_build_parser_help_documents_dynamic_host_port_contract() -> None:
    help_text = build_parser().format_help()

    assert "Docker-assigned loopback port" in help_text
    assert "host port stays Docker-assigned" in help_text
    assert "--host-port" in help_text
    assert "non-server container completion" in help_text
    assert "runtime for api mode" in help_text
    assert "eval for eval mode" in help_text
    assert "prod mode" in help_text


def test_build_docker_build_command_uses_install_profile_and_tag() -> None:
    command = build_docker_build_command(tag="agent-kb:test", install_profile="runtime")

    assert command == [
        "docker",
        "build",
        "--progress",
        "plain",
        "-t",
        "agent-kb:test",
        "--build-arg",
        "INSTALL_PROFILE=runtime",
        ".",
    ]


def test_build_docker_build_command_supports_smoke_profile() -> None:
    command = build_docker_build_command(tag="agent-kb:test", install_profile="smoke")

    assert command == [
        "docker",
        "build",
        "--progress",
        "plain",
        "-t",
        "agent-kb:test",
        "--build-arg",
        "INSTALL_PROFILE=smoke",
        ".",
    ]


def test_build_docker_run_command_binds_loopback_and_sets_runtime_env() -> None:
    command = build_docker_run_command(
        tag="agent-kb:test",
        container_name="agent-kb-smoke",
        host_port=28080,
        container_port=18080,
        app_runtime_mode="api",
    )

    assert command == [
        "docker",
        "run",
        "-d",
        "--name",
        "agent-kb-smoke",
        "-p",
        "127.0.0.1:28080:18080",
        "-e",
        "PORT=18080",
        "-e",
        "APP_RUNTIME_MODE=api",
        "agent-kb:test",
    ]


def test_build_docker_run_command_defaults_to_docker_assigned_loopback_port() -> None:
    command = build_docker_run_command(
        tag="agent-kb:test",
        container_name="agent-kb-smoke",
        host_port=None,
        container_port=18080,
        app_runtime_mode="api",
    )

    assert command == [
        "docker",
        "run",
        "-d",
        "--name",
        "agent-kb-smoke",
        "-p",
        "127.0.0.1::18080",
        "-e",
        "PORT=18080",
        "-e",
        "APP_RUNTIME_MODE=api",
        "agent-kb:test",
    ]


def test_build_docker_run_command_can_forward_extra_env() -> None:
    command = build_docker_run_command(
        tag="agent-kb:test",
        container_name="agent-kb-smoke",
        host_port=28080,
        container_port=18080,
        app_runtime_mode="prod",
        env_pairs=["THINKRAG_EMBED_PREWARM=0", "THINKRAG_OCR_PREWARM=0"],
    )

    assert command[-5:] == [
        "-e",
        "THINKRAG_EMBED_PREWARM=0",
        "-e",
        "THINKRAG_OCR_PREWARM=0",
        "agent-kb:test",
    ]
    assert "APP_RUNTIME_MODE=prod" in command


def test_wait_for_http_json_retries_remote_disconnect(monkeypatch) -> None:
    calls = {"count": 0}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return b'{"code": 0}'

    def fake_urlopen(url: str, timeout: int):
        calls["count"] += 1
        if calls["count"] == 1:
            raise http.client.RemoteDisconnected("startup race")
        return _Response()

    monkeypatch.setattr("scripts.docker_smoke.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("scripts.docker_smoke.time.sleep", lambda *_args, **_kwargs: None)

    assert wait_for_http_json("http://127.0.0.1:18080/api/health", timeout_seconds=2) == {"code": 0}
    assert calls["count"] == 2


def test_parse_published_port_reads_docker_port_output() -> None:
    assert parse_published_port("127.0.0.1:49155\n", container_port=18080) == 49155
    assert parse_published_port("[::]:49156\n", container_port=18080) == 49156


def test_select_verification_strategy_uses_container_exit_for_eval() -> None:
    assert select_verification_strategy(app_runtime_mode="eval", skip_healthcheck=False) == "container_exit"
    assert select_verification_strategy(app_runtime_mode="api", skip_healthcheck=False) == "healthcheck"
    assert select_verification_strategy(app_runtime_mode="eval", skip_healthcheck=True) == "skip"


def test_build_docker_run_command_normalizes_runtime_mode() -> None:
    command = build_docker_run_command(
        tag="agent-kb:test",
        container_name="agent-kb-smoke",
        host_port=28080,
        container_port=18080,
        app_runtime_mode="EVAL",
    )

    assert "APP_RUNTIME_MODE=eval" in command


def test_ensure_docker_available_accepts_ready_daemon(monkeypatch) -> None:
    seen: list[list[str]] = []

    def fake_run(command, **kwargs):
        seen.append(command)
        return SimpleNamespace(returncode=0, stdout="27.5.1\n", stderr="")

    monkeypatch.setattr("scripts.docker_smoke.subprocess.run", fake_run)

    ensure_docker_available()

    assert seen == [DOCKER_INFO_COMMAND]


def test_ensure_docker_available_reports_missing_cli(monkeypatch) -> None:
    def fake_run(_command, **_kwargs):
        raise FileNotFoundError("docker not found")

    monkeypatch.setattr("scripts.docker_smoke.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="Docker CLI is not installed"):
        ensure_docker_available()


def test_ensure_docker_available_reports_unready_daemon(monkeypatch) -> None:
    def fake_run(_command, **_kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="daemon down")

    monkeypatch.setattr("scripts.docker_smoke.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="Docker daemon is not available"):
        ensure_docker_available()


def test_parse_container_exit_code_reads_docker_wait_output() -> None:
    assert parse_container_exit_code("0\n", container_name="agent-kb-smoke") == 0
    assert parse_container_exit_code("12\n", container_name="agent-kb-smoke") == 12


def test_main_removes_image_even_when_healthcheck_fails(monkeypatch) -> None:
    container_names: list[str] = []
    image_tags: list[str] = []

    def fake_run_subprocess(command, *, capture_output=True):
        if command[:2] == ["docker", "run"]:
            return SimpleNamespace(stdout="container-123\n")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr("scripts.docker_smoke.ensure_docker_available", lambda: None)
    monkeypatch.setattr("scripts.docker_smoke.run_subprocess", fake_run_subprocess)
    monkeypatch.setattr("scripts.docker_smoke.default_container_name", lambda _tag: "agent-kb-smoke")
    monkeypatch.setattr("scripts.docker_smoke.resolve_published_port", lambda *_args, **_kwargs: 49155)
    monkeypatch.setattr("scripts.docker_smoke.wait_for_http_json", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("health failed")))
    monkeypatch.setattr("scripts.docker_smoke.read_container_logs", lambda *_args, **_kwargs: "")
    monkeypatch.setattr("scripts.docker_smoke.remove_container", lambda name: container_names.append(name))
    monkeypatch.setattr("scripts.docker_smoke.remove_image", lambda tag: image_tags.append(tag))

    with pytest.raises(RuntimeError, match="health failed"):
        __import__("scripts.docker_smoke", fromlist=["main"]).main(["--no-build"])

    assert container_names == ["agent-kb-smoke"]
    assert image_tags == ["agent-kb-runtime-smoke:local"]



def test_main_does_not_remove_image_when_build_step_fails_before_image_exists(monkeypatch) -> None:
    image_tags: list[str] = []

    def fake_run_subprocess(command, *, capture_output=True):
        raise RuntimeError("build failed")

    monkeypatch.setattr("scripts.docker_smoke.ensure_docker_available", lambda: None)
    monkeypatch.setattr("scripts.docker_smoke.run_subprocess", fake_run_subprocess)
    monkeypatch.setattr("scripts.docker_smoke.remove_image", lambda tag: image_tags.append(tag))

    with pytest.raises(RuntimeError, match="build failed"):
        __import__("scripts.docker_smoke", fromlist=["main"]).main([])

    assert image_tags == []




