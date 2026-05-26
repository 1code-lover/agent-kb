"""
模块功能：
- 根据运行环境创建索引存储实现。

执行逻辑：
1. 生产环境使用 RedisIndexStore。
2. 开发环境使用 SimpleIndexStore。
3. 对外暴露统一 INDEX_STORE 变量供 StorageContext 组装。
"""

import config

if config.THINKRAG_ENV == "production":
    from llama_index.storage.index_store.redis import RedisIndexStore

    # 生产环境索引存储走 Redis，便于服务重启后恢复索引元数据。
    INDEX_STORE = RedisIndexStore.from_host_and_port(
        host=config.REDIS_HOST, port=config.REDIS_PORT, namespace="think"
    )
elif config.THINKRAG_ENV == "development":
    from llama_index.core.storage.index_store import SimpleIndexStore

    # 开发环境使用本地索引存储，避免外部依赖。
    INDEX_STORE = SimpleIndexStore()