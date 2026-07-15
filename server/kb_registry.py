"""知识库注册表：使用 JSON 文件保存 KB 元数据。"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class KBRegistry:
    """线程安全的知识库 registry。

    写入时使用临时文件 + ``os.replace`` 原子替换，避免进程中断留下半截 JSON。
    对 read-modify-write 操作使用同一个 ``RLock`` 临界区，避免并发更新时丢失 doc_count。
    """

    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path is None:
            storage_path = Path("storage/kb_registry.json")
        self._path = storage_path
        self._lock = threading.RLock()
        self._ensure_file()

    def _ensure_file(self) -> None:
        """确保 registry 文件存在。"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            if not self._path.exists():
                self._write_unlocked([])

    def _read_unlocked(self) -> list[dict]:
        """在已持有锁时读取完整 registry。"""
        raw = self._path.read_text(encoding="utf-8")
        return json.loads(raw or "[]")

    def _write_unlocked(self, data: list[dict]) -> None:
        """在已持有锁时原子写入完整 registry。"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_name(
            f"{self._path.name}.tmp-{os.getpid()}-{threading.get_ident()}"
        )
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        try:
            with tmp_path.open("w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            last_exc: PermissionError | None = None
            for attempt in range(5):
                try:
                    os.replace(tmp_path, self._path)
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

    def _read(self) -> list[dict]:
        """读取全部知识库。"""
        with self._lock:
            return self._read_unlocked()

    def _write(self, data: list[dict]) -> None:
        """替换全部 registry 数据。"""
        with self._lock:
            self._write_unlocked(data)

    def _now(self) -> str:
        """返回当前 UTC 时间。"""
        return datetime.now(timezone.utc).isoformat()

    def list_kbs(self) -> list[dict]:
        """列出全部知识库。"""
        return self._read()

    def replace_all(self, data: list[dict]) -> None:
        """整体替换 registry 数据，供测试或迁移补偿使用。"""
        with self._lock:
            self._write_unlocked(data)

    def get_kb(self, kb_id: str) -> Optional[dict]:
        """获取单个知识库。"""
        with self._lock:
            for kb in self._read_unlocked():
                if kb["kb_id"] == kb_id:
                    return kb
        return None

    def create_kb(self, kb_id: str, kb_name: str) -> dict:
        """创建知识库；重复 kb_id 会失败。"""
        with self._lock:
            data = self._read_unlocked()
            if any(item["kb_id"] == kb_id for item in data):
                raise ValueError(f"知识库ID已存在: {kb_id}")
            now = self._now()
            kb = {
                "kb_id": kb_id,
                "kb_name": kb_name,
                "created_at": now,
                "updated_at": now,
                "status": "active",
                "doc_count": 0,
            }
            data.append(kb)
            self._write_unlocked(data)
            return kb

    def update_kb(self, kb_id: str, kb_name: str) -> dict:
        """更新知识库名称。"""
        with self._lock:
            data = self._read_unlocked()
            for item in data:
                if item["kb_id"] == kb_id:
                    item["kb_name"] = kb_name
                    item["updated_at"] = self._now()
                    self._write_unlocked(data)
                    return item
        raise ValueError(f"知识库不存在: {kb_id}")

    def delete_kb(self, kb_id: str) -> bool:
        """删除知识库 registry 记录。"""
        with self._lock:
            data = self._read_unlocked()
            for i, item in enumerate(data):
                if item["kb_id"] == kb_id:
                    data.pop(i)
                    self._write_unlocked(data)
                    return True
        raise ValueError(f"知识库不存在: {kb_id}")

    def exists(self, kb_id: str) -> bool:
        """判断知识库是否存在。"""
        return self.get_kb(kb_id) is not None

    def add_doc_count(self, kb_id: str, delta: int = 1) -> None:
        """增减文档计数，并将结果钳制到 0。"""
        with self._lock:
            data = self._read_unlocked()
            for item in data:
                if item["kb_id"] == kb_id:
                    item["doc_count"] = max(0, int(item.get("doc_count", 0)) + delta)
                    item["updated_at"] = self._now()
                    self._write_unlocked(data)
                    return
        raise ValueError(f"知识库不存在: {kb_id}")

    def set_doc_count(self, kb_id: str, count: int) -> None:
        """设置文档计数，并将负数钳制到 0。"""
        with self._lock:
            data = self._read_unlocked()
            for item in data:
                if item["kb_id"] == kb_id:
                    item["doc_count"] = max(0, int(count))
                    item["updated_at"] = self._now()
                    self._write_unlocked(data)
                    return
        raise ValueError(f"知识库不存在: {kb_id}")
