"""chat_follow_up_context 纯函数测试。"""

from __future__ import annotations

from api.services import chat_follow_up_context


def _build_hooks(**overrides: object) -> chat_follow_up_context.FollowUpQuestionHeuristicsHooks:
    defaults: dict[str, object] = {
        "tokenize_text": lambda text: set(str(text).lower().replace("?", "").split()),
        "question_requests_identifier_like_field": lambda question: False,
        "question_requests_exact_source_phrase": lambda question: False,
    }
    defaults.update(overrides)
    return chat_follow_up_context.FollowUpQuestionHeuristicsHooks(**defaults)


def test_question_looks_follow_up_accepts_explicit_pronoun_reference() -> None:
    """带 it/that one 之类显式指代的问句，应稳定命中 follow-up。"""
    assert chat_follow_up_context.question_looks_follow_up("Who approves it?", hooks=_build_hooks()) is True


def test_question_looks_follow_up_rejects_short_identifier_like_fragment() -> None:
    """短字段问句若本身就是 identifier-like，不应仅因 token 少就注入历史。"""
    hooks = _build_hooks(question_requests_identifier_like_field=lambda question: question == "CAB ticket?")

    assert chat_follow_up_context.question_looks_follow_up("CAB ticket?", hooks=hooks) is False


def test_question_looks_follow_up_rejects_short_exact_phrase_prompt() -> None:
    """短 exact phrase 问句也应优先保留精确检索，而不是误判为 follow-up。"""
    hooks = _build_hooks(question_requests_exact_source_phrase=lambda question: question == "authorization boundary?")

    assert chat_follow_up_context.question_looks_follow_up("authorization boundary?", hooks=hooks) is False


def test_question_looks_follow_up_keeps_short_non_identifier_fragment_as_follow_up() -> None:
    """仍需保留短省略问句的 follow-up 能力，避免回退到完全不看上下文。"""
    assert chat_follow_up_context.question_looks_follow_up("rollback owner?", hooks=_build_hooks()) is True


def test_question_looks_follow_up_keeps_explicit_follow_up_even_for_identifier_field() -> None:
    """显式 what about / it 指代应优先于 identifier-like 守卫，避免丢失真实追问。"""
    hooks = _build_hooks(question_requests_identifier_like_field=lambda question: "CAB ticket" in question)

    assert chat_follow_up_context.question_looks_follow_up("What about the CAB ticket?", hooks=hooks) is True
