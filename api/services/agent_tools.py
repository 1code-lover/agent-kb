"""Agent 工具辅助函数。"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from api.schemas import QueryRequest
from api.services.evidence_service import normalize_evidence as build_evidence_items
from api.services import chat_service, model_service
from api.services.fallback_store import FALLBACK_CONFIG_STORE
from api.services.tool_receipt_store import append_receipt
from server.security.command_validator import CommandValidator
from server.security.path_validator import PathValidator
from utils.logging_utils import COMMAND_LOG_FILE, append_json_log, now_iso, safe_preview
import config


_path_validator = PathValidator(config.PATH_SECURITY)
_command_validator = CommandValidator(config.COMMAND_SECURITY, path_validator=_path_validator)


def normalize_evidence(sources: list[dict[str, Any]], receipt_id: str | None = None) -> list[dict[str, Any]]:
    """兼容旧入口，内部统一委托给 evidence_service。"""
    return build_evidence_items(sources, receipt_id=receipt_id)


def _get_config_store():
    try:
        from server.stores.config_store import CONFIG_STORE

        return CONFIG_STORE
    except Exception:
        return FALLBACK_CONFIG_STORE


def _load_current_model_config() -> dict[str, Any]:
    """读取 Agent 直连模型所需的当前配置。"""
    config_store = _get_config_store()
    current_llm_info = config_store.get("current_llm_info") or {}
    current_llm_settings = config_store.get("current_llm_settings") or {}

    provider = str(current_llm_info.get("service_provider") or "").strip()
    model = str(current_llm_info.get("model") or "").strip()
    api_base = (current_llm_info.get("api_base") or "").strip().rstrip("/")
    api_key = current_llm_info.get("api_key") or ""
    temperature = current_llm_settings.get("temperature", 0.1)
    system_prompt = current_llm_settings.get("system_prompt", "")

    if provider == "Ollama" and not api_base:
        api_base = config.OLLAMA_API_URL.rstrip("/")
    if not provider or not api_base or not model:
        raise RuntimeError("Current model is not configured. Please save a provider and model first.")
    if provider != "Ollama" and not api_key:
        raise RuntimeError("Current model is not configured. Please save a provider and model first.")

    return {
        "provider": provider,
        "model": model,
        "api_base": api_base,
        "api_key": api_key,
        "temperature": temperature,
        "system_prompt": system_prompt,
    }


def _request_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    """发送模型 JSON 请求，并把网络/协议错误统一为可分类异常。"""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw_body = response.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Model request failed with HTTP {exc.code}: {detail[:400]}") from exc
    except Exception as exc:
        raise RuntimeError(f"Model request failed: {exc}") from exc

    try:
        body = json.loads(raw_body or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Model response was not valid JSON: {raw_body[:200]}") from exc
    if not isinstance(body, dict):
        raise RuntimeError("Model response was not a JSON object.")
    return body


def _build_messages(question: str, system_prompt: str) -> list[dict[str, str]]:
    """构造云端与 Ollama 共用的消息列表。"""
    return [
        {"role": "system", "content": system_prompt or "You are a helpful desktop agent."},
        {"role": "user", "content": question},
    ]


def _call_openai_compatible(
    question: str,
    model_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """调用 OpenAI 兼容的 chat completions。"""
    model_config = model_config or _load_current_model_config()
    provider = model_config["provider"]
    model = model_config["model"]
    api_base = model_config["api_base"]
    api_key = model_config["api_key"]

    url = f"{api_base}/chat/completions"
    payload = {
        "model": model,
        "messages": _build_messages(question, str(model_config.get("system_prompt") or "")),
        "temperature": model_config.get("temperature", 0.1),
    }
    body = _request_json(
        url,
        payload,
        {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )

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


def _call_ollama(question: str, model_config: dict[str, Any]) -> dict[str, Any]:
    """使用 Ollama 原生 /api/chat 协议调用本地模型。"""
    provider = model_config["provider"]
    model = model_config["model"]
    api_base = model_config["api_base"]
    payload = {
        "model": model,
        "messages": _build_messages(question, str(model_config.get("system_prompt") or "")),
        "options": {"temperature": model_config.get("temperature", 0.1)},
        "stream": False,
    }
    body = _request_json(f"{api_base}/api/chat", payload, {"Content-Type": "application/json"})
    if body.get("error"):
        raise RuntimeError(f"Model request failed: {str(body['error'])[:400]}")
    message = body.get("message") or {}
    answer = message.get("content") if isinstance(message, dict) else ""
    if not answer:
        raise RuntimeError("Model response did not contain an assistant message.")
    return {
        "provider": provider,
        "model": model,
        "api_base": api_base,
        "answer": answer,
        "raw": body,
    }


def _call_configured_model(question: str) -> dict[str, Any]:
    """按当前 provider 调用云端 OpenAI 兼容接口或本地 Ollama。"""
    model_config = _load_current_model_config()
    if model_config["provider"] == "Ollama":
        return _call_ollama(question, model_config)
    return _call_openai_compatible(question, model_config)


def _public_fallback_result(fallback: dict[str, Any], health: dict[str, Any]) -> dict[str, Any]:
    """裁剪 fallback 结果，避免 selected 中的 API Key 进入响应或回执。"""
    return {
        "applied": True,
        "error_kind": fallback.get("error_kind"),
        "candidate_count": fallback.get("candidate_count", 0),
        "fallback_from": health.get("fallback_from"),
        "fallback_to": health.get("fallback_to"),
        "fallback_attempt_summary": fallback.get("fallback_attempt_summary", {}),
    }


def run_llm_chat(session_id: str, question: str) -> dict[str, Any]:
    """执行 Agent 直连聊天，并在可恢复模型错误后自动切换一次。"""
    fallback_info: dict[str, Any] | None = None
    try:
        result = _call_configured_model(question)
    except Exception as first_error:
        fallback = model_service.attempt_model_fallback(first_error, session_id=session_id)
        if not fallback.get("applied"):
            raise
        try:
            result = _call_configured_model(question)
        except Exception as retry_error:
            model_service.update_model_health(
                state="unavailable",
                last_error_kind=model_service.classify_model_error(retry_error),
                last_error=str(retry_error)[:500],
                last_checked_at=now_iso(),
            )
            raise
        health = model_service.get_model_health()
        fallback_info = _public_fallback_result(fallback, health)

    model_health = model_service.get_model_health()
    receipt = append_receipt(
        session_id=session_id,
        tool_name="llm_chat",
        input_data={"question": question, "provider": result["provider"], "model": result["model"]},
        output_data={
            "answer": result["answer"],
            "provider": result["provider"],
            "model": result["model"],
            "fallback": fallback_info,
        },
        status="ok",
    )
    return {
        "result": result,
        "receipt": receipt,
        "evidence": [],
        "fallback": fallback_info,
        "model_health": model_health,
    }


def run_kb_search(session_id: str, question: str, kb_ids: list[str] | None = None) -> dict[str, Any]:
    result = chat_service.query(
        QueryRequest(question=question, session_id=session_id, kb_ids=kb_ids),
        record_history=False,
    )
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
    allowed, resolved_path, reason = _path_validator.validate_read(path_text)
    if not allowed:
        raise ValueError(f"File access denied: {reason}")

    target = Path(resolved_path)
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


def run_cmd(session_id: str, command: str) -> dict[str, Any]:
    cmd = command.strip()
    allowed, reason = _command_validator.validate(cmd)
    if not allowed:
        raise ValueError(f"Command blocked by security policy: {reason}")

    try:
        args = shlex.split(cmd, posix=False)
    except ValueError:
        args = cmd.split()

    timeout = _command_validator.get_timeout(cmd)
    started_at = time.perf_counter()
    completed = subprocess.run(
        args,
        shell=False,
        capture_output=True,
        text=True,
        timeout=timeout,
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
    append_json_log(
        "command_logger",
        COMMAND_LOG_FILE,
        {
            "logged_at": now_iso(),
            "session_id": session_id,
            "command": cmd,
            "cwd": os.getcwd(),
            "exit_code": completed.returncode,
            "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
            "status": "ok" if completed.returncode == 0 else "error",
            "receipt_id": receipt["id"],
            "stdout_preview": safe_preview(completed.stdout),
            "stderr_preview": safe_preview(completed.stderr),
            "combined_output_preview": safe_preview(output),
        },
    )
    return {"result": {"exit_code": completed.returncode, "output": output}, "receipt": receipt}


from api.schemas.tool_schemas import (
    KbSearchInput,
    KbSearchOutput,
    ReadFileInput,
    ReadFileOutput,
    RunCmdInput,
    RunCmdOutput,
)
from api.services.tool_registry import ToolBase


class KbSearchTool(ToolBase):
    """知识库搜索工具"""
    name = "kb_search"
    description = "Search knowledge base"
    input_schema = KbSearchInput
    output_schema = KbSearchOutput
    risk_level = "L0"

    def execute(self, input_data: dict) -> dict:
        """
        函数名：execute
        入参：
            - input_data (dict): 经过验证的输入数据，包含 session_id 和 question
        功能：执行知识库搜索
        运行逻辑：调用 run_kb_search 函数，提取 answer、sources 和 evidence_count
        出参：dict - 包含 answer、sources 和 evidence_count 的结果字典
        """
        result = run_kb_search(input_data["session_id"], input_data["question"])
        return {
            "answer": result["result"].get("answer", ""),
            "sources": result["result"].get("sources", []),
            "evidence_count": len(result.get("evidence", [])),
        }


class ReadFileTool(ToolBase):
    """文件读取工具"""
    name = "read_file"
    description = "Read local file"
    input_schema = ReadFileInput
    output_schema = ReadFileOutput
    risk_level = "L0"

    def execute(self, input_data: dict) -> dict:
        """
        函数名：execute
        入参：
            - input_data (dict): 经过验证的输入数据，包含 session_id 和 path
        功能：执行文件读取
        运行逻辑：调用 run_read_file 函数，提取 path 和 excerpt
        出参：dict - 包含 path 和 excerpt 的结果字典
        """
        result = run_read_file(input_data["session_id"], input_data["path"])
        return {
            "path": result["result"]["path"],
            "excerpt": result["result"]["excerpt"],
        }


class RunCmdTool(ToolBase):
    """命令执行工具"""
    name = "run_cmd"
    description = "Execute command"
    input_schema = RunCmdInput
    output_schema = RunCmdOutput
    risk_level = "L2"

    def execute(self, input_data: dict) -> dict:
        """
        函数名：execute
        入参：
            - input_data (dict): 经过验证的输入数据，包含 session_id 和 command
        功能：执行命令
        运行逻辑：调用 run_cmd 函数，提取 exit_code 和 output
        出参：dict - 包含 exit_code 和 output 的结果字典
        """
        result = run_cmd(input_data["session_id"], input_data["command"])
        return {
            "exit_code": result["result"]["exit_code"],
            "output": result["result"]["output"],
        }
