"""
模块功能：
- 提供摄取流水线（ingestion pipeline）的缓存配置。

执行逻辑：
1. 生产环境使用 RedisKVStore 构建 IngestionCache。
2. 开发环境默认关闭缓存，避免调试阶段出现旧数据干扰。
"""

from llama_index.core.ingestion import IngestionCache
from llama_index.storage.kvstore.redis import RedisKVStore as RedisCache
from config import REDIS_URI, DEV_MODE

redis_cache = IngestionCache(
    cache=RedisCache(redis_uri=REDIS_URI),
    collection="redis_pipeline_cache",
)

# 开发模式禁用缓存，确保每次变更都走完整管线，便于问题定位。
INGESTION_CACHE = redis_cache if not DEV_MODE else None