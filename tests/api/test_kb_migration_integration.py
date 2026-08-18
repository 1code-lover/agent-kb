"""历史共享索引迁移的真实 LlamaIndex 持久化集成测试。"""

from __future__ import annotations

from pathlib import Path

from llama_index.core import Settings, StorageContext, VectorStoreIndex, load_index_from_storage
from llama_index.core.embeddings import MockEmbedding
from llama_index.core.schema import TextNode

from api.services.kb_migration_service import KBMigrationService
from server.index import IndexManager


class _Registry:
    """提供迁移集成测试所需的最小知识库注册表。"""

    def list_kbs(self) -> list[dict[str, str]]:
        return [
            {"kb_id": "finance", "status": "active"},
            {"kb_id": "hr", "status": "active"},
        ]


class _Runtime:
    """记录迁移完成后被刷新的知识库运行时。"""

    def __init__(self) -> None:
        self.dropped: list[str] = []

    def drop_index_manager(self, kb_id: str) -> None:
        self.dropped.append(kb_id)


def _node(node_id: str, kb_id: str, text: str, ref_doc_id: str, embedding: list[float]) -> TextNode:
    """创建携带稳定标识、知识库归属和显式向量的真实节点。"""
    return TextNode(
        id_=node_id,
        text=text,
        metadata={"kb_id": kb_id, "ref_doc_id": ref_doc_id},
        embedding=embedding,
    )


def _load_target(persist_dir: Path):
    """从迁移后的物理目录重新加载索引和存储上下文。"""
    storage_context = StorageContext.from_defaults(persist_dir=str(persist_dir))
    index = load_index_from_storage(storage_context)
    return storage_context, index


def test_real_persistence_migrates_each_kb_into_an_isolated_reloadable_index(tmp_path, monkeypatch):
    """真实持久化迁移后，各知识库只能重新加载自己的节点和向量。"""
    monkeypatch.setattr(Settings, "_embed_model", MockEmbedding(embed_dim=4))
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    source_nodes = [
        _node("finance-1", "finance", "财务收入为 100 万元", "finance-doc", [1.0, 0.0, 0.0, 0.0]),
        _node("finance-2", "finance", "财务成本为 60 万元", "finance-doc", [0.0, 1.0, 0.0, 0.0]),
        _node("hr-1", "hr", "人力部门新增员工 3 人", "hr-doc", [0.0, 0.0, 1.0, 0.0]),
    ]
    source_storage = StorageContext.from_defaults()
    VectorStoreIndex(source_nodes, storage_context=source_storage, store_nodes_override=True)
    source_storage.persist(persist_dir=str(storage_root))

    source_manager = IndexManager("knowledge_base", persist_dir=storage_root)
    source_manager.load_index()
    runtime = _Runtime()
    service = KBMigrationService(
        storage_root=storage_root,
        source_manager_factory=lambda: source_manager,
        target_manager_factory=lambda kb_id, persist_dir=None: IndexManager(
            "knowledge_base",
            kb_id=kb_id,
            persist_dir=persist_dir,
        ),
        registry=_Registry(),
        runtime=runtime,
    )

    plan = service.scan()
    result = service.run_migration(plan_digest=plan["plan_digest"])

    assert result["state"] == "completed"
    assert {item["kb_id"]: item["state"] for item in result["results"]} == {
        "finance": "migrated",
        "hr": "migrated",
    }
    assert runtime.dropped == ["finance", "hr"]

    finance_storage, finance_index = _load_target(storage_root / "kbs" / "finance")
    hr_storage, hr_index = _load_target(storage_root / "kbs" / "hr")

    assert set(finance_storage.docstore.docs) == {"finance-1", "finance-2"}
    assert set(finance_index.index_struct.nodes_dict) == {"finance-1", "finance-2"}
    assert set(finance_storage.vector_store.data.embedding_dict) == {"finance-1", "finance-2"}
    assert all("人力部门" not in item.text for item in finance_storage.docstore.docs.values())

    assert set(hr_storage.docstore.docs) == {"hr-1"}
    assert set(hr_index.index_struct.nodes_dict) == {"hr-1"}
    assert set(hr_storage.vector_store.data.embedding_dict) == {"hr-1"}
    assert all("财务" not in item.text for item in hr_storage.docstore.docs.values())

    reloaded_source = StorageContext.from_defaults(persist_dir=str(storage_root))
    source_index = load_index_from_storage(reloaded_source)
    assert set(source_index.index_struct.nodes_dict) == {"finance-1", "finance-2", "hr-1"}
