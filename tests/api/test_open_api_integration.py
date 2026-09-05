"""只读 Open API 与知识库物理目录隔离的集成测试。"""

from __future__ import annotations

from types import SimpleNamespace

from tests.api._testclient import TestClient
from llama_index.core import Settings, StorageContext, VectorStoreIndex, load_index_from_storage
from llama_index.core.embeddings import MockEmbedding
from llama_index.core.schema import TextNode

from api.app import app
from api.routers import open_api
from api.services import chat_service, query_scope


class _Tokens:
    """仅授权 finance 的测试令牌。"""

    def verify_token(self, token):
        if token != "finance-token":
            raise PermissionError("Invalid access token")
        return {"token_id": "tok-finance", "name": "finance-agent", "kb_ids": ["finance"], "status": "active"}

    def authorize_kb(self, record, kb_id):
        if kb_id not in record["kb_ids"]:
            raise PermissionError("Knowledge base is not authorized")
        return {"kb_id": kb_id, "status": "active"}

    def touch_last_used(self, token_id):
        return None


class _Registry:
    def list_kbs(self):
        return [
            {"kb_id": "finance", "kb_name": "Finance", "status": "active"},
            {"kb_id": "hr", "kb_name": "HR", "status": "active"},
        ]


class _Audit:
    def append(self, **kwargs):
        return None


class _PhysicalEngine:
    """从指定物理目录加载节点并以稳定响应暴露加载结果。"""

    def __init__(self, persist_dir):
        storage_context = StorageContext.from_defaults(persist_dir=str(persist_dir))
        self.index = load_index_from_storage(storage_context)
        self.nodes = list(storage_context.docstore.docs.values())

    def query(self, question):
        text = " | ".join(node.text for node in self.nodes)
        return SimpleNamespace(response=text, source_nodes=[])


class _PhysicalRuntime:
    """按请求的单一 kb_id 选择真实隔离目录。"""

    def __init__(self, storage_root):
        self.storage_root = storage_root
        self.selected: list[str] = []
        self.query_engine_calls: list[dict] = []

    def ensure_index_loaded(self, kb_id=None):
        return True

    def build_query_engine(
        self,
        kb_ids=None,
        *,
        top_k=None,
        response_mode=None,
        use_reranker=None,
        top_n=None,
        reranker_model=None,
    ):
        assert kb_ids and len(kb_ids) == 1
        kb_id = kb_ids[0]
        self.selected.append(kb_id)
        self.query_engine_calls.append({
            "kb_ids": list(kb_ids),
            "top_k": top_k,
            "response_mode": response_mode,
            "use_reranker": use_reranker,
            "top_n": top_n,
            "reranker_model": reranker_model,
        })
        return _PhysicalEngine(self.storage_root / "kbs" / kb_id)


def _persist_kb(storage_root, kb_id, node_id, text, embedding):
    """在知识库独立目录中创建真实 LlamaIndex 索引。"""
    storage_context = StorageContext.from_defaults()
    node = TextNode(id_=node_id, text=text, metadata={"kb_id": kb_id}, embedding=embedding)
    VectorStoreIndex([node], storage_context=storage_context, store_nodes_override=True)
    storage_context.persist(persist_dir=str(storage_root / "kbs" / kb_id))


def test_open_api_reads_only_the_authorized_physical_kb(tmp_path, monkeypatch):
    """finance 令牌的回答只能来自 finance 物理索引，且 hr 请求在查询前被拒绝。"""
    monkeypatch.setattr(Settings, "_embed_model", MockEmbedding(embed_dim=4))
    storage_root = tmp_path / "storage"
    _persist_kb(storage_root, "finance", "finance-1", "FINANCE_ONLY revenue 100", [1.0, 0.0, 0.0, 0.0])
    _persist_kb(storage_root, "hr", "hr-1", "HR_ONLY headcount 20", [0.0, 1.0, 0.0, 0.0])
    runtime = _PhysicalRuntime(storage_root)

    monkeypatch.setattr(open_api, "access_token_service", _Tokens())
    monkeypatch.setattr(open_api, "kb_registry", _Registry())
    monkeypatch.setattr(open_api, "open_api_audit", _Audit())
    monkeypatch.setattr(chat_service, "runtime_state", runtime)
    monkeypatch.setattr(query_scope, "_ensure_kb_active", lambda kb_id: {"kb_id": kb_id, "status": "active"})
    monkeypatch.setattr(chat_service.model_service, "get_model_health", lambda: {"state": "ready"})

    client = TestClient(app)
    headers = {"Authorization": "Bearer finance-token"}
    response = client.post(
        "/api/open/v1/answer",
        headers=headers,
        json={"kb_id": "finance", "question": "summarize revenue"},
    )
    assert response.status_code == 200
    answer = response.json()["data"]["answer"]
    assert "FINANCE_ONLY" in answer
    assert "HR_ONLY" not in answer
    assert runtime.selected == ["finance"]

    denied = client.post(
        "/api/open/v1/answer",
        headers=headers,
        json={"kb_id": "hr", "question": "summarize headcount"},
    )
    assert denied.status_code == 403
    assert runtime.selected == ["finance"]



def test_open_api_answer_forwards_readonly_query_params_to_physical_runtime(tmp_path, monkeypatch):
    """answer 路由的只读检索参数应进入单 KB 物理 runtime。"""
    monkeypatch.setattr(Settings, "_embed_model", MockEmbedding(embed_dim=4))
    storage_root = tmp_path / "storage"
    _persist_kb(storage_root, "finance", "finance-1", "FINANCE_ONLY revenue 100", [1.0, 0.0, 0.0, 0.0])
    runtime = _PhysicalRuntime(storage_root)

    monkeypatch.setattr(open_api, "access_token_service", _Tokens())
    monkeypatch.setattr(open_api, "kb_registry", _Registry())
    monkeypatch.setattr(open_api, "open_api_audit", _Audit())
    monkeypatch.setattr(chat_service, "runtime_state", runtime)
    monkeypatch.setattr(query_scope, "_ensure_kb_active", lambda kb_id: {"kb_id": kb_id, "status": "active"})
    monkeypatch.setattr(chat_service.model_service, "get_model_health", lambda: {"state": "ready"})

    response = TestClient(app).post(
        "/api/open/v1/answer",
        headers={"Authorization": "Bearer finance-token"},
        json={
            "kb_id": "finance",
            "question": "summarize revenue",
            "top_k": 8,
            "response_mode": "tree_summarize",
            "use_reranker": False,
            "top_n": 2,
            "reranker_model": "bge-reranker-v2-m3",
        },
    )

    assert response.status_code == 200
    assert runtime.query_engine_calls == [{
        "kb_ids": ["finance"],
        "top_k": 8,
        "response_mode": "tree_summarize",
        "use_reranker": False,
        "top_n": 2,
        "reranker_model": "bge-reranker-v2-m3",
    }]
