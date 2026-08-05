"""StorageContext 工厂与默认上下文懒加载。

职责：
- 兼容历史默认 storage 目录；
- 支持按 kb_id / persist_dir 创建独立 StorageContext；
- 仅在真正访问默认知识库存储时，才懒加载全局默认 StorageContext。
"""

from __future__ import annotations

from pathlib import Path
from threading import Lock

from llama_index.core import StorageContext

from config import THINKRAG_ENV
from server.stores.doc_store import DOC_STORE
from server.stores.index_store import INDEX_STORE
from server.stores.vector_store import VECTOR_STORE
from server.utils.file import get_kb_storage_dir, get_storage_root

_DOCSTORE_FILENAME = "docstore.json"
_DEFAULT_STORAGE_CONTEXT: StorageContext | None = None
_DEFAULT_STORAGE_CONTEXT_LOCK = Lock()


def _normalize_persist_dir(persist_dir: str | Path | None = None) -> Path:
    """规范化 persist_dir；为空时回落到默认 storage 根目录。"""
    if persist_dir is None:
        return get_storage_root()
    return Path(persist_dir).resolve()


def _create_development_storage_context(resolved_dir: Path) -> StorageContext:
    """在开发模式下按目录创建或恢复 StorageContext。"""
    marker = resolved_dir / _DOCSTORE_FILENAME
    if marker.exists():
        storage_context = StorageContext.from_defaults(persist_dir=str(resolved_dir))
        print(f"Loaded storage context from {resolved_dir}")
        return storage_context

    storage_context = StorageContext.from_defaults()
    print(f"Created new storage context for {resolved_dir}")
    return storage_context


def _create_default_storage_context() -> StorageContext:
    """创建默认 storage/ 根目录对应的 StorageContext。"""
    if THINKRAG_ENV == "development":
        return _create_development_storage_context(_normalize_persist_dir(None))

    return StorageContext.from_defaults(
        docstore=DOC_STORE,
        index_store=INDEX_STORE,
        vector_store=VECTOR_STORE,
    )


def get_default_storage_context() -> StorageContext:
    """按需懒加载默认 StorageContext，并在进程内复用。"""
    global _DEFAULT_STORAGE_CONTEXT
    if _DEFAULT_STORAGE_CONTEXT is None:
        with _DEFAULT_STORAGE_CONTEXT_LOCK:
            if _DEFAULT_STORAGE_CONTEXT is None:
                _DEFAULT_STORAGE_CONTEXT = _create_default_storage_context()
    return _DEFAULT_STORAGE_CONTEXT


class LazyStorageContext:
    """兼容历史 STORAGE_CONTEXT 常量写法的懒加载代理。"""

    def get(self) -> StorageContext:
        """返回真实的默认 StorageContext。"""
        return get_default_storage_context()

    def __getattr__(self, item: str):
        return getattr(self.get(), item)

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试展示
        if _DEFAULT_STORAGE_CONTEXT is None:
            return "<LazyStorageContext unloaded>"
        return repr(_DEFAULT_STORAGE_CONTEXT)


def create_storage_context(persist_dir: str | Path | None = None) -> StorageContext:
    """按指定持久化目录创建 StorageContext。"""
    if persist_dir is None:
        return get_default_storage_context()

    resolved_dir = _normalize_persist_dir(persist_dir)
    if THINKRAG_ENV == "development":
        return _create_development_storage_context(resolved_dir)

    return StorageContext.from_defaults(
        docstore=DOC_STORE,
        index_store=INDEX_STORE,
        vector_store=VECTOR_STORE,
    )


def create_storage_context_for_kb(kb_id: str) -> StorageContext:
    """按知识库 ID 创建对应存储目录的 StorageContext。"""
    persist_dir = get_kb_storage_dir(kb_id, create=False)
    return create_storage_context(persist_dir=persist_dir)


STORAGE_CONTEXT = LazyStorageContext()

__all__ = [
    "STORAGE_CONTEXT",
    "LazyStorageContext",
    "create_storage_context",
    "create_storage_context_for_kb",
    "get_default_storage_context",
]
