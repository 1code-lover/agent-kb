"""会话存储模块回归测试。"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from api.services import session_store


def test_session_file_sanitizes_windows_unsafe_session_id(monkeypatch, tmp_path) -> None:
    """session_id 应清洗为 Windows 可接受的文件名。"""
    monkeypatch.setattr(session_store, "_SESSION_DIR", tmp_path)

    path = session_store._session_file("eval::case/1?")

    assert path.parent == tmp_path
    assert path.suffix == ".json"
    assert ":" not in path.name
    assert "/" not in path.name
    assert "?" not in path.name


def test_append_chat_message_supports_eval_style_session_id(monkeypatch, tmp_path) -> None:
    """评测风格 session_id 含 :: 时也应可正常持久化。"""
    monkeypatch.setattr(session_store, "_SESSION_DIR", tmp_path)

    session_id = "eval::eval-v5-md-002"
    session_store.reset_session(session_id)
    session_store.append_chat_message(session_id, "user", "hello")
    history = session_store.list_chat_messages(session_id)

    assert history[-1]["role"] == "user"
    assert history[-1]["content"] == "hello"

    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    assert ":" not in files[0].name
    assert session_store.load_session(session_id)["session_id"] == session_id



def test_atomic_write_retries_permission_error_then_succeeds(monkeypatch, tmp_path) -> None:
    """会话快照原子写入遇到临时锁时，应重试并最终成功。"""
    path = tmp_path / "session.json"
    real_replace = session_store.os.replace
    attempts = {"count": 0}

    def flaky_replace(src, dst):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise PermissionError("locked")
        return real_replace(src, dst)

    sleep = MagicMock()
    monkeypatch.setattr(session_store.os, "replace", flaky_replace)
    monkeypatch.setattr(session_store.time, "sleep", sleep)

    session_store._atomic_write(path, {"ok": True})

    assert attempts["count"] == 3
    assert json.loads(path.read_text(encoding="utf-8")) == {"ok": True}
    assert sleep.call_count == 2
    assert list(path.parent.glob("session.json.tmp-*")) == []



def test_atomic_write_raises_after_retries_and_cleans_tmp_file(monkeypatch, tmp_path) -> None:
    """若重试耗尽仍失败，应抛错且清理遗留 tmp 文件。"""
    path = tmp_path / "session.json"

    monkeypatch.setattr(
        session_store.os,
        "replace",
        MagicMock(side_effect=PermissionError("still locked")),
    )
    monkeypatch.setattr(session_store.time, "sleep", MagicMock())

    with pytest.raises(PermissionError, match="still locked"):
        session_store._atomic_write(path, {"ok": True})

    assert not path.exists()
    assert list(path.parent.glob("session.json.tmp-*")) == []
