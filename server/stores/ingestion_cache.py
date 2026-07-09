"""
模块功能：
- 提供摄取流水线（ingestion pipeline）的缓存配置。

执行逻辑：
1. 生产环境使用 RedisKVStore 构建 IngestionCache。
2. 开发环境默认关闭缓存，避免调试阶段出现旧数据干扰。
"""

from __future__ import annotations

from llama_index.core.ingestion import IngestionCache
from config import DEV_MODE

INGESTION_CACHE = None

if not DEV_MODE:
    try:
        from llama_index.storage.kvstore.redis import RedisKVStore as RedisCache
        from config import REDIS_URI

        INGESTION_CACHE = IngestionCache(
            cache=RedisCache(redis_uri=REDIS_URI),
            collection="redis_pipeline_cache",
        )
    except ImportError:
        pass
