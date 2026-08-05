"""半真实 Markdown 单库问答回归测试。"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.services import asset_service, kb_service
from server.asset_registry import KBAssetRegistry
from server.kb_registry import KBRegistry
from server.utils.file import get_kb_data_dir
from tests.api.chat_qa_metrics import build_chat_case_report, summarize_chat_case_reports

client = TestClient(app)
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "rag_quality" / "semireal_markdown"
CASE_FIXTURE = FIXTURE_DIR / "cases.json"
EVAL_V4_CASE_FIXTURE = FIXTURE_DIR.parent / "eval_v4" / "cases.json"
EVAL_V5_CASE_FIXTURE = FIXTURE_DIR.parent / "eval_v5" / "cases.json"
KB_ID = "kb-a"
FIXTURE_IMPORT_PATHS = {
    "scope-contract.md": "qa/contracts/scope-contract.md",
    "evidence-preview.md": "qa/evidence/evidence-preview.md",
    "refusal-guideline.md": "qa/policies/refusal-guideline.md",
    "evaluation-metrics.md": "qa/evaluation/evaluation-metrics.md",
    "folder-boundary.md": "qa/architecture/folder-boundary.md",
    "ingestion-priority.md": "qa/ingestion/ingestion-priority.md",
    "suite-metrics-gate.md": "qa/evaluation/suite-metrics-gate.md",
}
QUESTION_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "before",
    "current",
    "does",
    "each",
    "for",
    "how",
    "into",
    "must",
    "response",
    "should",
    "single",
    "that",
    "the",
    "their",
    "these",
    "this",
    "what",
    "which",
}


class FakeUploadFile:
    """模拟上传文件对象，供 import_files 直接消费。"""

    def __init__(self, filename: str, content: bytes, content_type: str = "text/markdown") -> None:
        self.filename = filename
        self.content_type = content_type
        self.file = io.BytesIO(content)


class FakeRefDocInfo:
    """模拟 ref_doc_info，使 preview 能回到 metadata 与 node 列表。"""

    def __init__(self, metadata: dict[str, str], node_ids: list[str]) -> None:
        self.metadata = metadata
        self.node_ids = node_ids


class FakeDocStore:
    """最小 docstore 实现，支持 evidence 与 preview 读取。"""

    def __init__(self) -> None:
        self.docs: dict[str, SimpleNamespace] = {}
        self.ref_docs: dict[str, FakeRefDocInfo] = {}

    def get_ref_doc_info(self, ref_doc_id: str):
        return self.ref_docs.get(ref_doc_id)

    def get_nodes(self, node_ids=None, raise_error: bool = False):
        node_ids = list(node_ids or [])
        return [self.docs[node_id] for node_id in node_ids if node_id in self.docs]


class FakeStorageContext:
    """最小 storage_context，仅暴露 preview 需要的 docstore。"""

    def __init__(self, docstore: FakeDocStore) -> None:
        self.docstore = docstore


class FakeSemirealIndexManager:
    """用真实导入 Markdown 内容构造稳定可控的半真实索引管理器。"""

    def __init__(self, kb_id: str, kb_dir: Path) -> None:
        self.kb_id = kb_id
        self.kb_dir = kb_dir.resolve()
        self.docstore = FakeDocStore()
        self.storage_context = FakeStorageContext(self.docstore)
        self.documents: list[dict[str, object]] = []
        self.index = None
        self._last_ingestion_diagnostics: dict[str, object] | None = None
        self._last_persist_diagnostics: dict[str, float] | None = None

    def load_files(self, paths, chunk_size: int, chunk_overlap: int, kb_id: str | None = None, persist: bool = False):
        nodes: list[SimpleNamespace] = []
        document_count = 0
        input_text_chars = 0

        for raw_path in paths:
            path = Path(raw_path).resolve()
            text = path.read_text(encoding="utf-8")
            relative_path = path.relative_to(self.kb_dir).as_posix()
            slug = re.sub(r"[^a-z0-9]+", "-", relative_path.lower()).strip("-")
            doc_id = f"doc-{slug}"
            node_id = f"node-{slug}"
            metadata = {
                "kb_id": kb_id or self.kb_id,
                "file_name": path.name,
                "title": path.name,
                "file_path": str(path),
                "relative_path": relative_path,
                "doc_id": doc_id,
                "page_label": "1",
            }
            node = SimpleNamespace(
                metadata=metadata,
                text=text,
                ref_doc_id=doc_id,
                node_id=node_id,
            )
            self.docstore.docs[node_id] = node
            self.docstore.ref_docs[doc_id] = FakeRefDocInfo(metadata=metadata, node_ids=[node_id])
            self.documents.append(
                {
                    "doc_id": doc_id,
                    "relative_path": relative_path,
                    "title": path.name,
                    "text": text,
                    "node": node,
                }
            )
            nodes.append(node)
            document_count += 1
            input_text_chars += len(text)

        self.index = object() if nodes else self.index
        self._last_ingestion_diagnostics = {
            "document_count": document_count,
            "empty_document_count": 0,
            "input_text_chars": input_text_chars,
            "node_count": len(nodes),
        }
        return nodes

    def check_index_exists(self) -> bool:
        return bool(self.documents)

    def persist(self) -> bool:
        self._last_persist_diagnostics = {
            "docstore_persist_ms": 0.0,
            "index_store_persist_ms": 0.0,
            "graph_store_persist_ms": 0.0,
            "vector_store_persist_ms": 0.0,
            "fallback_persist_ms": 0.0,
            "vector_store_namespaces_ms": {"default": 0.0},
            "total_ms": 0.0,
        }
        return True

    def persist_storage(self) -> bool:
        """兼容 import_files 当前调用的 persist_storage 别名。"""
        return self.persist()

    def consume_last_ingestion_diagnostics(self):
        payload = self._last_ingestion_diagnostics
        self._last_ingestion_diagnostics = None
        return payload

    def consume_last_persist_diagnostics(self):
        payload = self._last_persist_diagnostics
        self._last_persist_diagnostics = None
        return payload

    def search(self, question: str, top_k: int = 1) -> list[SimpleNamespace]:
        terms = _tokenize(question)
        if not terms:
            return []

        scored: list[SimpleNamespace] = []
        for document in self.documents:
            corpus = f"{document['title']}\n{document['text']}"
            corpus_tokens = _tokenize(corpus)
            overlap = terms & corpus_tokens
            if not overlap:
                continue
            scored.append(
                SimpleNamespace(
                    node=document["node"],
                    score=float(len(overlap)),
                    matched_terms=sorted(overlap),
                )
            )
        scored.sort(key=lambda item: (-float(item.score or 0.0), item.node.metadata.get("file_name", "")))
        return scored[:top_k]


class FakeSemirealQueryEngine:
    """使用半真实索引结果返回稳定答案与 source_nodes。"""

    def __init__(self, manager: FakeSemirealIndexManager) -> None:
        self.manager = manager

    def query(self, question: str):
        matches = self.manager.search(question, top_k=1)
        if not matches:
            return SimpleNamespace(
                response="No confirmable information is available in the current knowledge base.",
                source_nodes=[],
            )
        best = matches[0]
        answer = str(best.node.text).strip()
        return SimpleNamespace(response=answer, source_nodes=matches)


@pytest.fixture(autouse=True)
def _reset_service_state():
    yield
    kb_service._registry = None
    asset_service._registry = None


@pytest.fixture
def semireal_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """隔离 registry 与 runtime，并注入半真实 Markdown 索引环境。"""
    monkeypatch.chdir(tmp_path)

    import api.services.chat_service as chat_service

    registry = KBRegistry(storage_path=tmp_path / "storage" / "kb_registry.json")
    asset_registry = KBAssetRegistry(base_dir=tmp_path / "storage" / "kb_assets")
    kb_service._registry = registry
    asset_service._registry = asset_registry
    registry.create_kb(KB_ID, "KB A")

    manager = FakeSemirealIndexManager(kb_id=KB_ID, kb_dir=get_kb_data_dir(KB_ID, create=True))
    monkeypatch.setattr(kb_service.runtime_state, "ensure_models_ready", MagicMock(return_value=True))
    monkeypatch.setattr(kb_service.runtime_state, "get_index_manager", MagicMock(return_value=manager))
    monkeypatch.setattr(
        chat_service.runtime_state,
        "ensure_index_loaded",
        MagicMock(side_effect=lambda kb_id=None: manager.check_index_exists()),
    )
    build_query_engine = MagicMock(side_effect=lambda kb_ids=None: FakeSemirealQueryEngine(manager))
    monkeypatch.setattr(chat_service.runtime_state, "build_query_engine", build_query_engine)
    monkeypatch.setattr(chat_service.runtime_state, "get_index_manager", MagicMock(return_value=manager))
    monkeypatch.setattr(chat_service, "append_chat_message", lambda *args, **kwargs: None)

    return {
        "registry": registry,
        "manager": manager,
        "build_query_engine": build_query_engine,
        "tmp_path": tmp_path,
    }


@pytest.fixture
def imported_markdown_kb(semireal_runtime: dict[str, object]):
    """把 fixture Markdown 真实导入测试 KB，并返回运行时上下文。"""
    uploads = []
    relative_paths = []
    for name, relative_path in FIXTURE_IMPORT_PATHS.items():
        path = FIXTURE_DIR / name
        uploads.append(FakeUploadFile(filename=path.name, content=path.read_bytes()))
        relative_paths.append(relative_path)

    result = kb_service.import_files(
        uploads,
        chunk_size=128,
        chunk_overlap=16,
        kb_id=KB_ID,
        relative_paths=relative_paths,
        import_mode="preserve_tree",
    )

    semireal_runtime["import_result"] = result
    semireal_runtime["relative_paths"] = relative_paths
    return semireal_runtime



def _load_cases() -> list[dict[str, object]]:
    return json.loads(CASE_FIXTURE.read_text(encoding="utf-8"))


def _load_eval_v4_cases() -> list[dict[str, object]]:
    return json.loads(EVAL_V4_CASE_FIXTURE.read_text(encoding="utf-8"))


def _load_eval_v5_cases() -> list[dict[str, object]]:
    return json.loads(EVAL_V5_CASE_FIXTURE.read_text(encoding="utf-8"))


def _collect_markdown_fixture_docs() -> set[str]:
    docs = set(FIXTURE_IMPORT_PATHS)

    for case in _load_cases():
        expected_doc = str(case.get("expected_doc") or "").strip()
        if expected_doc:
            docs.add(expected_doc)

    for eval_cases in (_load_eval_v4_cases(), _load_eval_v5_cases()):
        for case in eval_cases:
            if str(case.get("kb_id") or "").strip() != "eval-kb-markdown":
                continue
            source_doc = str(case.get("source_doc") or "").strip()
            if source_doc:
                docs.add(source_doc)
            for seed_doc in case.get("seed_docs") or []:
                if str(seed_doc).strip():
                    docs.add(str(seed_doc).strip())
            for required_doc in case.get("required_evidence_docs") or []:
                if str(required_doc).strip():
                    docs.add(str(required_doc).strip())

    return docs


EXPECTED_MARKDOWN_FIXTURE_DOCS = _collect_markdown_fixture_docs()



def _tokenize(text: str) -> set[str]:
    """把问题与文档归一化成稳定 token，便于构造可回归匹配。"""
    normalized = set()
    for token in re.findall(r"[a-z0-9_]+", str(text).lower()):
        if len(token) <= 2 or token in QUESTION_STOPWORDS:
            continue
        normalized.add(token)
        if token.endswith("s") and len(token) > 4:
            normalized.add(token[:-1])
    return normalized


SEMIREAL_CASES = _load_cases()



def _query_case(case: dict[str, object]) -> tuple[dict[str, object], dict[str, object] | None]:
    """执行单条半真实问答 case，并在有证据时补查 preview。"""
    resp = client.post(
        "/api/chat/query",
        json={
            "question": case["question"],
            "session_id": case["case_id"],
            "kb_ids": [KB_ID],
        },
    )

    assert resp.status_code == 200
    payload = resp.json()["data"]
    expected_source_count = int(case.get("expected_source_count", 1))
    if expected_source_count == 0:
        return payload, None

    evidence = payload["evidence"][0]
    preview_resp = client.post(
        "/api/kb/preview",
        json={
            "kb_id": KB_ID,
            "evidence_id": evidence["id"],
        },
    )
    assert preview_resp.status_code == 200
    return payload, preview_resp.json()["data"]



def test_semireal_markdown_fixture_exists() -> None:
    """Markdown ?????? eval ???????????????"""
    assert CASE_FIXTURE.exists(), f"missing case fixture: {CASE_FIXTURE}"
    assert EVAL_V4_CASE_FIXTURE.exists(), f"missing eval v4 fixture: {EVAL_V4_CASE_FIXTURE}"
    assert EVAL_V5_CASE_FIXTURE.exists(), f"missing eval v5 fixture: {EVAL_V5_CASE_FIXTURE}"

    markdown_files = {path.name for path in FIXTURE_DIR.glob("*.md")}
    missing_base_files = set(FIXTURE_IMPORT_PATHS) - markdown_files
    assert not missing_base_files, f"missing base markdown fixtures: {sorted(missing_base_files)}"

    missing_expected_files = EXPECTED_MARKDOWN_FIXTURE_DOCS - markdown_files
    assert not missing_expected_files, f"missing referenced markdown fixtures: {sorted(missing_expected_files)}"

    unexpected_files = markdown_files - EXPECTED_MARKDOWN_FIXTURE_DOCS
    assert not unexpected_files, f"unexpected markdown fixtures without governance: {sorted(unexpected_files)}"



def test_semireal_markdown_case_matrix_is_broad_enough() -> None:
    """半真实样本应覆盖多种题型与至少一个显式无证据场景。"""
    categories = {str(case["category"]) for case in SEMIREAL_CASES}
    assert {"fact", "summary", "policy", "architecture", "no-evidence", "roadmap", "metrics"}.issubset(categories)
    assert any(case["expected_doc"] is None for case in SEMIREAL_CASES)
    assert len(SEMIREAL_CASES) >= 8



def test_semireal_markdown_import_preserves_tree_and_indexes_docs(imported_markdown_kb: dict[str, object]) -> None:
    """导入后应保留目录树，并把所有 Markdown 文档入索引。"""
    result = imported_markdown_kb["import_result"]
    manager: FakeSemirealIndexManager = imported_markdown_kb["manager"]
    tmp_path: Path = imported_markdown_kb["tmp_path"]

    assert result["kb_id"] == KB_ID
    assert result["success_count"] == len(FIXTURE_IMPORT_PATHS)
    assert result["failed_count"] == 0
    assert result["empty_count"] == 0
    assert len(result["file_results"]) == len(FIXTURE_IMPORT_PATHS)
    assert manager.check_index_exists() is True
    assert len(manager.documents) == len(FIXTURE_IMPORT_PATHS)

    indexed_titles = {document["title"] for document in manager.documents}
    assert indexed_titles == set(FIXTURE_IMPORT_PATHS)

    indexed_relative_paths = {document["relative_path"] for document in manager.documents}
    assert indexed_relative_paths == set(FIXTURE_IMPORT_PATHS.values())

    result_by_name = {item["name"]: item for item in result["file_results"]}
    for name, relative_path in FIXTURE_IMPORT_PATHS.items():
        item = result_by_name[name]
        assert item["status"] == "indexed"
        assert item["relative_path"] == relative_path
        assert item["folder_path"] == Path(relative_path).parent.as_posix()
        assert Path(item["path"]).is_file()
        assert (tmp_path / "data" / KB_ID / relative_path).is_file()


@pytest.mark.parametrize("case", SEMIREAL_CASES, ids=[case["case_id"] for case in SEMIREAL_CASES])
def test_chat_markdown_qa_semireal_contract(case: dict[str, object], imported_markdown_kb: dict[str, object]) -> None:
    """按 case 验证半真实 Markdown 的问答、证据与 preview 契约。"""
    build_query_engine: MagicMock = imported_markdown_kb["build_query_engine"]

    payload, preview = _query_case(case)

    assert payload["requested_scope_type"] == "single_kb"
    assert payload["requested_kb_ids"] == [KB_ID]
    assert payload["effective_scope_type"] == "single_kb"
    assert payload["effective_kb_ids"] == [KB_ID]
    assert payload["is_default_deny_applied"] is False
    assert payload["isolation_level"] == "logical_filter_only"

    answer = payload["answer"]
    for keypoint in case["expected_keypoints"]:
        assert keypoint in answer
    for blocked in case["must_not_contain"]:
        assert blocked not in answer

    expected_source_count = int(case.get("expected_source_count", 1))
    assert len(payload["sources"]) == expected_source_count
    assert len(payload["evidence"]) == expected_source_count

    if expected_source_count == 0:
        assert case["expected_doc"] is None
        assert payload["sources"] == []
        assert payload["evidence"] == []
    else:
        source = payload["sources"][0]
        evidence = payload["evidence"][0]
        assert source["file"] == case["expected_doc"]
        assert evidence["title"] == case["expected_doc"]
        assert evidence["source"] == case["expected_doc"]
        assert evidence["doc_id"]
        assert evidence["preview_locator"]["page"] == "1"
        assert evidence["preview_locator"]["node_id"].startswith("node-")

        assert preview is not None
        assert preview["doc_id"] == evidence["doc_id"]
        assert preview["locator"]["page"] == "1"
        assert preview["locator"]["node_id"] == evidence["preview_locator"]["node_id"]
        for term in case["preview_terms"]:
            assert term in preview["excerpt"]

    report = build_chat_case_report(
        case,
        payload,
        expected_kb_ids=[KB_ID],
        expected_isolation_level="logical_filter_only",
        preview_payload=preview,
    )
    assert report["passed"] is True
    assert report["scope_passed"] is True
    assert report["keypoint_coverage"] == 1.0
    assert report["blocked_term_clean"] is True
    assert report["source_count_match"] is True
    assert report["evidence_hit"] is True
    if report["preview_required"]:
        assert report["preview_resolvable"] is True
        assert report["preview_term_coverage"] == 1.0

    build_query_engine.assert_called_once_with(kb_ids=[KB_ID])



def test_chat_markdown_qa_semireal_suite_metrics(imported_markdown_kb: dict[str, object]) -> None:
    """半真实层需要有 suite 级指标，不只停留在逐 case 断言。"""
    build_query_engine: MagicMock = imported_markdown_kb["build_query_engine"]
    reports = []

    for case in SEMIREAL_CASES:
        payload, preview = _query_case(case)
        reports.append(
            build_chat_case_report(
                case,
                payload,
                expected_kb_ids=[KB_ID],
                expected_isolation_level="logical_filter_only",
                preview_payload=preview,
            )
        )

    summary = summarize_chat_case_reports(reports)
    assert summary["total_cases"] == len(SEMIREAL_CASES)
    assert summary["passed_cases"] == len(SEMIREAL_CASES)
    assert summary["failed_cases"] == 0
    assert summary["pass_rate"] == 1.0
    assert summary["scope_pass_rate"] == 1.0
    assert summary["average_keypoint_coverage"] == 1.0
    assert summary["evidence_hit_rate"] == 1.0
    assert summary["preview_resolvable_rate"] == 1.0
    assert summary["source_count_match_rate"] == 1.0
    assert summary["forbidden_term_clean_rate"] == 1.0
    assert summary["category_breakdown"]["no-evidence"]["count"] >= 1
    assert build_query_engine.call_count == len(SEMIREAL_CASES)
