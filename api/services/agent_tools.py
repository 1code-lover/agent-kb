"""Agent tool helpers."""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from api.schemas import QueryRequest
from api.services import chat_service
from api.services.approval_service import CMD_ALLOWLIST
from api.services.fallback_store import FALLBACK_CONFIG_STORE
from api.services.tool_receipt_store import append_receipt


def normalize_evidence(sources: list[dict[str, Any]], receipt_id: str | None = None) -> list[dict[str, Any]]:
    evidence = []
    for idx, source in enumerate(sources or [], start=1):
        evidence.append(
            {
                "id": f"ev-{idx}",
                "title": source.get("file") or "Knowledge Source",
                "source": source.get("file") or "N/A",
                "page": source.get("page") or "N/A",
                "score": source.get("score"),
                "excerpt": (source.get("text") or "")[:600],
                "receipt_id": receipt_id,
                "kb_id": "default",
            }
        )
    return evidence


def _get_config_store():
    try:
        from server.stores.config_store import CONFIG_STORE

        return CONFIG_STORE
    except Exception:
        return FALLBACK_CONFIG_STORE


def _call_openai_compatible(question: str) -> dict[str, Any]:
    config_store = _get_config_store()
    current_llm_info = config_store.get("current_llm_info") or {}
    current_llm_settings = config_store.get("current_llm_settings") or {}

    provider = current_llm_info.get("service_provider", "")
    model = current_llm_info.get("model", "")
    api_base = (current_llm_info.get("api_base") or "").strip().rstrip("/")
    api_key = current_llm_info.get("api_key") or ""
    temperature = current_llm_settings.get("temperature", 0.1)
    system_prompt = current_llm_settings.get("system_prompt", "")

    if provider == "Ollama":
        raise RuntimeError("Ollama direct agent chat is not implemented in the lightweight runtime yet.")
    if not api_base or not api_key or not model:
        raise RuntimeError("Current model is not configured. Please save a provider and model first.")

    url = f"{api_base}/chat/completions"
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt or "You are a helpful desktop agent."},
                {"role": "user", "content": question},
            ],
            "temperature": temperature,
        }
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    request = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Model request failed with HTTP {exc.code}: {detail[:400]}") from exc
    except Exception as exc:
        raise RuntimeError(f"Model request failed: {exc}") from exc

    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError("Model response did not contain any choices.")

    message = choices[0].get("message") or {}
    answer = message.get("content") or ""
    return {
        "provider": provider,
        "model": model,
        "api_base": api_base,
        "answer": answer,
        "raw": body,
    }


def run_llm_chat(session_id: str, question: str) -> dict[str, Any]:
    result = _call_openai_compatible(question)
    receipt = append_receipt(
        session_id=session_id,
        tool_name="llm_chat",
        input_data={"question": question, "provider": result["provider"], "model": result["model"]},
        output_data={"answer": result["answer"], "provider": result["provider"], "model": result["model"]},
        status="ok",
    )
    return {"result": result, "receipt": receipt, "evidence": []}


def run_kb_search(session_id: str, question: str) -> dict[str, Any]:
    result = chat_service.query(QueryRequest(question=question, session_id=session_id))
    sources = result.get("sources", [])
    receipt = append_receipt(
        session_id=session_id,
        tool_name="kb_search",
        input_data={"question": question},
        output_data={"answer": result.get("answer", ""), "sources_count": len(sources)},
        status="ok",
    )
    return {"result": result, "receipt": receipt, "evidence": normalize_evidence(sources, receipt["id"])}


def run_read_file(session_id: str, path_text: str) -> dict[str, Any]:
    target = Path(path_text)
    if not target.exists() or not target.is_file():
        raise ValueError("file not found")
    content = target.read_text(encoding="utf-8", errors="ignore")
    excerpt = content[:2000]
    receipt = append_receipt(
        session_id=session_id,
        tool_name="read_file",
        input_data={"path": str(target)},
        output_data={"chars": len(content), "excerpt": excerpt},
        status="ok",
    )
    return {"result": {"path": str(target), "excerpt": excerpt}, "receipt": receipt}


def run_cmd(session_id: str, command: str, enforce_allowlist: bool = True) -> dict[str, Any]:
    cmd = command.strip()
    if enforce_allowlist and cmd not in CMD_ALLOWLIST:
        raise ValueError("command not allowed")
    completed = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=8,
        cwd=os.getcwd(),
    )
    output = (completed.stdout or completed.stderr or "").strip()
    receipt = append_receipt(
        session_id=session_id,
        tool_name="run_cmd",
        input_data={"command": cmd},
        output_data={"exit_code": completed.returncode, "output": output[:2000]},
        status="ok" if completed.returncode == 0 else "error",
    )
    return {"result": {"exit_code": completed.returncode, "output": output}, "receipt": receipt}
