"""
模块功能：
- 提供本地持久化配置 KV 存储能力。

执行逻辑：
1. 基于 SimpleKVStore 扩展 LocalKVStore。
2. 在写入和删除后自动持久化到本地文件。
3. 启动时自动从持久化文件恢复 CONFIG_STORE。
"""

import json
import os
from typing import Optional, Dict
from llama_index.core.storage.kvstore import SimpleKVStore
from config import STORAGE_DIR, CONFIG_STORE_FILE

DATA_TYPE = Dict[str, Dict[str, dict]]

PERSISIT_PATH = os.path.join(STORAGE_DIR, CONFIG_STORE_FILE)


class LocalKVStore(SimpleKVStore):
    """
    本地持久化 KV 存储封装。

    主要职责：
    - 复用 SimpleKVStore 的内存读写能力。
    - 在变更操作后自动落盘，避免配置丢失。
    """

    def __init__(
        self,
        data: Optional[DATA_TYPE] = None,
    ) -> None:
        """
        初始化本地 KV 存储实例。

        Args:
            data: 初始 KV 数据。
        """
        super().__init__(data)

    def _pretty_write(self) -> None:
        """将持久化文件重新以缩进格式写回，便于人工查看。"""
        if not os.path.exists(self.persist_path):
            return
        with open(self.persist_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        with open(self.persist_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def put(self, key: str, val: dict) -> None:
        """
        写入键值对并立即持久化。

        Args:
            key: 配置键。
            val: 配置值字典。
        """
        super().put(key=key, val=val)
        super().persist(persist_path=self.persist_path)
        self._pretty_write()

    def delete(self, key: str) -> bool:
        """
        删除指定键并持久化变更。

        Args:
            key: 待删除键。

        Returns:
            bool: 删除成功返回 True；键不存在返回 False。
        """
        try:
            super().delete(key)
            super().persist(persist_path=self.persist_path)
            self._pretty_write()
            return True
        except KeyError:
            return False

    @classmethod
    def from_persist_path(
        cls, persist_path: str = PERSISIT_PATH
    ) -> "LocalKVStore":
        """
        从持久化文件恢复本地 KV 存储。

        Args:
            persist_path: 持久化文件路径。

        Returns:
            LocalKVStore: 恢复后的存储实例；文件不存在时返回空实例。
        """
        cls.persist_path = persist_path
        if os.path.exists(persist_path):
            return super().from_persist_path(persist_path=persist_path)
        else:
            return cls({})

CONFIG_STORE = LocalKVStore.from_persist_path()
