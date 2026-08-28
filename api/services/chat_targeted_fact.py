"""targeted-fact 候选抽取、评分与答案组装辅助逻辑。"""

from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Any, Callable
from api.services import chat_negative_contract_answers

IterBoundarySupportTexts = Callable[[dict[str, Any]], list[str]]
NormalizeExpandedAnswer = Callable[[str], str]
TokenizeText = Callable[[str], set[str]]
NormalizeTargetedSubquestion = Callable[[str], str]
ExtractLiteralQuestionTerms = Callable[[str], list[str]]
QuestionPredicate = Callable[[str], bool]
IterTargetedAnswerCandidates = Callable[[dict[str, Any]], list[str]]
SplitTargetedFactQuestion = Callable[[str], list[str]]
DedupeSourcesByFile = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]


@dataclass(frozen=True)
class TargetedFactHooks:
    """承载 targeted-fact 辅助逻辑所需依赖，避免 chat_service 直接耦合实现细节。"""

    iter_boundary_support_texts: IterBoundarySupportTexts
    normalize_expanded_answer: NormalizeExpandedAnswer
    tokenize_text: TokenizeText
    normalize_targeted_subquestion: NormalizeTargetedSubquestion
    extract_literal_question_terms: ExtractLiteralQuestionTerms
    question_requests_negative_contract: QuestionPredicate
    question_requests_summary_answer: QuestionPredicate
    question_prefers_cross_source_fact_assembly: QuestionPredicate
    split_targeted_fact_question: SplitTargetedFactQuestion
    dedupe_sources_by_file: DedupeSourcesByFile
    iter_targeted_answer_candidates: IterTargetedAnswerCandidates
    sentence_split_re: re.Pattern[str]
    clause_split_re: re.Pattern[str]
    time_value_re: re.Pattern[str]
    literal_path_re: re.Pattern[str]


_TARGETED_STRUCTURAL_FIELD_KEYS = (
    "has_requested_kb_ids",
    "has_effective_kb_ids",
    "has_requested_scope_type",
    "has_effective_scope_type",
    "has_doc_id",
    "has_preview_locator",
    "has_excerpt",
)
_TARGETED_RECOGNIZED_METADATA_MARKERS = ("title", "source", "isolation_level")
_TARGETED_ROLE_LABEL_MARKERS = (
    ("approver", "approver"),
    ("审批人", "approver"),
    ("批准人", "approver"),
    ("confirmer", "confirmer"),
    ("确认人", "confirmer"),
    ("rollback owner", "rollback owner"),
    ("回滚负责人", "rollback owner"),
    ("on-call manager", "on-call manager"),
    ("值班经理", "on-call manager"),
    ("incident commander", "incident commander"),
    ("指挥", "incident commander"),
    ("owner", "owner"),
    ("负责人", "owner"),
)
_TARGETED_SUPPORT_BONUS_KEYS = (
    "role_bonus",
    "time_bonus",
    "escalation_bonus",
    "effective_field_bonus",
    "alignment_bonus",
    "effective_boundary_bonus",
    "effective_scope_boundary_bonus",
    "effective_kb_level_bonus",
    "effective_org_object_bonus",
    "effective_path_bonus",
    "effective_scope_type_bonus",
    "effective_preview_bonus",
    "effective_negative_bonus",
    "boundary_object_bonus",
)
_TARGETED_SEMANTIC_BONUS_KEYS = (
    "role_bonus",
    "time_bonus",
    "escalation_bonus",
    "effective_field_bonus",
    "alignment_bonus",
    "effective_boundary_bonus",
    "effective_scope_boundary_bonus",
    "effective_kb_level_bonus",
    "effective_org_object_bonus",
    "effective_path_bonus",
    "effective_scope_type_bonus",
    "effective_preview_bonus",
    "effective_negative_bonus",
    "exact_role_phrase_bonus",
    "specific_label_bonus",
    "approval_phrase_bonus",
    "sign_phrase_bonus",
)
_TARGETED_STRUCTURAL_PRIORITY_BONUS_KEYS = (
    "effective_field_bonus",
    "effective_scope_type_bonus",
    "effective_preview_bonus",
    "effective_scope_boundary_bonus",
    "effective_kb_level_bonus",
    "effective_path_bonus",
)
_TARGETED_NUMERIC_VALUE_RE = re.compile(
    r"\b\d{1,2}:\d{2}\b|\b\d+\s*(?:minutes?|minute|mins?|hours?|hour)\b"
)


def _sum_targeted_score_keys(values: dict[str, Any], keys: tuple[str, ...]) -> int:
    """按 key 列表聚合 bool/int 型评分片段，减少散落的手工加总。"""
    return sum(int(values[key]) for key in keys)


def _max_targeted_score_keys(values: dict[str, int], keys: tuple[str, ...]) -> int:
    """返回指定评分 key 的最大值，供最低支撑信号判断复用。"""
    return max(int(values[key]) for key in keys)


def _collect_targeted_role_labels(
    normalized_subquestion: str, subquestion_lower: str
) -> list[str]:
    """把中英文角色问法统一归一到候选句里要命中的 label。"""
    return [
        candidate_marker
        for question_marker, candidate_marker in _TARGETED_ROLE_LABEL_MARKERS
        if question_marker in normalized_subquestion
        or question_marker in subquestion_lower
    ]


def _targeted_candidate_has_minimum_support(
    context: dict[str, Any], bonuses: dict[str, int]
) -> bool:
    """过滤只有词面重叠、没有语义/结构支撑的 targeted candidate。"""
    return not (
        context["overlap"] <= 0
        and context["literal_bonus"] <= 0
        and context["focus_token_bonus"] <= 0
        and _max_targeted_score_keys(bonuses, _TARGETED_SUPPORT_BONUS_KEYS) <= 0
    )


def _compute_targeted_semantic_bonus(bonuses: dict[str, int]) -> int:
    """聚合排序时真正参与语义贴题度比较的 bonus。"""
    return _sum_targeted_score_keys(bonuses, _TARGETED_SEMANTIC_BONUS_KEYS)


def _compute_targeted_structural_priority_score(bonuses: dict[str, int]) -> int:
    """聚合字段/preview/scope 等结构化优先级，稳定 tie-break。"""
    return _sum_targeted_score_keys(bonuses, _TARGETED_STRUCTURAL_PRIORITY_BONUS_KEYS)


def iter_targeted_answer_candidates(
    source: dict[str, Any], *, hooks: TargetedFactHooks
) -> list[str]:
    """从 source 中提取适合多事实重组的行/句/短子句候选。"""
    _iter_boundary_support_texts = hooks.iter_boundary_support_texts
    _SENTENCE_SPLIT_RE = hooks.sentence_split_re
    _CLAUSE_SPLIT_RE = hooks.clause_split_re
    candidates: list[str] = []
    seen: set[str] = set()
    for support_text in _iter_boundary_support_texts(source):
        for raw_line in str(support_text or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            normalized_line = line.lstrip("-*• ").strip()
            if normalized_line and normalized_line not in seen:
                seen.add(normalized_line)
                candidates.append(normalized_line)
            sentences = [
                segment.strip().rstrip("。！？!?;；.")
                for segment in _SENTENCE_SPLIT_RE.split(normalized_line)
                if segment.strip()
            ]
            for sentence in sentences:
                if sentence not in seen:
                    seen.add(sentence)
                    candidates.append(sentence)
            clauses = [
                segment.strip().rstrip("。！？!?;；.")
                for segment in _CLAUSE_SPLIT_RE.split(normalized_line)
                if segment.strip()
            ]
            for clause in clauses:
                if clause and clause not in seen:
                    seen.add(clause)
                    candidates.append(clause)
    return candidates


def _build_targeted_question_context(
    question: str, subquestion: str, candidate: str, *, hooks: TargetedFactHooks
) -> dict[str, Any] | None:
    """归一化 targeted-fact 打分所需的 question/candidate 上下文。"""
    candidate_text = str(candidate or "").strip()
    candidate_lower = candidate_text.lower()
    if not candidate_lower:
        return None
    normalized_subquestion = (
        hooks.normalize_targeted_subquestion(subquestion)
        or str(subquestion or "").strip()
    )
    subquestion_lower = normalized_subquestion.lower()
    subquestion_normalized = subquestion_lower.replace("-", " ")
    question_text = str(question or "")
    question_lower = question_text.lower()
    question_normalized = question_lower.replace("-", " ")
    candidate_tokens = hooks.tokenize_text(candidate_text)
    subquestion_tokens = hooks.tokenize_text(normalized_subquestion)
    question_tokens = hooks.tokenize_text(question_text)
    literal_terms = hooks.extract_literal_question_terms(
        normalized_subquestion or question_text
    )
    focus_tokens = {
        token
        for token in subquestion_tokens
        if "_" in token or "-" in token or len(token) >= 12
    }
    return {
        "candidate_text": candidate_text,
        "candidate_lower": candidate_lower,
        "normalized_subquestion": normalized_subquestion,
        "subquestion_lower": subquestion_lower,
        "subquestion_normalized": subquestion_normalized,
        "question_text": question_text,
        "question_lower": question_lower,
        "question_normalized": question_normalized,
        "candidate_tokens": candidate_tokens,
        "subquestion_tokens": subquestion_tokens,
        "question_tokens": question_tokens,
        "overlap": len(subquestion_tokens & candidate_tokens),
        "question_overlap": len(question_tokens & candidate_tokens),
        "literal_terms": literal_terms,
        "literal_bonus": sum(
            int(term.lower() in candidate_lower) for term in literal_terms
        ),
        "focus_token_bonus": len(focus_tokens & candidate_tokens),
        "has_time_value": bool(hooks.time_value_re.search(candidate_text)),
        "sentence_count": len(
            [
                segment
                for segment in hooks.sentence_split_re.split(candidate_text)
                if segment.strip()
            ]
        ),
        "contains_value_separator": any(
            token in candidate_text for token in (":", "：")
        )
        or any(
            phrase in candidate_lower
            for phrase in (
                " is ",
                " are ",
                " remain ",
                " remains ",
                " within ",
                " before ",
                " only",
                "must not",
                "must echo",
                "must include",
                "should carry",
            )
        ),
        "has_name_like_value": re.search(
            r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", candidate_text
        )
        is not None,
    }


def _contains_targeted_marker(text: str, markers: tuple[str, ...]) -> bool:
    """判断 text 是否命中任一 targeted marker。"""
    return any(marker in text for marker in markers)


def _build_targeted_role_question_signals(
    normalized_subquestion: str,
    subquestion_lower: str,
    subquestion_normalized: str,
) -> dict[str, bool]:
    """抽取角色/审批相关的 targeted 子问题信号。"""
    asks_sign_role = _contains_targeted_marker(
        subquestion_normalized,
        ("who signs", "who signed", "who sign", "谁签署", "谁签字", "签署人", "签字人"),
    )
    asks_role = (
        asks_sign_role
        or _contains_targeted_marker(
            subquestion_lower,
            (
                "approver",
                "approve",
                "approval",
                "sign-off",
                "confirmer",
                "owner",
                "manager",
                "commander",
                "lead",
                "owns",
                "handles",
            ),
        )
        or _contains_targeted_marker(
            normalized_subquestion,
            ("审批人", "批准人", "确认人", "负责人", "经理", "指挥"),
        )
    )
    return {
        "asks_sign_role": asks_sign_role,
        "asks_role": asks_role,
        "asks_approval_role": asks_role
        and (
            _contains_targeted_marker(
                subquestion_lower, ("approval", "approve", "approver")
            )
            or _contains_targeted_marker(normalized_subquestion, ("批准", "审批"))
        ),
    }


def _build_targeted_time_question_signals(
    subquestion_lower: str,
    subquestion_normalized: str,
    *,
    asks_role: bool,
) -> dict[str, bool]:
    """抽取 time / deadline / escalation 相关信号。"""
    return {
        "asks_escalation": _contains_targeted_marker(
            subquestion_lower,
            ("escalation", "escalate", "interval", "p1", "sev1", "incident"),
        ),
        "asks_time_value": _contains_targeted_marker(
            subquestion_lower,
            ("time", "deadline", "checkpoint", "interval", "minutes", "minute"),
        )
        or (
            not asks_role
            and _contains_targeted_marker(subquestion_lower, ("signed", "sign"))
        ),
        "asks_deadline_value": _contains_targeted_marker(
            subquestion_normalized,
            ("deadline", "checkpoint", "signed", "sign deadline", "closing time"),
        ),
        "asks_interval_value": _contains_targeted_marker(
            subquestion_lower, ("interval", "within", "minutes", "minute")
        ),
    }


def _build_targeted_scope_question_signals(
    subquestion_lower: str,
    subquestion_normalized: str,
) -> dict[str, bool]:
    """抽取 boundary / scope / path 相关信号。"""
    return {
        "asks_boundary": _contains_targeted_marker(
            subquestion_lower,
            (
                "authorization boundary",
                "permission wall",
                "access-control boundary",
                "access control boundary",
            ),
        ),
        "asks_kb_level": _contains_targeted_marker(
            subquestion_normalized,
            (
                "knowledge base level",
                "access control",
                "access control boundary",
                "real permission wall",
            ),
        ),
        "asks_org_object": "organization object" in subquestion_lower,
        "asks_internal_path": _contains_targeted_marker(
            subquestion_lower,
            ("internal filing path", "internal organization path", "folder path"),
        ),
        "asks_scope_type": "scope type" in subquestion_lower
        or "remain in force" in subquestion_lower,
        "asks_scope_boundary": _contains_targeted_marker(
            subquestion_lower,
            (
                "expand beyond",
                "expand outside",
                "stay inside",
                "remain inside",
                "outside the requested",
                "beyond the requested",
                "beyond requested",
            ),
        )
        or (
            "effective scope" in subquestion_lower
            and _contains_targeted_marker(
                subquestion_lower, ("requested kb", "requested knowledge base")
            )
        ),
    }


def _build_targeted_field_preview_question_signals(
    question_lower: str,
    subquestion_lower: str,
    subquestion_normalized: str,
) -> dict[str, bool]:
    """抽取字段对齐与 preview 相关信号。"""
    return {
        "asks_field_list": _contains_targeted_marker(
            subquestion_normalized,
            (
                "id field",
                "id fields",
                "which field",
                "which fields",
                "which two fields",
                "what field",
                "what fields",
                "response field",
                "response fields",
                "every answer carry",
                "must every answer carry",
                "stay aligned",
                "should echo",
                "must echo",
            ),
        ),
        "asks_exactly_two_fields": "two fields" in subquestion_normalized
        or "two id fields" in subquestion_normalized,
        "asks_alignment_field": _contains_targeted_marker(
            subquestion_normalized,
            (
                "stay aligned",
                "aligned with",
                "mirrors",
                "mirror",
                "cited paragraph",
                "cited evidence",
            ),
        ),
        "asks_preview_resolution": _contains_targeted_marker(
            subquestion_normalized,
            (
                "resolve back",
                "resolvable",
                "preview excerpt",
                "original pdf chunk",
                "original chunk",
            ),
        ),
        "asks_preview_contract": _contains_targeted_marker(
            subquestion_normalized,
            (
                "evidence output",
                "evidence field",
                "evidence fields",
                "preview",
                "resolvable",
                "resolve back",
                "ocr-derived assets",
                "ocr derived assets",
            ),
        )
        or (
            "evidence board" in question_lower
            and _contains_targeted_marker(
                subquestion_lower, ("what else", "what fields", "which fields")
            )
        ),
    }


def _build_targeted_question_signals(
    context: dict[str, Any], *, hooks: TargetedFactHooks
) -> dict[str, bool]:
    """抽取 targeted 子问题意图信号，便于后续 bonus/penalty 分层处理。"""
    signals = _build_targeted_role_question_signals(
        context["normalized_subquestion"],
        context["subquestion_lower"],
        context["subquestion_normalized"],
    )
    signals.update(
        _build_targeted_time_question_signals(
            context["subquestion_lower"],
            context["subquestion_normalized"],
            asks_role=signals["asks_role"],
        )
    )
    signals.update(
        _build_targeted_scope_question_signals(
            context["subquestion_lower"],
            context["subquestion_normalized"],
        )
    )
    signals.update(
        _build_targeted_field_preview_question_signals(
            context["question_lower"],
            context["subquestion_lower"],
            context["subquestion_normalized"],
        )
    )
    signals["asks_negative_contract"] = hooks.question_requests_negative_contract(
        context["question_text"]
    )
    return signals


def _extract_targeted_candidate_features(
    context: dict[str, Any], *, hooks: TargetedFactHooks
) -> dict[str, Any]:
    """抽取 candidate 中的结构化字段、边界与 preview 等显式特征。"""
    candidate_text = context["candidate_text"]
    candidate_lower = context["candidate_lower"]
    return {
        "has_requested_kb_ids": "requested_kb_ids" in candidate_lower,
        "has_effective_kb_ids": "effective_kb_ids" in candidate_lower,
        "has_alignment_phrase": any(
            marker in candidate_lower
            for marker in ("align", "aligned", "mirror", "mirrors", "echo", "echoes")
        ),
        "has_requested_scope_type": "requested_scope_type" in candidate_lower,
        "has_effective_scope_type": "effective_scope_type" in candidate_lower,
        "has_single_kb": "single_kb" in candidate_lower,
        "has_knowledge_base_level": any(
            marker in candidate_lower
            for marker in (
                "knowledge-base level",
                "knowledge base level",
                "access control",
            )
        ),
        "has_authorization_boundary": "authorization boundary" in candidate_lower,
        "has_org_object": any(
            marker in candidate_lower
            for marker in (
                "organization object",
                "organizational object",
                "organizational objects",
            )
        ),
        "has_internal_path": bool(hooks.literal_path_re.search(candidate_text))
        or any(
            marker in candidate_lower
            for marker in ("internal organization path", "internal filing path")
        ),
        "has_doc_id": "doc_id" in candidate_lower,
        "has_preview_locator": "preview_locator" in candidate_lower,
        "has_excerpt": "excerpt" in candidate_lower,
        "has_preview_resolution": any(
            marker in candidate_lower
            for marker in (
                "resolve back",
                "resolvable",
                "preview excerpt",
                "originating document",
                "original document",
                "cited evidence",
                "original pdf chunk",
                "pdf chunk",
                "original chunk",
            )
        ),
        "has_no_confirmable": "no confirmable information" in candidate_lower,
        "has_active_scope": "active knowledge base" in candidate_lower
        or "active pdf knowledge base" in candidate_lower,
        "has_no_fabricated_memory": any(
            marker in candidate_lower
            for marker in (
                "must not fabricate",
                "no fabricated memory",
                "outside memory",
            )
        ),
    }


def _compute_targeted_phrase_bonuses(
    context: dict[str, Any], signals: dict[str, bool]
) -> dict[str, int]:
    """计算 role / time / escalation 等直接短语命中 bonus。"""
    candidate_lower = context["candidate_lower"]
    subquestion_normalized = context["subquestion_normalized"]
    exact_role_phrase_bonus = int(
        any(
            phrase in candidate_lower
            for phrase in (
                "final approver",
                "final rollback approval",
                "business confirmer",
                "rollback owner",
                "on-call manager",
                "sign-off owner",
                "incident commander",
            )
        )
    )
    return {
        "exact_role_phrase_bonus": exact_role_phrase_bonus,
        "specific_label_bonus": sum(
            int(
                question_marker in subquestion_normalized
                and candidate_marker in candidate_lower
            )
            for question_marker, candidate_marker in (
                ("approver", "approver"),
                ("confirmer", "confirmer"),
                ("rollback owner", "rollback owner"),
                ("on-call manager", "on-call manager"),
                ("incident commander", "incident commander"),
                ("deadline", "before"),
                ("checkpoint", "checkpoint"),
                ("interval", "within"),
                ("closing time", "close before"),
                ("checklist", "checklist"),
                ("requested_kb_ids", "requested_kb_ids"),
                ("effective_kb_ids", "effective_kb_ids"),
                ("scope type", "single_kb"),
                ("organization object", "organization object"),
                ("authorization boundary", "authorization boundary"),
                ("knowledge base level", "knowledge base level"),
                ("access control", "access control"),
                ("doc_id", "doc_id"),
                ("preview_locator", "preview_locator"),
                ("excerpt", "excerpt"),
                ("resolvable", "resolvable"),
            )
        ),
        "approval_phrase_bonus": int(
            signals["asks_approval_role"]
            and any(
                marker in candidate_lower
                for marker in ("approval", "approve", "approver", "批准", "审批")
            )
        ),
        "sign_phrase_bonus": int(
            signals["asks_sign_role"]
            and any(
                marker in candidate_lower
                for marker in (
                    " sign",
                    "signs",
                    "signed",
                    "signature",
                    "checklist",
                    "签署",
                    "签字",
                )
            )
        ),
        "role_bonus": int(
            signals["asks_role"]
            and any(
                marker in candidate_lower
                for marker in (
                    "approver",
                    "approve",
                    "confirmer",
                    "owner",
                    "manager",
                    "commander",
                    "lead",
                )
            )
            and (
                context["contains_value_separator"]
                or context["has_name_like_value"]
                or exact_role_phrase_bonus > 0
            )
        ),
        "time_bonus": int(
            signals["asks_time_value"]
            and (
                context["has_time_value"]
                or any(
                    marker in candidate_lower
                    for marker in (
                        "minutes",
                        "minute",
                        "within",
                        "before",
                        "checkpoint",
                        "deadline",
                        "signed",
                        "close",
                    )
                )
            )
        ),
        "escalation_bonus": int(
            signals["asks_escalation"]
            and any(
                marker in candidate_lower
                for marker in (
                    "escalated",
                    "escalate",
                    "within",
                    "p1",
                    "sev1",
                    "incident",
                    "on-call",
                )
            )
            and (
                "first-ack" not in candidate_lower
                or "first-ack" in context["question_lower"]
            )
        ),
    }


def _count_targeted_structural_fields(features: dict[str, Any]) -> int:
    """统计结构化字段命中数，供 field bonus 与 recognized count 复用。"""
    return _sum_targeted_score_keys(features, _TARGETED_STRUCTURAL_FIELD_KEYS)


def _compute_targeted_base_structural_bonuses(
    candidate_lower: str,
    features: dict[str, Any],
) -> dict[str, int]:
    """计算与 question gating 无关的原始结构化 bonus。"""
    field_bonus = _count_targeted_structural_fields(features)
    return {
        "field_bonus": field_bonus,
        "boundary_object_bonus": int(
            _contains_targeted_marker(
                candidate_lower,
                (
                    "folder",
                    "path",
                    "organization object",
                    "organization path",
                    "internal organization path",
                ),
            )
        ),
        "boundary_bonus": int(features["has_authorization_boundary"])
        + int("knowledge base" in candidate_lower),
        "scope_boundary_bonus": int(
            (
                "knowledge base" in candidate_lower
                and _contains_targeted_marker(
                    candidate_lower,
                    (
                        "requested",
                        "stay inside",
                        "inside the explicitly",
                        "inside the declared",
                    ),
                )
            )
            or _contains_targeted_marker(
                candidate_lower,
                (
                    "stay inside",
                    "inside the explicitly requested",
                    "inside the declared knowledge scope",
                ),
            )
        ),
        "kb_level_bonus": int(features["has_knowledge_base_level"]),
        "org_object_bonus": int(
            features["has_org_object"] and "folder" in candidate_lower
        ),
        "path_bonus": int(features["has_internal_path"]),
        "scope_type_bonus": int(features["has_single_kb"])
        + int(
            features["has_requested_scope_type"] or features["has_effective_scope_type"]
        ),
        "preview_bonus": int(features["has_doc_id"])
        + int(features["has_preview_locator"])
        + int(features["has_excerpt"])
        + int(features["has_preview_resolution"]),
        "negative_bonus": int(features["has_no_confirmable"])
        + int(features["has_active_scope"])
        + int(features["has_no_fabricated_memory"]),
    }


def _count_targeted_recognized_fields(
    candidate_lower: str, features: dict[str, Any]
) -> int:
    """统计 candidate 内被识别出的字段/元信息数量。"""
    return _count_targeted_structural_fields(features) + sum(
        int(marker in candidate_lower)
        for marker in _TARGETED_RECOGNIZED_METADATA_MARKERS
    )


def _compute_targeted_alignment_bonus(
    subquestion_normalized: str, features: dict[str, Any]
) -> int:
    """判断字段对齐类问题是否命中了足够的结构化字段。"""
    return int(
        _contains_targeted_marker(
            subquestion_normalized, ("align", "aligned", "echo", "mirror", "mirrors")
        )
        and any(features[key] for key in _TARGETED_STRUCTURAL_FIELD_KEYS)
    )


def _compute_targeted_effective_structural_bonuses(
    signals: dict[str, bool],
    bonuses: dict[str, int],
    features: dict[str, Any],
) -> dict[str, int]:
    """根据子问题意图，对结构化 bonus 做 gating。"""
    return {
        "effective_field_bonus": bonuses["field_bonus"]
        if (signals["asks_field_list"] or signals["asks_preview_contract"])
        else 0,
        "effective_boundary_bonus": (
            bonuses["boundary_bonus"] + bonuses["boundary_object_bonus"]
        )
        if signals["asks_boundary"]
        else 0,
        "effective_scope_boundary_bonus": bonuses["scope_boundary_bonus"]
        if signals["asks_scope_boundary"]
        else 0,
        "effective_kb_level_bonus": bonuses["kb_level_bonus"]
        if signals["asks_kb_level"]
        else 0,
        "effective_org_object_bonus": bonuses["org_object_bonus"]
        if signals["asks_org_object"]
        else 0,
        "effective_path_bonus": bonuses["path_bonus"]
        if signals["asks_internal_path"]
        else 0,
        "effective_scope_type_bonus": bonuses["scope_type_bonus"]
        if signals["asks_scope_type"]
        else 0,
        "effective_preview_bonus": int(features["has_preview_resolution"])
        if signals["asks_preview_resolution"]
        else bonuses["preview_bonus"]
        if signals["asks_preview_contract"]
        else 0,
        "effective_negative_bonus": bonuses["negative_bonus"]
        if signals["asks_negative_contract"]
        else 0,
    }


def _compute_targeted_structural_bonuses(
    context: dict[str, Any],
    signals: dict[str, bool],
    features: dict[str, Any],
) -> dict[str, int]:
    """计算字段、scope、preview、boundary 等结构化 bonus。"""
    candidate_lower = context["candidate_lower"]
    bonuses = _compute_targeted_base_structural_bonuses(candidate_lower, features)
    bonuses["alignment_bonus"] = _compute_targeted_alignment_bonus(
        context["subquestion_normalized"], features
    )
    bonuses["recognized_field_count"] = _count_targeted_recognized_fields(
        candidate_lower, features
    )
    bonuses.update(
        _compute_targeted_effective_structural_bonuses(signals, bonuses, features)
    )
    return bonuses


def _compute_targeted_candidate_bonuses(
    context: dict[str, Any],
    signals: dict[str, bool],
    features: dict[str, Any],
) -> dict[str, int]:
    """聚合 targeted candidate 的贴题 bonus，供过滤和最终 score 复用。"""
    bonuses = _compute_targeted_phrase_bonuses(context, signals)
    bonuses.update(_compute_targeted_structural_bonuses(context, signals, features))
    return bonuses


def _targeted_candidate_should_be_rejected(
    context: dict[str, Any],
    signals: dict[str, bool],
    features: dict[str, Any],
    bonuses: dict[str, int],
) -> bool:
    """执行 targeted candidate 的 hard guard，避免无关候选进入排序阶段。"""
    subquestion_normalized = context["subquestion_normalized"]
    subquestion_lower = context["subquestion_lower"]
    candidate_lower = context["candidate_lower"]
    return any(
        (
            signals["asks_role"] and bonuses["role_bonus"] <= 0,
            signals["asks_approval_role"] and bonuses["approval_phrase_bonus"] <= 0,
            signals["asks_sign_role"] and bonuses["sign_phrase_bonus"] <= 0,
            signals["asks_escalation"] and bonuses["escalation_bonus"] <= 0,
            signals["asks_time_value"] and bonuses["time_bonus"] <= 0,
            "id field" in subquestion_normalized
            and not (
                features["has_requested_kb_ids"] or features["has_effective_kb_ids"]
            ),
            signals["asks_field_list"]
            and "evidence" in context["question_normalized"]
            and bonuses["preview_bonus"] <= 0,
            "response field" in subquestion_normalized
            and "knowledge base" in subquestion_normalized
            and not features["has_effective_kb_ids"],
            signals["asks_scope_type"] and not features["has_single_kb"],
            signals["asks_alignment_field"]
            and (
                bonuses["alignment_bonus"] <= 0 or not features["has_alignment_phrase"]
            ),
            signals["asks_scope_boundary"] and bonuses["scope_boundary_bonus"] <= 0,
            signals["asks_kb_level"]
            and bonuses["kb_level_bonus"] <= 0
            and not (
                "knowledge base" in candidate_lower
                and features["has_authorization_boundary"]
            ),
            signals["asks_org_object"] and bonuses["org_object_bonus"] <= 0,
            signals["asks_internal_path"]
            and context["literal_bonus"] <= 0
            and bonuses["path_bonus"] <= 0,
            signals["asks_preview_contract"] and bonuses["preview_bonus"] <= 0,
            signals["asks_preview_resolution"]
            and not features["has_preview_resolution"],
            signals["asks_negative_contract"]
            and any(
                marker in subquestion_lower
                for marker in (
                    "fabricated memory",
                    "active knowledge base",
                    "outside memory",
                )
            )
            and bonuses["negative_bonus"] <= 0,
            signals["asks_boundary"]
            and not any(
                (
                    bonuses["boundary_bonus"] > 0,
                    bonuses["kb_level_bonus"] > 0,
                    bonuses["org_object_bonus"] > 0,
                    bonuses["path_bonus"] > 0,
                )
            ),
        )
    )


def _compute_targeted_candidate_penalties(
    context: dict[str, Any],
    signals: dict[str, bool],
    bonuses: dict[str, int],
) -> dict[str, int]:
    """聚合 targeted candidate 的噪声 penalty。"""
    candidate_lower = context["candidate_lower"]
    subquestion_lower = context["subquestion_lower"]
    normalized_subquestion = context["normalized_subquestion"]
    asked_role_labels = _collect_targeted_role_labels(
        normalized_subquestion, subquestion_lower
    )
    numeric_value_count = len(_TARGETED_NUMERIC_VALUE_RE.findall(candidate_lower))
    penalties = {
        "live_penalty": int(
            any(
                marker in candidate_lower
                for marker in ("legacy", "retired", "dry-run", "rehearsal")
            )
            and not any(
                marker in subquestion_lower
                for marker in ("legacy", "retired", "ignore")
            )
        ),
        "label_only_penalty": int(
            signals["asks_role"]
            and not context["contains_value_separator"]
            and not context["has_name_like_value"]
        ),
        "role_label_mismatch_penalty": int(
            bool(asked_role_labels)
            and not any(label in candidate_lower for label in asked_role_labels)
        ),
        "deadline_mismatch_penalty": int(
            signals["asks_deadline_value"]
            and any(
                marker in candidate_lower for marker in ("within", "minute", "minutes")
            )
            and "before" not in candidate_lower
            and "deadline" not in candidate_lower
            and "checkpoint" not in candidate_lower
            and "close" not in candidate_lower
        ),
        "interval_mismatch_penalty": int(
            signals["asks_interval_value"]
            and any(
                marker in candidate_lower
                for marker in ("before", "deadline", "checkpoint")
            )
            and "within" not in candidate_lower
            and "minute" not in candidate_lower
            and "minutes" not in candidate_lower
        ),
        "first_ack_penalty": int(
            signals["asks_escalation"]
            and "first-ack" in candidate_lower
            and "first-ack" not in context["question_lower"]
        ),
        "unrelated_preview_penalty": int(
            signals["asks_preview_contract"] and bonuses["preview_bonus"] <= 0
        ),
        "unrelated_boundary_penalty": 2
        * int(
            (signals["asks_kb_level"] or signals["asks_boundary"])
            and any(
                marker in candidate_lower
                for marker in ("escalat", "on-call manager", "p1", "incident")
            )
            and not any(
                marker in subquestion_lower
                for marker in ("escalat", "on-call", "incident", "p1")
            )
        ),
        "exact_two_fields_penalty": max(bonuses["recognized_field_count"] - 2, 0)
        if signals["asks_exactly_two_fields"]
        else 0,
        "preview_resolution_noise_penalty": max(
            bonuses["recognized_field_count"] - 1, 0
        )
        if signals["asks_preview_resolution"]
        else 0,
        "multi_value_penalty": int(
            signals["asks_time_value"] and numeric_value_count > 1
        ),
    }
    penalties["total_penalty"] = sum(penalties.values())
    return penalties


def score_targeted_answer_candidate(
    question: str, subquestion: str, candidate: str, *, hooks: TargetedFactHooks
) -> tuple[int, ...] | None:
    """对子问题候选句打分，优先保留最小、最贴题、最少噪声且包含关键字段的 grounded 片段。"""
    context = _build_targeted_question_context(
        question, subquestion, candidate, hooks=hooks
    )
    if context is None:
        return None
    signals = _build_targeted_question_signals(context, hooks=hooks)
    features = _extract_targeted_candidate_features(context, hooks=hooks)
    bonuses = _compute_targeted_candidate_bonuses(context, signals, features)
    if _targeted_candidate_should_be_rejected(context, signals, features, bonuses):
        return None
    if not _targeted_candidate_has_minimum_support(context, bonuses):
        return None
    penalties = _compute_targeted_candidate_penalties(context, signals, bonuses)
    semantic_bonus = _compute_targeted_semantic_bonus(bonuses)
    structural_priority = _compute_targeted_structural_priority_score(bonuses)
    return (
        context["literal_bonus"] + context["focus_token_bonus"],
        semantic_bonus - penalties["total_penalty"],
        structural_priority,
        context["overlap"],
        context["question_overlap"],
        -context["sentence_count"],
        -penalties["total_penalty"],
        -len(context["candidate_text"]),
    )


def collect_alignment_field_segments(
    subquestion: str,
    sources: list[dict[str, Any]],
    *,
    hooks: TargetedFactHooks,
) -> list[tuple[str, dict[str, Any]]]:
    """为“哪两个 id 字段”类问题补齐多个字段名，而不是退化成泛化标题。"""
    lowered = hooks.normalize_targeted_subquestion(subquestion).lower()
    if "id field" not in lowered and "id fields" not in lowered:
        return []
    wanted_fields = ["requested_kb_ids", "effective_kb_ids"]
    collected: list[tuple[str, dict[str, Any]]] = []
    seen_fields: set[str] = set()
    for source in sources:
        for candidate in hooks.iter_targeted_answer_candidates(source):
            normalized = hooks.normalize_expanded_answer(candidate)
            if not normalized:
                continue
            candidate_lower = normalized.lower()
            for field in wanted_fields:
                if field in candidate_lower and field not in seen_fields:
                    seen_fields.add(field)
                    collected.append((normalized, source))
    wants_exact_pair = "two fields" in lowered or "two id fields" in lowered
    if wants_exact_pair and len(seen_fields) < len(wanted_fields):
        return []
    return collected


def source_reference_question_overlap(
    question: str, source: dict[str, Any], *, hooks: TargetedFactHooks
) -> int:
    """估算 source 与问题显式引用的重合度，帮助跨 source 组装时优先选对文档。"""
    source_blob_parts = [
        str(source.get("file") or "").strip(),
        str(source.get("title") or "").strip(),
        str(source.get("text") or "").strip(),
        str(source.get("excerpt") or "").strip(),
    ]
    source_blob = "\n".join(part for part in source_blob_parts if part)
    source_tokens = hooks.tokenize_text(source_blob)
    question_tokens = hooks.tokenize_text(question)
    overlap = len(source_tokens & question_tokens)
    source_file = str(source.get("file") or source.get("title") or "").strip().lower()
    source_blob_lower = source_blob.lower()
    literal_bonus = 0
    for term in hooks.extract_literal_question_terms(question):
        lowered = term.lower()
        if lowered and (lowered in source_file or lowered in source_blob_lower):
            literal_bonus += 3
    filename_hint = source_file.replace(".", " ").replace("-", " ").replace("_", " ")
    filename_overlap = len(hooks.tokenize_text(filename_hint) & question_tokens)
    return overlap + filename_overlap + literal_bonus


ScoredTargetedCandidate = tuple[tuple[int, ...], str, dict[str, Any]]
SelectedTargetedPair = tuple[str, dict[str, Any]]


def _append_targeted_selected_segment(
    normalized: str,
    source: dict[str, Any] | None,
    *,
    selected_segments: list[str],
    selected_sources: list[dict[str, Any]],
    selected_pairs: list[SelectedTargetedPair],
) -> bool:
    """向 targeted-fact 结果集中追加 segment，并保持 source/pair 去重。"""
    if not normalized or normalized in selected_segments:
        return False
    selected_segments.append(normalized)
    if source is not None:
        selected_sources.append(source)
        selected_pairs.append((normalized, source))
    return True


def _select_best_targeted_candidate_for_subquestion(
    question: str,
    subquestion: str,
    sources: list[dict[str, Any]],
    *,
    prefer_distinct_source: bool,
    selected_segments: list[str],
    selected_sources: list[dict[str, Any]],
    hooks: TargetedFactHooks,
) -> ScoredTargetedCandidate | None:
    """为单个 subquestion 选择最优 candidate，并在需要时优先未使用 source。"""
    best_overall: ScoredTargetedCandidate | None = None
    best_distinct: ScoredTargetedCandidate | None = None
    best_fresh: ScoredTargetedCandidate | None = None
    used_files = {
        str(source.get("file") or source.get("title") or "").strip()
        for source in selected_sources
    }
    for source in sources:
        source_file = str(source.get("file") or source.get("title") or "").strip()
        source_overlap = source_reference_question_overlap(
            question, source, hooks=hooks
        )
        for candidate in hooks.iter_targeted_answer_candidates(source):
            score = score_targeted_answer_candidate(
                question, subquestion, candidate, hooks=hooks
            )
            if score is None:
                continue
            normalized = hooks.normalize_expanded_answer(candidate)
            if not normalized:
                continue
            payload_score = (score[0], score[1], source_overlap, *score[2:])
            payload: ScoredTargetedCandidate = (payload_score, normalized, source)
            if best_overall is None or payload_score > best_overall[0]:
                best_overall = payload
            if normalized not in selected_segments and (
                best_fresh is None or payload_score > best_fresh[0]
            ):
                best_fresh = payload
            if prefer_distinct_source and source_file and source_file not in used_files:
                if best_distinct is None or payload_score > best_distinct[0]:
                    best_distinct = payload
    return best_distinct or best_fresh or best_overall


def _answer_targeted_subquestion_from_sources(
    question: str,
    subquestion: str,
    sources: list[dict[str, Any]],
    *,
    prefer_distinct_source: bool,
    selected_segments: list[str],
    selected_sources: list[dict[str, Any]],
    selected_pairs: list[SelectedTargetedPair],
    hooks: TargetedFactHooks,
) -> bool:
    """回答单个 subquestion，优先补齐 alignment 字段，否则退回 candidate 评分选择。"""
    alignment_segments = collect_alignment_field_segments(
        subquestion, sources, hooks=hooks
    )
    if alignment_segments:
        for normalized, source in alignment_segments:
            _append_targeted_selected_segment(
                normalized,
                source,
                selected_segments=selected_segments,
                selected_sources=selected_sources,
                selected_pairs=selected_pairs,
            )
        return True
    chosen = _select_best_targeted_candidate_for_subquestion(
        question,
        subquestion,
        sources,
        prefer_distinct_source=prefer_distinct_source,
        selected_segments=selected_segments,
        selected_sources=selected_sources,
        hooks=hooks,
    )
    if chosen is None:
        return False
    _append_targeted_selected_segment(
        chosen[1],
        chosen[2],
        selected_segments=selected_segments,
        selected_sources=selected_sources,
        selected_pairs=selected_pairs,
    )
    return True


def _collect_targeted_negative_contract_segments_from_answer(
    answer_text: str,
    *,
    fallback_source: dict[str, Any] | None,
    selected_segments: list[str],
    selected_sources: list[dict[str, Any]],
    selected_pairs: list[SelectedTargetedPair],
    hooks: TargetedFactHooks,
) -> None:
    """从现有 answer_text 中补收负向契约锚点，避免完全依赖 source 命中。"""
    for (
        normalized
    ) in chat_negative_contract_answers.collect_negative_contract_segments_from_answer(
        answer_text,
        normalize_expanded_answer=hooks.normalize_expanded_answer,
    ):
        _append_targeted_selected_segment(
            normalized,
            fallback_source,
            selected_segments=selected_segments,
            selected_sources=selected_sources,
            selected_pairs=selected_pairs,
        )


def _targeted_answer_has_required_coverage(
    subquestions: list[str],
    answered_subquestions: int,
    selected_segments: list[str],
    *,
    wants_negative_contract: bool,
    negative_contract: tuple[str, dict[str, Any]] | None,
) -> bool:
    """判断是否已经覆盖 targeted-fact 最小可返回条件。"""
    required_segments = max(2, len(subquestions)) if subquestions else 0
    if wants_negative_contract and negative_contract is not None:
        required_segments = min(required_segments or 2, 2)
    if subquestions and answered_subquestions < len(subquestions):
        return False
    if required_segments and len(selected_segments) < required_segments:
        return bool(
            subquestions
            and answered_subquestions >= len(subquestions)
            and selected_segments
        )
    return True


def _build_targeted_answer_from_selected_pairs(
    selected_pairs: list[SelectedTargetedPair],
    selected_segments: list[str],
    selected_sources: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    *,
    hooks: TargetedFactHooks,
) -> tuple[str, list[dict[str, Any]]]:
    """按 source 分组压缩已选 segment，并扩回必要的局部上下文。"""
    compressed_sources: list[dict[str, Any]] = []
    grouped_segments: dict[str, dict[str, Any]] = {}
    for normalized, source in selected_pairs:
        source_file = str(
            source.get("file") or source.get("title") or f"source-{id(source)}"
        ).strip()
        entry = grouped_segments.get(source_file)
        if entry is None:
            entry = {"source": dict(source), "segments": []}
            grouped_segments[source_file] = entry
        if normalized not in entry["segments"]:
            entry["segments"].append(normalized)
    final_segments: list[str] = []
    for item in grouped_segments.values():
        source_copy = item["source"]
        expanded_segments = expand_targeted_source_segments_with_local_context(
            source_copy, item["segments"], hooks=hooks
        )
        joined = "\n".join(expanded_segments)
        if joined:
            source_copy["text"] = joined
            source_copy["excerpt"] = joined
        compressed_sources.append(source_copy)
        for segment in expanded_segments:
            if segment not in final_segments:
                final_segments.append(segment)
    deduped_sources = (
        hooks.dedupe_sources_by_file(compressed_sources or selected_sources) or sources
    )
    return "\n".join(final_segments or selected_segments), deduped_sources


def maybe_answer_targeted_fact_question_from_sources(
    question: str,
    answer_text: str,
    sources: list[dict[str, Any]],
    *,
    hooks: TargetedFactHooks,
) -> tuple[str, list[dict[str, Any]]]:
    """针对多事实问题，用 source 重组更完整答案，并只保留被使用的来源。"""
    subquestions = hooks.split_targeted_fact_question(question)
    wants_negative_contract = hooks.question_requests_negative_contract(question)
    if not subquestions and not wants_negative_contract:
        return answer_text, sources
    compact_negative_answer = best_single_source_negative_contract_answer(
        question, sources, hooks=hooks
    )
    if compact_negative_answer is not None:
        return compact_negative_answer
    prefer_distinct_sources = hooks.question_prefers_cross_source_fact_assembly(
        question
    )
    selected_segments: list[str] = []
    selected_sources: list[dict[str, Any]] = []
    selected_pairs: list[SelectedTargetedPair] = []
    answered_subquestions = 0
    for index, subquestion in enumerate(subquestions):
        answered = _answer_targeted_subquestion_from_sources(
            question,
            subquestion,
            sources,
            prefer_distinct_source=prefer_distinct_sources and index > 0,
            selected_segments=selected_segments,
            selected_sources=selected_sources,
            selected_pairs=selected_pairs,
            hooks=hooks,
        )
        if answered:
            answered_subquestions += 1
    negative_contract = best_negative_contract_segment(question, sources, hooks=hooks)
    if negative_contract is not None:
        negative_sentence = hooks.normalize_expanded_answer(negative_contract[0])
        _append_targeted_selected_segment(
            negative_sentence,
            negative_contract[1],
            selected_segments=selected_segments,
            selected_sources=selected_sources,
            selected_pairs=selected_pairs,
        )
    if wants_negative_contract:
        _collect_targeted_negative_contract_segments_from_answer(
            answer_text,
            fallback_source=sources[0] if sources else None,
            selected_segments=selected_segments,
            selected_sources=selected_sources,
            selected_pairs=selected_pairs,
            hooks=hooks,
        )
    if not _targeted_answer_has_required_coverage(
        subquestions,
        answered_subquestions,
        selected_segments,
        wants_negative_contract=wants_negative_contract,
        negative_contract=negative_contract,
    ):
        return answer_text, sources
    return _build_targeted_answer_from_selected_pairs(
        selected_pairs,
        selected_segments,
        selected_sources,
        sources,
        hooks=hooks,
    )


def _build_negative_contract_hooks(
    hooks: TargetedFactHooks,
) -> chat_negative_contract_answers.NegativeContractHooks:
    """把 targeted-fact hooks 收口成负向契约子模块所需的最小依赖。"""
    return chat_negative_contract_answers.NegativeContractHooks(
        question_requests_negative_contract=hooks.question_requests_negative_contract,
        iter_targeted_answer_candidates=hooks.iter_targeted_answer_candidates,
        normalize_expanded_answer=hooks.normalize_expanded_answer,
    )


def best_single_source_negative_contract_answer(
    question: str,
    sources: list[dict[str, Any]],
    *,
    hooks: TargetedFactHooks,
) -> tuple[str, list[dict[str, Any]]] | None:
    """若同一 source 已覆盖 refusal/scope/no-fabrication 三条负向契约，则直接返回最小答案。"""
    return chat_negative_contract_answers.best_single_source_negative_contract_answer(
        question,
        sources,
        hooks=_build_negative_contract_hooks(hooks),
    )


def best_negative_contract_segment(
    question: str, sources: list[dict[str, Any]], *, hooks: TargetedFactHooks
) -> tuple[str, dict[str, Any]] | None:
    """为 refusal / negative-contract 问题补回 No confirmable information 这类锚点。"""
    return chat_negative_contract_answers.best_negative_contract_segment(
        question,
        sources,
        hooks=_build_negative_contract_hooks(hooks),
    )


def expand_targeted_source_segments_with_local_context(
    source: dict[str, Any],
    segments: list[str],
    *,
    hooks: TargetedFactHooks,
) -> list[str]:
    """同一 source 命中相邻多段时补回中间叙述行，但跳过其它结构化事实字段。"""
    _normalize_expanded_answer = hooks.normalize_expanded_answer
    _iter_boundary_support_texts = hooks.iter_boundary_support_texts
    _TIME_VALUE_RE = hooks.time_value_re
    normalized_segments = [
        _normalize_expanded_answer(segment)
        for segment in segments
        if _normalize_expanded_answer(segment)
    ]
    if len(normalized_segments) < 2:
        return normalized_segments
    ordered_lines: list[str] = []
    seen_lines: set[str] = set()
    for support_text in _iter_boundary_support_texts(source):
        for raw_line in str(support_text or "").splitlines():
            line = raw_line.strip().lstrip("-*• ").strip()
            if not line or line.startswith("#"):
                continue
            normalized_line = _normalize_expanded_answer(line)
            if normalized_line and normalized_line not in seen_lines:
                seen_lines.add(normalized_line)
                ordered_lines.append(normalized_line)
    if len(ordered_lines) < 2:
        return normalized_segments

    def _match_key(text: str) -> str:
        return str(text or "").strip().rstrip("。！？!?;；.").lower()

    matched_indexes: list[int] = []
    for segment in normalized_segments:
        segment_key = _match_key(segment)
        match_index = next(
            (
                index
                for index, line in enumerate(ordered_lines)
                if segment_key
                and (
                    _match_key(line).find(segment_key) >= 0
                    or segment_key.find(_match_key(line)) >= 0
                )
            ),
            None,
        )
        if match_index is not None:
            matched_indexes.append(match_index)
    if len(matched_indexes) < 2:
        return normalized_segments
    if max(matched_indexes) - min(matched_indexes) > 2:
        return normalized_segments
    expanded: list[str] = []
    start = min(matched_indexes)
    end = max(matched_indexes)
    selected_index_set = set(matched_indexes)
    for index in range(start, end + 1):
        line = ordered_lines[index]
        if index not in selected_index_set:
            if ":" in line or "：" in line or _TIME_VALUE_RE.search(line):
                continue
        if line not in expanded:
            expanded.append(line)
    return expanded or normalized_segments
