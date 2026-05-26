"""
模块功能：
- 创建对话记忆存储（开发环境本地内存，生产环境 Redis）。

执行逻辑：
1. 根据 DEV_MODE 选择 ChatStore 实现。
2. 统一通过 ChatMemoryBuffer 暴露对话记忆接口。
3. 在模块加载时初始化全局 CHAT_MEMORY 供上层直接使用。
"""

from config import DEV_MODE, REDIS_URI, CHAT_STORE_KEY


def create_chat_memory():
    """
    创建会话记忆对象。

    Returns:
        ChatMemoryBuffer: 可读写对话历史的内存对象。
    """

    if DEV_MODE:
        # 开发环境使用 SimpleChatStore，降低外部依赖并便于本地调试。
        from llama_index.core.storage.chat_store import SimpleChatStore
        from llama_index.core.memory import ChatMemoryBuffer

        simple_chat_store = SimpleChatStore()

        simple_chat_memory = ChatMemoryBuffer.from_defaults(
            token_limit=3000,
            chat_store=simple_chat_store,
            chat_store_key=CHAT_STORE_KEY,
        )
        return simple_chat_memory
    else:
        # 生产环境使用 Redis，支持跨进程共享和 TTL 控制。

        from llama_index.core.memory import ChatMemoryBuffer
        from llama_index.storage.chat_store.redis import RedisChatStore

        redis_chat_store = RedisChatStore(redis_url=REDIS_URI, ttl=3600)

        redis_chat_memory = ChatMemoryBuffer.from_defaults(
            token_limit=3000,
            chat_store=redis_chat_store,
            chat_store_key=CHAT_STORE_KEY,
        )
        return redis_chat_memory

CHAT_MEMORY = create_chat_memory()