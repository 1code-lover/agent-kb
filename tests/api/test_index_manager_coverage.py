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


def _manager() -> index_module.IndexManager:
    manager = index_module.IndexManager("test-index")
    manager.storage_context = FakeStorage()
    return manager


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
        MagicMock(return_value=[SimpleNamespace(text="alpha", metadata={"file_path": str(source.resolve())})]),
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
    assert diagnostics["stage_timings"]["document_load_ms"] >= 0
    assert diagnostics["stage_timings"]["chunking_ms"] == 2.0
    assert diagnostics["stage_timings"]["embedding_ms"] == 3.0
    assert diagnostics["stage_timings"]["index_insert_ms"] >= 0
    assert diagnostics["stage_timings"]["total_ms"] >= diagnostics["stage_timings"]["embedding_ms"]
    assert manager.consume_last_ingestion_diagnostics() is None



def test_load_documents_records_empty_document_statistics(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "note.md"
    source.write_text("alpha", encoding="utf-8")

    manager = _manager()
    monkeypatch.setattr(manager, "insert_nodes", MagicMock())

    class FakePipeline:
        def run(self, documents, diagnostics=None):
            diagnostics["node_count"] = 1
            diagnostics["nodes_with_embedding_count"] = 1
            diagnostics["nodes_without_embedding_count"] = 0
            diagnostics["stage_timings"].update(
                {
                    "chunking_ms": 2.0,
                    "embedding_ms": 3.0,
                    "title_extract_ms": 4.0,
                    "vector_store_ms": 5.0,
                    "docstore_ms": 6.0,
                }
            )
            return [SimpleNamespace(metadata={})]

    monkeypatch.setattr(index_module, "AdvancedIngestionPipeline", FakePipeline)

    docs = [
        SimpleNamespace(text="alpha", metadata={"file_path": str(source.resolve()), "file_name": "note.md"}),
        SimpleNamespace(text="   ", metadata={"file_name": "blank.md"}),
    ]

    nodes = manager.load_documents(docs, 128, 16, kb_id="kb-a")
    diagnostics = manager.consume_last_ingestion_diagnostics()

    assert len(nodes) == 1
    assert diagnostics is not None
    assert diagnostics["document_count"] == 2
    assert diagnostics["empty_document_count"] == 1
    assert diagnostics["input_text_chars"] == 5
    assert diagnostics["node_count"] == 1
    assert diagnostics["nodes_with_embedding_count"] == 1
    assert diagnostics["nodes_without_embedding_count"] == 0
    assert diagnostics["stage_timings"]["document_load_ms"] == 0.0
    assert diagnostics["stage_timings"]["chunking_ms"] == 2.0
    assert diagnostics["stage_timings"]["index_insert_ms"] >= 0
