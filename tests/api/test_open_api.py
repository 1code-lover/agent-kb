"""只读 Open API 授权、范围与审计测试。"""

from __future__ import annotations

import json
from pathlib import Path

from tests.api._testclient import TestClient

from api.app import app
from api.routers import open_api


class FakeTokens:
    def __init__(self):
        self.record = {"token_id": "tok-1", "name": "robot", "kb_ids": ["finance"], "status": "active"}

    def verify_token(self, token):
        if token != "good-token":
            raise PermissionError("Invalid access token")
        return dict(self.record)

    def authorize_kb(self, record, kb_id):
        if kb_id not in record["kb_ids"]:
            raise PermissionError("Knowledge base is not authorized")
        return {"kb_id": kb_id}

    def touch_last_used(self, token_id):
        return None


class Registry:
    def list_kbs(self):
        return [
            {"kb_id": "finance", "kb_name": "Finance", "status": "active"},
            {"kb_id": "hr", "kb_name": "HR", "status": "active"},
        ]


class Audit:
    def __init__(self):
        self.items = []

    def append(self, **kwargs):
        self.items.append(kwargs)


def test_open_api_requires_bearer_and_enforces_kb_scope(monkeypatch):
    tokens = FakeTokens()
    audit = Audit()
    monkeypatch.setattr(open_api, "access_token_service", tokens)
    monkeypatch.setattr(open_api, "kb_registry", Registry())
    monkeypatch.setattr(open_api, "open_api_audit", audit)
    monkeypatch.setattr(open_api, "run_readonly_query", lambda **kwargs: {"answer": "ok", "evidence": [], "kb_ids": [kwargs["kb_id"]]})
    client = TestClient(app)

    assert client.get("/api/open/v1/me").status_code == 401
    assert client.get("/api/open/v1/me", headers={"Authorization": "Bearer bad"}).status_code == 401
    headers = {"Authorization": "Bearer good-token"}
    assert client.get("/api/open/v1/me", headers=headers).json()["data"]["token_id"] == "tok-1"
    listed = client.get("/api/open/v1/knowledge-bases", headers=headers).json()["data"]["items"]
    assert [item["kb_id"] for item in listed] == ["finance"]
    assert client.post("/api/open/v1/answer", headers=headers, json={"kb_id": "hr", "question": "x"}).status_code == 403
    answer = client.post("/api/open/v1/answer", headers=headers, json={"kb_id": "finance", "question": "x"})
    assert answer.status_code == 200
    assert answer.json()["data"]["answer"] == "ok"
    assert audit.items[-1]["token_id"] == "tok-1"


def test_open_request_models_reject_execution_fields(monkeypatch):
    monkeypatch.setattr(open_api, "access_token_service", FakeTokens())
    response = TestClient(app).post(
        "/api/open/v1/answer",
        headers={"Authorization": "Bearer good-token"},
        json={"kb_id": "finance", "question": "x", "mode": "run_cmd", "command": "rm -rf /"},
    )
    assert response.status_code == 422


def test_open_answer_route_forwards_readonly_query_params(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(open_api, "access_token_service", FakeTokens())
    monkeypatch.setattr(open_api, "open_api_audit", Audit())
    monkeypatch.setattr(
        open_api,
        "run_readonly_query",
        lambda **kwargs: calls.append(kwargs) or {"answer": "ok", "evidence": []},
    )

    response = TestClient(app).post(
        "/api/open/v1/answer",
        headers={"Authorization": "Bearer good-token"},
        json={
            "kb_id": "finance",
            "question": "x",
            "top_k": 6,
            "response_mode": "tree_summarize",
            "use_reranker": False,
            "top_n": 2,
            "reranker_model": "bge-reranker-v2-m3",
        },
    )

    assert response.status_code == 200
    assert calls == [{
        "token_id": "tok-1",
        "kb_id": "finance",
        "question": "x",
        "top_k": 6,
        "response_mode": "tree_summarize",
        "use_reranker": False,
        "top_n": 2,
        "reranker_model": "bge-reranker-v2-m3",
    }]


def test_open_answer_rejects_unknown_response_mode(monkeypatch):
    monkeypatch.setattr(open_api, "access_token_service", FakeTokens())
    response = TestClient(app).post(
        "/api/open/v1/answer",
        headers={"Authorization": "Bearer good-token"},
        json={"kb_id": "finance", "question": "x", "response_mode": "unsupported-mode"},
    )
    assert response.status_code == 422


def test_open_api_schema_contains_only_readonly_paths_and_methods():
    schema = app.openapi()
    open_paths = {path: set(methods) for path, methods in schema["paths"].items() if path.startswith("/api/open/v1")}
    assert open_paths == {
        "/api/open/v1/me": {"get"},
        "/api/open/v1/knowledge-bases": {"get"},
        "/api/open/v1/search": {"post"},
        "/api/open/v1/answer": {"post"},
    }


def test_audit_file_omits_token_secret_and_question_body(tmp_path):
    """真实审计文件只能包含白名单字段，不能落盘敏感请求内容。"""
    from api.services.open_api_audit import OpenAPIAudit

    path = tmp_path / "open-api-audit.jsonl"
    audit = OpenAPIAudit(path)
    full_token = "nak_ro_tok-1_super-secret"
    full_question = "完整问题正文含有商业秘密"
    audit.append(
        token_id="tok-1",
        route="/answer",
        kb_id="finance",
        status_code=200,
        duration_ms=12.5,
        request_id="req-1",
        token=full_token,
        secret="super-secret",
        question=full_question,
    )

    raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert set(payload) == {
        "created_at",
        "duration_ms",
        "kb_id",
        "request_id",
        "route",
        "status_code",
        "token_id",
    }
    assert full_token not in raw
    assert "super-secret" not in raw
    assert full_question not in raw


def test_search_rejects_answer_only_query_fields(monkeypatch):
    monkeypatch.setattr(open_api, "access_token_service", FakeTokens())
    response = TestClient(app).post(
        "/api/open/v1/search",
        headers={"Authorization": "Bearer good-token"},
        json={"kb_id": "finance", "question": "revenue", "response_mode": "compact"},
    )
    assert response.status_code == 422



def test_search_uses_structured_retrieval_executor(monkeypatch):
    """search 路由必须返回结构化命中，不能复用生成式 answer 执行器。"""
    tokens = FakeTokens()
    audit = Audit()
    answer_calls: list[dict] = []
    search_calls: list[dict] = []
    monkeypatch.setattr(open_api, "access_token_service", tokens)
    monkeypatch.setattr(open_api, "open_api_audit", audit)
    monkeypatch.setattr(
        open_api,
        "run_readonly_query",
        lambda **kwargs: answer_calls.append(kwargs) or {"answer": "unexpected"},
    )
    monkeypatch.setattr(
        open_api,
        "run_readonly_search",
        lambda **kwargs: search_calls.append(kwargs) or {
            "kb_id": kwargs["kb_id"],
            "question": kwargs["question"],
            "hits": [{"kb_id": kwargs["kb_id"], "text": "match"}],
            "evidence": [{"kb_id": kwargs["kb_id"], "excerpt": "match"}],
        },
    )

    response = TestClient(app).post(
        "/api/open/v1/search",
        headers={"Authorization": "Bearer good-token"},
        json={"kb_id": "finance", "question": "revenue", "top_k": 3},
    )

    assert response.status_code == 200
    assert response.json()["data"]["hits"][0]["text"] == "match"
    assert search_calls == [{"token_id": "tok-1", "kb_id": "finance", "question": "revenue", "top_k": 3}]
    assert answer_calls == []

def test_open_answer_empty_kb_returns_400_instead_of_500(monkeypatch):
    monkeypatch.setattr(open_api, "access_token_service", FakeTokens())
    monkeypatch.setattr(open_api, "open_api_audit", Audit())
    monkeypatch.setattr(
        open_api,
        "run_readonly_query",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("Knowledge base is empty. Please import documents first.")),
    )

    response = TestClient(app).post(
        "/api/open/v1/answer",
        headers={"Authorization": "Bearer good-token"},
        json={"kb_id": "finance", "question": "x"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == 400
    assert "Please import documents first" in response.json()["message"]

def test_open_search_empty_kb_returns_400_instead_of_500(monkeypatch):
    monkeypatch.setattr(open_api, "access_token_service", FakeTokens())
    monkeypatch.setattr(open_api, "open_api_audit", Audit())
    monkeypatch.setattr(
        open_api,
        "run_readonly_search",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("Knowledge base is empty. Please import documents first.")),
    )

    response = TestClient(app).post(
        "/api/open/v1/search",
        headers={"Authorization": "Bearer good-token"},
        json={"kb_id": "finance", "question": "x"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == 400
    assert "Please import documents first" in response.json()["message"]


