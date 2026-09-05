"""聊天问答中的短答案扩写、精确短语修复与答案片段回溯逻辑。"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable

SourceList = list[dict[str, Any]]
TokenizeText = Callable[[str], set[str]]
SourceTextIterator = Callable[[dict[str, Any]], list[str]]
QuestionPredicate = Callable[[str], bool]
AnswerPredicate = Callable[[str], bool]
NormalizeAnswer = Callable[[str], str]

_ANSWER_EXPANSION_HINTS = (
    "是",
    "仍然",
    "负责",
    "批准",
    "签署",
    "必须",
    "包含",
    " is ",
    " are ",
    "remains",
    "gives",
    "signs",
    "must include",
    "includes",
)
_EXACT_HYPHEN_TOKEN_RE = re.compile(r"\b[a-z][a-z0-9_]*(?:-[a-z0-9_]+){2,}\b", re.IGNORECASE)
_EXACT_SOURCE_PHRASES = (
    "OCR fallback",
    "Evidence preview",
    "evidence preview",
    "must not fabricate from outside memory",
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


@dataclass(frozen=True)
class SourceAnswerRepairHooks:
    """承载短答案扩写 / 精确短语修复所需依赖，降低 chat_service 耦合。"""

    tokenize_text: TokenizeText
    iter_source_support_texts: SourceTextIterator
    question_requests_preview_expansion: QuestionPredicate
    question_requests_entity: QuestionPredicate
    question_requests_exact_source_phrase: QuestionPredicate
    answer_is_brief_entity: AnswerPredicate
    answer_is_refusal_like: AnswerPredicate
    normalize_expanded_answer: NormalizeAnswer
    sentence_split_re: re.Pattern[str]
    clause_split_re: re.Pattern[str]
    answer_edge_strip_chars: str
    answer_trailing_punct_chars: str
    cjk_token_re: re.Pattern[str]
    ascii_token_re: re.Pattern[str]
    question_stopwords: set[str]


def contains_exact_phrase(answer_text: str, phrase: str, *, cjk_token_re: re.Pattern[str]) -> bool:
    """判断答案是否已包含精确短语。"""
    answer = str(answer_text or "")
    if not phrase:
        return True
    if cjk_token_re.search(phrase):
        return phrase in answer
    return phrase.lower() in answer.lower()


def maybe_expand_brief_answer_from_sources(
    question: str,
    answer_text: str,
    sources: SourceList,
    *,
    hooks: SourceAnswerRepairHooks,
) -> str:
    """当回答过短且来源可直接支撑时，用最小完整句替换孤立名词。"""
    if not sources or not hooks.answer_is_brief_entity(answer_text):
        return answer_text

    answer_core = str(answer_text or "").strip().strip(hooks.answer_edge_strip_chars)
    answer_core = answer_core.strip(hooks.answer_trailing_punct_chars)
    if not answer_core:
        return answer_text

    question_tokens = hooks.tokenize_text(question)
    answer_tokens = hooks.tokenize_text(answer_core)
    focus_question_tokens = question_tokens - answer_tokens
    best_candidate = ""
    best_score: tuple[int, ...] | None = None
    question_is_preview = hooks.question_requests_preview_expansion(question)
    question_requests_entity = hooks.question_requests_entity(question)

    for source in sources:
        for support_text in hooks.iter_source_support_texts(source):
            sentences = [segment.strip() for segment in hooks.sentence_split_re.split(support_text) if segment.strip()]
            for sentence in sentences:
                if answer_core not in sentence:
                    continue
                clause_candidates = [segment.strip() for segment in hooks.clause_split_re.split(sentence) if segment.strip()]
                for candidate in [*clause_candidates, sentence]:
                    if answer_core not in candidate:
                        continue
                    if len(candidate) <= len(answer_core) or len(candidate) > 96:
                        continue
                    candidate_tokens = hooks.tokenize_text(candidate)
                    if not candidate_tokens:
                        continue
                    question_overlap = len(focus_question_tokens & candidate_tokens)
                    if question_overlap <= 0 and not question_is_preview:
                        continue
                    preview_bonus = int(question_is_preview and "preview" in candidate.lower())
                    entity_bonus = int(question_requests_entity and question_overlap > 0)
                    hint_score = int(any(hint in candidate.lower() for hint in _ANSWER_EXPANSION_HINTS))
                    clause_preference = int(candidate != sentence)
                    score = (hint_score, preview_bonus, entity_bonus, clause_preference, question_overlap, -len(candidate))
                    if best_score is None or score > best_score:
                        best_candidate = candidate
                        best_score = score

    expanded = hooks.normalize_expanded_answer(best_candidate)
    return expanded or answer_text


def tokenize_source_term_support_text(
    text: str,
    *,
    ascii_token_re: re.Pattern[str],
    cjk_token_re: re.Pattern[str],
    question_stopwords: set[str],
) -> set[str]:
    """抽取精确短语选择用 token，避免词干变体被重复计分。"""
    tokens: set[str] = set()
    for raw in ascii_token_re.findall(str(text or "").lower()):
        token = raw.strip()
        if len(token) > 2 and token not in question_stopwords:
            tokens.add(token)

    for block in cjk_token_re.findall(str(text or "")):
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


def question_supports_source_term(question: str, term: str, *, hooks: SourceAnswerRepairHooks) -> bool:
    """判断问题是否足够指向某个 source 精确短语。"""
    question_tokens = tokenize_source_term_support_text(
        question,
        ascii_token_re=hooks.ascii_token_re,
        cjk_token_re=hooks.cjk_token_re,
        question_stopwords=hooks.question_stopwords,
    )
    term_tokens = tokenize_source_term_support_text(
        term,
        ascii_token_re=hooks.ascii_token_re,
        cjk_token_re=hooks.cjk_token_re,
        question_stopwords=hooks.question_stopwords,
    )
    if not question_tokens or not term_tokens:
        return False
    overlap = question_tokens & term_tokens
    return len(overlap) >= min(2, len(term_tokens))


def answer_covers_source_term_tokens(answer_text: str, term: str, *, hooks: SourceAnswerRepairHooks) -> bool:
    """判断回答是否已覆盖 source 短语的核心 token，避免非 exact 题被过度替换。"""
    answer_tokens = tokenize_source_term_support_text(
        answer_text,
        ascii_token_re=hooks.ascii_token_re,
        cjk_token_re=hooks.cjk_token_re,
        question_stopwords=hooks.question_stopwords,
    )
    term_tokens = tokenize_source_term_support_text(
        term,
        ascii_token_re=hooks.ascii_token_re,
        cjk_token_re=hooks.cjk_token_re,
        question_stopwords=hooks.question_stopwords,
    )
    if not answer_tokens or not term_tokens:
        return False
    return term_tokens.issubset(answer_tokens)


def extract_exact_source_terms(text: str) -> list[str]:
    """从 source 文本中抽取适合保真的精确 token/短语。"""
    raw = str(text or "")
    terms: list[str] = []
    for match in _EXACT_HYPHEN_TOKEN_RE.finditer(raw):
        token = match.group(0).strip()
        if token and token not in terms:
            terms.append(token)
    for phrase in _EXACT_SOURCE_PHRASES:
        if phrase in raw and phrase not in terms:
            terms.append(phrase)
    return terms


def source_sentence_for_term(term: str, sources: SourceList, *, hooks: SourceAnswerRepairHooks) -> str:
    """查找包含精确短语的最小 source 句子。"""
    for source in sources:
        for support_text in hooks.iter_source_support_texts(source):
            sentences = [segment.strip() for segment in hooks.sentence_split_re.split(support_text) if segment.strip()]
            for sentence in sentences:
                if term.lower() in sentence.lower():
                    return hooks.normalize_expanded_answer(sentence)
    return ""


def maybe_repair_exact_terms_from_sources(
    question: str,
    answer_text: str,
    sources: SourceList,
    *,
    hooks: SourceAnswerRepairHooks,
) -> str:
    """当模型改写破坏精确 token/短语时，从 source 中补回保真短语。"""
    if not sources or hooks.answer_is_refusal_like(answer_text):
        return answer_text

    question_tokens = hooks.tokenize_text(question)
    requests_exact_phrase = hooks.question_requests_exact_source_phrase(question)
    requests_preview_phrase = hooks.question_requests_preview_expansion(question)
    if requests_preview_phrase and contains_exact_phrase(answer_text, "preview", cjk_token_re=hooks.cjk_token_re):
        return answer_text

    repaired_terms: list[str] = []
    answer_tokens = hooks.tokenize_text(answer_text)
    for source in sources:
        source_text = "\n".join(hooks.iter_source_support_texts(source))
        source_tokens = hooks.tokenize_text(source_text)
        if question_tokens and not (question_tokens & source_tokens):
            continue
        for term in extract_exact_source_terms(source_text):
            if term in repaired_terms or contains_exact_phrase(answer_text, term, cjk_token_re=hooks.cjk_token_re):
                continue
            if not requests_exact_phrase and answer_covers_source_term_tokens(answer_text, term, hooks=hooks):
                continue
            term_tokens = hooks.tokenize_text(term)
            term_is_supported_by_question = requests_exact_phrase or question_supports_source_term(question, term, hooks=hooks)
            if requests_exact_phrase:
                term_is_usable = bool(term_is_supported_by_question or term_tokens & question_tokens or term_tokens & answer_tokens)
            else:
                term_is_usable = term_is_supported_by_question
            if term_tokens and not term_is_usable:
                continue
            repaired_terms.append(term)

    if not repaired_terms:
        return answer_text

    sentence = source_sentence_for_term(repaired_terms[0], sources, hooks=hooks)
    if sentence and len(sentence) <= 180:
        return sentence

    suffix = "；精确来源短语：" + "，".join(repaired_terms) + "。"
    return str(answer_text or "").rstrip() + suffix


def strip_answer_source_prefix(segment: str, sources: SourceList) -> tuple[str, str | None]:
    """去掉 answer 里显式的 `file:` 前缀，便于按实际内容回溯来源。"""
    normalized = str(segment or "").strip()
    lowered = normalized.lower()
    for source in sources:
        file_name = str(source.get("file") or source.get("title") or "").strip()
        if not file_name:
            continue
        prefix = f"{file_name}:".lower()
        if lowered.startswith(prefix):
            return normalized[len(prefix) :].lstrip(), file_name
    return normalized, None


def extract_answer_support_segments(
    answer_text: str,
    sources: SourceList,
    *,
    hooks: SourceAnswerRepairHooks,
) -> list[dict[str, str | None]]:
    """把最终 answer 拆成可回溯到 source 的最小事实片段。"""
    raw_segments = [line.strip() for line in str(answer_text or "").splitlines() if line.strip()]
    if len(raw_segments) <= 1:
        raw_segments = [segment.strip() for segment in hooks.sentence_split_re.split(str(answer_text or "")) if segment.strip()]

    extracted: list[dict[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()
    for raw_segment in raw_segments:
        cleaned, mentioned_file = strip_answer_source_prefix(raw_segment, sources)
        normalized = hooks.normalize_expanded_answer(cleaned)
        if not normalized:
            continue
        key = (normalized, mentioned_file)
        if key in seen:
            continue
        seen.add(key)
        extracted.append({"text": normalized, "mentioned_file": mentioned_file})
    return extracted
