"""历史共享索引迁移到知识库独立索引的服务。"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import config
from api.runtime import runtime_state
from server.kb_registry import KBRegistry
from server.utils.file import get_storage_root, validate_kb_id


def _utc_now() -> str:
    """返回 UTC ISO 时间。"""
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: Any) -> str:
    """生成稳定 JSON，用于计划和内容摘要。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_write_json(path: Path, payload: Any) -> None:
    """原子写入 JSON 文件，并在 Windows 上对临时锁做有限重试。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}-{threading.get_ident()}")
    try:
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())

        last_exc: PermissionError | None = None
        for attempt in range(5):
            try:
                os.replace(tmp, path)
                last_exc = None
                break
            except PermissionError as exc:
                last_exc = exc
                time.sleep(0.02 * (attempt + 1))

        if last_exc is not None:
            raise last_exc
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _node_id(node: Any) -> str:
    return str(getattr(node, "node_id", None) or getattr(node, "id_", None) or "")


def _node_text(node: Any) -> str:
    get_content = getattr(node, "get_content", None)
    if callable(get_content):
        try:
            return str(get_content(metadata_mode="none"))
        except TypeError:
            return str(get_content())
    return str(getattr(node, "text", "") or "")


def _node_metadata(node: Any) -> dict[str, Any]:
    metadata = getattr(node, "metadata", None)
    return copy.deepcopy(metadata) if isinstance(metadata, dict) else {}


def _ref_doc_id(node: Any) -> str:
    direct = getattr(node, "ref_doc_id", None)
    if direct:
        return str(direct)
    metadata = _node_metadata(node)
    return str(metadata.get("ref_doc_id") or metadata.get("doc_id") or metadata.get("document_id") or _node_id(node))


def _summarize_nodes(nodes: Iterable[Any]) -> dict[str, Any]:
    """计算节点数、文档数与稳定内容摘要。"""
    rows = []
    ref_docs = set()
    for node in nodes:
        node_key = _node_id(node)
        ref_docs.add(_ref_doc_id(node))
        rows.append(
            {
                "node_id": node_key,
                "text_sha256": _sha256_bytes(_node_text(node).encode("utf-8")),
                "metadata": _node_metadata(node),
            }
        )
    rows.sort(key=lambda item: item["node_id"])
    return {
        "node_count": len(rows),
        "doc_count": len(ref_docs),
        "content_digest": _sha256_bytes(_canonical_json(rows).encode("utf-8")),
    }


class KBMigrationService:
    """扫描并安全迁移历史共享索引。"""

    def __init__(
        self,
        *,
        storage_root: str | Path | None = None,
        source_manager_factory: Callable[[], Any] | None = None,
        target_manager_factory: Callable[..., Any] | None = None,
        registry: Any | None = None,
        runtime: Any = runtime_state,
    ) -> None:
        self.storage_root = Path(storage_root or get_storage_root()).resolve()
        self.runtime = runtime
        self.registry = registry or KBRegistry(self.storage_root / "kb_registry.json")
        self.source_manager_factory = source_manager_factory or (lambda: runtime.get_index_manager("default"))
        self.target_manager_factory = target_manager_factory or self._default_target_manager_factory
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._last_plan: dict[str, Any] | None = None
        self._status: dict[str, Any] = {
            "state": "idle",
            "batch_id": None,
            "plan_digest": None,
            "current_kb_id": None,
            "completed_kb_count": 0,
            "total_kb_count": 0,
            "results": [],
            "anomalies": [],
            "last_error": None,
            "started_at": None,
            "finished_at": None,
            "thread_alive": False,
        }

    def _default_target_manager_factory(self, kb_id: str, persist_dir: str | Path | None = None) -> Any:
        from server.index import IndexManager

        return IndexManager(config.DEFAULT_INDEX_NAME, kb_id=kb_id, persist_dir=persist_dir)

    def get_status(self) -> dict[str, Any]:
        """返回后台任务状态快照。"""
        with self._lock:
            status = copy.deepcopy(self._status)
            status["thread_alive"] = self._thread is not None and self._thread.is_alive()
            return status

    def _load_source_nodes(self) -> tuple[Any, list[Any], dict[str, list[float]]]:
        manager = self.source_manager_factory()
        index = getattr(manager, "index", None)
        if index is None:
            load_index = getattr(manager, "load_index", None)
            if callable(load_index):
                try:
                    index = load_index()
                except ValueError:
                    return manager, [], {}
        docstore = getattr(getattr(manager, "storage_context", None), "docstore", None)
        docs = getattr(docstore, "docs", {}) or {}
        nodes_dict = getattr(getattr(index, "index_struct", None), "nodes_dict", None)
        valid_ids = set(nodes_dict.keys()) if isinstance(nodes_dict, dict) else set(docs.keys())
        nodes = [docs[node_id] for node_id in sorted(valid_ids) if node_id in docs]
        vector_store = getattr(getattr(manager, "storage_context", None), "vector_store", None)
        embeddings = getattr(getattr(vector_store, "data", None), "embedding_dict", None) or {}
        return manager, nodes, {str(key): list(value) for key, value in embeddings.items() if value is not None}

    def _active_kb_ids(self) -> set[str]:
        return {
            str(item.get("kb_id"))
            for item in self.registry.list_kbs()
            if item.get("status", "active") == "active" and item.get("kb_id")
        }

    def scan(self) -> dict[str, Any]:
        """扫描历史共享索引并生成无副作用迁移计划。"""
        _, nodes, embeddings = self._load_source_nodes()
        active = self._active_kb_ids()
        grouped: dict[str, list[Any]] = {}
        anomalies: list[dict[str, Any]] = []
        for node in nodes:
            metadata = _node_metadata(node)
            raw_kb_id = metadata.get("kb_id")
            if not raw_kb_id:
                anomalies.append({"node_id": _node_id(node), "reason": "missing_kb_id"})
                continue
            try:
                kb_id = validate_kb_id(str(raw_kb_id))
            except Exception:
                anomalies.append({"node_id": _node_id(node), "kb_id": str(raw_kb_id), "reason": "invalid_kb_id"})
                continue
            if kb_id == "default":
                continue
            if kb_id not in active:
                anomalies.append({"node_id": _node_id(node), "kb_id": kb_id, "reason": "unknown_kb"})
                continue
            grouped.setdefault(kb_id, []).append(node)

        items = []
        for kb_id, kb_nodes in sorted(grouped.items()):
            summary = _summarize_nodes(kb_nodes)
            embedded = sum(1 for node in kb_nodes if getattr(node, "embedding", None) is not None or _node_id(node) in embeddings)
            target_dir = self.storage_root / "kbs" / kb_id
            marker = self._read_target_marker(target_dir)
            items.append(
                {
                    "kb_id": kb_id,
                    **summary,
                    "embedded_node_count": embedded,
                    "missing_embedding_count": len(kb_nodes) - embedded,
                    "target_dir": str(target_dir),
                    "target_exists": target_dir.exists(),
                    "target_source_digest": marker.get("source_digest") if marker else None,
                }
            )
        anomalies.sort(key=lambda item: (item.get("reason", ""), item.get("node_id", "")))
        digest_items = [
            {key: value for key, value in item.items() if key not in {"target_exists", "target_source_digest"}}
            for item in items
        ]
        digest_input = {"knowledge_bases": digest_items, "anomalies": anomalies}
        plan = {
            "created_at": _utc_now(),
            "source_dir": str(self.storage_root),
            "knowledge_bases": items,
            "anomalies": anomalies,
            "plan_digest": _sha256_bytes(_canonical_json(digest_input).encode("utf-8")),
            "candidate_kb_count": len(items),
            "candidate_node_count": sum(item["node_count"] for item in items),
        }
        with self._lock:
            self._last_plan = copy.deepcopy(plan)
        return plan

    def _nodes_by_kb(self) -> tuple[dict[str, list[Any]], dict[str, list[float]]]:
        _, nodes, embeddings = self._load_source_nodes()
        grouped: dict[str, list[Any]] = {}
        for node in nodes:
            kb_id = _node_metadata(node).get("kb_id")
            if isinstance(kb_id, str):
                grouped.setdefault(kb_id, []).append(node)
        return grouped, embeddings

    def _migration_root(self) -> Path:
        return self.storage_root / "migrations"

    def _read_target_marker(self, target_dir: Path) -> dict[str, Any] | None:
        marker = target_dir / ".thinkrag-migration.json"
        if not marker.exists():
            return None
        try:
            value = json.loads(marker.read_text(encoding="utf-8"))
        except Exception:
            return None
        return value if isinstance(value, dict) else None

    def _create_backup(self, batch_id: str) -> dict[str, Any]:
        backup_root = self._migration_root() / "backups" / batch_id
        backup_storage = backup_root / "storage"
        backup_storage.mkdir(parents=True, exist_ok=False)
        try:
            files: list[dict[str, Any]] = []
            if self.storage_root.exists():
                for source in sorted(self.storage_root.iterdir(), key=lambda item: item.name):
                    if source.name in {"kbs", "migrations"}:
                        continue
                    target = backup_storage / source.name
                    if source.is_dir():
                        shutil.copytree(source, target, symlinks=True)
                    else:
                        shutil.copy2(source, target)
            for path in sorted(backup_storage.rglob("*")):
                if path.is_file():
                    files.append(
                        {
                            "path": str(path.relative_to(backup_storage)),
                            "size": path.stat().st_size,
                            "sha256": _sha256_bytes(path.read_bytes()),
                        }
                    )
            manifest = {
                "version": 1,
                "batch_id": batch_id,
                "created_at": _utc_now(),
                "source_dir": str(self.storage_root),
                "backup_dir": str(backup_storage),
                "files": files,
                "created_targets": [],
            }
            manifest_path = backup_root / "manifest.json"
            _atomic_write_json(manifest_path, manifest)
            return {"backup_dir": str(backup_storage), "manifest_path": str(manifest_path), "file_count": len(files)}
        except Exception:
            shutil.rmtree(backup_root, ignore_errors=True)
            raise

    def verify_manifest(self, manifest_path: str | Path) -> bool:
        """验证本工具备份 manifest 和文件哈希。"""
        path = Path(manifest_path).resolve()
        try:
            path.relative_to((self._migration_root() / "backups").resolve())
            manifest = json.loads(path.read_text(encoding="utf-8"))
            backup_dir = Path(manifest["backup_dir"]).resolve()
            backup_dir.relative_to((self._migration_root() / "backups").resolve())
        except Exception:
            return False
        for item in manifest.get("files", []):
            target = (backup_dir / item["path"]).resolve()
            try:
                target.relative_to(backup_dir)
            except ValueError:
                return False
            if not target.is_file() or target.stat().st_size != item["size"]:
                return False
            if _sha256_bytes(target.read_bytes()) != item["sha256"]:
                return False
        return True

    def _update_manifest_targets(self, manifest_path: str | Path, created_targets: list[str]) -> None:
        path = Path(manifest_path)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["created_targets"] = created_targets
        _atomic_write_json(path, manifest)

    def _clone_nodes(self, nodes: list[Any], embeddings: dict[str, list[float]], recompute: bool) -> list[Any]:
        cloned = []
        for node in nodes:
            item = copy.deepcopy(node)
            embedding = getattr(item, "embedding", None) or embeddings.get(_node_id(item))
            if embedding is not None:
                item.embedding = list(embedding)
            elif not recompute:
                raise ValueError(f"Node {_node_id(item)} is missing embedding")
            cloned.append(item)
        return cloned

    def _validate_plan_digest(self, plan_digest: str) -> dict[str, Any]:
        plan = self.scan()
        if plan["plan_digest"] != plan_digest:
            raise ValueError("Migration plan changed; scan again before starting")
        return plan

    def run_migration(
        self,
        *,
        plan_digest: str,
        kb_ids: list[str] | None = None,
        retry_failed_only: bool = False,
        recompute_missing_embeddings: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """同步执行迁移；后台 API 复用此核心方法。"""
        plan = self._validate_plan_digest(plan_digest)
        selected = set(kb_ids or [item["kb_id"] for item in plan["knowledge_bases"]])
        if retry_failed_only:
            with self._lock:
                previous_digest = self._status.get("plan_digest")
                failed_ids = {
                    str(item.get("kb_id"))
                    for item in self._status.get("results") or []
                    if item.get("state") in {"failed", "conflict", "blocked_missing_embeddings"}
                }
            if previous_digest != plan_digest:
                raise ValueError("No failed migration result matches this plan; run the full migration first")
            selected &= failed_ids
        items = [item for item in plan["knowledge_bases"] if item["kb_id"] in selected]
        if dry_run:
            return {"state": "dry_run", "plan": plan, "results": []}
        if not items:
            return {"state": "completed", "plan": plan, "results": [], "backup": None}

        batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + plan_digest[:10]
        backup = self._create_backup(batch_id)
        grouped, embeddings = self._nodes_by_kb()
        results: list[dict[str, Any]] = []
        created_targets: list[str] = []
        with self._lock:
            self._status.update(
                state="running",
                batch_id=batch_id,
                plan_digest=plan_digest,
                current_kb_id=None,
                completed_kb_count=0,
                total_kb_count=len(items),
                results=[],
                anomalies=plan["anomalies"],
                last_error=None,
                started_at=_utc_now(),
                finished_at=None,
            )

        for item in items:
            kb_id = item["kb_id"]
            with self._lock:
                self._status["current_kb_id"] = kb_id
            target_dir = self.storage_root / "kbs" / kb_id
            marker = self._read_target_marker(target_dir)
            if marker and marker.get("source_digest") == item["content_digest"]:
                result = {"kb_id": kb_id, "state": "already_migrated", "target_dir": str(target_dir)}
                results.append(result)
                continue
            if target_dir.exists():
                results.append({"kb_id": kb_id, "state": "conflict", "target_dir": str(target_dir), "error": "target_not_empty"})
                continue
            if item["missing_embedding_count"] and not recompute_missing_embeddings:
                results.append(
                    {
                        "kb_id": kb_id,
                        "state": "blocked_missing_embeddings",
                        "missing_embedding_count": item["missing_embedding_count"],
                    }
                )
                continue

            work_dir = self._migration_root() / "work" / batch_id / f"{kb_id}.partial"
            if work_dir.exists():
                shutil.rmtree(work_dir)
            try:
                manager = self.target_manager_factory(kb_id, persist_dir=work_dir)
                cloned = self._clone_nodes(grouped.get(kb_id, []), embeddings, recompute_missing_embeddings)
                manager.insert_nodes(cloned, persist=False)
                if not manager.persist_storage():
                    raise RuntimeError("target storage was not persisted")
                validation = _summarize_nodes(list(getattr(manager.storage_context.docstore, "docs", {}).values()))
                if validation["content_digest"] != item["content_digest"] or validation["node_count"] != item["node_count"]:
                    raise RuntimeError("target validation digest mismatch")
                marker_payload = {
                    "version": 1,
                    "batch_id": batch_id,
                    "kb_id": kb_id,
                    "source_digest": item["content_digest"],
                    "node_count": item["node_count"],
                    "doc_count": item["doc_count"],
                    "created_at": _utc_now(),
                }
                _atomic_write_json(work_dir / ".thinkrag-migration.json", marker_payload)
                target_dir.parent.mkdir(parents=True, exist_ok=True)
                os.replace(work_dir, target_dir)
                created_targets.append(str(target_dir))
                drop = getattr(self.runtime, "drop_index_manager", None)
                if callable(drop):
                    drop(kb_id)
                results.append({"kb_id": kb_id, "state": "migrated", "target_dir": str(target_dir), "validation": validation})
            except Exception as exc:
                if work_dir.exists():
                    failed_dir = self._migration_root() / "failed" / batch_id / kb_id
                    failed_dir.parent.mkdir(parents=True, exist_ok=True)
                    if failed_dir.exists():
                        shutil.rmtree(failed_dir)
                    os.replace(work_dir, failed_dir)
                results.append({"kb_id": kb_id, "state": "failed", "error": str(exc)})
            finally:
                with self._lock:
                    self._status["completed_kb_count"] = len(results)
                    self._status["results"] = copy.deepcopy(results)

        self._update_manifest_targets(backup["manifest_path"], created_targets)
        states = {item["state"] for item in results}
        if "failed" in states or "conflict" in states:
            final_state = "failed"
        elif "blocked_missing_embeddings" in states:
            final_state = "blocked"
        else:
            final_state = "completed"
        result_payload = {
            "state": final_state,
            "batch_id": batch_id,
            "plan_digest": plan_digest,
            "results": results,
            "anomalies": plan["anomalies"],
            "backup": backup,
            "created_targets": created_targets,
        }
        plan_path = self._migration_root() / "plans" / f"{batch_id}.json"
        _atomic_write_json(plan_path, {"plan": plan, "result": result_payload})
        with self._lock:
            self._status.update(
                state=final_state,
                current_kb_id=None,
                results=copy.deepcopy(results),
                last_error=next((item.get("error") for item in results if item.get("error")), None),
                finished_at=_utc_now(),
            )
        return result_payload

    def start(self, **kwargs: Any) -> tuple[dict[str, Any], bool]:
        """幂等启动后台迁移。"""
        with self._lock:
            if self._thread is not None:
                return self.get_status(), False
            thread = threading.Thread(target=self._run_background, kwargs=kwargs, name="thinkrag-kb-migration", daemon=True)
            self._thread = thread
            thread.start()
            return self.get_status(), True

    def _run_background(self, **kwargs: Any) -> None:
        try:
            self.run_migration(**kwargs)
        except Exception as exc:
            with self._lock:
                self._status.update(state="failed", last_error=str(exc), finished_at=_utc_now())
        finally:
            with self._lock:
                self._thread = None

    def rollback(self, batch_id: str) -> dict[str, Any]:
        """隔离本批次创建的目标目录，历史共享索引保持不变。"""
        manifest_path = self._migration_root() / "backups" / batch_id / "manifest.json"
        if not self.verify_manifest(manifest_path):
            raise ValueError("Migration backup manifest is invalid")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        moved = []
        for raw_target in manifest.get("created_targets", []):
            target = Path(raw_target).resolve()
            target.relative_to((self.storage_root / "kbs").resolve())
            marker = self._read_target_marker(target)
            if not marker or marker.get("batch_id") != batch_id:
                raise ValueError(f"Target is not owned by migration batch: {target}")
            rollback_dir = self._migration_root() / "rollback" / batch_id / target.name
            rollback_dir.parent.mkdir(parents=True, exist_ok=True)
            if rollback_dir.exists():
                raise ValueError(f"Rollback destination already exists: {rollback_dir}")
            os.replace(target, rollback_dir)
            drop = getattr(self.runtime, "drop_index_manager", None)
            if callable(drop):
                drop(target.name)
            moved.append({"kb_id": target.name, "from": str(target), "to": str(rollback_dir)})
        return {"state": "rolled_back", "batch_id": batch_id, "moved": moved}


kb_migration_service = KBMigrationService()

__all__ = ["KBMigrationService", "kb_migration_service"]
