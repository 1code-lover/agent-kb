"""聊天 follow-up 判定与上下文注入启发式。"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable

QuestionPredicate = Callable[[str], bool]
TokenizeText = Callable[[str], set[str]]

_FOLLOW_UP_EN_PATTERNS = (
    re.compile(r"\bwhat about\b"),
    re.compile(r"\bhow about\b"),
    re.compile(r"\bthis one\b"),
    re.compile(r"\bthat one\b"),
    re.compile(r"\b(?:it|they|them|their|those|these|he|she|his|her)\b"),
)
_FOLLOW_UP_CJK_MARKERS = (
    "继续",
    "刚才",
    "上面",
    "前面",
    "上一条",
    "上一轮",
    "这个",
    "那个",
    "它",
    "它们",
    "该",
    "其",
)


@dataclass(frozen=True)
class FollowUpQuestionHeuristicsHooks:
    """承载 follow-up 判定所需的轻量分类器，避免 chat_service 内继续堆条件。"""

    tokenize_text: TokenizeText
    question_requests_identifier_like_field: QuestionPredicate
    question_requests_exact_source_phrase: QuestionPredicate


def question_looks_follow_up(question: str, *, hooks: FollowUpQuestionHeuristicsHooks) -> bool:
    """判断问题是否更像依赖上文的 follow-up，而不是独立可答的精确字段提问。"""
    raw = str(question or "").strip()
    if not raw:
        return False

    lowered = raw.lower()
    if any(pattern.search(lowered) for pattern in _FOLLOW_UP_EN_PATTERNS):
        return True
    if any(marker in raw for marker in _FOLLOW_UP_CJK_MARKERS):
        return True

    content_tokens = hooks.tokenize_text(raw)
    if len(content_tokens) > 2 or len(raw) > 48:
        return False

    if hooks.question_requests_identifier_like_field(raw):
        return False
    if hooks.question_requests_exact_source_phrase(raw):
        return False

    return True
