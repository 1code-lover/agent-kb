"""chat_source_answers 的独立契约测试。"""

from __future__ import annotations

import re

from api.services import chat_question_intents, chat_source_answers


_ASCII_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_CJK_TOKEN_RE = re.compile(r"[一-鿿]+")
_SENTENCE_SPLIT_RE = re.compile(r"[。！？!?;\n]+|(?<=\.)\s+")


def _iter_source_support_texts(source: dict[str, str]) -> list[str]:
    texts: list[str] = []
    for field in ("text", "excerpt"):
        value = str(source.get(field) or "").strip()
        if value:
            texts.append(value)
    return texts


def _iter_boundary_support_texts(source: dict[str, str]) -> list[str]:
    return _iter_source_support_texts(source)


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


def _answer_is_refusal_like(answer_text: str) -> bool:
    lowered = str(answer_text or "").lower()
    return "no confirmable information" in lowered or "无法根据当前知识库确认" in answer_text


def _contains_exact_phrase(answer_text: str, phrase: str) -> bool:
    return str(phrase or "").lower() in str(answer_text or "").lower()


def _normalize_expanded_answer(candidate: str) -> str:
    cleaned = str(candidate or "").strip().strip("\"'“”‘’()[]{}<> ")
    cleaned = cleaned.lstrip("：:,，;； ")
    if not cleaned:
        return ""
    if cleaned[-1] not in "。！？.!?":
        cleaned += "。" if _CJK_TOKEN_RE.search(cleaned) else "."
    return cleaned


def _build_hooks() -> chat_source_answers.SourceProjectionHooks:
    return chat_source_answers.SourceProjectionHooks(
        tokenize_text=_tokenize_text,
        iter_source_support_texts=_iter_source_support_texts,
        iter_boundary_support_texts=_iter_boundary_support_texts,
        question_requests_preview_expansion=chat_question_intents.question_requests_preview_expansion,
        question_requests_boundary_answer=chat_question_intents.question_requests_boundary_answer,
        question_requests_scope_definition=chat_question_intents.question_requests_scope_definition,
        answer_is_refusal_like=_answer_is_refusal_like,
        answer_is_brief_entity=lambda answer: False,
        contains_exact_phrase=_contains_exact_phrase,
        normalize_expanded_answer=_normalize_expanded_answer,
        sentence_split_re=_SENTENCE_SPLIT_RE,
        answer_edge_strip_chars="\"'“”‘’()[]{}<> ",
        answer_trailing_punct_chars="。！？!?;?,:?",
    )


def test_extract_table_field_names_supports_mixed_language_questions():
    assert chat_source_answers.extract_table_field_names("表里，审批人和回滚负责人分别是什么？") == ["审批人", "回滚负责人"]
    assert chat_source_answers.extract_table_field_names("In the table, what are owner and checkpoint time?") == ["owner", "checkpoint time"]


def test_maybe_answer_table_fields_from_sources_prefers_markdown_table_values():
    hooks = _build_hooks()
    sources = [
        {
            "file": "approval.md",
            "text": "| 字段 | 值 |\n| --- | --- |\n| 审批人 | 李青 |\n| 回滚负责人 | 王磊 |",
        }
    ]

    answer = chat_source_answers.maybe_answer_table_fields_from_sources(
        "表里审批人和回滚负责人分别是什么？",
        "请查看表格。",
        sources,
        hooks=hooks,
    )

    assert answer == "审批人是 李青，回滚负责人是 王磊。"


def test_maybe_answer_preview_from_sources_prefers_resolve_sentence():
    hooks = _build_hooks()
    sources = [
        {
            "file": "preview-guide.pdf",
            "text": "Every answer should carry doc_id and preview_locator. Preview excerpt must resolve this file after chat returns sources.",
        }
    ]

    answer = chat_source_answers.maybe_answer_preview_from_sources(
        "What should preview excerpt resolve after chat returns sources?",
        "Preview checklist.",
        sources,
        hooks=hooks,
    )

    assert answer == "Preview excerpt must resolve this file after chat returns sources."


def test_maybe_answer_preview_from_sources_keeps_answer_when_doc_id_and_locator_are_already_present():
    hooks = _build_hooks()
    sources = [
        {
            "file": "preview-guide.pdf",
            "text": "Preview excerpt must resolve this file after chat returns sources.",
        }
    ]
    rich_answer = "Evidence package must include doc_id and preview_locator for every preview."

    answer = chat_source_answers.maybe_answer_preview_from_sources(
        "What should every evidence preview include?",
        rich_answer,
        sources,
        hooks=hooks,
    )

    assert answer == rich_answer


def test_maybe_answer_boundary_from_sources_compacts_folder_and_kb_sentences():
    hooks = _build_hooks()
    sources = [
        {
            "file": "workflow-boundary.md",
            "text": "Folder is organization only. Knowledge Base remains the authorization boundary.",
        }
    ]

    answer = chat_source_answers.maybe_answer_boundary_from_sources(
        "What remains the authorization boundary between folder and knowledge base?",
        "The KB is the boundary.",
        sources,
        hooks=hooks,
    )

    assert answer == "Folder is for organization only. Knowledge Base remains the authorization boundary."


def test_maybe_answer_scope_definition_from_sources_prefers_full_definition_sentence():
    hooks = _build_hooks()
    sources = [
        {
            "file": "一卡通.docx",
            "text": "非直属企业是指中储粮直属企业以外的参与中央事权粮食入库和出库业务的收储库点（包括租仓库点、委托库点）。",
        }
    ]

    answer = chat_source_answers.maybe_answer_scope_definition_from_sources(
        "非直属企业“一卡通”系统适用于哪些收储库点？",
        "非直属企业适用于收储库点。",
        sources,
        hooks=hooks,
    )

    assert "租仓库点" in answer
    assert "委托库点" in answer
