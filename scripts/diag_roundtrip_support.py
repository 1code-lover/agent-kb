"""?? roundtrip ????????????"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import requests


DEFAULT_LOCAL_API_PORT = 18080
API_PORT_ENV_KEYS = ("KB_API_PORT", "NORTHAGENT_API_PORT", "THINKRAG_API_PORT", "FOXGLOVE_API_PORT")
API_BASE_URL_ENV_KEYS = ("KB_API_BASE_URL", "NORTHAGENT_API_BASE_URL", "THINKRAG_API_BASE_URL", "FOXGLOVE_API_BASE_URL")


def _read_first_non_empty_env(env_names: tuple[str, ...], *, env: Mapping[str, str] | None = None) -> str:
    """按优先级读取第一个非空环境变量值。"""
    source = os.environ if env is None else env
    for env_name in env_names:
        value = source.get(env_name, "")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def normalize_api_base_url(value: str | None) -> str:
    """去除 API base URL 两端空白与尾部斜杠。"""
    raw = str(value or "").strip()
    return raw.rstrip("/") if raw else ""


def resolve_api_port(env: Mapping[str, str] | None = None, *, default_port: int = DEFAULT_LOCAL_API_PORT) -> int:
    """按桌面/runtime 合同解析 API 端口。"""
    explicit_base_url = normalize_api_base_url(_read_first_non_empty_env(API_BASE_URL_ENV_KEYS, env=env))
    if explicit_base_url:
        try:
            parsed = urlparse(explicit_base_url)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                if parsed.port is not None:
                    return parsed.port
                return 443 if parsed.scheme == "https" else 80
        except ValueError:
            pass

    raw_port = _read_first_non_empty_env(API_PORT_ENV_KEYS, env=env)
    try:
        parsed_port = int(raw_port)
    except (TypeError, ValueError):
        return default_port
    return parsed_port if parsed_port > 0 else default_port


def resolve_api_base_url(env: Mapping[str, str] | None = None, *, default_port: int = DEFAULT_LOCAL_API_PORT) -> str:
    """按桌面/runtime 合同解析 API base URL。"""
    explicit_base_url = normalize_api_base_url(_read_first_non_empty_env(API_BASE_URL_ENV_KEYS, env=env))
    if explicit_base_url:
        parsed = urlparse(explicit_base_url)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return explicit_base_url
    return f"http://127.0.0.1:{resolve_api_port(env, default_port=default_port)}"


def _get_import_payload(import_resp: dict[str, Any] | None) -> dict[str, Any]:
    """???????? data ?????????????"""
    if not isinstance(import_resp, dict):
        return {}
    payload = import_resp.get("data")
    return payload if isinstance(payload, dict) else {}


def _get_health_payload(health_resp: dict[str, Any] | None) -> dict[str, Any]:
    """?????????? data ??????????????"""
    if not isinstance(health_resp, dict):
        return {}
    payload = health_resp.get("data")
    if isinstance(payload, dict):
        return payload
    return health_resp


def _normalize_relative_path(relative_path: str | None) -> str | None:
    """???????? POSIX ???????????"""
    if not isinstance(relative_path, str):
        return None
    normalized = relative_path.replace("\\", "/").strip().strip("/")
    return normalized or None


def list_file_results(import_resp: dict[str, Any] | None) -> list[dict[str, Any]]:
    """???????? file_results??????????"""
    payload = _get_import_payload(import_resp)
    file_results = payload.get("file_results")
    if not isinstance(file_results, list):
        return []
    return [item for item in file_results if isinstance(item, dict)]


def find_file_result(
    import_resp: dict[str, Any] | None,
    *,
    relative_path: str | None = None,
    fallback_index: int = 0,
) -> dict[str, Any] | None:
    """? relative_path ?????? file_result???????????"""
    file_results = list_file_results(import_resp)
    if not file_results:
        return None

    normalized_relative_path = _normalize_relative_path(relative_path)
    if normalized_relative_path is not None:
        for item in file_results:
            if _normalize_relative_path(item.get("relative_path")) == normalized_relative_path:
                return item

    if 0 <= fallback_index < len(file_results):
        return file_results[fallback_index]
    return None


def resolve_saved_file_path(
    import_resp: dict[str, Any] | None,
    *,
    kb_id: str,
    relative_path: str | None = None,
    fallback_index: int = 0,
) -> Path | None:
    """?????????????????????????? None?"""
    candidates: list[Path] = []
    file_result = find_file_result(import_resp, relative_path=relative_path, fallback_index=fallback_index)
    if isinstance(file_result, dict):
        file_path = file_result.get("path")
        if isinstance(file_path, str) and file_path.strip():
            candidates.append(Path(file_path))

    normalized_relative_path = _normalize_relative_path(relative_path)
    if normalized_relative_path is not None and isinstance(kb_id, str) and kb_id.strip():
        candidates.append(Path("data") / kb_id / Path(normalized_relative_path))

    seen: set[str] = set()
    for candidate in candidates:
        raw_key = str(candidate)
        if raw_key in seen:
            continue
        seen.add(raw_key)
        try:
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue
    return None



def _warmup_state_is_ready(status: dict[str, Any]) -> bool:
    """?? is_ready + state ???????????

    ?????
    - ?? payload ?? is_ready ????????
    - ????? state???? state=ready ??????????? warming
      ??????????????????????????? ready?
    """
    if not bool(status.get("is_ready", False)):
        return False
    state = str(status.get("state") or "").strip().lower()
    if not state:
        return True
    return state == "ready"


def _append_detail(parts: list[str], label: str, value: Any) -> None:
    """把非空诊断字段追加到文本片段。"""
    if value in (None, ""):
        return
    parts.append(f"{label}={value}")


def _summarize_embedding_blocker(embedding: dict[str, Any], diagnostics: dict[str, Any]) -> str:
    """生成 embedding 未就绪时的可读阻塞原因。"""
    parts = ["embedding_warmup"]
    _append_detail(parts, "state", embedding.get("state"))
    _append_detail(parts, "ready", embedding.get("is_ready"))
    _append_detail(parts, "error", embedding.get("last_error"))
    if diagnostics:
        _append_detail(parts, "local_path_exists", diagnostics.get("local_path_exists"))
        _append_detail(parts, "allow_remote_download", diagnostics.get("allow_remote_download"))
        _append_detail(parts, "local_path", diagnostics.get("local_path"))
        _append_detail(parts, "hf_endpoint", diagnostics.get("hf_endpoint"))
    return "(" + ", ".join(parts) + ")"


def _summarize_ocr_blocker(ocr: dict[str, Any]) -> str:
    """生成 OCR 未就绪时的可读阻塞原因。"""
    parts = ["ocr_warmup"]
    _append_detail(parts, "state", ocr.get("state"))
    _append_detail(parts, "ready", ocr.get("is_ready"))
    _append_detail(parts, "error", ocr.get("last_error"))
    return "(" + ", ".join(parts) + ")"


def summarize_runtime_readiness(
    health_resp: dict[str, Any] | None,
    *,
    require_ocr: bool = False,
) -> dict[str, Any]:
    """?? /api/health ???? roundtrip ????????????"""
    health_payload = _get_health_payload(health_resp)
    embedding = health_payload.get("embedding_warmup") if isinstance(health_payload.get("embedding_warmup"), dict) else {}
    embedding_diagnostics = (
        health_payload.get("embedding_diagnostics") if isinstance(health_payload.get("embedding_diagnostics"), dict) else {}
    )
    ocr = health_payload.get("ocr_warmup") if isinstance(health_payload.get("ocr_warmup"), dict) else {}
    import_caps = health_payload.get("import_capabilities") if isinstance(health_payload.get("import_capabilities"), dict) else {}
    image_ocr_cap = import_caps.get("image_ocr") if isinstance(import_caps.get("image_ocr"), dict) else {}
    ocr_dependencies_ready = bool(image_ocr_cap.get("ready", False))

    embedding_ready = _warmup_state_is_ready(embedding)
    ocr_ready = _warmup_state_is_ready(ocr)
    blockers: list[str] = []
    blocker_details: list[str] = []
    if not embedding_ready:
        blockers.append("embedding_warmup")
        blocker_details.append(_summarize_embedding_blocker(embedding, embedding_diagnostics))
    if require_ocr:
        if not ocr_dependencies_ready:
            blockers.append("image_ocr_dependencies")
            blocker_details.append("(image_ocr_dependencies, ready=False)")
        elif not ocr_ready:
            blockers.append("ocr_warmup")
            blocker_details.append(_summarize_ocr_blocker(ocr))

    return {
        "is_ready": len(blockers) == 0,
        "blockers": blockers,
        "blocker_details": blocker_details,
        "embedding_ready": embedding_ready,
        "embedding_diagnostics": embedding_diagnostics,
        "ocr_ready": ocr_ready,
        "ocr_dependencies_ready": ocr_dependencies_ready,
    }


def wait_for_runtime_ready(
    base_url: str,
    *,
    timeout: float,
    poll_interval: float = 2.0,
    require_ocr: bool = False,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """?? /api/health??? roundtrip ???????????? ready?"""
    request_timeout = max(min(timeout, 30.0), 5.0)
    deadline = time.perf_counter() + max(timeout, 0.0)
    close_session = session is None
    http = session or requests.Session()
    last_payload: dict[str, Any] | None = None
    last_error: Exception | None = None

    try:
        while True:
            readiness: dict[str, Any]
            try:
                response = http.get(base_url.rstrip("/") + "/api/health", timeout=request_timeout)
                response.raise_for_status()
                last_payload = response.json()
                last_error = None
                readiness = summarize_runtime_readiness(last_payload, require_ocr=require_ocr)
                if readiness["is_ready"]:
                    return last_payload
            except requests.RequestException as exc:
                last_error = exc
                readiness = {
                    "is_ready": False,
                    "blockers": ["health_check_unreachable"],
                }

            if time.perf_counter() >= deadline:
                blocker_text = ", ".join(readiness["blockers"]) or "unknown"
                detail_text = "; ".join(readiness.get("blocker_details") or [])
                if detail_text:
                    blocker_text = f"{blocker_text}; details: {detail_text}"
                if last_error is not None:
                    blocker_text = f"{blocker_text}; last_error={type(last_error).__name__}: {last_error}"
                raise TimeoutError(f"runtime not ready within {timeout:.1f}s; blockers: {blocker_text}")

            remaining = max(deadline - time.perf_counter(), 0.0)
            time.sleep(min(max(poll_interval, 0.1), remaining if remaining > 0 else poll_interval))
    finally:
        if close_session:
            http.close()
