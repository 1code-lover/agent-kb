"""历史知识库迁移服务测试。"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from llama_index.core.schema import TextNode

from api.services import kb_migration_service as migration_module
from api.services.kb_migration_service import KBMigrationService


class FakeManager:
    def __init__(self, nodes=None, persist_dir=None):
        self.persist_dir = Path(persist_dir or ".")
        self.nodes = {node.node_id: node for node in (nodes or [])}
        self.index = SimpleNamespace(index_struct=SimpleNamespace(nodes_dict={k: k for k in self.nodes}))
        self.storage_context = SimpleNamespace(
            docstore=SimpleNamespace(docs=self.nodes),
            vector_store=SimpleNamespace(data=SimpleNamespace(embedding_dict={
                node.node_id: list(node.embedding) for node in self.nodes.values() if node.embedding is not None
            })),
        )
        self.persisted = False

    def load_index(self):
        return self.index

    def init_index(self, nodes, persist=True):
        self.nodes = {node.node_id: node for node in nodes}
        self.storage_context.docstore.docs = self.nodes
        self.index.index_struct.nodes_dict = {k: k for k in self.nodes}
        if persist:
            self.persist_storage()
        return self.index

    def insert_nodes(self, nodes, persist=True):
        return self.init_index(nodes, persist=persist)

    def persist_storage(self):
        self.persisted = True
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        (self.persist_dir / "docstore.json").write_text(json.dumps(sorted(self.nodes)), encoding="utf-8")
        return True


class FakeRegistry:
    def __init__(self, items):
        self.items = items

    def list_kbs(self):
        return copy.deepcopy(self.items)

    def get_kb(self, kb_id):
        return next((item for item in self.items if item["kb_id"] == kb_id), None)


def node(node_id, kb_id, text, *, embedding=None, ref_doc_id=None):
    item = TextNode(id_=node_id, text=text, metadata={"kb_id": kb_id})
    if ref_doc_id:
        item.metadata["ref_doc_id"] = ref_doc_id
    if embedding is not None:
        item.embedding = embedding
    return item


def make_service(tmp_path, source_nodes, target_managers=None, registry=None):
    source = FakeManager(source_nodes, tmp_path / "storage")
    target_managers = target_managers if target_managers is not None else {}

    def manager_factory(kb_id, persist_dir=None):
        if kb_id == "default":
            return source
        if persist_dir is not None:
            manager = FakeManager([], persist_dir)
            target_managers[(kb_id, str(persist_dir))] = manager
            return manager
        return target_managers.get((kb_id, "final"), FakeManager([]))

    service = KBMigrationService(
        storage_root=tmp_path / "storage",
        source_manager_factory=lambda: source,
        target_manager_factory=manager_factory,
        registry=registry or FakeRegistry([
            {"kb_id": "default", "status": "active"},
            {"kb_id": "finance", "status": "active"},
            {"kb_id": "hr", "status": "active"},
        ]),
    )
    return service, source, target_managers


def test_scan_groups_non_default_and_reports_anomalies_and_embedding_counts(tmp_path):
    service, _, _ = make_service(tmp_path, [
        node("n-default", "default", "keep", embedding=[1, 0]),
        node("n-finance", "finance", "invoice", embedding=[0, 1], ref_doc_id="doc-1"),
        node("n-finance-2", "finance", "line", ref_doc_id="doc-1"),
        node("n-unknown", "missing", "orphan"),
        node("n-invalid", "bad/id", "invalid"),
        node("n-none", "", "missing kb"),
    ])

    plan = service.scan()

    assert [item["kb_id"] for item in plan["knowledge_bases"]] == ["finance"]
    finance = plan["knowledge_bases"][0]
    assert finance["node_count"] == 2
    assert finance["doc_count"] == 1
    assert finance["embedded_node_count"] == 1
    assert finance["missing_embedding_count"] == 1
    assert {item["reason"] for item in plan["anomalies"]} == {"unknown_kb", "invalid_kb_id", "missing_kb_id"}
    assert plan["plan_digest"] == service.scan()["plan_digest"]


def test_dry_run_does_not_change_storage(tmp_path):
    service, _, _ = make_service(tmp_path, [node("n1", "finance", "x", embedding=[1, 0])])
    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    plan = service.scan()
    result = service.run_migration(plan_digest=plan["plan_digest"], dry_run=True)
    after = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    assert result["state"] == "dry_run"
    assert before == after


def test_missing_embedding_blocks_without_recompute(tmp_path):
    service, _, _ = make_service(tmp_path, [node("n1", "finance", "x")])
    plan = service.scan()
    result = service.run_migration(plan_digest=plan["plan_digest"])
    assert result["state"] == "blocked"
    assert result["results"][0]["state"] == "blocked_missing_embeddings"


def test_migration_creates_atomic_target_and_can_be_repeated(tmp_path):
    service, _, targets = make_service(tmp_path, [node("n1", "finance", "x", embedding=[1, 0])])
    plan = service.scan()
    result = service.run_migration(plan_digest=plan["plan_digest"])
    assert result["state"] == "completed"
    target = tmp_path / "storage" / "kbs" / "finance"
    assert target.exists()
    assert (target / "docstore.json").exists()
    assert result["results"][0]["state"] == "migrated"
    second = service.run_migration(plan_digest=plan["plan_digest"])
    assert second["results"][0]["state"] in {"already_migrated", "migrated"}
    assert not list((tmp_path / "storage" / "migrations" / "work").glob("**/*.partial")) if (tmp_path / "storage" / "migrations" / "work").exists() else True


def test_failed_kb_does_not_expose_partial_target_and_manifest_is_verifiable(tmp_path):
    class FailingManager(FakeManager):
        def persist_storage(self):
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            (self.persist_dir / "partial").write_text("partial", encoding="utf-8")
            raise RuntimeError("persist failed")

    source = FakeManager([node("n1", "finance", "x", embedding=[1, 0])], tmp_path / "storage")
    def manager_factory(kb_id, persist_dir=None):
        return FailingManager([], persist_dir)
    service = KBMigrationService(
        storage_root=tmp_path / "storage",
        source_manager_factory=lambda: source,
        target_manager_factory=manager_factory,
        registry=FakeRegistry([{ "kb_id": "finance", "status": "active" }]),
    )
    plan = service.scan()
    result = service.run_migration(plan_digest=plan["plan_digest"])
    assert result["state"] == "failed"
    assert not (tmp_path / "storage" / "kbs" / "finance").exists()
    assert result["backup"]["manifest_path"]
    assert service.verify_manifest(result["backup"]["manifest_path"])


def test_retry_failed_only_filters_previous_failed_kbs(tmp_path):
    """重试失败项时不得重复处理已经成功的知识库。"""
    attempts = {"finance": 0, "hr": 0}

    class SelectiveManager(FakeManager):
        def __init__(self, kb_id, persist_dir):
            super().__init__([], persist_dir)
            self.kb_id = kb_id

        def persist_storage(self):
            attempts[self.kb_id] += 1
            if self.kb_id == "hr" and attempts[self.kb_id] == 1:
                self.persist_dir.mkdir(parents=True, exist_ok=True)
                raise RuntimeError("first failure")
            return super().persist_storage()

    source = FakeManager([
        node("f1", "finance", "finance", embedding=[1, 0]),
        node("h1", "hr", "hr", embedding=[0, 1]),
    ], tmp_path / "storage")
    service = KBMigrationService(
        storage_root=tmp_path / "storage",
        source_manager_factory=lambda: source,
        target_manager_factory=lambda kb_id, persist_dir=None: SelectiveManager(kb_id, persist_dir),
        registry=FakeRegistry([{"kb_id": "finance", "status": "active"}, {"kb_id": "hr", "status": "active"}]),
    )
    plan = service.scan()
    first = service.run_migration(plan_digest=plan["plan_digest"])
    assert {item["kb_id"]: item["state"] for item in first["results"]} == {"finance": "migrated", "hr": "failed"}

    second = service.run_migration(plan_digest=plan["plan_digest"], retry_failed_only=True)
    assert [item["kb_id"] for item in second["results"]] == ["hr"]
    assert second["results"][0]["state"] == "migrated"
    assert attempts == {"finance": 1, "hr": 2}


def test_rollback_rejects_tampered_backup_manifest(tmp_path):
    """备份文件被篡改后必须拒绝回滚，且目标目录保持可用。"""
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True)
    (storage_root / "source.json").write_text('{"source": true}', encoding="utf-8")
    service, _, _ = make_service(tmp_path, [node("n1", "finance", "x", embedding=[1, 0])])
    plan = service.scan()
    result = service.run_migration(plan_digest=plan["plan_digest"])
    target = storage_root / "kbs" / "finance"
    manifest_path = Path(result["backup"]["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    backed_up_file = Path(manifest["backup_dir"]) / "source.json"
    backed_up_file.write_text('{"source": false}', encoding="utf-8")

    with pytest.raises(ValueError, match="manifest is invalid"):
        service.rollback(result["batch_id"])

    assert target.exists()


def test_rollback_rejects_target_not_owned_by_batch(tmp_path):
    """迁移标记不属于指定批次时不得移动目标目录。"""
    service, _, _ = make_service(tmp_path, [node("n1", "finance", "x", embedding=[1, 0])])
    plan = service.scan()
    result = service.run_migration(plan_digest=plan["plan_digest"])
    target = tmp_path / "storage" / "kbs" / "finance"
    marker_path = target / ".thinkrag-migration.json"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["batch_id"] = "another-batch"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")

    with pytest.raises(ValueError, match="not owned"):
        service.rollback(result["batch_id"])

    assert target.exists()


def test_successful_rollback_moves_only_batch_targets_and_keeps_source_and_backup(tmp_path):
    """成功回滚应隔离本批次目标，同时保留历史来源和已验证备份。"""
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True)
    source_file = storage_root / "source.json"
    source_file.write_text('{"source": true}', encoding="utf-8")
    service, _, _ = make_service(tmp_path, [node("n1", "finance", "x", embedding=[1, 0])])
    plan = service.scan()
    migrated = service.run_migration(plan_digest=plan["plan_digest"])
    target = storage_root / "kbs" / "finance"
    assert target.exists()

    rolled_back = service.rollback(migrated["batch_id"])

    rollback_dir = storage_root / "migrations" / "rollback" / migrated["batch_id"] / "finance"
    assert rolled_back["state"] == "rolled_back"
    assert rolled_back["moved"] == [{"kb_id": "finance", "from": str(target), "to": str(rollback_dir)}]
    assert not target.exists()
    assert rollback_dir.exists()
    assert source_file.read_text(encoding="utf-8") == '{"source": true}'
    assert service.verify_manifest(migrated["backup"]["manifest_path"])


def test_backup_copy_failure_cleans_partial_backup_and_never_creates_target(tmp_path, monkeypatch):
    """备份复制权限失败时必须清除不完整备份，且不得开始写目标索引。"""
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True)
    (storage_root / "source.json").write_text('{"source": true}', encoding="utf-8")
    service, _, _ = make_service(tmp_path, [node("n1", "finance", "x", embedding=[1, 0])])

    def deny_copy(*_args, **_kwargs):
        raise PermissionError("backup copy denied")

    monkeypatch.setattr("api.services.kb_migration_service.shutil.copy2", deny_copy)
    with pytest.raises(PermissionError, match="backup copy denied"):
        service._create_backup("permission-failure")

    assert not (storage_root / "migrations" / "backups" / "permission-failure").exists()
    assert not (storage_root / "kbs" / "finance").exists()


def test_atomic_write_json_retries_permission_error_then_succeeds(tmp_path, monkeypatch):
    """迁移 manifest/plan JSON 落盘遇到临时锁时，应重试并成功。"""
    path = tmp_path / "manifest.json"
    real_replace = migration_module.os.replace
    attempts = {"count": 0}

    def flaky_replace(src, dst):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise PermissionError("locked")
        return real_replace(src, dst)

    sleep = MagicMock()
    monkeypatch.setattr(migration_module.os, "replace", flaky_replace)
    monkeypatch.setattr(migration_module.time, "sleep", sleep)

    migration_module._atomic_write_json(path, {"ok": True})

    assert attempts["count"] == 3
    assert sleep.call_count == 2
    assert json.loads(path.read_text(encoding="utf-8")) == {"ok": True}
    assert list(path.parent.glob("manifest.json.tmp-*")) == []


def test_atomic_write_json_raises_after_retries_and_cleans_tmp_file(tmp_path, monkeypatch):
    """迁移 JSON 连续 replace 失败时，应抛错且不遗留 tmp 文件。"""
    path = tmp_path / "manifest.json"

    monkeypatch.setattr(migration_module.os, "replace", MagicMock(side_effect=PermissionError("still locked")))
    monkeypatch.setattr(migration_module.time, "sleep", MagicMock())

    with pytest.raises(PermissionError, match="still locked"):
        migration_module._atomic_write_json(path, {"ok": True})

    assert not path.exists()
    assert list(path.parent.glob("manifest.json.tmp-*")) == []
