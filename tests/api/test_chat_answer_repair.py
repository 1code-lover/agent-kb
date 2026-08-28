"""chat_answer_repair 的独立契约测试。"""

from __future__ import annotations

import re

from api.services import chat_answer_repair, chat_question_intents


_ASCII_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_CJK_TOKEN_RE = re.compile(r"[一-鿿]+")
_SENTENCE_SPLIT_RE = re.compile(r"[。！？!?;\n]+|(?<=\.)\s+")
_CLAUSE_SPLIT_RE = re.compile(r"[，,]+|(?<!\d)[：:]+(?!\d)")
_QUESTION_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "does",
    "for",
    "from",
    "have",
    "how",
    "into",
    "not",
    "that",
    "the",
    "their",
    "there",
    "these",
    "this",
    "what",
    "which",
    "with",
}


def _iter_source_support_texts(source: dict[str, str]) -> list[str]:
    texts: list[str] = []
    for field in ("text", "excerpt"):
        value = str(source.get(field) or "").strip()
        if value:
            texts.append(value)
    return texts


def _tokenize_text(text: str) -> set[str]:
    tokens: set[str] = set()
    lowered = str(text or "").lower()
    for raw in _ASCII_TOKEN_RE.findall(lowered):
        token = raw.strip()
        if token:
            tokens.add(token)
    for block in _CJK_TOKEN_RE.findall(str(text or "")):
        token = block.strip()
        if len(token) < 2:
            continue
        tokens.add(token)
        for size in (2, 3):
            if len(token) >= size:
                for index in range(0, len(token) - size + 1):
                    tokens.add(token[index : index + size])
    return tokens


def _question_requests_entity(question: str) -> bool:
    lowered = str(question or "").lower()
    return any(marker in lowered for marker in ("what", "which", "who", "what remains")) or "什么" in question


def _answer_is_brief_entity(answer_text: str) -> bool:
    cleaned = str(answer_text or "").strip().strip("\"'“”‘’()[]{}<> ").strip("。！？!?;?,:?")
    if not cleaned:
        return False
    if any(mark in cleaned for mark in ("。", ".", "!", "?", "；", ";", "\n")):
        return False
    ascii_words = _ASCII_TOKEN_RE.findall(cleaned.lower())
    cjk_blocks = _CJK_TOKEN_RE.findall(cleaned)
    return len(ascii_words) <= 4 and sum(len(block) for block in cjk_blocks) <= 10


def _answer_is_refusal_like(answer_text: str) -> bool:
    lowered = str(answer_text or "").lower()
    return "no confirmable information" in lowered or "无法根据当前知识库确认" in answer_text


def _normalize_expanded_answer(candidate: str) -> str:
    cleaned = str(candidate or "").strip().strip("\"'“”‘’()[]{}<> ")
    cleaned = cleaned.lstrip("：:,，;； ")
    if not cleaned:
        return ""
    if cleaned[-1] not in "。！？.!?":
        cleaned += "。" if _CJK_TOKEN_RE.search(cleaned) else "."
    return cleaned


def _build_hooks() -> chat_answer_repair.SourceAnswerRepairHooks:
    return chat_answer_repair.SourceAnswerRepairHooks(
        tokenize_text=_tokenize_text,
        iter_source_support_texts=_iter_source_support_texts,
        question_requests_preview_expansion=chat_question_intents.question_requests_preview_expansion,
        question_requests_entity=_question_requests_entity,
        question_requests_exact_source_phrase=chat_question_intents.question_requests_exact_source_phrase,
        answer_is_brief_entity=_answer_is_brief_entity,
        answer_is_refusal_like=_answer_is_refusal_like,
        normalize_expanded_answer=_normalize_expanded_answer,
        sentence_split_re=_SENTENCE_SPLIT_RE,
        clause_split_re=_CLAUSE_SPLIT_RE,
        answer_edge_strip_chars="\"'“”‘’()[]{}<> ",
        answer_trailing_punct_chars="。！？!?;?,:?",
        cjk_token_re=_CJK_TOKEN_RE,
        ascii_token_re=_ASCII_TOKEN_RE,
        question_stopwords=_QUESTION_STOPWORDS,
    )


def test_maybe_expand_brief_answer_from_sources_prefers_grounded_clause():
    hooks = _build_hooks()
    sources = [
        {
            "file": "diag-import-utf8.md",
            "text": "文档明确说明：知识库仍然是授权边界，文件夹只承担组织作用，不承担权限隔离。",
        }
    ]

    answer = chat_answer_repair.maybe_expand_brief_answer_from_sources(
        "诊断文档里，什么对象仍然是授权边界？",
        "知识库",
        sources,
        hooks=hooks,
    )

    assert answer == "知识库仍然是授权边界。"


def test_maybe_expand_brief_answer_from_sources_keeps_answer_without_grounded_clause():
    hooks = _build_hooks()
    sources = [{"file": "random.md", "text": "知识库可以被导入系统，随后完成索引。"}]

    answer = chat_answer_repair.maybe_expand_brief_answer_from_sources(
        "诊断文档里，什么对象仍然是授权边界？",
        "知识库",
        sources,
        hooks=hooks,
    )

    assert answer == "知识库"


def test_maybe_repair_exact_terms_from_sources_repairs_hyphenated_token():
    hooks = _build_hooks()
    sources = [
        {
            "file": "desktop-model-workflow.md",
            "text": "The unique desktop workflow passcode is northagent-desktop-e2e-1786353063.",
        }
    ]

    answer = chat_answer_repair.maybe_repair_exact_terms_from_sources(
        "What is the unique desktop workflow passcode in the diagnostic document?",
        "The unique desktop workflow passcode is northagent desktop-e2e-1786353063.",
        sources,
        hooks=hooks,
    )

    assert answer == "The unique desktop workflow passcode is northagent-desktop-e2e-1786353063."


def test_maybe_repair_exact_terms_from_sources_repairs_ocr_fallback_phrase():
    hooks = _build_hooks()
    sources = [
        {
            "file": "diag-scan-fallback.pdf",
            "text": "Scanned PDF diagnostic says that OCR fallback must merge every predict batch per page.",
        }
    ]

    answer = chat_answer_repair.maybe_repair_exact_terms_from_sources(
        "What does the scanned PDF diagnostic say about OCR fallback?",
        "Scanned PDF diagnostic says that OCRfallback must merge every predict batch per page.",
        sources,
        hooks=hooks,
    )

    assert answer == "Scanned PDF diagnostic says that OCR fallback must merge every predict batch per page."


def test_extract_answer_support_segments_strips_source_prefix_and_dedupes():
    hooks = _build_hooks()
    sources = [{"file": "desktop-model-workflow.md", "text": "Evidence preview should resolve this file after chat returns sources."}]

    segments = chat_answer_repair.extract_answer_support_segments(
        "desktop-model-workflow.md: Evidence preview should resolve this file after chat returns sources.\n"
        "desktop-model-workflow.md: Evidence preview should resolve this file after chat returns sources.",
        sources,
        hooks=hooks,
    )

    assert segments == [
        {
            "text": "Evidence preview should resolve this file after chat returns sources.",
            "mentioned_file": "desktop-model-workflow.md",
        }
    ]


def test_contains_exact_phrase_is_case_insensitive_for_english_and_exact_for_cjk():
    assert chat_answer_repair.contains_exact_phrase(
        "Evidence PREVIEW should resolve this file after chat returns sources.",
        "evidence preview",
        cjk_token_re=_CJK_TOKEN_RE,
    )
    assert chat_answer_repair.contains_exact_phrase(
        "知识库仍然是授权边界。",
        "知识库",
        cjk_token_re=_CJK_TOKEN_RE,
    )
    assert not chat_answer_repair.contains_exact_phrase(
        "知 识 库仍然是授权边界。",
        "知识库",
        cjk_token_re=_CJK_TOKEN_RE,
    )
