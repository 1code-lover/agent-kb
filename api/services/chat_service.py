"""\u804a\u5929\u670d\u52a1\uff1a\u5904\u7406\u57fa\u4e8e\u77e5\u8bc6\u5e93\u7684\u95ee\u7b54\u8bf7\u6c42\u3002"""

from __future__ import annotations

import re
from typing import Any

from api.runtime import runtime_state
from api.schemas import QueryRequest
from api.services.evidence_service import normalize_evidence, normalize_source_nodes
from api.services import model_service
from api.services.query_scope import resolve_chat_query_scope
from api.services.session_store import append_chat_message, clear_chat_messages, list_chat_messages

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

_REFUSAL_MARKERS = (
    "no confirmable information is available",
    "does not mention",
    "cannot be determined",
    "insufficient information",
    "not specified",
    "\u672a\u627e\u5230\u53ef\u786e\u8ba4\u7684\u4fe1\u606f",
    "\u6ca1\u6709\u53ef\u786e\u8ba4\u7684\u4fe1\u606f",
    "\u65e0\u6cd5\u6839\u636e\u5f53\u524d\u77e5\u8bc6\u5e93\u786e\u8ba4",
    "\u5f53\u524d\u77e5\u8bc6\u5e93\u4e2d\u6ca1\u6709",
)

_ASCII_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_CJK_TOKEN_RE = re.compile(f"[{chr(0x4E00)}-{chr(0x9FFF)}]+")
_SENTENCE_SPLIT_RE = re.compile(rf"[{chr(0x3002)}{chr(0xFF01)}{chr(0xFF1F)}!?;\n]+|(?<=\.)\s+")
_CLAUSE_SPLIT_RE = re.compile(f"[{chr(0xFF0C)},{chr(0xFF1A)}:]+")
_ENTITY_QUESTION_MARKERS = (
    "what",
    "which",
    "who",
    "\u4ec0\u4e48",
    "\u54ea\u4e2a",
    "\u8c01",
    "\u54ea\u4f4d",
    "\u54ea\u4e00\u4e2a",
)
_ANSWER_EXPANSION_HINTS = (
    "\u662f",
    "\u4ecd\u7136",
    "\u8d1f\u8d23",
    "\u6279\u51c6",
    "\u7b7e\u7f72",
    "\u5fc5\u987b",
    "\u5305\u542b",
    " is ",
    " are ",
    "remains",
    "gives",
    "signs",
    "must include",
    "includes",
)
_ANSWER_EDGE_STRIP_CHARS = "\"'\u201c\u201d\u2018\u2019()[]{}<> "
_ANSWER_TRAILING_PUNCT_CHARS = "\u3002\uff01\uff1f!?;?,:?"
_ANSWER_LEADING_PUNCT_CHARS = "\uff1a:\uff0c,\uff1b; "

_FOLLOW_UP_EN_PATTERNS = (
    re.compile(r"\bwhat about\b"),
    re.compile(r"\bhow about\b"),
    re.compile(r"\bthis one\b"),
    re.compile(r"\bthat one\b"),
    re.compile(r"\b(?:it|they|them|their|those|these|he|she|his|her)\b"),
)
_FOLLOW_UP_CJK_MARKERS = (
    "\u7ee7\u7eed",
    "\u521a\u624d",
    "\u4e0a\u9762",
    "\u524d\u9762",
    "\u4e0a\u4e00\u6761",
    "\u4e0a\u4e00\u8f6e",
    "\u8fd9\u4e2a",
    "\u90a3\u4e2a",
    "\u5b83",
    "\u5b83\u4eec",
    "\u8be5",
    "\u5176",
)
_MAX_FOLLOW_UP_HISTORY_MESSAGES = 4
_MAX_FOLLOW_UP_HISTORY_CHARS = 800


def _normalize_sources(response: Any) -> list[dict[str, Any]]:
    """\u7edf\u4e00\u6765\u6e90\u8282\u70b9\u5b57\u6bb5\uff0c\u590d\u7528 evidence service \u7684\u6807\u51c6\u5316\u903b\u8f91\u3002"""
    return normalize_source_nodes(response)


def _dedupe_sources_by_file(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """\u6309 kb_id + file \u5408\u5e76\u91cd\u590d\u6765\u6e90\uff0c\u4fdd\u7559\u6392\u5e8f\u6700\u9760\u524d\u7684 chunk\u3002"""
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        if not isinstance(source, dict):
            deduped.append(source)
            continue
        kb_id = str(source.get("kb_id") or "default").strip() or "default"
        file_name = str(source.get("file") or source.get("file_name") or source.get("title") or "").strip()
        if not file_name:
            deduped.append(source)
            continue
        key = (kb_id, file_name)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)
    return deduped


def _answer_is_refusal_like(answer_text: str) -> bool:
    """\u5224\u65ad\u56de\u7b54\u662f\u5426\u5c5e\u4e8e\u65e0\u6cd5\u786e\u8ba4\u4fe1\u606f\u7684\u62d2\u7b54\u7c7b\u8868\u8ff0\u3002"""
    lowered = str(answer_text or "").lower()
    return any(marker in lowered for marker in _REFUSAL_MARKERS)


def _tokenize_text(text: str) -> set[str]:
    """\u62bd\u53d6\u82f1\u6587 token\u3001\u7b80\u5355\u8bcd\u5e72\u548c\u4e2d\u6587 2/3-gram\uff0c\u4f9b\u8f7b\u91cf\u91cd\u53e0\u5339\u914d\u4f7f\u7528\u3002"""
    tokens: set[str] = set()

    for raw in _ASCII_TOKEN_RE.findall(str(text or "").lower()):
        token = raw.strip()
        if len(token) <= 2 or token in _QUESTION_STOPWORDS:
            continue
        tokens.add(token)
        if token.endswith("s") and len(token) > 4:
            tokens.add(token[:-1])
        if token.endswith("ed") and len(token) > 4:
            tokens.add(token[:-2])
        if token.endswith("ing") and len(token) > 5:
            tokens.add(token[:-3])

    for block in _CJK_TOKEN_RE.findall(str(text or "")):
        normalized = block.strip()
        if len(normalized) < 2:
            continue
        tokens.add(normalized)
        if len(normalized) == 2:
            continue
        for width in (2, 3):
            if len(normalized) < width:
                continue
            for index in range(len(normalized) - width + 1):
                tokens.add(normalized[index : index + width])

    return tokens


def _build_source_text_blob(source: dict[str, Any]) -> str:
    """\u62fc\u63a5\u5355\u6761 source \u7684\u5173\u952e\u6587\u672c\u5b57\u6bb5\uff0c\u4f9b\u4e3b\u9898\u5339\u914d\u590d\u7528\u3002"""
    parts = [
        source.get("file"),
        source.get("title"),
        source.get("source"),
        source.get("text"),
        source.get("excerpt"),
    ]
    return "\n".join(str(item) for item in parts if isinstance(item, str) and item.strip())


def _source_supports_question(question: str, source: dict[str, Any]) -> bool:
    """\u5224\u65ad\u4e00\u6761 source \u662f\u5426\u4e0e\u5f53\u524d\u95ee\u9898\u5b58\u5728\u8db3\u591f\u7684\u8bcd\u9762\u91cd\u53e0\u3002"""
    question_tokens = _tokenize_text(question)
    if not question_tokens:
        return True
    source_tokens = _tokenize_text(_build_source_text_blob(source))
    if not source_tokens:
        return False
    return bool(question_tokens & source_tokens)


def _answer_is_brief_entity(answer_text: str) -> bool:
    """\u5224\u65ad\u56de\u7b54\u662f\u5426\u662f\u8fc7\u77ed\u5b9e\u4f53\u7b54\u6848\uff0c\u9002\u5408\u5c1d\u8bd5 source-backed \u6269\u5199\u3002"""
    normalized = str(answer_text or "").strip().strip(_ANSWER_EDGE_STRIP_CHARS)
    normalized = normalized.strip(_ANSWER_TRAILING_PUNCT_CHARS)
    if not normalized or _answer_is_refusal_like(normalized):
        return False
    if any(mark in normalized for mark in ("\u3002", "\uff01", "\uff1f", "!", "?", ";")):
        return False

    cjk_blocks = _CJK_TOKEN_RE.findall(normalized)
    cjk_len = sum(len(block) for block in cjk_blocks)
    if cjk_len:
        return cjk_len <= 6

    ascii_tokens = _ASCII_TOKEN_RE.findall(normalized.lower())
    return 0 < len(ascii_tokens) <= 2 and len(normalized) <= 24


def _question_requests_entity(question: str) -> bool:
    """\u5224\u65ad\u95ee\u9898\u662f\u5426\u662f\u201c\u4ec0\u4e48/\u54ea\u4e2a/\u8c01\u201d\u7c7b\u5b9e\u4f53\u8bc6\u522b\u95ee\u9898\u3002"""
    lowered = str(question or "").lower()
    return any(marker in lowered for marker in _ENTITY_QUESTION_MARKERS)


def _iter_source_support_texts(source: dict[str, Any]) -> list[str]:
    """\u63d0\u53d6\u9002\u5408\u505a\u7b54\u6848\u6269\u5199\u7684 source \u6587\u672c\u5b57\u6bb5\u3002"""
    texts: list[str] = []
    for field in ("text", "excerpt"):
        value = source.get(field)
        if isinstance(value, str) and value.strip():
            texts.append(value.strip())
    return texts


def _normalize_expanded_answer(candidate: str) -> str:
    """\u6e05\u6d17 source \u5b50\u53e5\u5e76\u8865\u9f50\u53e5\u672b\u6807\u70b9\uff0c\u751f\u6210\u6700\u5c0f\u5b8c\u6574\u53e5\u3002"""
    cleaned = str(candidate or "").strip().strip(_ANSWER_EDGE_STRIP_CHARS)
    cleaned = cleaned.lstrip(_ANSWER_LEADING_PUNCT_CHARS)
    if not cleaned:
        return ""
    if cleaned[-1] not in "\u3002\uff01\uff1f.!?":
        cleaned += "\u3002" if _CJK_TOKEN_RE.search(cleaned) else "."
    return cleaned


def _maybe_expand_brief_answer_from_sources(question: str, answer_text: str, sources: list[dict[str, Any]]) -> str:
    """\u5f53\u56de\u7b54\u8fc7\u77ed\u4e14\u6765\u6e90\u53ef\u76f4\u63a5\u652f\u6491\u65f6\uff0c\u7528\u6700\u5c0f\u5b8c\u6574\u53e5\u66ff\u6362\u5b64\u7acb\u540d\u8bcd\u3002"""
    if not sources or not _question_requests_entity(question) or not _answer_is_brief_entity(answer_text):
        return answer_text

    answer_core = str(answer_text or "").strip().strip(_ANSWER_EDGE_STRIP_CHARS)
    answer_core = answer_core.strip(_ANSWER_TRAILING_PUNCT_CHARS)
    if not answer_core:
        return answer_text

    question_tokens = _tokenize_text(question)
    answer_tokens = _tokenize_text(answer_core)
    focus_question_tokens = question_tokens - answer_tokens
    best_candidate = ""
    best_score: tuple[int, int, int] | None = None

    for source in sources:
        for support_text in _iter_source_support_texts(source):
            sentences = [segment.strip() for segment in _SENTENCE_SPLIT_RE.split(support_text) if segment.strip()]
            for sentence in sentences:
                if answer_core not in sentence:
                    continue
                clause_candidates = [segment.strip() for segment in _CLAUSE_SPLIT_RE.split(sentence) if segment.strip()]
                for candidate in [*clause_candidates, sentence]:
                    if answer_core not in candidate:
                        continue
                    if len(candidate) <= len(answer_core) or len(candidate) > 96:
                        continue
                    candidate_tokens = _tokenize_text(candidate)
                    if not candidate_tokens:
                        continue
                    question_overlap = len(focus_question_tokens & candidate_tokens)
                    if question_overlap <= 0:
                        continue
                    hint_score = int(any(hint in candidate.lower() for hint in _ANSWER_EXPANSION_HINTS))
                    clause_preference = int(candidate != sentence)
                    score = (hint_score, clause_preference, question_overlap, -len(candidate))
                    if best_score is None or score > best_score:
                        best_candidate = candidate
                        best_score = score

    expanded = _normalize_expanded_answer(best_candidate)
    return expanded or answer_text


def _prune_sources_for_refusal(question: str, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """\u62d2\u7b54\u65f6\u88c1\u526a\u65e0\u5173\u6765\u6e90\uff0c\u907f\u514d\u628a\u9519\u8bef\u4e3b\u9898\u7684\u8bc1\u636e\u66b4\u9732\u7ed9\u524d\u7aef\u3002"""
    grounded = [source for source in sources if _source_supports_question(question, source)]
    return grounded


def _question_looks_follow_up(question: str) -> bool:
    """\u5224\u65ad\u5f53\u524d\u95ee\u9898\u662f\u5426\u66f4\u50cf\u4f9d\u8d56\u4e0a\u4e0b\u6587\u7684 follow-up \u63d0\u95ee\u3002"""
    raw = str(question or "").strip()
    if not raw:
        return False

    lowered = raw.lower()
    if any(pattern.search(lowered) for pattern in _FOLLOW_UP_EN_PATTERNS):
        return True
    if any(marker in raw for marker in _FOLLOW_UP_CJK_MARKERS):
        return True

    content_tokens = _tokenize_text(raw)
    return len(content_tokens) <= 2 and len(raw) <= 48


def _load_recent_history_for_follow_up(session_id: str) -> list[dict[str, str]]:
    """\u88c1\u526a\u5f53\u524d session \u6700\u8fd1\u51e0\u6761\u6709\u6548\u5bf9\u8bdd\uff0c\u4f9b follow-up \u95ee\u7b54\u6539\u5199\u4f7f\u7528\u3002"""
    recent_messages = list_chat_messages(session_id)
    normalized: list[dict[str, str]] = []
    total_chars = 0

    for item in reversed(list(recent_messages or [])):
        role = str(item.get("role") or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = " ".join(str(item.get("content") or "").split())
        if not content:
            continue
        remaining = _MAX_FOLLOW_UP_HISTORY_CHARS - total_chars
        if remaining <= 0:
            break
        clipped = content[-remaining:]
        normalized.append({"role": role, "content": clipped})
        total_chars += len(clipped)
        if len(normalized) >= _MAX_FOLLOW_UP_HISTORY_MESSAGES:
            break

    normalized.reverse()
    return normalized


def _build_history_grounded_question(question: str, session_id: str) -> str:
    """\u5bf9 follow-up \u63d0\u95ee\u6ce8\u5165\u540c session \u7684\u6700\u8fd1\u4e0a\u4e0b\u6587\uff0c\u4f46\u4e0d\u6539\u53d8 KB \u8303\u56f4\u5951\u7ea6\u3002"""
    if not _question_looks_follow_up(question):
        return question

    history = _load_recent_history_for_follow_up(session_id)
    if not history:
        return question

    lines = ["Conversation context from the same session:"]
    for item in history:
        speaker = "User" if item["role"] == "user" else "Assistant"
        lines.append(f"{speaker}: {item['content']}")
    lines.append(f"Current question: {str(question or '').strip()}")
    lines.append("Answer only from the active knowledge base.")
    return "\n".join(lines)


def query(request: QueryRequest, record_history: bool = True) -> dict[str, Any]:
    """\u6267\u884c\u5355\u8f6e\u95ee\u7b54\uff0c\u5e76\u8fd4\u56de\u7b54\u6848\u3001\u8bc1\u636e\u4e0e\u8303\u56f4\u56de\u663e\u3002"""
    scope = resolve_chat_query_scope(request.kb_ids)

    if not runtime_state.ensure_index_loaded():
        raise ValueError("Knowledge base is empty. Please import documents first.")

    grounded_question = _build_history_grounded_question(request.question, request.session_id)
    engine = runtime_state.build_query_engine(kb_ids=scope.effective_kb_ids)
    try:
        answer = engine.query(grounded_question)
    except Exception as exc:
        fallback = model_service.attempt_model_fallback(exc, session_id=request.session_id)
        if not fallback.get("applied"):
            raise
        runtime_state.invalidate_llm()
        engine = runtime_state.build_query_engine(kb_ids=scope.effective_kb_ids)
        answer = engine.query(grounded_question)
    answer_text = getattr(answer, "response", str(answer))
    sources = _dedupe_sources_by_file(_normalize_sources(answer))
    if _answer_is_refusal_like(answer_text):
        sources = _prune_sources_for_refusal(request.question, sources)
    else:
        answer_text = _maybe_expand_brief_answer_from_sources(request.question, answer_text, sources)

    if record_history:
        append_chat_message(request.session_id, "user", request.question)
        append_chat_message(request.session_id, "assistant", answer_text)

    result = {
        "session_id": request.session_id,
        "answer": answer_text,
        "sources": sources,
        "evidence": normalize_evidence(sources),
    }
    result.update(scope.to_dict())
    return result


def get_history(session_id: str) -> list[dict[str, Any]]:
    """\u8bfb\u53d6\u4f1a\u8bdd\u5386\u53f2\u3002"""
    return list_chat_messages(session_id)


def clear_history(session_id: str) -> None:
    """\u6e05\u7a7a\u4f1a\u8bdd\u5386\u53f2\u3002"""
    clear_chat_messages(session_id)
