"""M2 多知识库导入 + 查询过滤 测试"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestM2Schemas:
    """M2 Schema 扩展验证"""

    def test_query_request_kb_ids_default(self):
        from api.schemas import QueryRequest
        req = QueryRequest(question="test")
        assert req.model_dump().get("kb_ids") is None

    def test_query_request_kb_ids_set(self):
        from api.schemas import QueryRequest
        req = QueryRequest(question="test", kb_ids=["kb1", "kb2"])
        assert req.model_dump()["kb_ids"] == ["kb1", "kb2"]

    def test_url_import_request_kb_id_default(self):
        from api.schemas import UrlImportRequest
        req = UrlImportRequest(urls=["https://example.com"])
        assert req.model_dump().get("kb_id") == "default"

    def test_url_import_request_kb_id_set(self):
        from api.schemas import UrlImportRequest
        req = UrlImportRequest(urls=["https://example.com"], kb_id="my-kb")
        assert req.model_dump()["kb_id"] == "my-kb"

    def test_delete_docs_request_kb_id_default(self):
        from api.schemas import DeleteDocsRequest
        req = DeleteDocsRequest()
        assert req.model_dump().get("kb_id") == "default"

    def test_delete_docs_request_kb_id_set(self):
        from api.schemas import DeleteDocsRequest
        req = DeleteDocsRequest(doc_ids=["doc1"], kb_id="my-kb")
        assert req.model_dump()["kb_id"] == "my-kb"


class TestM2KbIdFilter:
    """KBIdFilter 过滤逻辑"""

    def _make_node(self, metadata=None):
        from llama_index.core.schema import NodeWithScore, TextNode
        return NodeWithScore(node=TextNode(text="test", metadata=metadata or {}), score=1.0)

    def test_kb_id_filter_matches(self):
        """kb_id 匹配时保留节点"""
        from server.kb_filter import KBIdFilter
        node = self._make_node({"kb_id": "my-kb"})
        filtr = KBIdFilter(kb_ids=["my-kb"])
        result = filtr.postprocess_nodes([node])
        assert len(result) == 1

    def test_kb_id_filter_no_match(self):
        """kb_id 不匹配时过滤掉"""
        from server.kb_filter import KBIdFilter
        node = self._make_node({"kb_id": "other-kb"})
        filtr = KBIdFilter(kb_ids=["my-kb"])
        result = filtr.postprocess_nodes([node])
        assert len(result) == 0

    def test_kb_id_filter_no_kb_id_in_metadata_for_non_default(self):
        """节点无 kb_id 元数据时只归 default，非 default 查询应过滤掉。"""
        from server.kb_filter import KBIdFilter
        node = self._make_node({"file_name": "test.txt"})
        filtr = KBIdFilter(kb_ids=["my-kb"])
        result = filtr.postprocess_nodes([node])
        assert len(result) == 0

    def test_kb_id_filter_no_kb_id_in_metadata_for_default(self):
        """节点无 kb_id 元数据时允许 default 查询保留。"""
        from server.kb_filter import KBIdFilter
        node = self._make_node({"file_name": "test.txt"})
        filtr = KBIdFilter(kb_ids=["default"])
        result = filtr.postprocess_nodes([node])
        assert len(result) == 1

    def test_kb_id_filter_pass_through_empty(self):
        """kb_ids 为空或 None 时不过滤"""
        from server.kb_filter import KBIdFilter
        node = self._make_node({"kb_id": "some-kb"})
        filtr = KBIdFilter(kb_ids=[])
        result = filtr.postprocess_nodes([node])
        assert len(result) == 1

    def test_kb_id_filter_pass_through_none(self):
        """kb_ids 为 None 时不过滤"""
        from server.kb_filter import KBIdFilter
        node = self._make_node({"kb_id": "some-kb"})
        filtr = KBIdFilter(kb_ids=None)
        result = filtr.postprocess_nodes([node])
        assert len(result) == 1

    def test_kb_id_filter_multiple_kb_ids(self):
        """多个 kb_id 时匹配任一"""
        from server.kb_filter import KBIdFilter
        node1 = self._make_node({"kb_id": "kb1"})
        node2 = self._make_node({"kb_id": "kb2"})
        filtr = KBIdFilter(kb_ids=["kb1", "kb3"])
        result = filtr.postprocess_nodes([node1, node2])
        assert len(result) == 1
        assert result[0].node.metadata["kb_id"] == "kb1"

    def test_filter_with_node_with_score(self):
        """NodeWithScore 结构也能正确过滤（同 _make_node）"""
        from server.kb_filter import KBIdFilter
        node1 = self._make_node({"kb_id": "kb1"})
        node2 = self._make_node({"kb_id": "kb2"})
        filtr = KBIdFilter(kb_ids=["kb1"])
        result = filtr.postprocess_nodes([node1, node2])
        assert len(result) == 1
        assert result[0].node.metadata["kb_id"] == "kb1"

    def test_filter_empty_nodes(self):
        """空列表返回空列表"""
        from server.kb_filter import KBIdFilter
        filtr = KBIdFilter(kb_ids=["my-kb"])
        result = filtr.postprocess_nodes([])
        assert result == []


class TestM2KbServiceImport:
    """KB 服务层导入支持 kb_id"""

    def test_import_files_with_kb_id_routes_to_load_files(self):
        """import_files 调用 IndexManager.load_files 时传入 kb_id"""
        from api.services.kb_service import import_files
        import tempfile
        tmp_save = tempfile.mkdtemp()

        mock_manager = MagicMock()
        mock_manager.load_files.return_value = [MagicMock()]

        with patch("api.services.kb_service.runtime_state.get_index_manager", return_value=mock_manager):
            with patch("api.services.kb_service.runtime_state.ensure_models_ready"):
                with patch("api.services.kb_service._ensure_kb_active", return_value={"kb_id": "my-kb", "status": "active"}):
                    with patch("api.services.kb_service._get_registry") as mock_registry_factory:
                        mock_registry_factory.return_value.add_doc_count.return_value = None
                        with patch("api.services.kb_service.get_kb_data_dir", return_value=__import__("pathlib").Path(tmp_save)):
                            mock_file = MagicMock()
                            mock_file.file.read.return_value = b"content"
                            mock_file.filename = "test.txt"
                            mock_file.content_type = "text/plain"
                            result = import_files([mock_file], 2048, 512, kb_id="my-kb")
                            assert result["kb_id"] == "my-kb"
                            call_kwargs = mock_manager.load_files.call_args[1]
                            assert call_kwargs["kb_id"] == "my-kb"

    def test_import_urls_with_kb_id(self):
        """import_urls 调用 IndexManager.load_websites 时传入 kb_id"""
        from api.services.kb_service import import_urls

        mock_manager = MagicMock()
        mock_manager.load_websites.return_value = [MagicMock()]

        with patch("api.services.kb_service.runtime_state.get_index_manager", return_value=mock_manager):
            with patch("api.services.kb_service.runtime_state.ensure_models_ready"):
                with patch("api.services.kb_service._ensure_kb_active", return_value={"kb_id": "my-kb", "status": "active"}):
                    with patch("api.services.kb_service._get_registry") as mock_registry_factory:
                        mock_registry_factory.return_value.add_doc_count.return_value = None
                        result = import_urls(["https://example.com"], 2048, 512, kb_id="my-kb")
                        assert result["kb_id"] == "my-kb"
                        call_kwargs = mock_manager.load_websites.call_args[1]
                        assert call_kwargs["kb_id"] == "my-kb"

    def test_list_docs_filters_by_kb_id(self):
        """list_docs 传入 kb_id 时只返回该知识库的文档"""
        from api.services.kb_service import list_docs

        mock_manager = MagicMock()
        mock_docstore = MagicMock()

        class FakeRefDocInfo:
            def __init__(self, metadata):
                self.metadata = metadata

        doc_info = {
            "doc1": FakeRefDocInfo(metadata={"file_path": "/a/b.txt", "file_name": "b.txt", "kb_id": "my-kb"}),
            "doc2": FakeRefDocInfo(metadata={"file_path": "/a/c.txt", "file_name": "c.txt", "kb_id": "other-kb"}),
        }
        mock_docstore.get_all_ref_doc_info.return_value = doc_info
        mock_docstore.docs = doc_info
        mock_manager.storage_context.docstore = mock_docstore

        with patch("api.services.kb_service.runtime_state.get_index_manager", return_value=mock_manager):
            docs = list_docs(kb_id="my-kb")
            assert len(docs) == 1
            assert docs[0]["kb_id"] == "my-kb"
            assert docs[0]["name"] == "b.txt"

    def test_list_docs_without_kb_id_returns_all(self):
        """list_docs 不传 kb_id 时返回全部文档"""
        from api.services.kb_service import list_docs

        mock_manager = MagicMock()
        mock_docstore = MagicMock()

        class FakeRefDocInfo:
            def __init__(self, metadata):
                self.metadata = metadata

        doc_info = {
            "doc1": FakeRefDocInfo(metadata={"file_name": "a.txt"}),
            "doc2": FakeRefDocInfo(metadata={"file_name": "b.txt", "kb_id": "my-kb"}),
        }
        mock_docstore.get_all_ref_doc_info.return_value = doc_info
        mock_docstore.docs = doc_info
        mock_manager.storage_context.docstore = mock_docstore

        with patch("api.services.kb_service.runtime_state.get_index_manager", return_value=mock_manager):
            docs = list_docs()
            assert len(docs) == 2

    def test_list_docs_filter_excludes_unlabeled_docs_for_non_default(self):
        """旧无 kb_id 节点只归 default KB，非 default 不应混入。"""
        from api.services.kb_service import list_docs

        mock_manager = MagicMock()
        mock_docstore = MagicMock()

        class FakeRefDocInfo:
            def __init__(self, metadata):
                self.metadata = metadata

        doc_info = {
            "doc1": FakeRefDocInfo(metadata={"file_name": "legacy.txt"}),
            "doc2": FakeRefDocInfo(metadata={"file_name": "new.txt", "kb_id": "my-kb"}),
        }
        mock_docstore.get_all_ref_doc_info.return_value = doc_info
        mock_docstore.docs = doc_info
        mock_manager.storage_context.docstore = mock_docstore

        with patch("api.services.kb_service.runtime_state.get_index_manager", return_value=mock_manager):
            docs = list_docs(kb_id="my-kb")
            assert len(docs) == 1
            assert docs[0]["id"] == "doc2"

    def test_delete_docs_with_kb_id(self):
        """delete_docs 支持在指定 kb_id 内删除"""
        from api.services.kb_service import delete_docs
        from api.schemas import DeleteDocsRequest

        mock_manager = MagicMock()
        mock_docstore = MagicMock()

        class FakeRefDocInfo:
            def __init__(self, metadata):
                self.metadata = metadata

        doc_info = {
            "doc1": FakeRefDocInfo(metadata={"file_name": "a.txt", "kb_id": "my-kb"}),
            "doc2": FakeRefDocInfo(metadata={"file_name": "b.txt", "kb_id": "other-kb"}),
        }
        mock_docstore.get_all_ref_doc_info.return_value = doc_info
        mock_docstore.docs = doc_info
        mock_manager.storage_context.docstore = mock_docstore

        with patch("api.services.kb_service.runtime_state.get_index_manager", return_value=mock_manager):
            with patch("api.services.kb_service.runtime_state.ensure_index_loaded"):
                req = DeleteDocsRequest(doc_ids=["doc1"], kb_id="my-kb")
                result = delete_docs(req)
                mock_manager.delete_ref_doc.assert_called_once_with("doc1")

    def test_delete_docs_with_kb_id_skips_other_kb(self):
        """delete_docs 不会删除其他知识库的文档"""
        from api.services.kb_service import delete_docs
        from api.schemas import DeleteDocsRequest

        mock_manager = MagicMock()
        mock_docstore = MagicMock()

        class FakeRefDocInfo:
            def __init__(self, metadata):
                self.metadata = metadata

        doc_info = {
            "doc1": FakeRefDocInfo(metadata={"file_name": "a.txt", "kb_id": "other-kb"}),
        }
        mock_docstore.get_all_ref_doc_info.return_value = doc_info
        mock_docstore.docs = doc_info
        mock_manager.storage_context.docstore = mock_docstore

        with patch("api.services.kb_service.runtime_state.get_index_manager", return_value=mock_manager):
            with patch("api.services.kb_service.runtime_state.ensure_index_loaded"):
                req = DeleteDocsRequest(doc_ids=["doc1"], kb_id="my-kb")
                result = delete_docs(req)
                mock_manager.delete_ref_doc.assert_not_called()


class TestM2BootstrapDefaultKb:
    """启动时自动创建 default 知识库"""

    def test_bootstrap_creates_default_kb(self):
        """bootstrap_runtime 调用后 default KB 存在"""
        from api.runtime import bootstrap_runtime

        with patch("server.stores.config_store.CONFIG_STORE.get", return_value={"temp": "val"}):
            with patch("server.kb_registry.KBRegistry") as MockRegistry:
                mock_instance = MagicMock()
                MockRegistry.return_value = mock_instance
                mock_instance.exists.return_value = False
                bootstrap_runtime()
                mock_instance.create_kb.assert_called_once_with("default", "Default Knowledge Base")

    def test_bootstrap_skips_if_default_exists(self):
        """default 知识库已存在时跳过创建"""
        from api.runtime import bootstrap_runtime

        with patch("server.stores.config_store.CONFIG_STORE.get", return_value={"temp": "val"}):
            with patch("server.kb_registry.KBRegistry") as MockRegistry:
                mock_instance = MagicMock()
                MockRegistry.return_value = mock_instance
                mock_instance.exists.return_value = True
                bootstrap_runtime()
                mock_instance.create_kb.assert_not_called()


class TestM2ChatServiceKbIds:
    """chat_service 查询透传 kb_ids"""

    def test_query_passes_kb_ids_to_build_query_engine(self):
        """query 将 request.kb_ids 传给 build_query_engine"""
        from api.services.chat_service import query
        mock_engine = MagicMock()
        mock_answer = MagicMock()
        mock_answer.response = "answer"
        mock_answer.source_nodes = []
        mock_engine.query.return_value = mock_answer

        with patch("api.services.chat_service.runtime_state.ensure_index_loaded", return_value=True):
            with patch("api.services.chat_service.runtime_state.build_query_engine", return_value=mock_engine) as mock_build:
                from api.schemas import QueryRequest
                req = QueryRequest(question="test", kb_ids=["kb1", "kb2"])
                query(req, record_history=False)
                mock_build.assert_called_once_with(kb_ids=["kb1", "kb2"])

    def test_query_without_kb_ids(self):
        """不传 kb_ids 时 build_query_engine 不传参"""
        from api.services.chat_service import query
        mock_engine = MagicMock()
        mock_answer = MagicMock()
        mock_answer.response = "answer"
        mock_answer.source_nodes = []
        mock_engine.query.return_value = mock_answer

        with patch("api.services.chat_service.runtime_state.ensure_index_loaded", return_value=True):
            with patch("api.services.chat_service.runtime_state.build_query_engine", return_value=mock_engine) as mock_build:
                from api.schemas import QueryRequest
                req = QueryRequest(question="test")
                query(req, record_history=False)
                mock_build.assert_called_once_with(kb_ids=None)


class TestM2AgentEvidenceKbId:
    """Agent evidence 保留真实 kb_id"""

    def test_normalize_evidence_preserves_source_kb_id(self):
        from api.services.agent_tools import normalize_evidence

        evidence = normalize_evidence(
            [
                {
                    "file": "a.txt",
                    "page": "1",
                    "score": 0.9,
                    "text": "abc",
                    "kb_id": "kb_product",
                }
            ],
            receipt_id="receipt-1",
        )

        assert len(evidence) == 1
        assert evidence[0]["kb_id"] == "kb_product"
        assert evidence[0]["receipt_id"] == "receipt-1"
