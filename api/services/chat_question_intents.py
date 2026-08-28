"""聊天问答 question intent 与 identifier-gap 分类器。"""

from __future__ import annotations

import re
from typing import Any, Callable

from api.services import chat_contract_markers

TokenizeText = Callable[[str], set[str]]
SourceTextBuilder = Callable[[dict[str, Any]], str]
QuestionPredicate = Callable[[str], bool]
LiteralExtractor = Callable[[str], list[str]]

_ENTITY_QUESTION_MARKERS = (
    "what",
    "which",
    "who",
    "什么",
    "哪个",
    "谁",
    "哪位",
    "哪一个",
)
_PREVIEW_QUESTION_HINTS = (
    "preview",
    "resolve this file",
    "resolve after chat returns sources",
    "chat returns sources",
    "evidence preview",
)
_BOUNDARY_QUESTION_HINTS = (
    "boundary",
    "boundaries",
    "authorization",
    "folder",
    "knowledge base",
    "边界",
    "授权",
    "文件夹",
    "知识库",
)

_SCOPE_DEFINITION_LITERAL_MARKERS = (
    "适用于",
    "适用范围",
    "applies to",
)
_MULTI_FACT_MERGE_MARKERS = (
    "in one answer",
    "one answer",
    "同一答案",
    "同一个答案",
    "分别",
    "同时",
)
_SCOPE_DEFINITION_QUESTION_PATTERNS = (
    re.compile(r"(范围|包括).{0,12}(哪些|什么|哪类|哪种|哪些单位|哪些库点)"),
    re.compile(r"(哪些|什么|哪类|哪种).{0,12}(范围|包括|适用)"),
    re.compile(r"\bwhat(?:'s| is)?\s+the\s+scope\b", re.IGNORECASE),
    re.compile(r"\bscope\s+of\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+does\b.{0,40}\binclude\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+is\s+included\b", re.IGNORECASE),
    re.compile(r"\bwhich\b.{0,40}\bare\s+included\b", re.IGNORECASE),
)
_EXACT_PHRASE_QUESTION_HINTS = (
    "exact",
    "unique",
    "passcode",
    "what does",
    "what should",
    "what must",
    "原文",
    "精确",
    "唯一",
)
_IDENTIFIER_LIKE_TOKENS = {
    "cab",
    "checksum",
    "doc_id",
    "passcode",
    "preview_locator",
    "ticket",
    "token",
    "uri",
    "url",
}
_IDENTIFIER_FIELD_RULES = (
    {
        "question_terms": frozenset({"cab", "ticket"}),
        "support_terms": frozenset({"cab", "ticket"}),
        "support_patterns": (re.compile(r"\bcab[-\s]?[a-z0-9]+\b", re.IGNORECASE),),
    },
    {
        "question_terms": frozenset({"bridge", "url"}),
        "support_terms": frozenset({"url", "uri", "link", "http", "https", "address"}),
        "support_patterns": (),
    },
    {
        "question_terms": frozenset({"checksum", "token"}),
        "support_terms": frozenset({"checksum", "token", "hash", "sha", "sha256", "md5"}),
        "support_patterns": (),
    },
    {
        "question_terms": frozenset({"pager", "rotation"}),
        "support_terms": frozenset({"id", "identifier", "pager", "rotation"}),
        "support_patterns": (
            re.compile(r"\brotation\b.{0,20}\bid\b", re.IGNORECASE),
            re.compile(r"\bid\b.{0,20}\brotation\b", re.IGNORECASE),
        ),
    },
    {
        "question_terms": frozenset({"room", "number"}),
        "support_terms": frozenset({"room", "number", "no", "no.", "#", "房间", "会议室", "编号", "号"}),
        "support_patterns": (
            re.compile(r"\broom\b.{0,12}(?:number|#|no\.?)?\s*[a-z0-9-]+", re.IGNORECASE),
        ),
    },
)
_TARGETED_FACT_SPLIT_PATTERNS = (
    re.compile(r",\s+and\s+(?=(?:who|what|which|does|do|may|must|should|can|is|are|when)\b)", re.IGNORECASE),
    re.compile(r",\s+or\s+(?=(?:who|what|which|does|do|may|must|should|can|is|are|when)\b)", re.IGNORECASE),
    re.compile(r"\sand\s+(?=(?:who|what|which|does|do|may|must|should|can|is|are|when)\b)", re.IGNORECASE),
    re.compile(r"\sor\s+(?=(?:who|what|which|does|do|may|must|should|can|is|are|when)\b)", re.IGNORECASE),
)
_TARGETED_SUBQUESTION_START_RE = re.compile(
    r"\b(who|what|which|does|do|may|must|should|can|is|are|when|where|whether)\b",
    re.IGNORECASE,
)
_TARGETED_FACT_MARKERS = (
    "who is",
    "who gives",
    "who approves",
    "who signs",
    "who owns",
    "who handles",
    "which value",
    "what value",
    "which field",
    "which fields",
    "what field",
    "what fields",
    "response field",
    "response fields",
    "what remains",
    "what must",
    "stay aligned",
    "scope type",
    "checkpoint time",
    "knowledge base level",
    "permission wall",
    "authorization boundary",
    "approver",
    "confirmer",
    "rollback owner",
    "on-call manager",
    "escalation interval",
    "sign deadline",
    "doc_id",
    "excerpt",
    "preview_locator",
    "requested_kb_ids",
    "effective_kb_ids",
)
_TARGETED_CROSS_SOURCE_MARKERS = (
    "who ",
    "which value",
    "what remains",
    "what field",
    "authorization boundary",
    "access control",
)
_TARGETED_PREFIX_HINTS = (
    "according to",
    "across",
    "compare",
    "from",
    "in the",
    "in ",
    "on the",
    "on ",
    "under",
    "board",
    "whiteboard",
    "matrix",
    "note",
    "manual",
    "contract",
    "guide",
)
_TARGETED_CJK_ITEM_SPLIT_RE = re.compile(r"\s*(?:和|及|与|、)\s*")
_TARGETED_CJK_PARALLEL_SUFFIX_RE = re.compile(r"分别\s*(?P<suffix>是?谁|由谁)")
_TARGETED_CJK_ROLE_HINTS = (
    "approver",
    "confirmer",
    "rollback owner",
    "sign-off owner",
    "manager",
    "commander",
    "owner",
    "审批人",
    "批准人",
    "确认人",
    "负责人",
    "经理",
    "指挥",
)
_TARGETED_EXACT_HINTS = (
    "which field",
    "which fields",
    "what field",
    "what fields",
    "response field",
    "response fields",
    "stay aligned",
    "echo",
    "carry",
    "resolve back",
    "preview excerpt",
)
_RECENT_DOC_PAIR_EN_RE = re.compile(r"\b(?:those|the)\s+two\s+(?:pdfs?|docs?|documents?)\b", re.IGNORECASE)
_RECENT_DOC_ACTION_EN_RE = re.compile(r"\b(?:we|i)\s+(?:just\s+)?(?:opened|viewed|looked\s+at|read)\b|\b(?:just|recently)\s+(?:opened|viewed|looked\s+at|read)\b", re.IGNORECASE)
_RECENT_DOC_PAIR_CJK_RE = re.compile(r"(?:刚才|前面|上面).{0,8}(?:看的|打开的|那|这)?(?:两份|两个).{0,6}(?:文档|资料|pdf|PDF)")
_TARGETED_MULTI_FACT_PROMPT_RE = re.compile(r"\b(?:who|what|which|when|where|how many)\b", re.IGNORECASE)
_TARGETED_CJK_FACT_MARKERS = (
    "谁",
    "哪位",
    "哪个",
    "什么",
    "几分钟",
    "多久",
    "何时",
    "多少",
)


def question_requests_entity(question: str) -> bool:
    """判断问题是否是“什么/哪个/谁”类实体识别问题。"""
    lowered = str(question or "").lower()
    return any(marker in lowered for marker in _ENTITY_QUESTION_MARKERS)



def question_requests_preview_expansion(question: str) -> bool:
    """判断问题是否在问 preview 该如何落到 source 原句。"""
    lowered = str(question or "").lower()
    return any(hint in lowered for hint in _PREVIEW_QUESTION_HINTS)



def question_requests_boundary_answer(question: str) -> bool:
    """判断问题是否在问知识库/文件夹/授权边界关系。"""
    raw = str(question or "")
    lowered = raw.lower()
    has_boundary_hint = any(hint in lowered or hint in raw for hint in _BOUNDARY_QUESTION_HINTS)
    has_explicit_relation = "authorization boundary" in lowered or "授权边界" in raw
    has_folder_hint = "folder" in lowered or "文件夹" in raw
    has_kb_hint = "knowledge base" in lowered or "知识库" in raw
    return has_boundary_hint and (has_explicit_relation or (has_folder_hint and has_kb_hint))



def question_requests_summary_answer(question: str) -> bool:
    """识别“一句话总结/summary”类问题。"""
    raw = str(question or "")
    lowered = raw.lower()
    return any(marker in lowered for marker in ("summary", "summarize", "in one sentence")) or any(
        marker in raw for marker in ("一句话", "总结", "概括")
    )



def question_benefits_from_brief_answer_expansion(
    question: str,
    *,
    question_requests_preview_expansion: QuestionPredicate,
    question_requests_summary_answer: QuestionPredicate,
    question_requests_multi_fact_merge: QuestionPredicate,
    question_requests_targeted_fact_answer: QuestionPredicate,
) -> bool:
    """仅在通用事实问答里启用短答案扩写，避免压过更具体的题型修复器。"""
    return not any(
        (
            question_requests_preview_expansion(question),
            question_requests_summary_answer(question),
            question_requests_multi_fact_merge(question),
            question_requests_targeted_fact_answer(question),
        )
    )



def question_requests_scope_definition(question: str) -> bool:
    """判断问题是否在问范围/适用对象/定义句。"""
    raw = str(question or "")
    lowered = raw.lower()

    if any(marker in raw or marker in lowered for marker in _SCOPE_DEFINITION_LITERAL_MARKERS):
        return True

    return any(pattern.search(raw) or pattern.search(lowered) for pattern in _SCOPE_DEFINITION_QUESTION_PATTERNS)



def question_requests_multi_fact_merge(question: str) -> bool:
    """判断问题是否显式要求把多个 source 事实合并到同一答案。"""
    raw = str(question or "")
    lowered = raw.lower()
    return any(marker in raw or marker in lowered for marker in _MULTI_FACT_MERGE_MARKERS)



def question_requests_exact_source_phrase(question: str) -> bool:
    """判断问题是否倾向索要唯一/精确来源短语。"""
    lowered = str(question or "").lower()
    return any(hint in lowered for hint in _EXACT_PHRASE_QUESTION_HINTS)



def matched_identifier_field_rules(question: str, *, tokenize_text: TokenizeText) -> list[dict[str, Any]]:
    """抽取问题中命中的高风险字段规则，避免把主题词误当成字段证据。"""
    question_tokens = tokenize_text(question)
    return [rule for rule in _IDENTIFIER_FIELD_RULES if rule["question_terms"].issubset(question_tokens)]



def question_requests_identifier_like_field(question: str, *, tokenize_text: TokenizeText) -> bool:
    """识别 ticket/url/token 等字段型问题。"""
    question_tokens = tokenize_text(question)
    return bool(matched_identifier_field_rules(question, tokenize_text=tokenize_text) or (_IDENTIFIER_LIKE_TOKENS & question_tokens))



def source_supports_identifier_rule(source_blob: str, source_terms: set[str], rule: dict[str, Any]) -> bool:
    """判断单条 source 是否包含字段级证据，而不是只共享主题词。"""
    support_terms = set(rule.get("support_terms") or ())
    if support_terms and support_terms & source_terms:
        return True
    for pattern in rule.get("support_patterns") or ():
        if pattern.search(source_blob):
            return True
    return False



def sources_support_identifier_like_field(
    question: str,
    sources: list[dict[str, Any]],
    *,
    tokenize_text: TokenizeText,
    build_source_text_blob: SourceTextBuilder,
) -> bool:
    """如果问题显式要求标识字段，至少一条来源应包含相应字段证据。"""
    matched_rules = matched_identifier_field_rules(question, tokenize_text=tokenize_text)
    if matched_rules:
        for source in sources:
            source_blob = build_source_text_blob(source)
            source_terms = tokenize_text(source_blob)
            if any(source_supports_identifier_rule(source_blob, source_terms, rule) for rule in matched_rules):
                return True
        return False

    requested_terms = _IDENTIFIER_LIKE_TOKENS & tokenize_text(question)
    if not requested_terms:
        return True
    for source in sources:
        source_terms = tokenize_text(build_source_text_blob(source))
        if requested_terms & source_terms:
            return True
    return False



def question_requests_negative_contract(question: str) -> bool:
    """识别 refusal / active-scope / no-fabrication 这类负向契约问题。"""
    return chat_contract_markers.question_requests_negative_contract(question)

def split_parallel_cjk_targeted_fact_question(question: str) -> list[str]:
    """识别“X 和 Y 分别是谁/由谁负责”这类中文并列角色问句。"""
    raw = str(question or "").strip().strip("?？")
    if "分别" not in raw:
        return []

    suffix_match = _TARGETED_CJK_PARALLEL_SUFFIX_RE.search(raw)
    if suffix_match is None:
        return []

    focus = re.split(r"[，,:：]\s*", raw[: suffix_match.start()])[-1].strip()
    if not focus:
        return []

    items = [segment.strip() for segment in _TARGETED_CJK_ITEM_SPLIT_RE.split(focus) if segment.strip()]
    if len(items) < 2:
        return []

    suffix = suffix_match.group("suffix").strip()
    if not any(any(hint in item.lower() or hint in item for hint in _TARGETED_CJK_ROLE_HINTS) for item in items):
        return []

    normalized_parts: list[str] = []
    for item in items:
        normalized = f"{item}{suffix}".strip(" ,，；;")
        if normalized and normalized not in normalized_parts:
            normalized_parts.append(normalized)
    return normalized_parts if len(normalized_parts) >= 2 else []



def question_mentions_recent_doc_pair(question: str) -> bool:
    """判断问题是否在引用“刚打开/刚看的两份文档”这类历史双文档上下文。"""
    raw = str(question or "")
    lowered = raw.lower()
    has_recent_english_pair = bool(_RECENT_DOC_PAIR_EN_RE.search(lowered) and _RECENT_DOC_ACTION_EN_RE.search(lowered))
    has_recent_cjk_pair = bool(_RECENT_DOC_PAIR_CJK_RE.search(raw))
    return has_recent_english_pair or has_recent_cjk_pair


def question_requests_targeted_fact_answer(
    question: str,
    *,
    extract_literal_question_terms: LiteralExtractor | None = None,
) -> bool:
    """识别需要按子问题重组精确事实的问法。"""
    raw = str(question or "")
    lowered = raw.lower()
    if not lowered:
        return False

    if split_parallel_cjk_targeted_fact_question(question):
        return True

    has_targeted_split_signal = any(pattern.search(raw) for pattern in _TARGETED_FACT_SPLIT_PATTERNS)
    recent_doc_pair = question_mentions_recent_doc_pair(question)
    if not has_targeted_split_signal and not recent_doc_pair:
        return False

    if question_requests_negative_contract(question):
        return True

    literal_terms = list(extract_literal_question_terms(question) if extract_literal_question_terms else ())
    if literal_terms and any(marker in lowered for marker in ("authorization boundary", "access control", "knowledge-base level", "knowledge base level")):
        return True

    if any(marker in lowered for marker in _TARGETED_FACT_MARKERS):
        return True

    if recent_doc_pair:
        cjk_fact_hits = sum(raw.count(marker) for marker in _TARGETED_CJK_FACT_MARKERS if marker in raw)
        english_fact_hits = len(_TARGETED_MULTI_FACT_PROMPT_RE.findall(raw))
        has_clause_split = any(separator in raw for separator in ("，", ",", "；", ";"))
        if has_clause_split and (cjk_fact_hits >= 2 or english_fact_hits >= 2):
            return True

    return question_prefers_cross_source_fact_assembly(question) and any(marker in lowered for marker in _TARGETED_CROSS_SOURCE_MARKERS)



def question_may_need_exact_term_repair(
    question: str,
    *,
    question_requests_exact_source_phrase: QuestionPredicate,
    question_requests_preview_expansion: QuestionPredicate,
    question_requests_boundary_answer: QuestionPredicate,
    question_requests_scope_definition: QuestionPredicate,
    question_requests_targeted_fact_answer: QuestionPredicate,
    question_requests_identifier_like_field: QuestionPredicate,
) -> bool:
    """判断问题是否值得进入精确短语修复分支，避免 plain targeted 题无差别叠加 exact repair。"""
    if any(
        predicate(question)
        for predicate in (
            question_requests_exact_source_phrase,
            question_requests_preview_expansion,
            question_requests_boundary_answer,
            question_requests_scope_definition,
        )
    ):
        return True

    if not question_requests_targeted_fact_answer(question):
        return False

    lowered = str(question or "").lower()
    return question_requests_identifier_like_field(question) or any(hint in lowered for hint in _TARGETED_EXACT_HINTS)


def question_prefers_cross_source_fact_assembly(question: str) -> bool:
    """判断问题是否明确要求跨文档/跨看板拼装事实。"""
    lowered = str(question or "").lower()
    return "across" in lowered or "compare" in lowered or question_mentions_recent_doc_pair(question)



def normalize_targeted_subquestion(subquestion: str) -> str:
    """裁掉 Compare/On/In/Under 等共享前缀，只保留真正的子问题子句。"""
    raw = str(subquestion or "").strip().strip("?？").strip(" ,，；;")
    if not raw:
        return ""

    colon_parts = re.split(r"[:：]\s*", raw, maxsplit=1)
    if len(colon_parts) == 2 and _TARGETED_SUBQUESTION_START_RE.search(colon_parts[1]):
        raw = colon_parts[1].strip()

    match = _TARGETED_SUBQUESTION_START_RE.search(raw)
    if match is not None and match.start() > 0:
        prefix = raw[: match.start()].lower()
        if any(hint in prefix for hint in _TARGETED_PREFIX_HINTS):
            raw = raw[match.start() :].strip()

    return raw.strip(" ,，；;")



def split_targeted_fact_question(
    question: str,
    *,
    question_requests_targeted_fact_answer: QuestionPredicate,
) -> list[str]:
    """按事实子问题切开复合问句，并移除共享前缀。"""
    raw = str(question or "").strip().strip("?？")
    if not raw or not question_requests_targeted_fact_answer(raw):
        return []

    cjk_parts = split_parallel_cjk_targeted_fact_question(raw)
    if cjk_parts:
        return cjk_parts

    parts = [raw]
    for pattern in _TARGETED_FACT_SPLIT_PATTERNS:
        next_parts: list[str] = []
        for part in parts:
            split_parts = [segment.strip(" ,，；;") for segment in pattern.split(part) if segment.strip(" ,，；;")]
            next_parts.extend(split_parts or [part])
        parts = next_parts

    normalized_parts: list[str] = []
    for part in parts:
        normalized = normalize_targeted_subquestion(part)
        if normalized and normalized not in normalized_parts:
            normalized_parts.append(normalized)
    return normalized_parts if len(normalized_parts) >= 2 else []

