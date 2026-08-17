"""StorageContext 工厂分支补充测试。"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from llama_index.core import StorageContext


@pytest.fixture()
def storage_context_module():
    """重新加载 storage_context 模块，避免测试之间共享全局缓存。"""
    module = importlib.reload(importlib.import_module("server.stores.storage_context"))
    yield module
    module._DEFAULT_STORAGE_CONTEXT = None


def test_normalize_persist_dir_defaults_to_storage_root(
    monkeypatch: pytest.MonkeyPatch,
    storage_context_module,
    tmp_path: Path,
) -> None:
    """未显式指定 persist_dir 时应回退到 storage 根目录。"""
    storage_root = tmp_path / "storage-root"
    monkeypatch.setattr(storage_context_module, "get_storage_root", lambda: storage_root)

    assert storage_context_module._normalize_persist_dir() == storage_root


def test_create_storage_context_uses_isolated_directory_in_non_development(
    monkeypatch: pytest.MonkeyPatch,
    storage_context_module,
    tmp_path: Path,
) -> None:
    """显式 persist_dir 在非开发环境下也必须创建 KB 独立存储上下文。"""
    persist_dir = tmp_path / "storage" / "kbs" / "kb-a"
    captured: list[dict[str, object]] = []

    def fake_from_defaults(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(name="storage-context")

    monkeypatch.setattr(storage_context_module, "THINKRAG_ENV", "production")
    monkeypatch.setattr(StorageContext, "from_defaults", staticmethod(fake_from_defaults))

    result = storage_context_module.create_storage_context(persist_dir=persist_dir)

    assert result.name == "storage-context"
    assert captured == [{}]


def test_create_storage_context_loads_existing_development_persist_dir(
    monkeypatch: pytest.MonkeyPatch,
    storage_context_module,
    tmp_path: Path,
) -> None:
    """开发环境下若 persist_dir 已有 docstore 标记文件，应按目录恢复 StorageContext。"""
    persist_dir = tmp_path / "storage" / "kbs" / "kb-a"
    persist_dir.mkdir(parents=True, exist_ok=True)
    (persist_dir / "docstore.json").write_text("{}", encoding="utf-8")
    captured: list[dict[str, object]] = []

    def fake_from_defaults(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(source="persisted")

    monkeypatch.setattr(storage_context_module, "THINKRAG_ENV", "development")
    monkeypatch.setattr(StorageContext, "from_defaults", staticmethod(fake_from_defaults))

    result = storage_context_module.create_storage_context(persist_dir=persist_dir)

    assert result.source == "persisted"
    assert captured == [{"persist_dir": str(persist_dir.resolve())}]


def test_create_storage_context_creates_fresh_context_when_marker_missing(
    monkeypatch: pytest.MonkeyPatch,
    storage_context_module,
    tmp_path: Path,
) -> None:
    """开发环境下若目录不存在 docstore 标记文件，应创建全新 StorageContext。"""
    persist_dir = tmp_path / "storage" / "kbs" / "kb-a"
    persist_dir.mkdir(parents=True, exist_ok=True)
    captured: list[dict[str, object]] = []

    def fake_from_defaults(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(source="fresh")

    monkeypatch.setattr(storage_context_module, "THINKRAG_ENV", "development")
    monkeypatch.setattr(StorageContext, "from_defaults", staticmethod(fake_from_defaults))

    result = storage_context_module.create_storage_context(persist_dir=persist_dir)

    assert result.source == "fresh"
    assert captured == [{}]


def test_create_storage_context_for_kb_delegates_to_kb_storage_dir(
    monkeypatch: pytest.MonkeyPatch,
    storage_context_module,
    tmp_path: Path,
) -> None:
    """按知识库创建 StorageContext 时应先解析 kb 专属存储目录，再委托通用工厂。"""
    target_dir = tmp_path / "storage" / "kbs" / "kb-a"
    calls: dict[str, object] = {}

    monkeypatch.setattr(storage_context_module, "get_kb_storage_dir", lambda kb_id, create=False: target_dir)

    def fake_create_storage_context(*, persist_dir):
        calls["persist_dir"] = persist_dir
        return SimpleNamespace(source="delegated")

    monkeypatch.setattr(storage_context_module, "create_storage_context", fake_create_storage_context)

    result = storage_context_module.create_storage_context_for_kb("kb-a")

    assert result.source == "delegated"
    assert calls["persist_dir"] == target_dir


def test_create_default_storage_context_uses_shared_stores_in_non_development(
    monkeypatch: pytest.MonkeyPatch,
    storage_context_module,
) -> None:
    """默认 StorageContext 在非开发环境下应复用共享 doc/index/vector store。"""
    captured: list[dict[str, object]] = []

    def fake_from_defaults(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(source="default-shared")

    monkeypatch.setattr(storage_context_module, "THINKRAG_ENV", "production")
    monkeypatch.setattr(StorageContext, "from_defaults", staticmethod(fake_from_defaults))

    result = storage_context_module._create_default_storage_context()

    assert result.source == "default-shared"
    assert captured == [
        {
            "docstore": storage_context_module.DOC_STORE,
            "index_store": storage_context_module.INDEX_STORE,
            "vector_store": storage_context_module.VECTOR_STORE,
        }
    ]


def test_create_storage_context_without_persist_dir_reuses_default_context(
    monkeypatch: pytest.MonkeyPatch,
    storage_context_module,
) -> None:
    """未显式传入 persist_dir 时应直接复用默认 StorageContext。"""
    default_context = SimpleNamespace(source="default-context")
    monkeypatch.setattr(storage_context_module, "get_default_storage_context", lambda: default_context)

    assert storage_context_module.create_storage_context() is default_context


def test_explicit_kb_storage_contexts_remain_physically_isolated_after_reload(
    monkeypatch: pytest.MonkeyPatch,
    storage_context_module,
    tmp_path: Path,
) -> None:
    """两个 KB 持久化后应拥有独立文件集，重载时不得看到对方节点。"""
    from llama_index.core.schema import TextNode

    monkeypatch.setattr(storage_context_module, "THINKRAG_ENV", "production")
    kb_a_dir = tmp_path / "storage" / "kbs" / "kb-a"
    kb_b_dir = tmp_path / "storage" / "kbs" / "kb-b"

    kb_a_context = storage_context_module.create_storage_context(persist_dir=kb_a_dir)
    kb_b_context = storage_context_module.create_storage_context(persist_dir=kb_b_dir)

    assert kb_a_context is not kb_b_context
    assert kb_a_context.docstore is not kb_b_context.docstore

    node_a = TextNode(id_="kb-a-node", text="alpha only", metadata={"kb_id": "kb-a"})
    kb_a_context.docstore.add_documents([node_a])
    kb_a_context.persist(persist_dir=str(kb_a_dir))
    kb_b_context.persist(persist_dir=str(kb_b_dir))

    reloaded_a = storage_context_module.create_storage_context(persist_dir=kb_a_dir)
    reloaded_b = storage_context_module.create_storage_context(persist_dir=kb_b_dir)

    assert reloaded_a.docstore.document_exists("kb-a-node") is True
    assert reloaded_b.docstore.document_exists("kb-a-node") is False
    assert (kb_a_dir / "docstore.json").is_file()
    assert (kb_b_dir / "docstore.json").is_file()
