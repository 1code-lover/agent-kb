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
from api.services import chat_service
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
