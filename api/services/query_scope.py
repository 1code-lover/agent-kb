"""共享查询范围解析逻辑。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from api.services.kb_service import _ensure_kb_active
from server.kb_errors import KBValidationError
from server.utils.file import validate_kb_id

_PHYSICAL_ISOLATED = "physical_isolated"


@dataclass(frozen=True, slots=True)
class ChatQueryScope:
    """Chat 主链路可执行的单库范围。"""

    requested_scope_type: str
    requested_kb_ids: list[str]
    effective_scope_type: str
    effective_kb_ids: list[str]
    is_default_deny_applied: bool
    isolation_level: str = _PHYSICAL_ISOLATED

    def to_dict(self) -> dict[str, Any]:
        """返回可直接回传给 API 的范围回显字段。"""
        return {
            "requested_scope_type": self.requested_scope_type,
            "requested_kb_ids": list(self.requested_kb_ids),
            "effective_scope_type": self.effective_scope_type,
            "effective_kb_ids": list(self.effective_kb_ids),
            "is_default_deny_applied": self.is_default_deny_applied,
            "isolation_level": self.isolation_level,
        }


def _normalize_requested_kb_ids(kb_ids: Sequence[str]) -> list[str]:
    """校验并去重请求中的 kb_ids，保留原始顺序。"""
    normalized: list[str] = []
    seen: set[str] = set()
    for kb_id in kb_ids:
        safe_kb_id = validate_kb_id(kb_id)
        if safe_kb_id in seen:
            continue
        normalized.append(safe_kb_id)
        seen.add(safe_kb_id)
    return normalized


def resolve_chat_query_scope(kb_ids: Sequence[str] | None) -> ChatQueryScope:
    """将 legacy `kb_ids` 输入解析为 P0 主链路允许的单库范围。"""
    if kb_ids is None:
        raise KBValidationError("未声明知识库范围，请显式声明单库 kb_ids")

    normalized_kb_ids = _normalize_requested_kb_ids(kb_ids)
    if not normalized_kb_ids:
        raise KBValidationError("知识库范围不能为空，请显式声明单库 kb_ids")

    if len(normalized_kb_ids) > 1:
        raise KBValidationError("P0 主线暂不支持多知识库查询，请拆分为单库请求")

    kb_id = normalized_kb_ids[0]
    _ensure_kb_active(kb_id)
    return ChatQueryScope(
        requested_scope_type="single_kb",
        requested_kb_ids=[kb_id],
        effective_scope_type="single_kb",
        effective_kb_ids=[kb_id],
        is_default_deny_applied=False,
    )
