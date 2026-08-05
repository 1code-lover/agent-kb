"""会话存储模块回归测试。"""

from __future__ import annotations

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
