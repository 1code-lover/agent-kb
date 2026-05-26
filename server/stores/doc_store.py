"""
模块功能：
- 根据运行环境创建文档存储实现。

执行逻辑：
1. 生产环境使用 RedisDocumentStore。
2. 开发环境使用 SimpleDocumentStore。
3. 对外暴露统一 DOC_STORE 变量供 StorageContext 组装。
"""

import config

if config.THINKRAG_ENV == "production":
    from llama_index.storage.docstore.redis import RedisDocumentStore

    # 生产环境文档存储走 Redis，支持跨实例共享与持久化。
    DOC_STORE = RedisDocumentStore.from_host_and_port(
        host=config.REDIS_HOST, port=config.REDIS_PORT, namespace="think"
    )
elif config.THINKRAG_ENV == "development":
    from llama_index.core.storage.docstore import SimpleDocumentStore

    # 开发环境优先使用本地轻量存储，降低调试门槛。
    DOC_STORE = SimpleDocumentStore()