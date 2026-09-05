"""\u804a\u5929\u670d\u52a1\uff1a\u5904\u7406\u57fa\u4e8e\u77e5\u8bc6\u5e93\u7684\u95ee\u7b54\u8bf7\u6c42\u3002"""

from __future__ import annotations

import re
from functools import lru_cache
from types import SimpleNamespace
from typing import Any

from api.runtime import runtime_state
from api.schemas import QueryRequest
from api.services.evidence_service import normalize_evidence, normalize_source_nodes
from api.services.chat_postprocessors import SourceAnswerPostprocessorHooks, apply_source_answer_postprocessors
from api.services.chat_contract_markers import (
    REFUSAL_MARKERS as _REFUSAL_MARKERS,
    REFUSAL_SOURCE_MARKERS as _REFUSAL_SOURCE_MARKERS,
    extract_negative_contract_labels,
)
from api.services import (
    chat_answer_repair,
    chat_composite_answers,
    chat_follow_up_context,
    chat_query_flow,
    chat_question_intents,
    chat_source_answers,
    chat_source_reconciliation,
    chat_source_selection,
    chat_targeted_fact,
    kb_service,
    model_service,
)
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

_ASCII_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_CJK_TOKEN_RE = re.compile(f"[{chr(0x4E00)}-{chr(0x9FFF)}]+")
_SENTENCE_SPLIT_RE = re.compile(rf"[{chr(0x3002)}{chr(0xFF01)}{chr(0xFF1F)}!?;\n]+|(?<=\.)\s+")
_CLAUSE_SPLIT_RE = re.compile(rf"[{chr(0xFF0C)},]+|(?<!\d)[{chr(0xFF1A)}:]+(?!\d)")
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
_EXACT_HYPHEN_TOKEN_RE = re.compile(r"\b[a-z][a-z0-9_]*(?:-[a-z0-9_]+){2,}\b", re.IGNORECASE)
_EXACT_SOURCE_PHRASES = (
    "OCR fallback",
    "Evidence preview",
    "evidence preview",
    "Knowledge Base",
    "Knowledge Base remains the authorization boundary",
    "Folder remains organization only",
    "folder is for organization only",
    "knowledge base is the authorization boundary",
    "authorization boundary",
    "resolve this file after chat returns sources",
    "doc_id",
    "preview_locator",
    "各类粮油仓储单位",
)
_LITERAL_PATH_RE = re.compile(r"`?([a-z0-9_.-]+(?:/[a-z0-9_.-]+)+/?)`?", re.IGNORECASE)
_TIME_VALUE_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
_NEGATIVE_CONTRACT_SEGMENT_HINTS = (
    "no confirmable information",
    "active knowledge base",
    "active pdf knowledge base",
    "no fabricated memory",
    "must not fabricate",
    "outside memory",
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
    """判断回答是否整体属于无可确认信息的拒答，而不是事实答案里顺带引用拒答规则。"""
    lines = [line.strip() for line in str(answer_text or "").splitlines() if line.strip()]
    if not lines:
        return False

    line_labels = [extract_negative_contract_labels(line) for line in lines]
    if not any("refusal" in labels for labels in line_labels):
        return False

    def _line_looks_like_grounded_fact(line: str, labels: set[str]) -> bool:
        if labels:
            return False
        normalized = line.lower()
        if re.search(r"\.(?:md|pdf|png|jpe?g|txt|docx?):", normalized):
            return True
        if normalized.startswith(("- ", "* ", "1. ", "2. ", "3. ")):
            return True
        if ":" in line:
            return True
        return False

    first_material_index: int | None = None
    for index, (line, labels) in enumerate(zip(lines, line_labels, strict=False)):
        if labels or _line_looks_like_grounded_fact(line, labels):
            first_material_index = index
            break

    if first_material_index is None:
        return False
    if _line_looks_like_grounded_fact(lines[first_material_index], line_labels[first_material_index]):
        return False

    return not any(
        _line_looks_like_grounded_fact(line, labels)
        for line, labels in zip(lines, line_labels, strict=False)
    )

def _tokenize_text(text: str) -> set[str]:
    """抽取英文 token、简单词干和中文 2/3-gram，供轻量重叠匹配使用。"""
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

def _extract_scope_kb_ids(scope: Any | None) -> list[str]:
    """提取 scope 中的 KB 标识，供 refusal wording 做模态级兜底判断。"""
    if scope is None:
        return []
    raw_kb_ids = getattr(scope, "effective_kb_ids", None) or getattr(scope, "requested_kb_ids", None)
    if not isinstance(raw_kb_ids, (list, tuple, set)):
        return []
    normalized: list[str] = []
    for kb_id in raw_kb_ids:
        value = str(kb_id or "").strip()
        if value:
            normalized.append(value)
    return normalized


def _scope_prefers_pdf_refusal(scope: Any | None) -> bool:
    """当 active KB 本身就是 PDF 集合时，即使问题未显式写 PDF 也应输出 PDF 边界文案。"""
    kb_ids = _extract_scope_kb_ids(scope)
    if not kb_ids:
        return False

    doc_names: list[str] = []
    for kb_id in kb_ids:
        try:
            docs = kb_service.list_docs(kb_id)
        except Exception:
            docs = []
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            label = str(doc.get("name") or doc.get("path") or "").strip().lower()
            if label:
                doc_names.append(label)

    if doc_names:
        return all(label.endswith(".pdf") for label in doc_names)

    return all("pdf" in kb_id.lower() for kb_id in kb_ids)


def _build_refusal_answer(question: str, scope: Any | None = None) -> str:
    """根据问题模态和范围上下文，生成稳定且带边界约束的拒答文案。"""
    lowered = str(question or "").lower()
    strict_boundary_clause = any(
        phrase in lowered
        for phrase in (
            "which document defines",
            "which pdf defines",
            "outside memory",
            "fabricated memory",
            "tenant shard",
            "checksum escrow",
            "namespace pinning",
        )
    )
    if "pdf" in lowered or _scope_prefers_pdf_refusal(scope):
        answer = "No confirmable information is available in the current knowledge base. Please answer from the active PDF knowledge base only."
    else:
        answer = "No confirmable information is available in the current knowledge base. Please answer from the active knowledge base only."
    if strict_boundary_clause:
        answer += " You must not fabricate from outside memory."
    return answer


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
    """判断问题是否是“什么/哪个/谁”类实体识别问题。"""
    return chat_question_intents.question_requests_entity(question)


def _question_requests_preview_expansion(question: str) -> bool:
    """判断问题是否在问 preview 该如何落到 source 原句。"""
    return chat_question_intents.question_requests_preview_expansion(question)


def _question_requests_boundary_answer(question: str) -> bool:
    """判断问题是否在问知识库/文件夹/授权边界关系。"""
    return chat_question_intents.question_requests_boundary_answer(question)


def _question_requests_summary_answer(question: str) -> bool:
    """识别“一句话总结/summary”类问题，供 summary/source 裁剪共用。"""
    return chat_question_intents.question_requests_summary_answer(question)


def _question_benefits_from_brief_answer_expansion(question: str) -> bool:
    """仅在通用事实问答里启用短答案扩写，避免压过更具体的题型修复器。"""
    return chat_question_intents.question_benefits_from_brief_answer_expansion(
        question,
        question_requests_preview_expansion=_question_requests_preview_expansion,
        question_requests_summary_answer=_question_requests_summary_answer,
        question_requests_multi_fact_merge=_question_requests_multi_fact_merge,
        question_requests_targeted_fact_answer=_question_requests_targeted_fact_answer,
    )


def _iter_source_support_texts(source: dict[str, Any]) -> list[str]:
    """\u63d0\u53d6\u9002\u5408\u505a\u7b54\u6848\u6269\u5199\u7684 source \u6587\u672c\u5b57\u6bb5\u3002"""
    texts: list[str] = []
    for field in ("text", "excerpt"):
        value = source.get(field)
        if isinstance(value, str) and value.strip():
            texts.append(_normalize_source_text(value))
    return texts


def _source_document_text(source: dict[str, Any]) -> str:
    """从 source 的 doc_id 回看完整文档文本，补足过短 chunk 的上下文。"""
    kb_id = source.get("kb_id")
    doc_id = source.get("doc_id")
    if not isinstance(kb_id, str) or not kb_id.strip() or not isinstance(doc_id, str) or not doc_id.strip():
        return ""
    try:
        manager = runtime_state.get_index_manager(kb_id.strip())
        doc_store = manager.storage_context.docstore
        document = doc_store.get_document(doc_id.strip()) if hasattr(doc_store, "get_document") else None
        text = getattr(document, "text", "") if document is not None else ""
        if isinstance(text, str) and text.strip():
            return _normalize_source_text(text)

        ref_doc = doc_store.get_ref_doc_info(doc_id.strip()) if hasattr(doc_store, "get_ref_doc_info") else None
        node_ids = list(getattr(ref_doc, "node_ids", []) or [])
        nodes = []
        if hasattr(doc_store, "get_nodes"):
            try:
                nodes = list(doc_store.get_nodes(node_ids=node_ids, raise_error=False) or [])
            except TypeError:
                nodes = list(doc_store.get_nodes(node_ids) or [])
        else:
            docs = getattr(doc_store, "docs", {}) or {}
            nodes = [docs[node_id] for node_id in node_ids if node_id in docs]
    except Exception:
        return ""

    node_text = "\n".join(_normalize_source_text(str(getattr(node, "text", "") or "")) for node in nodes)
    return node_text.strip()


def _iter_boundary_support_texts(source: dict[str, Any]) -> list[str]:
    """边界兜底优先使用完整文档文本，再回落到检索 chunk。"""
    texts = [_source_document_text(source), *_iter_source_support_texts(source)]
    selected: list[str] = []
    seen: set[str] = set()
    for text in texts:
        normalized = str(text or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        selected.append(normalized)
    return selected


def _normalize_source_text(text: str) -> str:
    """清理 source 文本中的 UTF-16 NUL 夹字和多余空白。"""
    cleaned = str(text or "")
    if "\x00" in cleaned:
        cleaned = cleaned.replace("\x00", "")
    return cleaned.strip()


def _normalize_expanded_answer(candidate: str) -> str:
    """\u6e05\u6d17 source \u5b50\u53e5\u5e76\u8865\u9f50\u53e5\u672b\u6807\u70b9\uff0c\u751f\u6210\u6700\u5c0f\u5b8c\u6574\u53e5\u3002"""
    cleaned = str(candidate or "").strip().strip(_ANSWER_EDGE_STRIP_CHARS)
    cleaned = cleaned.lstrip(_ANSWER_LEADING_PUNCT_CHARS)
    if not cleaned:
        return ""
    if cleaned[-1] not in "\u3002\uff01\uff1f.!?":
        cleaned += "\u3002" if _CJK_TOKEN_RE.search(cleaned) else "."
    return cleaned


@lru_cache(maxsize=1)
def _build_source_projection_hooks() -> chat_source_answers.SourceProjectionHooks:
    """构建 source projection 所需 hooks，收敛表格/preview/边界/范围修复器依赖。"""
    return chat_source_answers.SourceProjectionHooks(
        tokenize_text=_tokenize_text,
        iter_source_support_texts=_iter_source_support_texts,
        iter_boundary_support_texts=_iter_boundary_support_texts,
        question_requests_preview_expansion=_question_requests_preview_expansion,
        question_requests_boundary_answer=_question_requests_boundary_answer,
        question_requests_scope_definition=_question_requests_scope_definition,
        answer_is_refusal_like=_answer_is_refusal_like,
        answer_is_brief_entity=_answer_is_brief_entity,
        contains_exact_phrase=_contains_exact_phrase,
        normalize_expanded_answer=_normalize_expanded_answer,
        sentence_split_re=_SENTENCE_SPLIT_RE,
        answer_edge_strip_chars=_ANSWER_EDGE_STRIP_CHARS,
        answer_trailing_punct_chars=_ANSWER_TRAILING_PUNCT_CHARS,
    )


@lru_cache(maxsize=1)
def _build_source_answer_repair_hooks() -> chat_answer_repair.SourceAnswerRepairHooks:
    """构建短答案扩写 / 精确短语修复所需 hooks，继续压缩 chat_service 内部纯函数链。"""
    return chat_answer_repair.SourceAnswerRepairHooks(
        tokenize_text=_tokenize_text,
        iter_source_support_texts=_iter_source_support_texts,
        question_requests_preview_expansion=_question_requests_preview_expansion,
        question_requests_entity=_question_requests_entity,
        question_requests_exact_source_phrase=_question_requests_exact_source_phrase,
        answer_is_brief_entity=_answer_is_brief_entity,
        answer_is_refusal_like=_answer_is_refusal_like,
        normalize_expanded_answer=_normalize_expanded_answer,
        sentence_split_re=_SENTENCE_SPLIT_RE,
        clause_split_re=_CLAUSE_SPLIT_RE,
        answer_edge_strip_chars=_ANSWER_EDGE_STRIP_CHARS,
        answer_trailing_punct_chars=_ANSWER_TRAILING_PUNCT_CHARS,
        cjk_token_re=_CJK_TOKEN_RE,
        ascii_token_re=_ASCII_TOKEN_RE,
        question_stopwords=_QUESTION_STOPWORDS,
    )


@lru_cache(maxsize=1)
def _build_source_selection_hooks() -> chat_source_selection.SourceSelectionHooks:
    """构建来源裁剪 / 最小支撑集选择所需 hooks，继续下沉 chat_service 里的支撑判断启发式。"""
    return chat_source_selection.SourceSelectionHooks(
        build_source_text_blob=_build_source_text_blob,
        tokenize_text=_tokenize_text,
        normalize_expanded_answer=_normalize_expanded_answer,
        dedupe_sources_by_file=_dedupe_sources_by_file,
        answer_is_refusal_like=_answer_is_refusal_like,
        question_requests_summary_answer=_question_requests_summary_answer,
        question_prefers_cross_source_fact_assembly=_question_prefers_cross_source_fact_assembly,
        question_requests_targeted_fact_answer=_question_requests_targeted_fact_answer,
        question_requests_boundary_answer=_question_requests_boundary_answer,
        question_requests_negative_contract=_question_requests_negative_contract,
        source_supports_question=_source_supports_question,
        extract_answer_support_segments=_extract_answer_support_segments,
        refusal_markers=_REFUSAL_MARKERS,
        refusal_source_markers=_REFUSAL_SOURCE_MARKERS,
    )


@lru_cache(maxsize=1)
def _build_source_reconciliation_hooks() -> chat_source_reconciliation.SourceReconciliationHooks:
    """构建 query 后 source 补检索 / reconcile 所需 hooks，继续压缩 chat_service 内部入口职责。"""
    return chat_source_reconciliation.SourceReconciliationHooks(
        normalize_sources=_normalize_sources,
        source_supports_question=_source_supports_question,
        dedupe_sources_by_file=_dedupe_sources_by_file,
        extract_literal_question_terms=_extract_literal_question_terms,
        question_prefers_cross_source_fact_assembly=_question_prefers_cross_source_fact_assembly,
        question_requests_targeted_fact_answer=_question_requests_targeted_fact_answer,
        build_source_text_blob=_build_source_text_blob,
    )


def _build_query_flow_hooks() -> chat_query_flow.QueryFlowHooks:
    """构建 follow-up / preflight / query engine 前置流程所需 hooks。"""
    return chat_query_flow.QueryFlowHooks(
        question_looks_follow_up=_question_looks_follow_up,
        list_chat_messages=list_chat_messages,
        question_requests_exact_source_phrase=_question_requests_exact_source_phrase,
        normalize_sources=lambda response: _normalize_sources(
            SimpleNamespace(source_nodes=list(response))
            if isinstance(response, (list, tuple))
            else response
        ),
        dedupe_sources=_dedupe_sources_by_file,
        reconcile_sources_for_question=_reconcile_sources_for_question,
        source_supports_question=_source_supports_question,
        build_refusal_answer=_build_refusal_answer,
        append_chat_message=append_chat_message,
        get_model_health=model_service.get_model_health,
        normalize_evidence=normalize_evidence,
        build_query_engine=runtime_state.build_query_engine,
        attempt_model_fallback=model_service.attempt_model_fallback,
        invalidate_llm=getattr(runtime_state, "invalidate_llm", lambda: None),
        question_requests_identifier_like_field=_question_requests_identifier_like_field,
        sources_support_identifier_like_field=_sources_support_identifier_like_field,
        answer_is_refusal_like=_answer_is_refusal_like,
        prune_sources_for_refusal=_prune_sources_for_refusal,
        apply_source_answer_postprocessors=_apply_source_answer_postprocessors,
        max_follow_up_history_messages=_MAX_FOLLOW_UP_HISTORY_MESSAGES,
        max_follow_up_history_chars=_MAX_FOLLOW_UP_HISTORY_CHARS,
    )


@lru_cache(maxsize=1)
def _build_composite_answer_hooks() -> chat_composite_answers.CompositeAnswerHooks:
    """构建 multi-fact merge / summary bundle 所需 hooks，继续下沉 chat_service 里的组合启发式。"""
    return chat_composite_answers.CompositeAnswerHooks(
        tokenize_text=_tokenize_text,
        iter_boundary_support_texts=_iter_boundary_support_texts,
        iter_targeted_answer_candidates=_iter_targeted_answer_candidates,
        question_requests_boundary_answer=_question_requests_boundary_answer,
        question_requests_multi_fact_merge=_question_requests_multi_fact_merge,
        question_requests_summary_answer=_question_requests_summary_answer,
        answer_is_refusal_like=_answer_is_refusal_like,
        normalize_expanded_answer=_normalize_expanded_answer,
        sentence_split_re=_SENTENCE_SPLIT_RE,
        time_value_re=_TIME_VALUE_RE,
    )

def _extract_table_field_names(question: str) -> list[str]:
    """从“表里某些字段是什么”类问题中抽取字段名。"""
    return chat_source_answers.extract_table_field_names(question)


def _extract_markdown_table_values(text: str, fields: list[str]) -> dict[str, str]:
    """从 Markdown 表格中按字段名抽取对应值。"""
    return chat_source_answers.extract_markdown_table_values(text, fields, tokenize_text=_tokenize_text)


def _maybe_answer_table_fields_from_sources(question: str, answer_text: str, sources: list[dict[str, Any]]) -> str:
    """表格字段问答命中 source 时，优先用表格原值补齐答案。"""
    return chat_source_answers.maybe_answer_table_fields_from_sources(
        question,
        answer_text,
        sources,
        hooks=_build_source_projection_hooks(),
    )


def _maybe_answer_preview_from_sources(question: str, answer_text: str, sources: list[dict[str, Any]]) -> str:
    """preview 问题命中 source 时，优先返回 source 中的 preview 原句。"""
    return chat_source_answers.maybe_answer_preview_from_sources(
        question,
        answer_text,
        sources,
        hooks=_build_source_projection_hooks(),
    )


def _multi_source_boundary_answer_is_complete(
    question: str,
    answer_text: str,
    sources: list[dict[str, Any]],
) -> bool:
    """判断跨文档原答是否已完整覆盖边界、知识库锚点和问题点名的范围字段。"""
    return chat_source_answers.multi_source_boundary_answer_is_complete(
        question,
        answer_text,
        sources,
        hooks=_build_source_projection_hooks(),
    )


def _maybe_answer_boundary_from_sources(question: str, answer_text: str, sources: list[dict[str, Any]]) -> str:
    """边界类问题命中 source 时，按问题范围保留最小且完整的原句。"""
    return chat_source_answers.maybe_answer_boundary_from_sources(
        question,
        answer_text,
        sources,
        hooks=_build_source_projection_hooks(),
    )


def _question_requests_scope_definition(question: str) -> bool:
    """判断问题是否在问范围/适用对象/定义句。"""
    return chat_question_intents.question_requests_scope_definition(question)


def _maybe_answer_scope_definition_from_sources(question: str, answer_text: str, sources: list[dict[str, Any]]) -> str:
    """范围/定义类问题命中 source 时，优先返回完整定义句。"""
    return chat_source_answers.maybe_answer_scope_definition_from_sources(
        question,
        answer_text,
        sources,
        hooks=_build_source_projection_hooks(),
    )


def _question_requests_multi_fact_merge(question: str) -> bool:
    """判断问题是否明确要求把多个 source 事实合并到同一答案。"""
    return chat_question_intents.question_requests_multi_fact_merge(question)


def _maybe_merge_source_facts_from_sources(question: str, answer_text: str, sources: list[dict[str, Any]]) -> str:
    """当问题明确要求一个回答里包含多个 source 事实时，委托 composite answers 选择最完整的事实句。"""
    return chat_composite_answers.maybe_merge_source_facts_from_sources(
        question,
        answer_text,
        sources,
        hooks=_build_composite_answer_hooks(),
    )

def _maybe_expand_brief_answer_from_sources(question: str, answer_text: str, sources: list[dict[str, Any]]) -> str:
    """当回答过短且来源可直接支撑时，用最小完整句替换孤立名词。"""
    return chat_answer_repair.maybe_expand_brief_answer_from_sources(
        question,
        answer_text,
        sources,
        hooks=_build_source_answer_repair_hooks(),
    )

def _contains_exact_phrase(answer_text: str, phrase: str) -> bool:
    """判断答案是否已包含精确短语。"""
    return chat_answer_repair.contains_exact_phrase(answer_text, phrase, cjk_token_re=_CJK_TOKEN_RE)

def _question_requests_exact_source_phrase(question: str) -> bool:
    """判断问题是否倾向索要唯一/精确来源短语。"""
    return chat_question_intents.question_requests_exact_source_phrase(question)


def _question_supports_source_term(question: str, term: str) -> bool:
    """判断问题是否足够指向某个 source 精确短语。"""
    return chat_answer_repair.question_supports_source_term(
        question,
        term,
        hooks=_build_source_answer_repair_hooks(),
    )


def _tokenize_source_term_support_text(text: str) -> set[str]:
    """抽取精确短语选择用 token，避免词干变体被重复计分。"""
    return chat_answer_repair.tokenize_source_term_support_text(
        text,
        ascii_token_re=_ASCII_TOKEN_RE,
        cjk_token_re=_CJK_TOKEN_RE,
        question_stopwords=_QUESTION_STOPWORDS,
    )


def _extract_exact_source_terms(text: str) -> list[str]:
    """从 source 文本中抽取适合保真的精确 token/短语。"""
    return chat_answer_repair.extract_exact_source_terms(text)


def _source_sentence_for_term(term: str, sources: list[dict[str, Any]]) -> str:
    """查找包含精确短语的最小 source 句子。"""
    return chat_answer_repair.source_sentence_for_term(
        term,
        sources,
        hooks=_build_source_answer_repair_hooks(),
    )


def _maybe_repair_exact_terms_from_sources(question: str, answer_text: str, sources: list[dict[str, Any]]) -> str:
    """当模型改写破坏精确 token/短语时，从 source 中补回保真表达。"""
    return chat_answer_repair.maybe_repair_exact_terms_from_sources(
        question,
        answer_text,
        sources,
        hooks=_build_source_answer_repair_hooks(),
    )

def _source_supports_refusal_answer(answer_text: str, source: dict[str, Any]) -> bool:
    """判断来源是否直接支持“缺证据/需拒答”这个结论，而不只是与问题同主题。"""
    return chat_source_selection.source_supports_refusal_answer(
        answer_text,
        source,
        hooks=_build_source_selection_hooks(),
    )


def _prune_sources_for_refusal(question: str, answer_text: str, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """拒答时仅保留同时支撑问题主题和拒答结论的来源。"""
    return chat_source_selection.prune_sources_for_refusal(
        question,
        answer_text,
        sources,
        hooks=_build_source_selection_hooks(),
    )

def _strip_answer_source_prefix(segment: str, sources: list[dict[str, Any]]) -> tuple[str, str | None]:
    """去掉 answer 里显式的 `file:` 前缀，便于按实际内容回溯来源。"""
    return chat_answer_repair.strip_answer_source_prefix(segment, sources)


def _extract_answer_support_segments(answer_text: str, sources: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    """把最终 answer 拆成可回溯到 source 的最小事实片段。"""
    return chat_answer_repair.extract_answer_support_segments(
        answer_text,
        sources,
        hooks=_build_source_answer_repair_hooks(),
    )

def _source_supports_answer_segment(source: dict[str, Any], segment: str) -> bool:
    """判断单个 source 是否足以支撑 answer 里的某个事实片段。"""
    return chat_source_selection.source_supports_answer_segment(
        source,
        segment,
        hooks=_build_source_selection_hooks(),
    )



def _score_source_selection(question: str, answer_text: str, source: dict[str, Any], supported_count: int, *, mentioned: bool) -> tuple[int, ...]:
    """为 source 最小化选择最贴题、最贴近答案的来源。"""
    return chat_source_selection.score_source_selection(
        question,
        answer_text,
        source,
        supported_count,
        mentioned=mentioned,
        hooks=_build_source_selection_hooks(),
    )



def _minimize_sources_for_answer(question: str, answer_text: str, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """在不丢失 answer 支撑关系的前提下，尽量缩到最小必要来源集合。"""
    return chat_source_selection.minimize_sources_for_answer(
        question,
        answer_text,
        sources,
        hooks=_build_source_selection_hooks(),
    )

def _matched_identifier_field_rules(question: str) -> list[dict[str, Any]]:
    """抽取问题中命中的高风险字段规则，避免把 war-room 之类主题词误当成字段证据。"""
    return chat_question_intents.matched_identifier_field_rules(question, tokenize_text=_tokenize_text)


def _question_requests_identifier_like_field(question: str) -> bool:
    """识别 ticket/url/token 等字段型问题；这类问题若来源中完全缺字段证据，应稳定拒答。"""
    return chat_question_intents.question_requests_identifier_like_field(question, tokenize_text=_tokenize_text)


def _source_supports_identifier_rule(source_blob: str, source_terms: set[str], rule: dict[str, Any]) -> bool:
    """判断单条 source 是否包含字段级证据，而不是只共享主题词。"""
    return chat_question_intents.source_supports_identifier_rule(source_blob, source_terms, rule)


def _sources_support_identifier_like_field(question: str, sources: list[dict[str, Any]]) -> bool:
    """如果问题显式要求标识字段，至少一条来源应包含相应字段证据。"""
    return chat_question_intents.sources_support_identifier_like_field(
        question,
        sources,
        tokenize_text=_tokenize_text,
        build_source_text_blob=_build_source_text_blob,
    )


def _question_requests_negative_contract(question: str) -> bool:
    """识别 refusal / active-scope / no-fabrication 这类负向契约问题。"""
    return chat_question_intents.question_requests_negative_contract(question)


def _question_requests_targeted_fact_answer(question: str) -> bool:
    """识别需要按子问题重组精确事实的问法，避免对泛化流程问句过度裁剪。"""
    return chat_question_intents.question_requests_targeted_fact_answer(
        question,
        extract_literal_question_terms=_extract_literal_question_terms,
    )


def _question_prefers_cross_source_fact_assembly(question: str) -> bool:
    """判断问题是否明确要求跨文档/跨看板拼装事实。"""
    return chat_question_intents.question_prefers_cross_source_fact_assembly(question)


def _normalize_targeted_subquestion(subquestion: str) -> str:
    """裁掉 Compare/On/In/Under 等共享前缀，只保留真正的子问题子句。"""
    return chat_question_intents.normalize_targeted_subquestion(subquestion)



def _split_targeted_fact_question(question: str) -> list[str]:
    """按事实子问题切开复合问句，并移除共享前缀以免误触发其它门槛。"""
    return chat_question_intents.split_targeted_fact_question(
        question,
        question_requests_targeted_fact_answer=_question_requests_targeted_fact_answer,
    )


def _extract_literal_question_terms(question: str) -> list[str]:
    """抽取问题里必须保真的路径/字面 token，例如 cutover/runbook/。"""
    terms: list[str] = []
    seen: set[str] = set()
    for match in _LITERAL_PATH_RE.finditer(str(question or "")):
        term = str(match.group(1) or "").strip()
        lowered = term.lower()
        if term and lowered not in seen:
            seen.add(lowered)
            terms.append(term)
    return terms


def _source_matches_literal_terms(source: dict[str, Any], literal_terms: list[str]) -> bool:
    """判断来源是否命中了问题里显式出现的路径/字面 token。"""
    return chat_source_reconciliation.source_matches_literal_terms(
        source,
        literal_terms,
        hooks=_build_source_reconciliation_hooks(),
    )


def _collect_candidate_sources_for_question(engine: Any, question: str, *, top_k: int = 4) -> list[dict[str, Any]]:
    """尽量从引擎/检索器里补拿更多候选 source，供精确答案重组使用。"""
    return chat_source_reconciliation.collect_candidate_sources_for_question(
        engine,
        question,
        hooks=_build_source_reconciliation_hooks(),
        top_k=top_k,
    )


def _reconcile_sources_for_question(engine: Any, question: str, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """必要时补充/替换来源，避免跨文档问题只拿到半边证据。"""
    candidates = _collect_candidate_sources_for_question(engine, question)
    return chat_source_reconciliation.reconcile_sources_from_candidates(
        question,
        sources,
        candidates,
        hooks=_build_source_reconciliation_hooks(),
    )



@lru_cache(maxsize=1)
def _build_targeted_fact_hooks() -> chat_targeted_fact.TargetedFactHooks:
    """构建 targeted-fact 子模块依赖，隔离 chat_service 与具体实现细节。"""
    hooks: chat_targeted_fact.TargetedFactHooks | None = None

    def _iter_targeted(source: dict[str, Any]) -> list[str]:
        return chat_targeted_fact.iter_targeted_answer_candidates(source, hooks=hooks)

    hooks = chat_targeted_fact.TargetedFactHooks(
        iter_boundary_support_texts=_iter_boundary_support_texts,
        normalize_expanded_answer=_normalize_expanded_answer,
        tokenize_text=_tokenize_text,
        normalize_targeted_subquestion=_normalize_targeted_subquestion,
        extract_literal_question_terms=_extract_literal_question_terms,
        question_requests_negative_contract=_question_requests_negative_contract,
        question_requests_summary_answer=_question_requests_summary_answer,
        question_prefers_cross_source_fact_assembly=_question_prefers_cross_source_fact_assembly,
        split_targeted_fact_question=_split_targeted_fact_question,
        dedupe_sources_by_file=_dedupe_sources_by_file,
        iter_targeted_answer_candidates=_iter_targeted,
        sentence_split_re=_SENTENCE_SPLIT_RE,
        clause_split_re=_CLAUSE_SPLIT_RE,
        time_value_re=_TIME_VALUE_RE,
        literal_path_re=_LITERAL_PATH_RE,
    )
    return hooks



def _iter_targeted_answer_candidates(source: dict[str, Any]) -> list[str]:
    """从 source 中提取适合多事实重组的行/句/短子句候选。"""
    return chat_targeted_fact.iter_targeted_answer_candidates(
        source,
        hooks=_build_targeted_fact_hooks(),
    )



def _score_targeted_answer_candidate(question: str, subquestion: str, candidate: str) -> tuple[int, ...] | None:
    """对子问题候选句打分，优先保留最小、最贴题、最少噪声且包含关键字段的 grounded 片段。"""
    return chat_targeted_fact.score_targeted_answer_candidate(
        question,
        subquestion,
        candidate,
        hooks=_build_targeted_fact_hooks(),
    )





def _best_single_source_negative_contract_answer(
    question: str,
    sources: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]] | None:
    """若同一 source 已覆盖 refusal/scope/no-fabrication 三条负向契约，则直接返回最小答案。"""
    return chat_targeted_fact.best_single_source_negative_contract_answer(
        question,
        sources,
        hooks=_build_targeted_fact_hooks(),
    )



def _best_negative_contract_segment(question: str, sources: list[dict[str, Any]]) -> tuple[str, dict[str, Any]] | None:
    """为 refusal / negative-contract 问题补回 No confirmable information 这类锚点。"""
    return chat_targeted_fact.best_negative_contract_segment(
        question,
        sources,
        hooks=_build_targeted_fact_hooks(),
    )



def _maybe_answer_summary_bundle_from_sources(question: str, answer_text: str, sources: list[dict[str, Any]]) -> str:
    """处理“一句话总结/summary”类问题时，委托 composite answers 组装时间/边界/拒答锚点。"""
    return chat_composite_answers.maybe_answer_summary_bundle_from_sources(
        question,
        answer_text,
        sources,
        hooks=_build_composite_answer_hooks(),
    )

def _expand_targeted_source_segments_with_local_context(
    source: dict[str, Any],
    segments: list[str],
) -> list[str]:
    """同一 source 命中相邻多段时补回中间叙述行，但跳过其它结构化事实字段。"""
    return chat_targeted_fact.expand_targeted_source_segments_with_local_context(
        source,
        segments,
        hooks=_build_targeted_fact_hooks(),
    )



def _maybe_answer_targeted_fact_question_from_sources(
    question: str,
    answer_text: str,
    sources: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """针对多事实问题，用 source 重组更完整答案，并只保留被使用的来源。"""
    if not sources or _answer_is_refusal_like(answer_text):
        return answer_text, sources

    if _question_requests_summary_answer(question):
        return answer_text, sources

    return chat_targeted_fact.maybe_answer_targeted_fact_question_from_sources(
        question,
        answer_text,
        sources,
        hooks=_build_targeted_fact_hooks(),
    )


def _question_looks_follow_up(question: str) -> bool:
    """判断当前问题是否更像依赖上下文的 follow-up 提问。"""
    return chat_follow_up_context.question_looks_follow_up(
        question,
        hooks=chat_follow_up_context.FollowUpQuestionHeuristicsHooks(
            tokenize_text=_tokenize_text,
            question_requests_identifier_like_field=_question_requests_identifier_like_field,
            question_requests_exact_source_phrase=_question_requests_exact_source_phrase,
        ),
    )


def _load_recent_history_for_follow_up(session_id: str) -> list[dict[str, str]]:
    """裁剪当前 session 最近几条有效对话，供 follow-up 问答改写使用。"""
    return chat_query_flow.load_recent_history_for_follow_up(
        session_id,
        hooks=_build_query_flow_hooks(),
    )


def _build_history_grounded_question(question: str, session_id: str) -> str:
    """对 follow-up 提问注入同 session 的最近上下文，但不改变 KB 范围契约。"""
    return chat_query_flow.build_history_grounded_question(
        question,
        session_id,
        hooks=_build_query_flow_hooks(),
    )


def _preflight_exact_question_sources(engine: Any, question: str) -> list[dict[str, Any]] | None:
    """唯一值/原文类问题先做一次纯检索；无相关证据时不调用 LLM，避免跨库臆答。"""
    return chat_query_flow.preflight_exact_question_sources(
        engine,
        question,
        hooks=_build_query_flow_hooks(),
    )


def _build_no_source_result(request: QueryRequest, scope: Any, *, record_history: bool) -> dict[str, Any]:
    """构造限定知识库无相关证据时的稳定拒答结果。"""
    return chat_query_flow.build_no_source_result(
        request,
        scope,
        record_history=record_history,
        hooks=_build_query_flow_hooks(),
    )


def _build_query_engine_for_request(request: QueryRequest, scope: Any) -> Any:
    """把请求级 RAG 参数透传到查询引擎构建逻辑。"""
    return chat_query_flow.build_query_engine_for_request(
        request,
        scope,
        hooks=_build_query_flow_hooks(),
    )



def _execute_query_with_model_fallback(
    engine: Any,
    request: QueryRequest,
    scope: Any,
    grounded_question: str,
) -> tuple[Any, Any]:
    """执行 query，并在可恢复模型错误时重建 query engine 后重试一次。"""
    return chat_query_flow.execute_query_with_model_fallback(
        engine,
        request,
        scope,
        grounded_question,
        hooks=_build_query_flow_hooks(),
    )



def _build_query_result(
    request: QueryRequest,
    scope: Any,
    answer_text: str,
    sources: list[dict[str, Any]],
    *,
    record_history: bool,
) -> dict[str, Any]:
    """组装 query 返回值，并按需记录当前轮会话历史。"""
    return chat_query_flow.build_query_result(
        request,
        scope,
        answer_text,
        sources,
        record_history=record_history,
        hooks=_build_query_flow_hooks(),
    )


def _extract_query_answer_payload(
    answer: Any,
    engine: Any,
    question: str,
) -> tuple[str, list[dict[str, Any]]]:
    """提取回答文本并收口 source normalize / dedupe / reconcile 中段流程。"""
    return chat_query_flow.extract_query_answer_payload(
        answer,
        engine,
        question,
        hooks=_build_query_flow_hooks(),
    )


def _finalize_query_answer(
    question: str,
    answer_text: str,
    sources: list[dict[str, Any]],
    *,
    scope: Any | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """收口 query 尾段的 identifier-gap、refusal pruning 与 postprocessor 分支。"""
    return chat_query_flow.finalize_query_answer(
        question,
        answer_text,
        sources,
        scope=scope,
        hooks=_build_query_flow_hooks(),
    )


def _question_may_need_exact_term_repair(question: str) -> bool:
    """复用 question-intent classifier，判断问题是否值得进入精确短语修复分支。"""
    return chat_question_intents.question_may_need_exact_term_repair(
        question,
        question_requests_exact_source_phrase=_question_requests_exact_source_phrase,
        question_requests_preview_expansion=_question_requests_preview_expansion,
        question_requests_boundary_answer=_question_requests_boundary_answer,
        question_requests_scope_definition=_question_requests_scope_definition,
        question_requests_targeted_fact_answer=_question_requests_targeted_fact_answer,
        question_requests_identifier_like_field=_question_requests_identifier_like_field,
    )



def _build_source_answer_postprocessor_hooks() -> SourceAnswerPostprocessorHooks:
    """构建后处理回调集合，隔离调度层与具体 heuristic 实现。"""
    return SourceAnswerPostprocessorHooks(
        extract_table_field_names=_extract_table_field_names,
        question_requests_preview_expansion=_question_requests_preview_expansion,
        answer_is_brief_entity=_answer_is_brief_entity,
        question_benefits_from_brief_answer_expansion=_question_benefits_from_brief_answer_expansion,
        question_requests_boundary_answer=_question_requests_boundary_answer,
        question_requests_scope_definition=_question_requests_scope_definition,
        question_requests_multi_fact_merge=_question_requests_multi_fact_merge,
        question_requests_summary_answer=_question_requests_summary_answer,
        question_requests_targeted_fact_answer=_question_requests_targeted_fact_answer,
        question_may_need_exact_term_repair=_question_may_need_exact_term_repair,
        maybe_answer_table_fields_from_sources=_maybe_answer_table_fields_from_sources,
        maybe_answer_preview_from_sources=_maybe_answer_preview_from_sources,
        maybe_expand_brief_answer_from_sources=_maybe_expand_brief_answer_from_sources,
        maybe_answer_boundary_from_sources=_maybe_answer_boundary_from_sources,
        maybe_answer_scope_definition_from_sources=_maybe_answer_scope_definition_from_sources,
        maybe_merge_source_facts_from_sources=_maybe_merge_source_facts_from_sources,
        maybe_answer_summary_bundle_from_sources=_maybe_answer_summary_bundle_from_sources,
        maybe_answer_targeted_fact_question_from_sources=_maybe_answer_targeted_fact_question_from_sources,
        maybe_repair_exact_terms_from_sources=_maybe_repair_exact_terms_from_sources,
        minimize_sources_for_answer=_minimize_sources_for_answer,
    )



def _apply_source_answer_postprocessors(
    question: str,
    answer_text: str,
    sources: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """按题型调度 source-backed 后处理，避免每个问题都串行跑完整规则链。"""
    return apply_source_answer_postprocessors(
        question,
        answer_text,
        sources,
        hooks=_build_source_answer_postprocessor_hooks(),
    )



def query(request: QueryRequest, record_history: bool = True) -> dict[str, Any]:
    """执行单轮问答，并返回答案、证据与范围回显。"""
    scope = resolve_chat_query_scope(request.kb_ids)

    if not runtime_state.ensure_index_loaded(scope.effective_kb_ids[0] if scope.effective_kb_ids else None):
        raise ValueError("Knowledge base is empty. Please import documents first.")

    grounded_question = _build_history_grounded_question(request.question, request.session_id)
    engine = _build_query_engine_for_request(request, scope)
    exact_sources = _preflight_exact_question_sources(engine, grounded_question)
    if exact_sources == []:
        return _build_no_source_result(request, scope, record_history=record_history)

    answer, engine = _execute_query_with_model_fallback(engine, request, scope, grounded_question)
    answer_text, sources = _extract_query_answer_payload(
        answer,
        engine,
        request.question,
    )

    answer_text, sources = _finalize_query_answer(
        request.question,
        answer_text,
        sources,
        scope=scope,
    )

    return _build_query_result(
        request,
        scope,
        answer_text,
        sources,
        record_history=record_history,
    )



def get_history(session_id: str) -> list[dict[str, Any]]:
    """\u8bfb\u53d6\u4f1a\u8bdd\u5386\u53f2\u3002"""
    return list_chat_messages(session_id)


def clear_history(session_id: str) -> None:
    """\u6e05\u7a7a\u4f1a\u8bdd\u5386\u53f2\u3002"""
    clear_chat_messages(session_id)












