"""知识库最近导入回执存储。"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.utils.file import validate_kb_id

_LOCK = threading.RLock()
_STORAGE_ROOT = Path("storage/kb_import_receipts")


def _storage_path(kb_id: str) -> Path:
    """返回指定知识库最近回执的落盘路径。"""
    return _STORAGE_ROOT / f"{validate_kb_id(kb_id)}.json"


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    """使用临时文件 + 原子替换写入 JSON，避免半写入状态。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp-{os.getpid()}-{threading.get_ident()}")
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        with tmp_path.open("w", encoding="utf-8") as fh:
            fh.write(serialized)
            fh.flush()
            os.fsync(fh.fileno())
        last_exc: PermissionError | None = None
        for attempt in range(5):
            try:
                os.replace(tmp_path, path)
                last_exc = None
                break
            except PermissionError as exc:
                last_exc = exc
                time.sleep(0.02 * (attempt + 1))
        if last_exc is not None:
            raise last_exc
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def save_latest_import_receipt(
    kb_id: str,
    *,
    source_label: str,
    result: dict[str, Any],
    created_at: str | None = None,
) -> dict[str, Any]:
    """保存某个知识库最近一次导入回执。"""
    safe_kb_id = validate_kb_id(kb_id)
    payload = {
        "kb_id": safe_kb_id,
        "source_label": str(source_label or "导入"),
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "result": result,
    }
    path = _storage_path(safe_kb_id)
    with _LOCK:
        _atomic_write(path, payload)
    return payload


def load_latest_import_receipt(kb_id: str) -> dict[str, Any] | None:
    """读取某个知识库最近一次导入回执；不存在时返回 None。"""
    safe_kb_id = validate_kb_id(kb_id)
    path = _storage_path(safe_kb_id)
    if not path.exists():
        return None
    with _LOCK:
        raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw or "{}")
    if not payload:
        return None
    payload["kb_id"] = safe_kb_id
    return payload


def delete_latest_import_receipt(kb_id: str) -> None:
    """删除某个知识库最近一次导入回执。"""
    safe_kb_id = validate_kb_id(kb_id)
    path = _storage_path(safe_kb_id)
    with _LOCK:
        if not path.exists():
            return
        try:
            path.unlink()
        except FileNotFoundError:
            return
