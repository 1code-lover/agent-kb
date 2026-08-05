"""?? roundtrip ????????????"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import requests


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


def summarize_runtime_readiness(
    health_resp: dict[str, Any] | None,
    *,
    require_ocr: bool = False,
) -> dict[str, Any]:
    """?? /api/health ???? roundtrip ????????????"""
    health_payload = _get_health_payload(health_resp)
    embedding = health_payload.get("embedding_warmup") if isinstance(health_payload.get("embedding_warmup"), dict) else {}
    ocr = health_payload.get("ocr_warmup") if isinstance(health_payload.get("ocr_warmup"), dict) else {}
    import_caps = health_payload.get("import_capabilities") if isinstance(health_payload.get("import_capabilities"), dict) else {}
    image_ocr_cap = import_caps.get("image_ocr") if isinstance(import_caps.get("image_ocr"), dict) else {}
    ocr_dependencies_ready = bool(image_ocr_cap.get("ready", False))

    embedding_ready = _warmup_state_is_ready(embedding)
    ocr_ready = _warmup_state_is_ready(ocr)
    blockers: list[str] = []
    if not embedding_ready:
        blockers.append("embedding_warmup")
    if require_ocr:
        if not ocr_dependencies_ready:
            blockers.append("image_ocr_dependencies")
        elif not ocr_ready:
            blockers.append("ocr_warmup")

    return {
        "is_ready": len(blockers) == 0,
        "blockers": blockers,
        "embedding_ready": embedding_ready,
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
                if last_error is not None:
                    blocker_text = f"{blocker_text}; last_error={type(last_error).__name__}: {last_error}"
                raise TimeoutError(f"runtime not ready within {timeout:.1f}s; blockers: {blocker_text}")

            remaining = max(deadline - time.perf_counter(), 0.0)
            time.sleep(min(max(poll_interval, 0.1), remaining if remaining > 0 else poll_interval))
    finally:
        if close_session:
            http.close()
