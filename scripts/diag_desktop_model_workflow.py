"""桌面端模型配置与知识库真实工作流诊断脚本。"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import requests

try:
    from scripts.diag_roundtrip_support import DEFAULT_LOCAL_API_PORT, resolve_api_base_url, wait_for_runtime_ready
except ModuleNotFoundError:
    from diag_roundtrip_support import DEFAULT_LOCAL_API_PORT, resolve_api_base_url, wait_for_runtime_ready

DEFAULT_BASE_URL = f"http://127.0.0.1:{DEFAULT_LOCAL_API_PORT}"
DEFAULT_TIMEOUT = 240.0
DEFAULT_ISOLATION_KB_ID = "default"
DEFAULT_RELATIVE_PATH = "desktop-e2e/desktop-model-workflow.md"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """读取命令行参数。"""
    parser = argparse.ArgumentParser(description="诊断桌面端模型配置、文件导入、问答、preview 与跨 KB 隔离")
    parser.add_argument(
        "--base-url",
        default=resolve_api_base_url(),
        help="本地 API 地址；优先读取 KB_API_BASE_URL，未设置时回退到 KB_API_PORT（默认 18080）",
    )
    parser.add_argument("--kb-id", default=None, help="目标知识库 ID，默认创建临时诊断知识库")
    parser.add_argument("--kb-name", default="Desktop Model Workflow Diagnostic", help="目标知识库名称")
    parser.add_argument("--isolation-kb-id", default=DEFAULT_ISOLATION_KB_ID, help="跨 KB 隔离对照知识库")
    parser.add_argument("--source-path", default=str(Path("temp") / "desktop-model-workflow.md"), help="诊断源文件路径")
    parser.add_argument("--relative-path", default=DEFAULT_RELATIVE_PATH, help="导入后的知识库相对路径")
    parser.add_argument("--provider", default="", help="可选；先切换到指定模型供应商")
    parser.add_argument("--model", default="", help="可选；先切换到指定模型")
    parser.add_argument("--api-base", default="", help="可选；指定模型 Base URL")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="HTTP 超时时间（秒）")
    parser.add_argument("--output-path", default=None, help="将 JSON 报告写入指定路径")
    return parser.parse_args(argv)


def _sha256_bytes(payload: bytes) -> str:
    """计算字节内容的 SHA256。"""
    return hashlib.sha256(payload).hexdigest()


def _request_json(method: str, url: str, *, timeout: float, allow_http_error: bool = False, **kwargs: Any) -> dict[str, Any]:
    """发起 HTTP 请求并返回 JSON。"""
    response = requests.request(method, url, timeout=timeout, **kwargs)
    if not allow_http_error:
        response.raise_for_status()
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw_text": response.text}
    payload["_http_status"] = response.status_code
    return payload


def _unwrap(response: dict[str, Any]) -> dict[str, Any]:
    """读取标准 API 响应中的 data 对象。"""
    payload = response.get("data")
    return payload if isinstance(payload, dict) else {}


def _ensure_kb(base_url: str, kb_id: str, kb_name: str, timeout: float) -> dict[str, Any]:
    """创建诊断知识库；若已存在则复用。"""
    response = requests.post(
        base_url.rstrip("/") + "/api/kb",
        json={"kb_id": kb_id, "kb_name": kb_name},
        timeout=timeout,
    )
    if response.status_code == 409:
        return {"code": 409, "message": "kb_exists", "data": {"kb_id": kb_id, "kb_name": kb_name}}
    response.raise_for_status()
    return response.json()


def _create_source_file(path: Path, unique_code: str) -> dict[str, Any]:
    """创建用于桌面 E2E 导入的诊断 Markdown 文件。"""
    text = (
        "# Desktop model workflow diagnostic\n\n"
        "This document verifies the NorthAgent desktop workflow.\n"
        f"The unique desktop workflow passcode is {unique_code}.\n"
        "The selected knowledge base is the authorization boundary for this diagnostic document.\n"
        "Evidence preview must resolve this file after chat returns sources.\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    payload = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "sha256": _sha256_bytes(payload),
        "size": len(payload),
        "unique_code": unique_code,
        "text_preview": text,
    }


def _get_model_options(base_url: str, timeout: float) -> dict[str, Any]:
    """读取模型选项。"""
    return _request_json("GET", base_url.rstrip("/") + "/api/model/options", timeout=timeout)


def _get_model_health(base_url: str, timeout: float) -> dict[str, Any]:
    """读取模型健康状态。"""
    return _request_json("GET", base_url.rstrip("/") + "/api/model/health", timeout=timeout)


def _resolve_model_selection(args: argparse.Namespace, options_payload: dict[str, Any]) -> dict[str, Any]:
    """按命令行参数或当前配置确定需要选择的模型。"""
    current = options_payload.get("current_llm_info") if isinstance(options_payload.get("current_llm_info"), dict) else {}
    provider = args.provider.strip() or str(current.get("service_provider") or "").strip()
    model = args.model.strip() or str(current.get("model") or "").strip()
    api_base = args.api_base.strip() or str(current.get("api_base") or "").strip()
    if not provider or not model:
        raise RuntimeError("no active model configured; pass --provider and --model or configure a model first")
    return {
        "service_provider": provider,
        "model": model,
        "api_base": api_base,
        "session_id": "desktop-e2e",
    }


def _select_model(base_url: str, selection: dict[str, Any], timeout: float) -> dict[str, Any]:
    """通过模型选择接口模拟桌面端重新配置模型。"""
    payload = {key: value for key, value in selection.items() if value}
    return _request_json("POST", base_url.rstrip("/") + "/api/model/select", timeout=timeout, json=payload)


def _test_model(base_url: str, selected_model: dict[str, Any], timeout: float) -> dict[str, Any]:
    """对当前模型做一次 OpenAI-compatible 探活。"""
    request_payload = {
        "provider_name": selected_model.get("service_provider") or selected_model.get("provider_name") or "",
        "api_base": selected_model.get("api_base") or "",
        "model": selected_model.get("model") or "",
    }
    return _request_json("POST", base_url.rstrip("/") + "/api/model/providers/test", timeout=timeout, json=request_payload)


def _import_file(base_url: str, kb_id: str, source_path: Path, relative_path: str, timeout: float) -> dict[str, Any]:
    """通过真实文件导入接口上传诊断文件。"""
    with source_path.open("rb") as handle:
        response = requests.post(
            base_url.rstrip("/") + "/api/kb/file/import",
            files={"files": (source_path.name, handle, "text/markdown")},
            data={
                "kb_id": kb_id,
                "chunk_size": "256",
                "chunk_overlap": "16",
                "relative_paths": relative_path,
                "import_mode": "preserve_tree",
            },
            timeout=timeout,
        )
    response.raise_for_status()
    return response.json()


def _query_chat(base_url: str, *, kb_id: str, question: str, session_id: str, timeout: float, allow_error: bool = False) -> dict[str, Any]:
    """调用聊天问答接口。"""
    return _request_json(
        "POST",
        base_url.rstrip("/") + "/api/chat/query",
        timeout=timeout,
        allow_http_error=allow_error,
        json={
            "question": question,
            "session_id": session_id,
            "kb_ids": [kb_id],
            "top_k": 5,
        },
    )


def _preview_first_evidence(base_url: str, kb_id: str, evidence: list[dict[str, Any]], timeout: float) -> dict[str, Any] | None:
    """根据第一条 evidence 请求 preview。"""
    if not evidence:
        return None
    first = evidence[0]
    request_payload: dict[str, Any] = {"kb_id": kb_id}
    if first.get("id"):
        request_payload["evidence_id"] = first["id"]
    elif first.get("doc_id"):
        request_payload["doc_id"] = first["doc_id"]
    else:
        return None
    if isinstance(first.get("preview_locator"), dict):
        request_payload["preview_locator"] = first["preview_locator"]
    return _request_json("POST", base_url.rstrip("/") + "/api/kb/preview", timeout=timeout, json=request_payload)


def _contains(text: Any, term: str) -> bool:
    """大小写不敏感地判断文本是否包含关键词。"""
    return term.lower() in str(text or "").lower()


def _collection_contains(collection: list[dict[str, Any]], term: str) -> bool:
    """判断来源或 evidence 集合是否包含关键词。"""
    haystack = json.dumps(collection, ensure_ascii=False)
    return _contains(haystack, term)


def _emit_report(report: dict[str, Any], output_path: str | None) -> None:
    """输出 JSON 报告，并在需要时落盘。"""
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")
    print(payload)


def main() -> int:
    """执行桌面端真实工作流诊断。"""
    args = _parse_args()
    base_url = args.base_url.rstrip("/")
    timestamp = int(time.time())
    kb_id = args.kb_id or f"diag-desktop-e2e-{timestamp}"
    unique_code = f"northagent-desktop-e2e-{timestamp}"
    question = f"What is the unique desktop workflow passcode in the diagnostic document?"

    health_resp = wait_for_runtime_ready(base_url, timeout=args.timeout, require_ocr=False)
    source_info = _create_source_file(Path(args.source_path), unique_code)
    options_resp = _get_model_options(base_url, args.timeout)
    options_payload = _unwrap(options_resp)
    selection = _resolve_model_selection(args, options_payload)
    select_resp = _select_model(base_url, selection, args.timeout)
    selected_model = _unwrap(select_resp)
    model_test_resp = _test_model(base_url, selected_model, args.timeout)
    health_after_select_resp = _get_model_health(base_url, args.timeout)

    ensure_kb_resp = _ensure_kb(base_url, kb_id, args.kb_name, args.timeout)
    import_resp = _import_file(base_url, kb_id, Path(args.source_path), args.relative_path, args.timeout)
    chat_resp = _query_chat(
        base_url,
        kb_id=kb_id,
        question=question,
        session_id=f"desktop-e2e-{kb_id}",
        timeout=args.timeout,
    )
    chat_payload = _unwrap(chat_resp)
    sources = chat_payload.get("sources") if isinstance(chat_payload.get("sources"), list) else []
    evidence = chat_payload.get("evidence") if isinstance(chat_payload.get("evidence"), list) else []
    preview_resp = _preview_first_evidence(base_url, kb_id, evidence, args.timeout)

    isolation_resp = _query_chat(
        base_url,
        kb_id=args.isolation_kb_id,
        question=question,
        session_id=f"desktop-e2e-isolation-{timestamp}",
        timeout=args.timeout,
        allow_error=True,
    )
    isolation_payload = _unwrap(isolation_resp)
    isolation_sources = isolation_payload.get("sources") if isinstance(isolation_payload.get("sources"), list) else []
    isolation_evidence = isolation_payload.get("evidence") if isinstance(isolation_payload.get("evidence"), list) else []

    answer = str(chat_payload.get("answer") or "")
    preview_payload = _unwrap(preview_resp or {})
    model_test_payload = _unwrap(model_test_resp)
    health_payload = _unwrap(health_after_select_resp)

    checks = {
        "runtime_ready": bool(health_resp),
        "model_options_loaded": bool(options_payload.get("providers")),
        "model_health_loaded": bool(health_payload),
        "model_selected": selected_model.get("service_provider") == selection["service_provider"]
        and selected_model.get("model") == selection["model"],
        "model_test_reachable": bool(model_test_payload.get("reachable")),
        "file_imported": bool(_unwrap(import_resp).get("file_results")),
        "chat_answer_has_unique_code": _contains(answer, unique_code),
        "chat_sources_present": len(sources) > 0,
        "chat_sources_have_unique_code": _collection_contains(sources, unique_code),
        "chat_evidence_present": len(evidence) > 0,
        "preview_returned": preview_resp is not None and int((preview_resp or {}).get("_http_status", 0)) < 400,
        "preview_has_unique_code": _contains(preview_payload.get("excerpt") or preview_payload.get("content"), unique_code),
        "cross_kb_did_not_leak_target_kb": not _collection_contains(isolation_sources + isolation_evidence, kb_id),
        "cross_kb_did_not_leak_unique_code": not _collection_contains(isolation_sources + isolation_evidence, unique_code),
    }
    checks["run_passed"] = all(checks.values())

    report = {
        "base_url": base_url,
        "kb_id": kb_id,
        "isolation_kb_id": args.isolation_kb_id,
        "question": question,
        "source": source_info,
        "model": {
            "requested": {
                "service_provider": selection["service_provider"],
                "model": selection["model"],
                "api_base": selection.get("api_base", ""),
            },
            "selected": {
                "service_provider": selected_model.get("service_provider"),
                "model": selected_model.get("model"),
                "api_base": selected_model.get("api_base"),
                "api_key_valid": selected_model.get("api_key_valid"),
            },
            "test": {
                "reachable": model_test_payload.get("reachable"),
                "detail": model_test_payload.get("detail"),
                "trace_id": model_test_payload.get("trace_id"),
            },
            "health": health_payload,
        },
        "checks": checks,
        "api": {
            "health": _unwrap(health_resp),
            "ensure_kb": _unwrap(ensure_kb_resp),
            "import_summary": _unwrap(import_resp),
            "chat_summary": {
                "answer": answer,
                "sources_count": len(sources),
                "evidence_count": len(evidence),
                "requested_kb_ids": chat_payload.get("requested_kb_ids"),
                "effective_kb_ids": chat_payload.get("effective_kb_ids"),
                "first_source": sources[0] if sources else None,
                "first_evidence": evidence[0] if evidence else None,
            },
            "preview": preview_payload,
            "isolation": {
                "http_status": isolation_resp.get("_http_status"),
                "answer": isolation_payload.get("answer"),
                "sources_count": len(isolation_sources),
                "evidence_count": len(isolation_evidence),
                "sources": isolation_sources,
                "evidence": isolation_evidence,
                "error": isolation_resp.get("detail") or isolation_resp.get("message"),
            },
        },
    }

    _emit_report(report, args.output_path)
    return 0 if checks["run_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
