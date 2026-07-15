"""KBRegistry 原子写入与并发计数测试。"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from server.kb_registry import KBRegistry


def test_write_failure_keeps_existing_json_valid(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    registry = KBRegistry(storage_path=tmp_path / "kb_registry.json")
    registry.create_kb("kb-a", "KB A")

    def fail_replace(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr("server.kb_registry.os.replace", fail_replace)

    with pytest.raises(OSError):
        registry.create_kb("kb-b", "KB B")

    data = json.loads((tmp_path / "kb_registry.json").read_text(encoding="utf-8"))
    assert [item["kb_id"] for item in data] == ["kb-a"]


def test_concurrent_add_doc_count_does_not_lose_updates(tmp_path) -> None:
    registry = KBRegistry(storage_path=tmp_path / "kb_registry.json")
    registry.create_kb("kb-a", "KB A")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _i: registry.add_doc_count("kb-a", 1), range(100)))

    assert registry.get_kb("kb-a")["doc_count"] == 100


def test_concurrent_decrement_doc_count_never_negative(tmp_path) -> None:
    registry = KBRegistry(storage_path=tmp_path / "kb_registry.json")
    registry.create_kb("kb-a", "KB A")
    registry.set_doc_count("kb-a", 10)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _i: registry.add_doc_count("kb-a", -1), range(100)))

    assert registry.get_kb("kb-a")["doc_count"] == 0


def test_set_doc_count_clamps_negative_to_zero(tmp_path) -> None:
    registry = KBRegistry(storage_path=tmp_path / "kb_registry.json")
    registry.create_kb("kb-a", "KB A")

    registry.set_doc_count("kb-a", -10)

    assert registry.get_kb("kb-a")["doc_count"] == 0


def test_doc_count_update_for_missing_kb_raises(tmp_path) -> None:
    registry = KBRegistry(storage_path=tmp_path / "kb_registry.json")

    with pytest.raises(ValueError, match="\u4e0d\u5b58\u5728"):
        registry.add_doc_count("missing", 1)

    with pytest.raises(ValueError, match="\u4e0d\u5b58\u5728"):
        registry.set_doc_count("missing", 1)
