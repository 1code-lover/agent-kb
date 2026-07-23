"""???????????"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from api.services.kb_service import _ensure_kb_active
from server.kb_errors import KBValidationError
from server.utils.file import validate_kb_id

_LOGICAL_FILTER_ONLY = "logical_filter_only"


@dataclass(frozen=True, slots=True)
class ChatQueryScope:
    """Chat ????????????"""

    requested_scope_type: str
    requested_kb_ids: list[str]
    effective_scope_type: str
    effective_kb_ids: list[str]
    is_default_deny_applied: bool
    isolation_level: str = _LOGICAL_FILTER_ONLY

    def to_dict(self) -> dict[str, Any]:
        """???????? API ????????"""
        return {
            "requested_scope_type": self.requested_scope_type,
            "requested_kb_ids": list(self.requested_kb_ids),
            "effective_scope_type": self.effective_scope_type,
            "effective_kb_ids": list(self.effective_kb_ids),
            "is_default_deny_applied": self.is_default_deny_applied,
            "isolation_level": self.isolation_level,
        }


def _normalize_requested_kb_ids(kb_ids: Sequence[str]) -> list[str]:
    """????????? kb_ids????????"""
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
    """? legacy `kb_ids` ????? P0 ???????????"""
    if kb_ids is None:
        raise KBValidationError("???????????????? kb_ids")

    normalized_kb_ids = _normalize_requested_kb_ids(kb_ids)
    if not normalized_kb_ids:
        raise KBValidationError("????????????????? kb_ids")

    if len(normalized_kb_ids) > 1:
        raise KBValidationError("P0 ?????????????????????")

    kb_id = normalized_kb_ids[0]
    _ensure_kb_active(kb_id)
    return ChatQueryScope(
        requested_scope_type="single_kb",
        requested_kb_ids=[kb_id],
        effective_scope_type="single_kb",
        effective_kb_ids=[kb_id],
        is_default_deny_applied=False,
    )
