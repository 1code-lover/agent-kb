"""
模块功能：
- 根据运行环境创建统一 StorageContext。

执行逻辑：
1. 开发环境优先从本地持久化目录恢复。
2. 若本地持久化不存在，则创建新的默认上下文。
3. 生产环境使用 doc/index/vector 三类存储拼装上下文。
"""

from llama_index.core import StorageContext
from config import THINKRAG_ENV
from server.stores.doc_store import DOC_STORE
from server.stores.vector_store import VECTOR_STORE
from server.stores.index_store import INDEX_STORE


def create_storage_context():
    """
    创建并返回当前环境对应的 StorageContext。

    Returns:
        StorageContext: 可被索引管理模块复用的存储上下文实例。
    """
    if THINKRAG_ENV == "development":
        # 开发环境优先复用本地持久化，保证重启后索引状态可延续。
        import os
        from config import STORAGE_DIR
        persist_dir = "./" + STORAGE_DIR
        if os.path.exists(STORAGE_DIR + "/docstore.json"):
            dev_storage_context = StorageContext.from_defaults(
                persist_dir=persist_dir
            )
            print(f"Loaded storage context from {persist_dir}")
            return dev_storage_context
        else:
            # 首次启动无持久化文件时创建全新上下文，后续由上层负责持久化。
            dev_storage_context = StorageContext.from_defaults()
            print(f"Created new storage context")
            return dev_storage_context
    elif THINKRAG_ENV == "production":
        pro_storage_context = StorageContext.from_defaults(
            docstore=DOC_STORE,
            index_store=INDEX_STORE,
            vector_store=VECTOR_STORE,
        )
        return pro_storage_context

STORAGE_CONTEXT = create_storage_context()