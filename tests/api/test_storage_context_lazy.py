"""storage_context ????????"""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
from llama_index.core import StorageContext



def test_storage_context_module_import_does_not_eagerly_load_default_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """???????????? StorageContext.from_defaults?"""

    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_from_defaults(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            docstore=object(),
            index_store=object(),
            vector_store=object(),
        )

    monkeypatch.setattr(StorageContext, "from_defaults", staticmethod(fake_from_defaults))

    storage_context_module = importlib.reload(importlib.import_module("server.stores.storage_context"))
    compat_module = importlib.reload(importlib.import_module("server.stores.strage_context"))

    assert calls == []

    _ = storage_context_module.STORAGE_CONTEXT.docstore
    assert len(calls) == 1

    _ = compat_module.STORAGE_CONTEXT.docstore
    assert len(calls) == 1





def test_advanced_ingestion_pipeline_accepts_injected_storage_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AdvancedIngestionPipeline 应允许注入外部 storage_context，而不因额外属性报错。"""

    ingestion_module = importlib.import_module("server.ingestion")
    captured: dict[str, object] = {}

    def fake_pipeline_init(self, **kwargs) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(ingestion_module.IngestionPipeline, "__init__", fake_pipeline_init)
    monkeypatch.setattr(
        ingestion_module,
        "Settings",
        SimpleNamespace(embed_model=object(), text_splitter=object()),
    )

    fake_storage = SimpleNamespace(docstore=object(), vector_store=object())
    pipeline = ingestion_module.AdvancedIngestionPipeline(storage_context=fake_storage)

    assert isinstance(pipeline, ingestion_module.AdvancedIngestionPipeline)
    assert captured["docstore"] is fake_storage.docstore
    assert captured["vector_store"] is fake_storage.vector_store

def test_get_default_storage_context_only_initializes_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """?????? StorageContext ??????????"""

    calls: list[int] = []

    def fake_from_defaults(*args, **kwargs):
        calls.append(1)
        return SimpleNamespace(
            docstore=object(),
            index_store=object(),
            vector_store=object(),
        )

    monkeypatch.setattr(StorageContext, "from_defaults", staticmethod(fake_from_defaults))
    storage_context_module = importlib.reload(importlib.import_module("server.stores.storage_context"))

    first = storage_context_module.get_default_storage_context()
    second = storage_context_module.get_default_storage_context()

    assert first is second
    assert calls == [1]
