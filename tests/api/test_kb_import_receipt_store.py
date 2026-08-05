"""知识库最近导入回执存储测试。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from api.services import kb_import_receipt_store as receipt_store


@pytest.fixture
def isolated_receipt_root(tmp_path, monkeypatch):
    """把回执落盘隔离到临时目录，避免污染真实 storage。"""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_save_and_load_latest_import_receipt_roundtrip(isolated_receipt_root):
    """保存后的最近回执应能完整读回。"""
    saved = receipt_store.save_latest_import_receipt(
        "kb-a",
        source_label="批量导入",
        result={"receipt_id": "r-1", "indexed_chunks": 3},
        created_at="2026-07-30T00:00:00+00:00",
    )

    loaded = receipt_store.load_latest_import_receipt("kb-a")

    assert loaded == saved
    assert loaded["source_label"] == "批量导入"
    assert loaded["result"]["receipt_id"] == "r-1"


def test_load_latest_import_receipt_returns_none_when_file_missing(isolated_receipt_root):
    """文件不存在时应返回 None。"""
    assert receipt_store.load_latest_import_receipt("kb-a") is None


def test_load_latest_import_receipt_returns_none_for_empty_payload(isolated_receipt_root):
    """空 JSON 对象不应被当成有效回执。"""
    path = receipt_store._storage_path("kb-a")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")

    assert receipt_store.load_latest_import_receipt("kb-a") is None


def test_load_latest_import_receipt_normalizes_kb_id_field(isolated_receipt_root):
    """读取时应以请求中的 kb_id 为准，避免脏数据污染回显。"""
    path = receipt_store._storage_path("kb-a")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "kb_id": "other-kb",
                "source_label": "批量导入",
                "created_at": "2026-07-30T00:00:00+00:00",
                "result": {"receipt_id": "r-2"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    loaded = receipt_store.load_latest_import_receipt("kb-a")

    assert loaded is not None
    assert loaded["kb_id"] == "kb-a"


def test_delete_latest_import_receipt_is_noop_when_file_missing(isolated_receipt_root):
    """删除不存在的最近回执不应报错。"""
    receipt_store.delete_latest_import_receipt("kb-a")

    assert receipt_store.load_latest_import_receipt("kb-a") is None


def test_delete_latest_import_receipt_tolerates_racy_file_not_found(isolated_receipt_root, monkeypatch):
    """exists 判真但 unlink 时被别处删掉，也应被安全吞掉。"""
    path = receipt_store._storage_path("kb-a")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")

    def _raise_file_not_found(self):
        raise FileNotFoundError("already deleted")

    monkeypatch.setattr(Path, "unlink", _raise_file_not_found)

    receipt_store.delete_latest_import_receipt("kb-a")


def test_atomic_write_retries_permission_error_then_succeeds(isolated_receipt_root, monkeypatch):
    """原子写入遇到临时文件锁时，应重试并最终成功。"""
    path = isolated_receipt_root / "storage" / "kb_import_receipts" / "kb-a.json"
    real_replace = receipt_store.os.replace
    attempts = {"count": 0}

    def flaky_replace(src, dst):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise PermissionError("locked")
        return real_replace(src, dst)

    sleep = MagicMock()
    monkeypatch.setattr(receipt_store.os, "replace", flaky_replace)
    monkeypatch.setattr(receipt_store.time, "sleep", sleep)

    receipt_store._atomic_write(path, {"ok": True})

    assert attempts["count"] == 3
    assert json.loads(path.read_text(encoding="utf-8")) == {"ok": True}
    assert sleep.call_count == 2
    assert list(path.parent.glob("kb-a.json.tmp-*")) == []


def test_atomic_write_raises_after_retries_and_cleans_tmp_file(isolated_receipt_root, monkeypatch):
    """若重试耗尽仍失败，应抛错且清理遗留 tmp 文件。"""
    path = isolated_receipt_root / "storage" / "kb_import_receipts" / "kb-a.json"

    monkeypatch.setattr(
        receipt_store.os,
        "replace",
        MagicMock(side_effect=PermissionError("still locked")),
    )
    monkeypatch.setattr(receipt_store.time, "sleep", MagicMock())

    with pytest.raises(PermissionError, match="still locked"):
        receipt_store._atomic_write(path, {"ok": True})

    assert not path.exists()
    assert list(path.parent.glob("kb-a.json.tmp-*")) == []
