"""
模块功能：
- 统一管理知识库索引的创建、加载、写入和删除。

执行逻辑：
1. 维护 IndexManager 的索引状态（index/index_id/storage_context）。
2. 提供目录、文件、网页三类数据源的摄取入口。
3. 负责将文档处理成节点并写入向量索引。

关键依赖：
- llama_index.core 的索引与存储上下文能力
- server.ingestion.AdvancedIngestionPipeline
- server.utils_json.sanitize_for_json
"""

import os
from pathlib import Path
from typing import Any
from llama_index.core import Settings, StorageContext, VectorStoreIndex
from llama_index.core import load_index_from_storage, load_indices_from_storage
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from server.stores.strage_context import STORAGE_CONTEXT
from server.ingestion import AdvancedIngestionPipeline
from config import DEV_MODE
from server.utils_json import sanitize_for_json  # metadata 清洗，避免 Tag 不可序列化


def _resolve_path_metadata(value: Any) -> Path | None:
    """将 metadata 中的路径字段安全解析为绝对路径。

    LlamaIndex 读取器或外部 reader 可能把 file_path 写成 dict/list 等结构化
    metadata；这些值不能直接传给 Path()，否则会导致导入接口 400。
    """
    if not isinstance(value, (str, os.PathLike)):
        return None

    raw = os.fspath(value).strip()
    if not raw:
        return None

    try:
        return Path(raw).resolve()
    except (OSError, TypeError, ValueError):
        return None


class IndexManager:
    """
    功能：
    - 管理索引生命周期及多种数据输入路径。
    """

    def __init__(self, index_name):
        """
        功能：
        - 初始化索引管理器状态。

        输入：
        - index_name(str): 业务侧索引标识。

        输出：
        - 无返回值，初始化对象属性。
        """
        self.index_name: str = index_name
        self.storage_context: StorageContext = STORAGE_CONTEXT
        self.index_id: str = None
        self.index: VectorStoreIndex = None

    def check_index_exists(self):
        """
        功能：
        - 检查存储上下文中是否已有可用索引。

        执行逻辑：
        1. 从 storage_context 加载全部索引。
        2. 若存在索引，则缓存第一个索引及其 index_id。

        输出：
        - bool: 是否存在可加载索引。
        """
        indices = load_indices_from_storage(self.storage_context)
        print(f"Loaded {len(indices)} indices")
        if len(indices) > 0:
            self.index = indices[0]
            self.index_id = indices[0].index_id
            return True
        else:
            return False

    def init_index(self, nodes):
        """
        功能：
        - 基于节点集合创建新索引并持久化（开发模式）。

        输入：
        - nodes(list): 已完成分块与向量化的节点列表。

        输出：
        - VectorStoreIndex: 新建后的索引对象。
        """
        self.index = VectorStoreIndex(nodes, 
                                      storage_context=self.storage_context, 
                                      store_nodes_override=True) # note: no nodes in doc store if using vector database, set store_nodes_override=True to add nodes to doc store
        self.index_id = self.index.index_id
        if DEV_MODE:
            self.storage_context.persist()
        print(f"Created index {self.index.index_id}")
        return self.index

    def load_index(self): # Load index from storage, using index_id if available
        """
        功能：
        - 从存储加载索引，优先使用已缓存 index_id。

        执行逻辑：
        1. 若对象中已有索引实例，直接返回。
        2. 若存在 index_id，按 index_id 精确加载。
        3. 否则走兼容兜底加载并自动选择第一个可用索引。

        输出：
        - VectorStoreIndex: 当前可用索引实例。

        异常：
        - ValueError: 未找到任何索引时抛出。
        """
        # 已加载索引时直接复用，避免重复 I/O 和重复初始化。
        if self.index is not None:
            print(f"Index {self.index.index_id} already loaded")
            return self.index

        # 优先按 index_id 精确加载，避免多索引场景误取。
        if self.index_id is not None:
            self.index = load_index_from_storage(self.storage_context, index_id=self.index_id)
        else:
            # 兼容历史数据：旧版本可能未保存 index_id，只能全局加载。
            try:
                self.index = load_index_from_storage(self.storage_context)
            except ValueError as e:
                indices = load_indices_from_storage(self.storage_context)
                if len(indices) > 0:
                    self.index = indices[0]
                    self.index_id = indices[0].index_id
                else:
                    raise ValueError("No indices found in storage context. Please create an index first.") from e

        if not DEV_MODE:
            self.index._store_nodes_override = True
        print(f"Loaded index {self.index.index_id}")
        return self.index

    def insert_nodes(self, nodes):
        """
        功能：
        - 向已有索引插入节点；若索引不存在则自动初始化。

        输入：
        - nodes(list): 待插入节点。

        输出：
        - VectorStoreIndex: 插入后索引对象。
        """
        if self.index is not None:
            self.index.insert_nodes(nodes=nodes)
            if DEV_MODE:
                self.storage_context.persist()                
            print(f"Inserted {len(nodes)} nodes into index {self.index.index_id}")
        else:
            self.init_index(nodes=nodes)
        return self.index

    def load_dir(self, input_dir, chunk_size, chunk_overlap):
        """
        功能：
        - 从目录读取文档并构建/更新索引。
        """
        Settings.chunk_size = chunk_size
        Settings.chunk_overlap = chunk_overlap
        from server.text_splitter import create_text_splitter
        Settings.text_splitter = create_text_splitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        file_paths = []
        for root, _dirs, files in os.walk(input_dir):
            for f in files:
                file_paths.append(os.path.join(root, f))
        documents = self._load_documents(file_paths) if file_paths else []
        if len(documents) > 0:
            pipeline = AdvancedIngestionPipeline()
            nodes = pipeline.run(documents=documents)
            index = self.insert_nodes(nodes)
            return nodes
        else:
            print("No documents found")
            return []
        
    def _load_documents(self, file_paths):
        """
        功能：
        - 从文件路径列表读取 Document，PDF 自动走 OCR 回退。
        """
        non_pdf, pdf_docs = [], []
        for fp in file_paths:
            ext = os.path.splitext(fp)[1].lower()
            if ext == '.pdf':
                from server.readers.pdf_ocr import PDFOCRReader
                reader = PDFOCRReader()
                docs = reader.load_data(fp)
                if docs:
                    pdf_docs.extend(docs)
                else:
                    print(f'  跳过空 PDF: {fp}')
            else:
                non_pdf.append(fp)
        if non_pdf:
            from_dirs = SimpleDirectoryReader(input_files=non_pdf).load_data()
        else:
            from_dirs = []
        return from_dirs + pdf_docs

    def load_files(
        self,
        file_paths: list[str | Path],
        chunk_size: int,
        chunk_overlap: int,
        kb_id: str | None = None,
    ) -> list[Any]:
        """
        说明：
        - 文件真实路径由服务层确认；这里不再二次拼接全局保存目录，只补充 kb_id。
        """
        Settings.chunk_size = chunk_size
        Settings.chunk_overlap = chunk_overlap
        from server.text_splitter import create_text_splitter
        Settings.text_splitter = create_text_splitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        files = [Path(file_path).resolve() for file_path in file_paths]
        print([str(file_path) for file_path in files])
        documents = self._load_documents([str(file_path) for file_path in files])
        file_by_name = {file_path.name: file_path for file_path in files}
        if len(documents) > 0:
            for document in documents:
                if hasattr(document, "metadata") and isinstance(getattr(document, "metadata"), dict):
                    metadata = sanitize_for_json(document.metadata)
                    raw_path = metadata.get("file_path")
                    resolved_path = _resolve_path_metadata(raw_path)
                    if resolved_path is None:
                        file_name = metadata.get("file_name")
                        resolved_path = file_by_name.get(file_name) if isinstance(file_name, str) else None
                    if resolved_path is None and len(files) == 1:
                        resolved_path = files[0]
                    if resolved_path is not None:
                        metadata["file_path"] = str(resolved_path)
                        metadata["file_name"] = metadata.get("file_name") or resolved_path.name
                    document.metadata = metadata

            pipeline = AdvancedIngestionPipeline()
            nodes = pipeline.run(documents=documents)
            for n in nodes:
                if not hasattr(n, "metadata") or not isinstance(getattr(n, "metadata"), dict):
                    n.metadata = {}
                n.metadata = sanitize_for_json(n.metadata)
                raw_path = n.metadata.get("file_path")
                resolved_path = _resolve_path_metadata(raw_path)
                if resolved_path is None:
                    file_name = n.metadata.get("file_name")
                    resolved_path = file_by_name.get(file_name) if isinstance(file_name, str) else None
                if resolved_path is None and len(files) == 1:
                    resolved_path = files[0]
                if resolved_path is not None:
                    n.metadata["file_path"] = str(resolved_path)
                    n.metadata["file_name"] = Path(resolved_path).name
                if kb_id is not None:
                    n.metadata["kb_id"] = kb_id
            self.insert_nodes(nodes)
            return nodes
        else:         
            print("No documents found")
            return []
        
    def load_websites(self, websites, chunk_size, chunk_overlap, kb_id: str | None = None):
        """
        功能：
        - 从网页 URL 抓取文本并写入索引。

        输入：
        - websites(str|list): URL 文本或 URL 列表。
        - chunk_size(int): 分块大小。
        - chunk_overlap(int): 分块重叠。

        执行逻辑：
        1. 规范化 URL 输入。
        2. 使用 BeautifulSoupWebReader 抓取正文并清洗 metadata。
        3. 首轮抓取失败时使用 r.jina.ai 镜像重试。
        4. 生成节点并插入索引。

        输出：
        - list: 生成并写入的节点列表。

        异常：
        - ValueError: 所有 URL 都无法提取文本时抛出。
        """
        Settings.chunk_size = chunk_size
        Settings.chunk_overlap = chunk_overlap
        from server.text_splitter import create_text_splitter
        Settings.text_splitter = create_text_splitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        from server.readers.beautiful_soup_web import BeautifulSoupWebReader

        # 清理输入（空行/空格）
        if isinstance(websites, str):
            websites = [u.strip() for u in websites.splitlines() if u.strip()]
        else:
            websites = [str(u).strip() for u in (websites or []) if str(u).strip()]

        def fetch_docs(urls):
            """
            功能：
            - 抓取 URL 文档并返回可安全入库的有效文档列表。
            """
            docs = BeautifulSoupWebReader().load_data(urls) or []

            # 防止 metadata 里混入不可序列化对象
            for d in docs:
                if hasattr(d, "metadata") and isinstance(getattr(d, "metadata"), dict):
                    d.metadata = sanitize_for_json(d.metadata)
                if hasattr(d, "extra_info") and isinstance(getattr(d, "extra_info"), dict):
                    d.extra_info = sanitize_for_json(d.extra_info)

            # 过滤空正文，避免后续分块流程收到空内容节点。
            valid = []
            for d in docs:
                if d is None:
                    continue

                text = getattr(d, "text", None)
                if text is None and hasattr(d, "get_content"):
                    try:
                        text = d.get_content()
                    except Exception:
                        text = None

                if text is None or str(text).strip() == "":
                    continue

                valid.append(d)

            return valid

        documents = fetch_docs(websites)

        # 首轮抓取失败时使用代理镜像重试，提升目标站点兼容性。
        if not documents:
            fallback_websites = [f"https://r.jina.ai/{u}" for u in websites]
            documents = fetch_docs(fallback_websites)

        if not documents:
            raise ValueError("No extractable text from the given URL(s).")

        pipeline = AdvancedIngestionPipeline()
        pipeline.disable_cache = True;
        pipeline.cache = None;
        nodes = pipeline.run(documents=documents) or []
        if not nodes:
            return []

        if kb_id is not None:
            for n in nodes:
                n.metadata["kb_id"] = kb_id
        self.insert_nodes(nodes)
        return nodes

    # Delete a document and all related nodes
    def delete_ref_doc(self, ref_doc_id):
        """
        功能：
        - 删除指定文档及其关联节点。

        输入：
        - ref_doc_id(str): 参考文档 ID。

        背景：
        - 历史脏数据可能导致某些 node_id 存在于 docstore 的 ref_doc_info 中，
          但已不在 index_struct.nodes_dict 里；LlamaIndex 原生
          delete_ref_doc 遇到这类 node_id 会执行 `del nodes_dict[node_id]`
          直接抛 KeyError，导致整次删除请求失败。这里提前把陈旧 node_id
          从 docstore 关联信息中摘掉，避免原生删除逻辑再次触碰它们。

        输出：
        - 无返回值。
        """
        docstore = self.storage_context.docstore
        ref_doc_info = docstore.get_ref_doc_info(ref_doc_id)
        nodes_dict = getattr(self.index.index_struct, "nodes_dict", {}) or {}
        if ref_doc_info is not None:
            stale_node_ids = [
                node_id for node_id in ref_doc_info.node_ids if node_id not in nodes_dict
            ]
            for node_id in stale_node_ids:
                docstore.delete_document(node_id, raise_error=False)

        self.index.delete_ref_doc(ref_doc_id=ref_doc_id, delete_from_docstore=True)
        self.storage_context.persist()
        print("Deleted document", ref_doc_id)
