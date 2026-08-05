"""IndexManager 轻量覆盖率回归测试。

这些用例通过 monkeypatch 隔离 LlamaIndex、OCR、网页抓取等重依赖，覆盖本阶段目录化存储相关的索引入口及其周边分支。
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from server import index as index_module


class FakeIndex:
    """用于替代真实 VectorStoreIndex 的轻量索引对象。"""

    def __init__(self, index_id: str = "idx", nodes_dict: dict[str, str] | None = None) -> None:
        self.index_id = index_id
        self.inserted_nodes = None
        self.deleted = None
        self._store_nodes_override = False
        self.index_struct = SimpleNamespace(nodes_dict=nodes_dict if nodes_dict is not None else {})

    def insert_nodes(self, nodes):
        self.inserted_nodes = nodes

    def delete_ref_doc(self, ref_doc_id, delete_from_docstore):
        self.deleted = (ref_doc_id, delete_from_docstore)


class FakeRefDocInfo:
    """轻量 RefDocInfo 替代品，仅携带测试需要的 node_ids。"""

    def __init__(self, node_ids: list[str]) -> None:
        self.node_ids = node_ids


class FakeDocStore:
    """记录 get_ref_doc_info / delete_document 调用的轻量 docstore。"""

    def __init__(self, ref_doc_info: FakeRefDocInfo | None = None) -> None:
        self._ref_doc_info = ref_doc_info
        self.deleted_documents: list[str] = []

    def get_ref_doc_info(self, ref_doc_id):
        return self._ref_doc_info

    def delete_document(self, node_id, raise_error=True):
        self.deleted_documents.append(node_id)


class FakeStorage:
    """记录 persist 调用次数的轻量存储上下文。"""

    def __init__(self, docstore: FakeDocStore | None = None) -> None:
        self.persist_calls = 0
        self.docstore = docstore if docstore is not None else FakeDocStore()

    def persist(self) -> None:
        self.persist_calls += 1


class FakePersistTarget:
    """按 persist 过程记录调用参数。"""

    def __init__(self) -> None:
        self.persist_calls: list[tuple[str | None, object]] = []

    def persist(self, persist_path=None, fs=None) -> None:
        self.persist_calls.append((persist_path, fs))


class FakeProfiledStorage:
    """按 doc/index/vector/graph 分阶段记录落盘耗时。"""

    def __init__(self) -> None:
        self.docstore = FakePersistTarget()
        self.index_store = FakePersistTarget()
        self.graph_store = FakePersistTarget()
        self.property_graph_store = None
        self.vector_stores = {
            "default": FakePersistTarget(),
            "image": FakePersistTarget(),
        }
        self.persist_calls = 0

    def persist(self) -> None:
        self.persist_calls += 1


def _manager() -> index_module.IndexManager:
    manager = index_module.IndexManager("test-index")
    manager.storage_context = FakeStorage()
    return manager




def test_non_default_index_manager_uses_kb_storage_context_factory_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """非 default 知识库初始化时，只应命中当前 KB 的 storage_context 工厂。"""

    created: list[str] = []
    fake_context = SimpleNamespace(docstore=object(), index_store=object(), vector_store=object())
    expected_dir = (tmp_path / "storage" / "kbs" / "kb-a").resolve()

    monkeypatch.setattr(index_module, "create_storage_context", lambda persist_dir=None: created.append(persist_dir) or fake_context)
    monkeypatch.setattr(
        index_module,
        "get_default_storage_context",
        lambda: (_ for _ in ()).throw(AssertionError("default storage context should not be touched")),
    )
    monkeypatch.setattr(index_module, "get_kb_storage_dir", lambda kb_id, create=False: expected_dir)

    manager = index_module.IndexManager("test-index", kb_id="kb-a")

    assert manager.storage_context is fake_context
    assert manager.persist_dir == expected_dir
    assert created == [str(expected_dir)]



def test_create_ingestion_pipeline_prefers_manager_storage_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_create_ingestion_pipeline 应显式把 manager.storage_context 传给 pipeline。"""

    captured: dict[str, object] = {}

    class FakePipeline:
        def __init__(self, *, storage_context=None) -> None:
            captured["storage_context"] = storage_context

    monkeypatch.setattr(index_module, "AdvancedIngestionPipeline", FakePipeline)
    manager = _manager()

    pipeline = manager._create_ingestion_pipeline()

    assert isinstance(pipeline, FakePipeline)
    assert captured["storage_context"] is manager.storage_context

def test_check_index_exists_sets_first_index(monkeypatch: pytest.MonkeyPatch) -> None:
    first = FakeIndex("first")
    monkeypatch.setattr(index_module, "load_indices_from_storage", MagicMock(return_value=[first]))

    manager = _manager()

    assert manager.check_index_exists() is True
    assert manager.index is first
    assert manager.index_id == "first"


def test_check_index_exists_returns_false_when_storage_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(index_module, "load_indices_from_storage", MagicMock(return_value=[]))

    manager = _manager()

    assert manager.check_index_exists() is False
    assert manager.index is None


def test_init_index_persists_and_returns_created_index(monkeypatch: pytest.MonkeyPatch) -> None:
    created = FakeIndex("created")
    vector_ctor = MagicMock(return_value=created)
    monkeypatch.setattr(index_module, "VectorStoreIndex", vector_ctor)
    monkeypatch.setattr(index_module, "DEV_MODE", True)
    manager = _manager()

    result = manager.init_index(["node"])

    assert result is created
    assert manager.index_id == "created"
    assert manager.storage_context.persist_calls == 1
    vector_ctor.assert_called_once_with(["node"], storage_context=manager.storage_context, store_nodes_override=True)


def test_init_index_can_skip_persist(monkeypatch: pytest.MonkeyPatch) -> None:
    created = FakeIndex("created")
    vector_ctor = MagicMock(return_value=created)
    monkeypatch.setattr(index_module, "VectorStoreIndex", vector_ctor)
    monkeypatch.setattr(index_module, "DEV_MODE", True)
    manager = _manager()

    result = manager.init_index(["node"], persist=False)

    assert result is created
    assert manager.storage_context.persist_calls == 0


def test_load_index_returns_cached_index_without_storage_call(monkeypatch: pytest.MonkeyPatch) -> None:
    cached = FakeIndex("cached")
    load_spy = MagicMock()
    monkeypatch.setattr(index_module, "load_index_from_storage", load_spy)
    manager = _manager()
    manager.index = cached

    assert manager.load_index() is cached
    load_spy.assert_not_called()


def test_load_index_uses_known_index_id_and_sets_store_override(monkeypatch: pytest.MonkeyPatch) -> None:
    loaded = FakeIndex("known")
    load_spy = MagicMock(return_value=loaded)
    monkeypatch.setattr(index_module, "load_index_from_storage", load_spy)
    monkeypatch.setattr(index_module, "DEV_MODE", False)
    manager = _manager()
    manager.index_id = "known"

    assert manager.load_index() is loaded
    load_spy.assert_called_once_with(manager.storage_context, index_id="known")
    assert loaded._store_nodes_override is True


def test_load_index_falls_back_to_first_available_index(monkeypatch: pytest.MonkeyPatch) -> None:
    fallback = FakeIndex("fallback")
    monkeypatch.setattr(index_module, "load_index_from_storage", MagicMock(side_effect=ValueError("missing")))
    monkeypatch.setattr(index_module, "load_indices_from_storage", MagicMock(return_value=[fallback]))
    monkeypatch.setattr(index_module, "DEV_MODE", True)
    manager = _manager()

    assert manager.load_index() is fallback
    assert manager.index_id == "fallback"


def test_load_index_raises_when_no_index_can_be_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(index_module, "load_index_from_storage", MagicMock(side_effect=ValueError("missing")))
    monkeypatch.setattr(index_module, "load_indices_from_storage", MagicMock(return_value=[]))
    manager = _manager()

    with pytest.raises(ValueError, match="No indices found"):
        manager.load_index()


def test_insert_nodes_inserts_into_existing_index_and_persists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(index_module, "DEV_MODE", True)
    manager = _manager()
    manager.index = FakeIndex("existing")

    result = manager.insert_nodes(["n1", "n2"])

    assert result is manager.index
    assert manager.index.inserted_nodes == ["n1", "n2"]
    assert manager.storage_context.persist_calls == 1


def test_insert_nodes_can_skip_persist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(index_module, "DEV_MODE", True)
    manager = _manager()
    manager.index = FakeIndex("existing")

    result = manager.insert_nodes(["n1", "n2"], persist=False)

    assert result is manager.index
    assert manager.index.inserted_nodes == ["n1", "n2"]
    assert manager.storage_context.persist_calls == 0



def test_delete_ref_doc_removes_stale_node_ids_before_delegate(monkeypatch: pytest.MonkeyPatch) -> None:
    """删除文档前应先清理 docstore 中的陈旧 node 引用。"""
    monkeypatch.setattr(index_module, "DEV_MODE", True)
    docstore = FakeDocStore(FakeRefDocInfo(["node-live", "node-stale"]))
    manager = index_module.IndexManager("test-index")
    manager.storage_context = FakeStorage(docstore=docstore)
    manager.index = FakeIndex("existing", nodes_dict={"node-live": "live"})

    manager.delete_ref_doc("doc-1")

    assert docstore.deleted_documents == ["node-stale"]
    assert manager.index.deleted == ("doc-1", True)
    assert manager.storage_context.persist_calls == 1


def test_delete_ref_doc_keeps_normal_nodes_and_still_persists(monkeypatch: pytest.MonkeyPatch) -> None:
    """无陈旧引用时不应误删正常 node，但仍要执行原有删除流程。"""
    monkeypatch.setattr(index_module, "DEV_MODE", True)
    docstore = FakeDocStore(FakeRefDocInfo(["node-a", "node-b"]))
    manager = index_module.IndexManager("test-index")
    manager.storage_context = FakeStorage(docstore=docstore)
    manager.index = FakeIndex("existing", nodes_dict={"node-a": "a", "node-b": "b"})

    manager.delete_ref_doc("doc-2")

    assert docstore.deleted_documents == []
    assert manager.index.deleted == ("doc-2", True)
    assert manager.storage_context.persist_calls == 1


def test_persist_storage_records_component_timings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(index_module, "DEV_MODE", True)
    manager = index_module.IndexManager("test-index")
    manager.storage_context = FakeProfiledStorage()

    assert manager.persist_storage() is True

    diagnostics = manager.consume_last_persist_diagnostics()
    assert diagnostics is not None
    assert diagnostics["docstore_persist_ms"] >= 0
    assert diagnostics["index_store_persist_ms"] >= 0
    assert diagnostics["graph_store_persist_ms"] >= 0
    assert diagnostics["vector_store_persist_ms"] >= 0
    assert diagnostics["fallback_persist_ms"] == 0.0
    assert diagnostics["vector_store_namespaces_ms"].keys() == {"default", "image"}
    assert diagnostics["vector_store_namespaces_ms"]["default"] >= 0
    assert diagnostics["vector_store_namespaces_ms"]["image"] >= 0
    assert diagnostics["total_ms"] >= diagnostics["vector_store_persist_ms"]
    assert manager.storage_context.persist_calls == 0
    assert manager.storage_context.docstore.persist_calls[0][0].endswith("docstore.json")
    assert manager.storage_context.index_store.persist_calls[0][0].endswith("index_store.json")
    assert manager.storage_context.graph_store.persist_calls[0][0].endswith("graph_store.json")
    assert manager.storage_context.vector_stores["default"].persist_calls[0][0].endswith("default__vector_store.json")
    assert manager.storage_context.vector_stores["image"].persist_calls[0][0].endswith("image__vector_store.json")
    assert manager.consume_last_persist_diagnostics() is None


def test_persist_storage_uses_manager_persist_dir_for_component_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """确保使用 manager 自身的 persist_dir，而不是默认 storage/。"""

    monkeypatch.setattr(index_module, "DEV_MODE", True)
    persist_dir = tmp_path / "storage" / "kbs" / "kb-a"
    manager = index_module.IndexManager(
        "test-index",
        storage_context=FakeProfiledStorage(),
        persist_dir=persist_dir,
        kb_id="kb-a",
    )

    assert manager.persist_storage() is True

    assert manager.storage_context.docstore.persist_calls[0][0] == str((persist_dir / "docstore.json").resolve())
    assert manager.storage_context.index_store.persist_calls[0][0] == str((persist_dir / "index_store.json").resolve())
    assert manager.storage_context.graph_store.persist_calls[0][0] == str((persist_dir / "graph_store.json").resolve())
    assert manager.storage_context.vector_stores["default"].persist_calls[0][0] == str((persist_dir / "default__vector_store.json").resolve())
    assert manager.storage_context.vector_stores["image"].persist_calls[0][0] == str((persist_dir / "image__vector_store.json").resolve())


def test_persist_storage_fallback_passes_manager_persist_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """确保在 fallback persist 时也传入 manager 的持久化目录。"""

    class FallbackStorage(FakeStorage):
        def __init__(self) -> None:
            super().__init__()
            self.persist_kwargs: list[str | None] = []

        def persist(self, persist_dir=None) -> None:
            self.persist_calls += 1
            self.persist_kwargs.append(persist_dir)

    monkeypatch.setattr(index_module, "DEV_MODE", True)
    persist_dir = tmp_path / "storage" / "kbs" / "kb-a"
    storage = FallbackStorage()
    manager = index_module.IndexManager(
        "test-index",
        storage_context=storage,
        persist_dir=persist_dir,
        kb_id="kb-a",
    )
    monkeypatch.setattr(manager, "_persist_storage_with_diagnostics", MagicMock(return_value=None))

    assert manager.persist_storage() is True

    assert storage.persist_kwargs == [str(persist_dir.resolve())]
    diagnostics = manager.consume_last_persist_diagnostics()
    assert diagnostics is not None
    assert diagnostics["fallback_persist_ms"] >= 0
    assert diagnostics["total_ms"] == diagnostics["fallback_persist_ms"]


def test_insert_nodes_initializes_index_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager()
    init_spy = MagicMock(return_value=FakeIndex("new"))
    monkeypatch.setattr(manager, "init_index", init_spy)

    result = manager.insert_nodes(["n1"])

    init_spy.assert_called_once_with(nodes=["n1"], persist=True)
    assert result is None


def test_load_dir_reads_files_runs_pipeline_and_inserts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "data" / "a.txt"
    source.parent.mkdir(parents=True)
    source.write_text("alpha", encoding="utf-8")
    manager = _manager()
    monkeypatch.setattr(manager, "_load_documents", MagicMock(return_value=[SimpleNamespace(metadata={})]))
    monkeypatch.setattr(manager, "insert_nodes", MagicMock())

    class FakePipeline:
        def run(self, documents):
            return [SimpleNamespace(metadata={"from": len(documents)})]

    monkeypatch.setattr(index_module, "AdvancedIngestionPipeline", FakePipeline)

    nodes = manager.load_dir(str(source.parent), 128, 16)

    assert nodes[0].metadata == {"from": 1}
    manager._load_documents.assert_called_once_with([str(source)])
    manager.insert_nodes.assert_called_once_with(nodes)


def test_load_dir_returns_empty_for_empty_directory(tmp_path: Path) -> None:
    manager = _manager()

    assert manager.load_dir(str(tmp_path), 128, 16) == []


def test_load_documents_combines_other_non_pdf_and_pdf_docs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    docx = tmp_path / "a.docx"
    pdf = tmp_path / "b.pdf"
    docx.write_bytes(b"PK")
    pdf.write_bytes(b"%PDF")

    class FakeSimpleDirectoryReader:
        def __init__(self, input_files):
            self.input_files = input_files

        def load_data(self):
            return [SimpleNamespace(text="docx", metadata={"input_files": self.input_files})]

    class FakePDFOCRReader:
        def load_data(self, fp):
            return [SimpleNamespace(text="pdf", metadata={"file_path": fp})]

    fake_pdf_module = types.ModuleType("server.readers.pdf_ocr")
    fake_pdf_module.PDFOCRReader = FakePDFOCRReader
    monkeypatch.setitem(sys.modules, "server.readers.pdf_ocr", fake_pdf_module)
    monkeypatch.setattr(index_module, "SimpleDirectoryReader", FakeSimpleDirectoryReader)

    docs = _manager()._load_documents([str(docx), str(pdf)])

    assert [doc.text for doc in docs] == ["docx", "pdf"]
    assert docs[0].metadata["input_files"] == [str(docx)]
    assert docs[1].metadata["file_path"] == str(pdf)


def test_load_documents_preserves_utf8_markdown_chinese_text(tmp_path: Path) -> None:
    """UTF-8 Markdown 正文应按原样保留，不能在导入前后变成问号。"""
    source = tmp_path / "readme.md"
    expected = (
        "中文导入验证\n"
        "这个 Markdown 文档用于验证中文 UTF-8 导入。\n"
        "关键短语：目录范围浏览、知识库助手、证据预览。\n"
    )
    source.write_bytes(expected.encode("utf-8"))

    docs = _manager()._load_documents([str(source)])

    assert len(docs) == 1
    assert docs[0].text == expected
    assert "?" not in docs[0].text
    assert docs[0].metadata["file_name"] == "readme.md"
    assert docs[0].metadata["source_encoding"] == "utf-8"

def test_load_documents_decodes_gb18030_markdown_without_question_marks(tmp_path: Path) -> None:
    """GB18030 Markdown 正文应保留原文，不能被 utf-8 ignore 解成问号。"""
    source = tmp_path / "readme.md"
    expected = (
        "产品说明\n"
        "知识库导入应该保留正文\n"
        "![流程图](./images/流程图.png)\n"
    )
    source.write_bytes(expected.encode("gb18030"))

    docs = _manager()._load_documents([str(source)])

    assert len(docs) == 1
    assert docs[0].text == expected
    assert "?" not in docs[0].text
    assert docs[0].metadata["file_name"] == "readme.md"


def test_load_documents_decodes_utf16_markdown_without_losing_text(tmp_path: Path) -> None:
    """UTF-16 Markdown 正文与内嵌图片路径应完整保留。"""
    source = tmp_path / "readme.md"
    expected = (
        "产品说明\n"
        "这是 UTF-16 编码的知识库文档\n"
        "![流程图](./images/流程图.png)\n"
    )
    source.write_bytes(expected.encode("utf-16"))

    docs = _manager()._load_documents([str(source)])

    assert len(docs) == 1
    assert docs[0].text == expected
    assert docs[0].metadata["file_name"] == "readme.md"
    assert docs[0].metadata["source_encoding"].startswith("utf-16")
    assert "流程图.png" in docs[0].text
    assert "?" not in docs[0].text



def test_load_files_records_last_ingestion_diagnostics(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "data" / "kb-a" / "a.txt"
    source.parent.mkdir(parents=True)
    source.write_text("alpha", encoding="utf-8")

    manager = _manager()
    monkeypatch.setattr(
        manager,
        "_load_documents",
        MagicMock(return_value=[SimpleNamespace(text="alpha", metadata={"file_path": str(source.resolve()), "file_name": source.name, "source_type": "pdf_ocr_fallback", "ocr_attempted": True, "ocr_status": "success", "ocr_text_length": 5, "indexed_from_ocr": True, "ocr_engine": "mock-paddleocr"})]),
    )
    monkeypatch.setattr(manager, "insert_nodes", MagicMock())

    class FakePipeline:
        def run(self, documents, diagnostics=None):
            diagnostics["node_count"] = 2
            diagnostics["nodes_with_embedding_count"] = 1
            diagnostics["nodes_without_embedding_count"] = 1
            diagnostics["stage_timings"].update(
                {
                    "chunking_ms": 2.0,
                    "embedding_ms": 3.0,
                    "title_extract_ms": 4.0,
                    "vector_store_ms": 5.0,
                    "docstore_ms": 6.0,
                }
            )
            return [SimpleNamespace(metadata={}), SimpleNamespace(metadata={})]

    monkeypatch.setattr(index_module, "AdvancedIngestionPipeline", FakePipeline)

    nodes = manager.load_files([source], 128, 16, kb_id="kb-a")
    diagnostics = manager.consume_last_ingestion_diagnostics()

    assert len(nodes) == 2
    assert diagnostics is not None
    assert diagnostics["document_count"] == 1
    assert diagnostics["empty_document_count"] == 0
    assert diagnostics["input_text_chars"] == 5
    assert diagnostics["node_count"] == 2
    assert diagnostics["nodes_with_embedding_count"] == 1
    assert diagnostics["nodes_without_embedding_count"] == 1
    assert diagnostics["source_file_diagnostics"] == [{"file_path": str(source.resolve()), "file_name": source.name, "source_type": "pdf_ocr_fallback", "ocr_attempted": True, "ocr_status": "success", "ocr_text_length": 5, "ocr_error": None, "indexed_from_ocr": True, "ocr_engine": "mock-paddleocr"}]
    assert diagnostics["stage_timings"]["document_load_ms"] >= 0
    assert diagnostics["stage_timings"]["chunking_ms"] == 2.0
    assert diagnostics["stage_timings"]["embedding_ms"] == 3.0
    assert diagnostics["stage_timings"]["index_insert_ms"] >= 0



def test_load_files_keeps_source_file_diagnostics_when_pipeline_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "data" / "kb-a" / "scan.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"%PDF-1.4")

    manager = _manager()
    monkeypatch.setattr(
        manager,
        "_load_documents",
        MagicMock(return_value=[SimpleNamespace(text="alpha", metadata={"file_path": str(source.resolve()), "file_name": source.name, "source_type": "pdf_ocr_fallback", "ocr_attempted": True, "ocr_status": "success", "ocr_text_length": 5, "indexed_from_ocr": True, "ocr_engine": "mock-paddleocr", "ocr_total_ms": 70.0})]),
    )
    monkeypatch.setattr(
        manager,
        "_run_pipeline_with_diagnostics",
        MagicMock(side_effect=ValueError("Metadata length (155) is longer than chunk size (128).")),
    )
    monkeypatch.setattr(manager, "insert_nodes", MagicMock())

    with pytest.raises(ValueError, match="Metadata length"):
        manager.load_files([source], 128, 16, kb_id="kb-a")

    diagnostics = manager.consume_last_ingestion_diagnostics()
    assert diagnostics is not None
    assert diagnostics["source_file_diagnostics"] == [{"file_path": str(source.resolve()), "file_name": source.name, "source_type": "pdf_ocr_fallback", "ocr_attempted": True, "ocr_status": "success", "ocr_text_length": 5, "ocr_error": None, "indexed_from_ocr": True, "ocr_engine": "mock-paddleocr", "ocr_total_ms": 70.0}]
    assert diagnostics["stage_timings"]["document_load_ms"] >= 0
    manager.insert_nodes.assert_not_called()


def test_load_files_returns_empty_without_inserting_nodes_when_pipeline_yields_none(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """????????????????? insert_nodes????????"""
    source = tmp_path / "data" / "kb-a" / "empty.md"
    source.parent.mkdir(parents=True)
    source.write_text("   \n\n", encoding="utf-8")

    manager = _manager()
    monkeypatch.setattr(
        manager,
        "_load_documents",
        MagicMock(return_value=[SimpleNamespace(text="", metadata={"file_path": str(source.resolve()), "file_name": source.name})]),
    )
    monkeypatch.setattr(manager, "insert_nodes", MagicMock())

    class FakePipeline:
        def run(self, documents, diagnostics=None):
            diagnostics["node_count"] = 0
            diagnostics["nodes_with_embedding_count"] = 0
            diagnostics["nodes_without_embedding_count"] = 0
            return None

    monkeypatch.setattr(index_module, "AdvancedIngestionPipeline", FakePipeline)

    nodes = manager.load_files([source], 128, 16, kb_id="kb-a")
    diagnostics = manager.consume_last_ingestion_diagnostics()

    assert nodes == []
    assert diagnostics is not None
    assert diagnostics["document_count"] == 1
    assert diagnostics["empty_document_count"] == 1
    assert diagnostics["node_count"] == 0
    manager.insert_nodes.assert_not_called()



def test_load_documents_returns_empty_without_inserting_nodes_when_pipeline_yields_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """??????????????????????"""
    manager = _manager()
    monkeypatch.setattr(manager, "insert_nodes", MagicMock())

    class FakePipeline:
        def run(self, documents, diagnostics=None):
            diagnostics["node_count"] = 0
            diagnostics["nodes_with_embedding_count"] = 0
            diagnostics["nodes_without_embedding_count"] = 0
            return None

    monkeypatch.setattr(index_module, "AdvancedIngestionPipeline", FakePipeline)

    nodes = manager.load_documents(
        [SimpleNamespace(text="", metadata={"file_name": "empty.md"})],
        128,
        16,
        kb_id="kb-a",
    )
    diagnostics = manager.consume_last_ingestion_diagnostics()

    assert nodes == []
    assert diagnostics is not None
    assert diagnostics["document_count"] == 1
    assert diagnostics["empty_document_count"] == 1
    assert diagnostics["node_count"] == 0
    manager.insert_nodes.assert_not_called()


def test_index_document_helper_functions_cover_fallback_branches(tmp_path: Path) -> None:
    """文档辅助函数应兼容 get_content 回退、空值与坏路径输入。"""

    class ContentOnlyDoc:
        def get_content(self):
            return "beta"

    class BrokenContentDoc:
        def get_content(self):
            raise RuntimeError("boom")

    file_path = tmp_path / "note.md"
    file_path.write_text("alpha", encoding="utf-8")

    built = index_module._build_text_document(file_path)
    summary = index_module._summarize_documents(
        [
            SimpleNamespace(text="alpha"),
            ContentOnlyDoc(),
            BrokenContentDoc(),
            None,
        ]
    )

    assert index_module._read_document_text(None) == ""
    assert index_module._read_document_text(ContentOnlyDoc()) == "beta"
    assert index_module._read_document_text(BrokenContentDoc()) == ""
    assert built.text == "alpha"
    assert built.metadata["file_path"] == str(file_path.resolve())
    assert built.metadata["file_name"] == "note.md"
    assert built.metadata["file_type"] == "text/markdown"
    assert built.metadata["file_size"] == 5
    assert built.metadata["source_encoding"].lower().startswith("utf")
    assert summary == {
        "document_count": 4,
        "empty_document_count": 2,
        "input_text_chars": 9,
    }
    assert index_module._resolve_path_metadata({"bad": True}) is None
    assert index_module._resolve_path_metadata("   ") is None
    assert index_module._resolve_path_metadata(file_path) == file_path.resolve()
    assert index_module._format_file_date(None) is None
    assert index_module._format_file_date(float("inf")) is None


def test_collect_document_source_diagnostics_filters_duplicates_and_counts_embeddings(
    tmp_path: Path,
) -> None:
    """PDF/OCR 源诊断只应保留合法路径，并对同一路径去重。"""
    pdf_path = tmp_path / "manual.pdf"
    pdf_path.write_text("stub", encoding="utf-8")

    diagnostics = index_module._collect_document_source_diagnostics(
        [
            SimpleNamespace(metadata=None),
            SimpleNamespace(metadata={"file_path": {"bad": True}, "source_type": "pdf_text_layer"}),
            SimpleNamespace(metadata={"file_path": str(pdf_path), "source_type": "markdown"}),
            SimpleNamespace(
                metadata={
                    "file_path": str(pdf_path),
                    "file_name": "manual.pdf",
                    "source_type": "pdf_text_layer",
                    "ocr_attempted": False,
                    "ocr_status": None,
                    "ocr_text_length": 0,
                    "indexed_from_ocr": False,
                    "ocr_engine": None,
                }
            ),
            SimpleNamespace(
                metadata={
                    "file_path": str(pdf_path),
                    "file_name": "ignored-duplicate.pdf",
                    "source_type": "pdf_ocr_fallback",
                    "ocr_attempted": True,
                    "ocr_status": "success",
                    "ocr_text_length": 12,
                    "indexed_from_ocr": True,
                    "ocr_engine": "mock",
                }
            ),
        ]
    )

    with_embeddings, without_embeddings = index_module._count_nodes_with_embeddings(
        [SimpleNamespace(embedding=[0.1]), SimpleNamespace(embedding=None), SimpleNamespace()]
    )

    assert diagnostics == [
        {
            "file_path": str(pdf_path.resolve()),
            "file_name": "manual.pdf",
            "source_type": "pdf_text_layer",
            "ocr_attempted": False,
            "ocr_status": None,
            "ocr_text_length": 0,
            "ocr_error": None,
            "indexed_from_ocr": False,
            "ocr_engine": None,
        }
    ]
    assert (with_embeddings, without_embeddings) == (1, 2)


def test_load_websites_falls_back_to_jina_and_inserts_kb_nodes(monkeypatch: pytest.MonkeyPatch) -> None:
    """网页导入在首轮抓取为空时应走镜像回退，并补齐 kb_id。"""
    manager = _manager()
    manager.insert_nodes = MagicMock()
    load_calls: list[list[str]] = []

    class BlankDoc:
        text = "   "
        metadata = {"source": "blank"}
        extra_info = {"kind": "blank"}

    class ContentOnlyDoc:
        text = None

        def __init__(self) -> None:
            self.metadata = {"title": "fallback"}
            self.extra_info = {"kind": "content-only"}

        def get_content(self):
            return "Recovered body from fallback"

    class FakeReader:
        def load_data(self, urls):
            normalized = list(urls)
            load_calls.append(normalized)
            if len(load_calls) == 1:
                return [None, BlankDoc()]
            return [ContentOnlyDoc()]

    fake_reader_module = types.ModuleType("server.readers.beautiful_soup_web")
    fake_reader_module.BeautifulSoupWebReader = FakeReader
    monkeypatch.setitem(sys.modules, "server.readers.beautiful_soup_web", fake_reader_module)

    fake_splitter_module = types.ModuleType("server.text_splitter")
    fake_splitter_module.create_text_splitter = lambda **kwargs: SimpleNamespace(**kwargs)
    monkeypatch.setitem(sys.modules, "server.text_splitter", fake_splitter_module)
    index_module.Settings._node_parser = SimpleNamespace(chunk_size=0, chunk_overlap=0)

    class FakePipeline:
        def __init__(self) -> None:
            self.disable_cache = False
            self.cache = object()
            self.documents = None

        def run(self, documents):
            self.documents = list(documents)
            return [SimpleNamespace(metadata={"origin": "web"})]

    pipeline = FakePipeline()
    monkeypatch.setattr(manager, "_create_ingestion_pipeline", lambda: pipeline)

    nodes = manager.load_websites("https://a.example\n\n https://b.example ", 256, 32, kb_id="kb-web")

    assert load_calls == [
        ["https://a.example", "https://b.example"],
        ["https://r.jina.ai/https://a.example", "https://r.jina.ai/https://b.example"],
    ]
    assert pipeline.disable_cache is True
    assert pipeline.cache is None
    assert len(pipeline.documents) == 1
    assert pipeline.documents[0].get_content() == "Recovered body from fallback"
    assert isinstance(pipeline.documents[0].metadata, dict)
    assert isinstance(pipeline.documents[0].extra_info, dict)
    assert nodes[0].metadata["kb_id"] == "kb-web"
    manager.insert_nodes.assert_called_once_with(nodes)


def test_load_websites_raises_when_primary_and_fallback_have_no_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """网页导入在主抓取与镜像回退都无有效正文时应明确报错。"""
    manager = _manager()
    manager.insert_nodes = MagicMock()
    load_calls: list[list[str]] = []

    class EmptyDoc:
        text = ""
        metadata = {}
        extra_info = {}

    class FakeReader:
        def load_data(self, urls):
            load_calls.append(list(urls))
            return [None, EmptyDoc()]

    fake_reader_module = types.ModuleType("server.readers.beautiful_soup_web")
    fake_reader_module.BeautifulSoupWebReader = FakeReader
    monkeypatch.setitem(sys.modules, "server.readers.beautiful_soup_web", fake_reader_module)

    fake_splitter_module = types.ModuleType("server.text_splitter")
    fake_splitter_module.create_text_splitter = lambda **kwargs: SimpleNamespace(**kwargs)
    monkeypatch.setitem(sys.modules, "server.text_splitter", fake_splitter_module)
    index_module.Settings._node_parser = SimpleNamespace(chunk_size=0, chunk_overlap=0)

    with pytest.raises(ValueError, match="No extractable text"):
        manager.load_websites([" https://c.example "], 128, 16, kb_id="kb-web")

    assert load_calls == [
        ["https://c.example"],
        ["https://r.jina.ai/https://c.example"],
    ]
    manager.insert_nodes.assert_not_called()

def test_merge_source_file_diagnostics_filters_invalid_items_and_overrides(tmp_path: Path) -> None:
    """文件级诊断合并应跳过非 list / 无效项，并允许后者覆盖前者。"""
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF")

    merged = index_module._merge_source_file_diagnostics(
        None,
        "bad",
        [{"invalid": True}],
        [
            {
                "file_path": str(source),
                "file_name": "scan.pdf",
                "source_type": "pdf_ocr_fallback",
                "ocr_attempted": False,
            }
        ],
        [
            {
                "file_path": str(source),
                "file_name": "scan-override.pdf",
                "source_type": "pdf_ocr_fallback",
                "ocr_attempted": True,
                "ocr_status": "success",
            }
        ],
    )

    assert merged == [
        {
            "file_path": str(source.resolve()),
            "file_name": "scan-override.pdf",
            "source_type": "pdf_ocr_fallback",
            "ocr_attempted": True,
            "ocr_status": "success",
            "ocr_text_length": 0,
            "ocr_error": None,
            "indexed_from_ocr": False,
            "ocr_engine": None,
        }
    ]


def test_finalize_ingestion_total_ignores_invalid_stage_values() -> None:
    """总耗时计算应忽略非数值 stage 字段和损坏的 total_ms。"""
    stage_timings = {
        "document_load_ms": "bad",
        "embedding_ms": 5.0,
        "index_insert_ms": None,
        "total_ms": "broken",
    }

    total_ms = index_module._finalize_ingestion_total(stage_timings, started_at=0.0)

    assert total_ms >= 5.0
    assert stage_timings["total_ms"] == total_ms



def test_resolve_path_metadata_returns_none_when_path_resolution_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """路径解析失败时应返回 None，而不是将异常泄漏给上层。"""

    class BrokenPath:
        def __init__(self, raw: str) -> None:
            self.raw = raw

        def resolve(self):
            raise OSError("boom")

    monkeypatch.setattr(index_module, "Path", BrokenPath)

    assert index_module._resolve_path_metadata("C:/tmp/example.md") is None



def test_persist_storage_returns_false_when_dev_mode_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """非 DEV_MODE 下 persist_storage 应显式返回 False。"""
    manager = _manager()
    monkeypatch.setattr(index_module, "DEV_MODE", False)

    assert manager.persist_storage() is False
    assert manager.consume_last_persist_diagnostics() is None



def test_load_documents_normalizes_node_metadata_and_respects_persist_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """load_documents 应回填 file_path/file_name/kb_id，并将 persist 标志透传给 insert_nodes。"""
    source = tmp_path / "kb-a" / "note.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("alpha", encoding="utf-8")
    manager = _manager()
    monkeypatch.setattr(manager, "insert_nodes", MagicMock())

    class FakePipeline:
        def run(self, documents, diagnostics=None):
            diagnostics["node_count"] = 1
            diagnostics["nodes_with_embedding_count"] = 1
            diagnostics["nodes_without_embedding_count"] = 0
            return [SimpleNamespace(metadata={"tags": {"kb", "note"}})]

    monkeypatch.setattr(index_module, "AdvancedIngestionPipeline", FakePipeline)

    nodes = manager.load_documents(
        [SimpleNamespace(text="alpha", metadata={"file_path": str(source), "tags": {"kb", "note"}})],
        128,
        16,
        kb_id="kb-a",
        persist=False,
    )

    assert nodes[0].metadata["file_path"] == str(source.resolve())
    assert nodes[0].metadata["file_name"] == "note.md"
    assert nodes[0].metadata["kb_id"] == "kb-a"
    assert sorted(nodes[0].metadata["tags"]) == ["kb", "note"]
    manager.insert_nodes.assert_called_once_with(nodes, persist=False)
    diagnostics = manager.consume_last_ingestion_diagnostics()
    assert diagnostics is not None
    assert diagnostics["input_file_count"] == 1
    assert diagnostics["document_count"] == 1
    assert diagnostics["node_count"] == 1



def test_load_files_backfills_metadata_for_single_input_and_empty_loader(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """load_files 应在单文件场景下回填 metadata，并在 loader 结果为空时稳定返回空列表。"""
    source = tmp_path / "kb-a" / "only.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("alpha", encoding="utf-8")
    manager = _manager()
    monkeypatch.setattr(manager, "insert_nodes", MagicMock())

    monkeypatch.setattr(
        manager,
        "_load_documents",
        MagicMock(return_value=[SimpleNamespace(text="alpha", metadata={"file_name": source.name})]),
    )

    class FakePipeline:
        def run(self, documents, diagnostics=None):
            diagnostics["node_count"] = 1
            diagnostics["nodes_with_embedding_count"] = 1
            diagnostics["nodes_without_embedding_count"] = 0
            return [SimpleNamespace(metadata=None)]

    monkeypatch.setattr(index_module, "AdvancedIngestionPipeline", FakePipeline)

    nodes = manager.load_files([source], 128, 16, kb_id="kb-a", persist=False)

    assert nodes[0].metadata["file_path"] == str(source.resolve())
    assert nodes[0].metadata["file_name"] == source.name
    assert nodes[0].metadata["kb_id"] == "kb-a"
    manager.insert_nodes.assert_called_once_with(nodes, persist=False)

    manager.insert_nodes.reset_mock()
    monkeypatch.setattr(manager, "_load_documents", MagicMock(return_value=[]))

    empty_nodes = manager.load_files([source], 128, 16, kb_id="kb-a")
    diagnostics = manager.consume_last_ingestion_diagnostics()

    assert empty_nodes == []
    manager.insert_nodes.assert_not_called()
    assert diagnostics is not None
    assert diagnostics["input_file_count"] == 1
    assert diagnostics["document_count"] == 0
