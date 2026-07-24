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


def test_insert_nodes_initializes_index_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager()
    init_spy = MagicMock(return_value=FakeIndex("new"))
    monkeypatch.setattr(manager, "init_index", init_spy)

    result = manager.insert_nodes(["n1"])

    init_spy.assert_called_once_with(nodes=["n1"])
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


def test_load_documents_combines_non_pdf_and_pdf_docs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    txt = tmp_path / "a.txt"
    pdf = tmp_path / "b.pdf"
    txt.write_text("alpha", encoding="utf-8")
    pdf.write_bytes(b"%PDF")

    class FakeSimpleDirectoryReader:
        def __init__(self, input_files):
            self.input_files = input_files

        def load_data(self):
            return [SimpleNamespace(text="txt", metadata={"input_files": self.input_files})]

    class FakePDFOCRReader:
        def load_data(self, fp):
            return [SimpleNamespace(text="pdf", metadata={"file_path": fp})]

    fake_pdf_module = types.ModuleType("server.readers.pdf_ocr")
    fake_pdf_module.PDFOCRReader = FakePDFOCRReader
    monkeypatch.setitem(sys.modules, "server.readers.pdf_ocr", fake_pdf_module)
    monkeypatch.setattr(index_module, "SimpleDirectoryReader", FakeSimpleDirectoryReader)

    docs = _manager()._load_documents([str(txt), str(pdf)])

    assert [doc.text for doc in docs] == ["txt", "pdf"]
    assert docs[0].metadata["input_files"] == [str(txt)]
    assert docs[1].metadata["file_path"] == str(pdf)


def test_load_documents_skips_empty_pdf(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pdf = tmp_path / "empty.pdf"
    pdf.write_bytes(b"%PDF")

    class EmptyPDFOCRReader:
        def load_data(self, fp):
            return []

    fake_pdf_module = types.ModuleType("server.readers.pdf_ocr")
    fake_pdf_module.PDFOCRReader = EmptyPDFOCRReader
    monkeypatch.setitem(sys.modules, "server.readers.pdf_ocr", fake_pdf_module)

    assert _manager()._load_documents([str(pdf)]) == []


def test_load_files_handles_empty_documents(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "a.txt"
    source.write_text("alpha", encoding="utf-8")
    manager = _manager()
    monkeypatch.setattr(manager, "_load_documents", MagicMock(return_value=[]))

    assert manager.load_files([source], 128, 16, kb_id="kb-a") == []


def test_load_files_maps_nodes_by_file_name_and_normalizes_metadata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("alpha", encoding="utf-8")
    b.write_text("bravo", encoding="utf-8")
    manager = _manager()
    docs = [SimpleNamespace(metadata={"file_name": "a.txt"}), SimpleNamespace(metadata={"file_name": "b.txt"})]
    monkeypatch.setattr(manager, "_load_documents", MagicMock(return_value=docs))
    monkeypatch.setattr(manager, "insert_nodes", MagicMock())

    class NodeWithoutMetadata:
        pass

    class FakePipeline:
        def run(self, documents):
            return [NodeWithoutMetadata(), SimpleNamespace(metadata={"file_name": "b.txt"})]

    monkeypatch.setattr(index_module, "AdvancedIngestionPipeline", FakePipeline)

    nodes = manager.load_files([a, b], 128, 16, kb_id="kb-a")

    assert nodes[0].metadata["kb_id"] == "kb-a"
    assert "file_path" not in nodes[0].metadata
    assert nodes[1].metadata["file_path"] == str(b.resolve())
    assert nodes[1].metadata["file_name"] == "b.txt"
    assert nodes[1].metadata["kb_id"] == "kb-a"
    manager.insert_nodes.assert_called_once_with(nodes)



def test_load_files_ignores_non_string_file_path_metadata_and_maps_by_file_name(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("alpha", encoding="utf-8")
    b.write_text("bravo", encoding="utf-8")
    manager = _manager()
    docs = [
        SimpleNamespace(metadata={"file_path": {"bad": "shape"}, "file_name": "b.txt"}),
    ]
    monkeypatch.setattr(manager, "_load_documents", MagicMock(return_value=docs))
    monkeypatch.setattr(manager, "insert_nodes", MagicMock())

    class FakePipeline:
        def run(self, documents):
            assert documents[0].metadata["file_path"] == str(b.resolve())
            assert documents[0].metadata["file_name"] == "b.txt"
            return [SimpleNamespace(metadata={"file_path": {"bad": "shape"}, "file_name": "b.txt"})]

    monkeypatch.setattr(index_module, "AdvancedIngestionPipeline", FakePipeline)

    nodes = manager.load_files([a, b], 128, 16, kb_id="kb-a")

    assert nodes[0].metadata["file_path"] == str(b.resolve())
    assert nodes[0].metadata["file_name"] == "b.txt"
    assert nodes[0].metadata["kb_id"] == "kb-a"
    manager.insert_nodes.assert_called_once_with(nodes)


def test_load_websites_uses_fallback_filters_docs_and_inserts(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    class DocWithContent:
        metadata = {"source": object()}
        extra_info = {"extra": object()}
        text = None

        def get_content(self):
            return "fallback text"

    class BrokenDoc:
        metadata = {}
        extra_info = {}
        text = None

        def get_content(self):
            raise RuntimeError("cannot read")

    class FakeReader:
        def load_data(self, urls):
            calls.append(list(urls))
            if len(calls) == 1:
                return [None, SimpleNamespace(text="   ", metadata={}, extra_info={}), BrokenDoc()]
            return [DocWithContent()]

    fake_web_module = types.ModuleType("server.readers.beautiful_soup_web")
    fake_web_module.BeautifulSoupWebReader = FakeReader
    monkeypatch.setitem(sys.modules, "server.readers.beautiful_soup_web", fake_web_module)
    manager = _manager()
    monkeypatch.setattr(manager, "insert_nodes", MagicMock())

    class FakePipeline:
        disable_cache = False
        cache = "cache"

        def run(self, documents):
            return [SimpleNamespace(metadata={"url": calls[-1][0]})]

    monkeypatch.setattr(index_module, "AdvancedIngestionPipeline", FakePipeline)

    nodes = manager.load_websites(" https://example.com \n", 128, 16, kb_id="kb-a")

    assert calls == [["https://example.com"], ["https://r.jina.ai/https://example.com"]]
    assert nodes[0].metadata["kb_id"] == "kb-a"
    assert nodes[0].metadata["url"] == "https://r.jina.ai/https://example.com"
    manager.insert_nodes.assert_called_once_with(nodes)


def test_load_websites_raises_when_no_extractable_text(monkeypatch: pytest.MonkeyPatch) -> None:
    class EmptyReader:
        def load_data(self, urls):
            return []

    fake_web_module = types.ModuleType("server.readers.beautiful_soup_web")
    fake_web_module.BeautifulSoupWebReader = EmptyReader
    monkeypatch.setitem(sys.modules, "server.readers.beautiful_soup_web", fake_web_module)

    with pytest.raises(ValueError, match="No extractable text"):
        _manager().load_websites(["https://example.com"], 128, 16)


def test_load_websites_returns_empty_when_pipeline_produces_no_nodes(monkeypatch: pytest.MonkeyPatch) -> None:
    class Reader:
        def load_data(self, urls):
            return [SimpleNamespace(text="ok", metadata={}, extra_info={})]

    fake_web_module = types.ModuleType("server.readers.beautiful_soup_web")
    fake_web_module.BeautifulSoupWebReader = Reader
    monkeypatch.setitem(sys.modules, "server.readers.beautiful_soup_web", fake_web_module)

    class EmptyPipeline:
        def run(self, documents):
            return []

    monkeypatch.setattr(index_module, "AdvancedIngestionPipeline", EmptyPipeline)

    assert _manager().load_websites(["https://example.com"], 128, 16) == []


def test_delete_ref_doc_deletes_from_docstore_and_persists() -> None:
    manager = _manager()
    manager.index = FakeIndex("idx")

    manager.delete_ref_doc("doc-1")

    assert manager.index.deleted == ("doc-1", True)
    assert manager.storage_context.persist_calls == 1


def test_delete_ref_doc_prunes_stale_node_ids_not_in_index_struct() -> None:
    """历史脏数据下 ref_doc_info 里的 node_id 可能已不在 index_struct.nodes_dict：
    LlamaIndex 原生 delete_ref_doc 遇到这类陈旧 id 会执行 `del nodes_dict[node_id]`
    直接抛 KeyError；这里验证陈旧 id 会被提前从 docstore 摘掉，不再传给原生删除逻辑。
    """
    docstore = FakeDocStore(FakeRefDocInfo(node_ids=["stale-node", "valid-node"]))
    manager = _manager()
    manager.storage_context = FakeStorage(docstore=docstore)
    manager.index = FakeIndex("idx", nodes_dict={"valid-node": "doc-1"})

    manager.delete_ref_doc("doc-1")

    assert docstore.deleted_documents == ["stale-node"]
    assert manager.index.deleted == ("doc-1", True)
    assert manager.storage_context.persist_calls == 1


def test_delete_ref_doc_skips_pruning_when_no_stale_node_ids() -> None:
    docstore = FakeDocStore(FakeRefDocInfo(node_ids=["valid-node"]))
    manager = _manager()
    manager.storage_context = FakeStorage(docstore=docstore)
    manager.index = FakeIndex("idx", nodes_dict={"valid-node": "doc-1"})

    manager.delete_ref_doc("doc-1")

    assert docstore.deleted_documents == []
    assert manager.index.deleted == ("doc-1", True)
