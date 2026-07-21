"""KBId 检索后置过滤器，根据 kb_id metadata 过滤检索节点。"""

from __future__ import annotations

from typing import Any

from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle


class KBIdFilter(BaseNodePostprocessor):
    """知识库 ID 后置过滤器

    根据节点 metadata 中的 "kb_id" 字段进行过滤。
    未标注 kb_id 的节点只归 default；非 default 查询不得混入旧数据。
    kb_ids 为空或 None 时不过滤。
    """

    def __init__(self, kb_ids: list[str] | None = None):
        super().__init__()
        self._kb_ids: set[str] | None = set(kb_ids) if kb_ids else None

    @classmethod
    def class_name(cls) -> str:
        return "KBIdFilter"

    def _postprocess_nodes(
        self,
        nodes: list[NodeWithScore],
        query_bundle: QueryBundle | None = None,
    ) -> list[NodeWithScore]:
        if not self._kb_ids:
            return nodes
        # 无 kb_id 的旧节点只归 default；非 default 查询不能混入旧节点或 default 节点。
        result: list[NodeWithScore] = []
        for node in nodes:
            kb_id = node.node.metadata.get("kb_id")
            if kb_id is None:
                if "default" in self._kb_ids:
                    result.append(node)
            elif kb_id in self._kb_ids:
                result.append(node)
        return result
