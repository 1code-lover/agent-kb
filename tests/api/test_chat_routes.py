"""Chat 路由契约补充测试。"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.app import app
from api.routers import chat as chat_router
from server.kb_errors import (
    KBConflictError,
    KBConsistencyError,
    KBNotFoundError,
    KBServiceError,
    KBUnavailableError,
    KBValidationError,
)

client = TestClient(app)


class GenericKBError(KBServiceError):
    """用于覆盖 chat 路由默认 KB 错误映射分支的通用异常。"""


@pytest.mark.parametrize(
    ("exc", "expected_status"),
    [
        (KBValidationError("参数非法"), 400),
        (KBUnavailableError("知识库不可用"), 400),
        (KBNotFoundError("知识库不存在"), 404),
        (KBConflictError("知识库冲突"), 409),
        (KBConsistencyError("知识库状态不一致"), 500),
        (GenericKBError("未知 chat 错误"), 400),
    ],
)
def test_raise_http_from_kb_error_maps_status_code(exc: KBServiceError, expected_status: int) -> None:
    """chat 路由应把稳定 KB 异常映射为约定 HTTP 状态码。"""

    with pytest.raises(HTTPException) as caught:
        chat_router._raise_http_from_kb_error(exc)

    assert caught.value.status_code == expected_status
    assert caught.value.detail == exc.message


def test_query_route_returns_service_payload() -> None:
    """/api/chat/query 应透传 QueryRequest 并包装服务层结果。"""

    payload = {"answer": "命中答案", "sources": [{"id": "e1"}], "scope": {"kb_id": "kb-a"}}
    with patch("api.routers.chat.chat_service.query", return_value=payload) as mock_query:
        resp = client.post(
            "/api/chat/query",
            json={"question": "测试问题", "session_id": "s-1", "kb_ids": ["kb-a"]},
        )

    assert resp.status_code == 200
    assert resp.json()["data"] == payload
    request = mock_query.call_args.args[0]
    assert request.question == "测试问题"
    assert request.session_id == "s-1"
    assert request.kb_ids == ["kb-a"]


def test_query_route_maps_runtime_error_to_503() -> None:
    """chat query 若遇到运行时故障，应返回 503。"""

    with patch("api.routers.chat.chat_service.query", side_effect=RuntimeError("engine unavailable")):
        resp = client.post("/api/chat/query", json={"question": "测试问题"})

    assert resp.status_code == 503
    assert resp.json()["message"] == "engine unavailable"


def test_query_route_maps_unexpected_error_to_400() -> None:
    """chat query 的其他异常应统一映射为 400。"""

    with patch("api.routers.chat.chat_service.query", side_effect=ValueError("bad payload")):
        resp = client.post("/api/chat/query", json={"question": "测试问题"})

    assert resp.status_code == 400
    assert resp.json()["message"] == "bad payload"


def test_history_route_returns_messages_for_session() -> None:
    """/api/chat/history 应根据 session_id 返回会话历史。"""

    messages = [{"role": "user", "content": "hello"}]
    with patch("api.routers.chat.chat_service.get_history", return_value=messages) as mock_get_history:
        resp = client.get("/api/chat/history", params={"session_id": "s-2"})

    assert resp.status_code == 200
    assert resp.json()["data"] == {"session_id": "s-2", "messages": messages}
    mock_get_history.assert_called_once_with("s-2")


def test_clear_history_route_calls_service_and_returns_receipt() -> None:
    """DELETE /api/chat/history 应清理会话并返回 cleared 回执。"""

    with patch("api.routers.chat.chat_service.clear_history") as mock_clear_history:
        resp = client.request("DELETE", "/api/chat/history", params={"session_id": "s-3"})

    assert resp.status_code == 200
    assert resp.json()["data"] == {"session_id": "s-3", "cleared": True}
    mock_clear_history.assert_called_once_with("s-3")
