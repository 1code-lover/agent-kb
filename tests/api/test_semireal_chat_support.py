from __future__ import annotations

from types import SimpleNamespace

from tests.api._semireal_chat_support import SemirealIndexManager, SemirealQueryEngine


def test_semireal_search_ignores_low_signal_say_overlap_in_no_evidence_question(tmp_path) -> None:
    """????? say/assistant ?????????????"""
    manager = SemirealIndexManager("eval-kb-markdown", tmp_path)
    manager.register_text_document(
        path=tmp_path / "refusal-guideline.md",
        text=(
            "If the current knowledge base has no confirmable evidence, the assistant should explicitly say "
            "that no confirmable information is available and must not fabricate an answer.\n"
            "The reply should stay inside the active knowledge base instead of guessing from outside memory.\n"
        ),
        kb_id="eval-kb-markdown",
    )

    matches = manager.search("What does the atlas retention escrow memo say about rotating shard seals?", top_k=1)

    assert matches == []


def test_semireal_search_keeps_real_refusal_question_retrievable(tmp_path) -> None:
    """???????????? refusal guideline?"""
    manager = SemirealIndexManager("eval-kb-markdown", tmp_path)
    manager.register_text_document(
        path=tmp_path / "refusal-guideline.md",
        text=(
            "If the current knowledge base has no confirmable evidence, the assistant should explicitly say "
            "that no confirmable information is available and must not fabricate an answer.\n"
            "The reply should stay inside the active knowledge base instead of guessing from outside memory.\n"
        ),
        kb_id="eval-kb-markdown",
    )

    matches = manager.search("What should the assistant say when the current KB has no confirmable evidence?", top_k=1)

    assert len(matches) == 1
    assert matches[0].node.metadata["file_name"] == "refusal-guideline.md"


def test_semireal_search_supports_cjk_overlap_for_multilingual_cases(tmp_path) -> None:
    """???????????????????"""
    manager = SemirealIndexManager("eval-kb-markdown", tmp_path)
    manager.register_text_document(
        path=tmp_path / "folder-boundary.md",
        text=(
            "Folders are organizational objects inside one knowledge base.\n"
            "\u6587\u4ef6\u5939\u53ea\u662f\u77e5\u8bc6\u5e93\u5185\u90e8\u7684\u7ec4\u7ec7\u5bf9\u8c61\uff0c\u4e0d\u662f\u65b0\u7684\u6388\u6743\u8fb9\u754c\u3002\n"
            "\u67e5\u8be2\u8303\u56f4\u4e0e\u8bbf\u95ee\u63a7\u5236\u4ecd\u7136\u505c\u7559\u5728\u77e5\u8bc6\u5e93\u5c42\u3002\n"
        ),
        kb_id="eval-kb-markdown",
    )

    matches = manager.search("\u6839\u636e\u8fd9\u4efd\u8bf4\u660e\uff0c\u6587\u4ef6\u5939\u662f\u4e0d\u662f\u65b0\u7684\u6388\u6743\u8fb9\u754c\uff1f", top_k=1)

    assert len(matches) == 1
    assert matches[0].node.metadata["file_name"] == "folder-boundary.md"


def test_semireal_load_documents_marks_nodes_without_embedding_and_keeps_text_fallback_searchable(tmp_path) -> None:
    """?? embedding ????????????????"""
    manager = SemirealIndexManager("eval-kb-pdf", tmp_path)
    manager.load_documents(
        [
            SimpleNamespace(
                text="Authorization boundary remains the knowledge base for external agent access.",
                metadata={
                    "file_name": "embedding-gap.pdf",
                    "title": "embedding-gap.pdf",
                    "relative_path": "pdf/weak-signals/embedding-gap.pdf",
                    "page_label": "1",
                    "simulate_nodes_without_embedding": True,
                },
            )
        ],
        chunk_size=128,
        chunk_overlap=16,
        kb_id="eval-kb-pdf",
    )

    diagnostics = manager.consume_last_ingestion_diagnostics()
    assert diagnostics is not None
    assert diagnostics["document_count"] == 1
    assert diagnostics["node_count"] == 1
    assert diagnostics["nodes_with_embedding_count"] == 0
    assert diagnostics["nodes_without_embedding_count"] == 1

    matches = manager.search("What authorization boundary rule is defined for external agent access?", top_k=1)

    assert len(matches) == 1
    assert matches[0].node.metadata["file_name"] == "embedding-gap.pdf"
    assert matches[0].score > 0


def test_semireal_search_requires_question_anchors_for_weak_signal_refusal_cases(tmp_path) -> None:
    """????????????? refusal ???????"""
    manager = SemirealIndexManager("eval-kb-image", tmp_path)
    manager.register_text_document(
        path=tmp_path / "escalation-whiteboard-business.png",
        text=(
            "Knowledge base remains the authorization boundary. "
            "If evidence is missing, reply No confirmable information is available in the current knowledge base."
        ),
        kb_id="eval-kb-image",
    )

    matches = manager.search(
        "If the weak failed board has no confirmable OCR evidence, what boundary should the assistant stay inside?",
        top_k=1,
    )

    assert matches == []


def test_semireal_search_boosts_title_terms_for_multi_source_questions(tmp_path) -> None:
    """?????????????????????"""
    manager = SemirealIndexManager("eval-kb-pdf", tmp_path)
    manager.register_text_document(
        path=tmp_path / "scope-manual.pdf",
        text="The authorization boundary remains the single_kb knowledge base.",
        kb_id="eval-kb-pdf",
    )
    manager.register_text_document(
        path=tmp_path / "folder-boundary.pdf",
        text="Folders are organizational objects; the authorization boundary remains the knowledge base.",
        kb_id="eval-kb-pdf",
    )
    manager.register_text_document(
        path=tmp_path / "embedding-gap.pdf",
        text="Authorization boundary remains the knowledge base for external agents.",
        kb_id="eval-kb-pdf",
    )

    matches = manager.search(
        "Across the scope manual and the folder boundary note, what remains the authorization boundary rule?",
        top_k=2,
    )

    assert {match.node.metadata["file_name"] for match in matches} == {"folder-boundary.pdf", "scope-manual.pdf"}


def test_semireal_search_keeps_short_alnum_anchor_for_cutover_incident_questions(tmp_path) -> None:
    manager = SemirealIndexManager("eval-kb-markdown", tmp_path)
    manager.register_text_document(
        path=tmp_path / "cutover-approval.md",
        text=(
            "Payroll cutover approval matrix.\n"
            "Final approver: Release Manager Li Qing.\n"
            "Rollback owner: Platform SRE Wang Lei.\n"
        ),
        kb_id="eval-kb-markdown",
    )
    manager.register_text_document(
        path=tmp_path / "handover-sla.md",
        text=(
            "War-room handover SLA.\n"
            "P1 cutover incident must be escalated to on-call manager Zhao Lin within 15 minutes.\n"
            "Service desk first-ack SLA is 5 minutes.\n"
        ),
        kb_id="eval-kb-markdown",
    )

    matches = manager.search(
        "P1 cutover incident \u9700\u8981\u5728\u51e0\u5206\u949f\u5185\u5347\u7ea7\u7ed9\u8c01\uff1f",
        top_k=1,
    )

    assert len(matches) == 1
    assert matches[0].node.metadata["file_name"] == "handover-sla.md"
    assert "p1" in matches[0].body_overlap

def test_semireal_query_engine_extracts_focus_segment_from_long_document(tmp_path) -> None:
    manager = SemirealIndexManager("eval-kb-markdown", tmp_path)
    manager.register_text_document(
        path=tmp_path / "long-handbook.md",
        text=(
            "Payroll release handbook.\n"
            "Shift notes: archive stale screenshots after every rehearsal.\n"
            "Reminder: folder names stay inside one knowledge base.\n"
            "Final approval checkpoint closes at 21:40 Beijing time.\n"
            "Operators should verify preview_locator before publishing evidence.\n"
            "Distractor note: the legacy dry-run closed at 18:00 and is no longer active.\n"
        ),
        kb_id="eval-kb-markdown",
    )

    engine = SemirealQueryEngine(manager)
    result = engine.query("What time does the final approval checkpoint close?")

    assert "21:40 Beijing time" in result.response
    assert "18:00" not in result.response
    assert len(result.source_nodes) == 1


def test_semireal_query_engine_returns_two_sources_for_comparison_question(tmp_path) -> None:
    manager = SemirealIndexManager("eval-kb-markdown", tmp_path)
    manager.register_text_document(
        path=tmp_path / "cutover-approval.md",
        text=(
            "Payroll cutover approval matrix.\n"
            "Final approver: Release Manager Li Qing.\n"
            "Evidence preview must stay traceable.\n"
        ),
        kb_id="eval-kb-markdown",
    )
    manager.register_text_document(
        path=tmp_path / "handover-commander.md",
        text=(
            "War-room handover commander sheet.\n"
            "Primary incident commander: Zhao Lin.\n"
            "Knowledge Base remains the authorization boundary.\n"
        ),
        kb_id="eval-kb-markdown",
    )

    engine = SemirealQueryEngine(manager)
    result = engine.query("Compare the final approver and the primary incident commander for this release.")

    assert len(result.source_nodes) == 2
    assert "Li Qing" in result.response
    assert "Zhao Lin" in result.response
