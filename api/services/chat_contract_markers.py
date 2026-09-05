"""聊天拒答 / negative-contract 共享 marker 与标签识别。"""

from __future__ import annotations

import re

REFUSAL_MARKERS = (
    "no confirmable information is available",
    "no confirmable information",
    "no confirmable evidence",
    "does not mention",
    "cannot be determined",
    "insufficient information",
    "not specified",
    "未找到可确认的信息",
    "没有可确认的信息",
    "没有可确认的证据",
    "缺少可确认的证据",
    "无法根据当前知识库确认",
    "当前知识库中没有",
)

SCOPE_MARKERS = (
    "active pdf knowledge base",
    "active knowledge base",
    "current knowledge base",
    "当前知识库",
)

SCOPE_PATTERNS = (
    re.compile(r"\b(?:current|active)\s+kb\b", re.IGNORECASE),
    re.compile(r"当前\s*kb", re.IGNORECASE),
)

MEMORY_MARKERS = (
    "must not fabricate",
    "no fabricated memory",
    "outside memory",
    "不得编造",
    "不能编造",
    "不要编造",
    "外部记忆",
)

SCOPE_CONTEXT_MARKERS = (
    "stay inside",
    "inside the",
    "authorization boundary",
    "scope boundary",
    "范围内",
    "边界内",
    "留在",
)

REFUSAL_SOURCE_MARKERS = REFUSAL_MARKERS + (
    "not listed",
    "not provided",
    "left blank",
    "missing",
    "blank",
    "empty",
    "未写",
    "未提供",
    "未列出",
    "未注明",
    "未提及",
    "缺失",
    "空白",
) + MEMORY_MARKERS + SCOPE_MARKERS

NEGATIVE_CONTRACT_QUESTION_HINTS = (
    "outside memory",
    "fabricated memory",
    "fabricate",
    "no confirmable evidence",
    "no confirmable information",
    "evidence is sparse",
    "ocr evidence is sparse",
    "可确认的信息",
    "可确认的证据",
    "外部记忆",
    "不得编造",
    "不能编造",
    "不要编造",
)

NEGATIVE_CONTRACT_QUESTION_PATTERNS = (
    re.compile(r"\bconfirmable (?:evidence|information)\s+(?:is\s+)?(?:missing|absent)\b", re.IGNORECASE),
    re.compile(r"\b(?:missing|absent)\s+confirmable (?:evidence|information)\b", re.IGNORECASE),
    re.compile(r"(?:没有|缺少)(?:可确认的?|可确认之)?(?:信息|证据)"),
    re.compile(r"无法根据当前知识库确认"),
)

NEGATIVE_CONTRACT_SEGMENT_ORDER = ("refusal", "scope", "memory")


def extract_negative_contract_labels(text: str) -> set[str]:
    """识别一段文本承担了哪类 negative-contract 角色。"""
    lowered = str(text or "").strip().lower()
    if not lowered:
        return set()

    labels: set[str] = set()
    if any(marker in lowered for marker in REFUSAL_MARKERS):
        labels.add("refusal")
    if any(marker in lowered for marker in MEMORY_MARKERS):
        labels.add("memory")
    if any(marker in lowered for marker in SCOPE_MARKERS) or any(pattern.search(lowered) for pattern in SCOPE_PATTERNS):
        labels.add("scope")
    elif ("knowledge base" in lowered or "知识库" in lowered) and any(marker in lowered for marker in SCOPE_CONTEXT_MARKERS):
        labels.add("scope")
    return labels



def question_requests_negative_contract(question: str) -> bool:
    """识别 refusal / active-scope / no-fabrication 这类负向契约问题。"""
    raw = str(question or "")
    lowered = raw.lower()
    return any(marker in lowered for marker in NEGATIVE_CONTRACT_QUESTION_HINTS) or any(
        pattern.search(raw) for pattern in NEGATIVE_CONTRACT_QUESTION_PATTERNS
    )
