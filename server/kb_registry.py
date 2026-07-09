"""知识库目录管理（基于 JSON 文件存储）"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class KBRegistry:
    """知识库目录 registry，基于 JSON 文件存储

    提供知识库 CRUD 操作，线程安全（文件锁 + threading.Lock）。
    """

    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path is None:
            storage_path = Path("storage/kb_registry.json")
        self._path = storage_path
        self._lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self):
        """确保存储文件存在"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("[]", encoding="utf-8")

    def _read(self) -> list[dict]:
        """读取全部知识库列表"""
        with self._lock:
            raw = self._path.read_text(encoding="utf-8")
            return json.loads(raw)

    def _write(self, data: list[dict]):
        """写入知识库列表"""
        with self._lock:
            self._path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def list_kbs(self) -> list[dict]:
        """获取全部知识库列表"""
        return self._read()

    def get_kb(self, kb_id: str) -> Optional[dict]:
        """按 kb_id 获取知识库"""
        for kb in self._read():
            if kb["kb_id"] == kb_id:
                return kb
        return None

    def create_kb(self, kb_id: str, kb_name: str) -> dict:
        """创建知识库"""
        now = self._now()
        kb = {
            "kb_id": kb_id,
            "kb_name": kb_name,
            "created_at": now,
            "updated_at": now,
            "status": "active",
            "doc_count": 0,
        }
        data = self._read()
        if any(item["kb_id"] == kb_id for item in data):
            raise ValueError(f"知识库ID已存在: {kb_id}")
        data.append(kb)
        self._write(data)
        return kb

    def update_kb(self, kb_id: str, kb_name: str) -> dict:
        """更新知识库名称"""
        data = self._read()
        for item in data:
            if item["kb_id"] == kb_id:
                item["kb_name"] = kb_name
                item["updated_at"] = self._now()
                self._write(data)
                return item
        raise ValueError(f"知识库不存在: {kb_id}")

    def delete_kb(self, kb_id: str) -> bool:
        """删除知识库"""
        data = self._read()
        for i, item in enumerate(data):
            if item["kb_id"] == kb_id:
                data.pop(i)
                self._write(data)
                return True
        raise ValueError(f"知识库不存在: {kb_id}")

    def exists(self, kb_id: str) -> bool:
        """检查知识库是否存在"""
        return any(item["kb_id"] == kb_id for item in self._read())
