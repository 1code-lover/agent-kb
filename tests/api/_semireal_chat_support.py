"""半真实多格式问答测试支撑工具。"""

from __future__ import annotations

import io
import re

import fitz
from pathlib import Path
from types import SimpleNamespace
from typing import Any


QUESTION_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "before",
    "board",
    "boards",
    "compare",
    "comparison",
    "current",
    "define",
    "defines",
    "document",
    "documents",
    "does",
    "each",
    "for",
    "from",
    "has",
    "how",
    "image",
    "images",
    "into",
    "manual",
    "mention",
    "mentions",
    "must",
    "knowledge",
    "base",
    "ocr",
    "pdf",
    "response",
    "say",
    "should",
    "single",
    "that",
    "the",
    "their",
    "these",
    "this",
    "what",
    "when",
    "which",
    "with",
}

TITLE_TOKEN_STOPWORDS = {
    "board",
    "boards",
    "jpeg",
    "jpg",
    "md",
    "pdf",
    "png",
    "txt",
}

GENERIC_POLICY_TERMS = {
    "active",
    "answer",
    "assistant",
    "available",
    "boundary",
    "confirmable",
    "current",
    "evidence",
    "fabricate",
    "information",
    "inside",
    "reply",
    "rule",
    "stay",
}

WEAK_SIGNAL_TERMS = {
    "cannot",
    "checksum",
    "dependency",
    "escrow",
    "failed",
    "fail",
    "helios",
    "invent",
    "inventing",
    "orion",
    "produced",
    "produc",
    "shard",
    "tenant",
    "text",
    "weak",
}
RISKY_ZERO_OVERLAP_SEGMENTS = (
    "outside memory",
)


FOCUSED_QUESTION_HINTS = (
    "what time",
    "when ",
    "what is",
    "who is",
    "what does",
    "according to",
    " how many minutes",
    "???",
    "??",
    "??",
)


class FakeUploadFile:
    """模拟上传文件对象，供 import_files 直接消费。"""

    def __init__(self, filename: str, content: bytes, content_type: str) -> None:
        self.filename = filename
        self.content_type = content_type
        self.file = io.BytesIO(content)


class FakeRefDocInfo:
    """模拟 ref_doc_info，使 preview 能回到 metadata 与节点列表。"""

    def __init__(self, metadata: dict[str, str], node_ids: list[str]) -> None:
        self.metadata = metadata
        self.node_ids = node_ids


class FakeDocStore:
    """æ¨¡æ docstoreï¼è¡¥é½éå¯¼å
¥è·¯å¾æéç evidence / preview è®¿é®è½åã"""

    def __init__(self) -> None:
        self.docs: dict[str, SimpleNamespace] = {}
        self.ref_docs: dict[str, FakeRefDocInfo] = {}

    def get_all_ref_doc_info(self) -> dict[str, FakeRefDocInfo]:
        return dict(self.ref_docs)

    def get_ref_doc_info(self, ref_doc_id: str):
        return self.ref_docs.get(ref_doc_id)

    def get_document(self, node_id: str, raise_error: bool = True):
        node = self.docs.get(node_id)
        if node is None and raise_error:
            raise ValueError(f"node_id {node_id} not found")
        return node

    def get_nodes(self, node_ids=None, raise_error: bool = False):
        del raise_error
        node_ids = list(node_ids or [])
        return [self.docs[node_id] for node_id in node_ids if node_id in self.docs]

    def remove_ref_doc(self, ref_doc_id: str) -> None:
        ref_doc = self.ref_docs.pop(ref_doc_id, None)
        if ref_doc is None:
            return
        for node_id in list(getattr(ref_doc, "node_ids", []) or []):
            self.docs.pop(node_id, None)


class FakeStorageContext:
    """最小 storage_context，仅暴露 preview 所需的 docstore。"""

    def __init__(self, docstore: FakeDocStore) -> None:
        self.docstore = docstore


def _iter_cjk_terms(text: str) -> list[str]:
    """提取中文连续片段，并补充 2-4 字滑窗词项。"""
    terms: set[str] = set()
    for chunk in re.findall(r"[㐀-䶿一-鿿]+", str(text)):
        normalized_chunk = chunk.strip()
        if len(normalized_chunk) <= 1:
            continue
        terms.add(normalized_chunk)
        upper = min(len(normalized_chunk), 4)
        for size in range(2, upper + 1):
            for index in range(0, len(normalized_chunk) - size + 1):
                terms.add(normalized_chunk[index : index + size])
    return sorted(terms)



def _normalize_english_tokens(text: str, *, stopwords: set[str] | None) -> set[str]:
    normalized: set[str] = set()
    blocked = set(stopwords or set())
    for token in re.findall(r"[a-z0-9_]+", str(text).lower()):
        keep_short_alnum = len(token) <= 2 and any(ch.isdigit() for ch in token) and any(ch.isalpha() for ch in token)
        if (len(token) <= 2 and not keep_short_alnum) or token in blocked:
            continue
        normalized.add(token)
        if token.endswith("s") and len(token) > 4:
            normalized.add(token[:-1])
        if token.endswith("ed") and len(token) > 4:
            normalized.add(token[:-2])
        if token.endswith("ing") and len(token) > 5:
            normalized.add(token[:-3])
        if token.startswith("refus") and token.endswith("al") and len(token) > 5:
            normalized.add(token[:-2])
    return normalized


def tokenize(text: str) -> set[str]:
    """???????????? token???????????"""
    return set(_iter_cjk_terms(str(text))) | _normalize_english_tokens(str(text), stopwords=QUESTION_STOPWORDS)


def tokenize_title(text: str) -> set[str]:
    """??????????????????????"""
    return set(_iter_cjk_terms(str(text))) | _normalize_english_tokens(str(text), stopwords=TITLE_TOKEN_STOPWORDS)


def _build_title_token_frequency(documents: list[dict[str, Any]]) -> dict[str, int]:
    """?????????? token ????????????????"""
    frequencies: dict[str, int] = {}
    for document in documents:
        tokens = tokenize_title(str(document.get("title") or ""))
        for token in tokens:
            frequencies[token] = int(frequencies.get(token, 0)) + 1
    return frequencies


def _is_bullet_line(line: str) -> bool:
    return bool(re.match(r"^(?:[-*?]|\d+\.)\s+", line.strip()))


def _split_extractable_segments(text: str) -> list[str]:
    raw_lines = [line.strip() for line in str(text).splitlines() if line.strip() and not line.strip().startswith("#")]
    segments: list[str] = []
    index = 0
    while index < len(raw_lines):
        current = raw_lines[index]
        if current.endswith(":") and index + 1 < len(raw_lines) and _is_bullet_line(raw_lines[index + 1]):
            block = [current]
            index += 1
            while index < len(raw_lines) and _is_bullet_line(raw_lines[index]):
                block.append(raw_lines[index])
                index += 1
            segments.append("\n".join(block))
            continue
        if _is_bullet_line(current):
            block = [current]
            index += 1
            while index < len(raw_lines) and _is_bullet_line(raw_lines[index]):
                block.append(raw_lines[index])
                index += 1
            segments.append("\n".join(block))
            continue
        pieces = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", current) if segment.strip()]
        segments.extend(pieces)
        index += 1
    return segments


def _build_extract_answer(question: str, text: str) -> str:
    segments = _split_extractable_segments(text)
    if not segments:
        return str(text).strip()

    terms = tokenize(question)
    if not terms:
        return str(text).strip()

    scored_segments: list[tuple[int, int, str]] = []
    safe_fallback_segments: list[str] = []
    for index, segment in enumerate(segments):
        overlap = terms & tokenize(segment)
        lowered_segment = segment.lower()
        is_risky_zero_overlap = not overlap and any(flag in lowered_segment for flag in RISKY_ZERO_OVERLAP_SEGMENTS)
        if is_risky_zero_overlap:
            continue
        safe_fallback_segments.append(segment)
        if overlap:
            scored_segments.append((len(overlap), index, segment))

    if not scored_segments:
        return "\n".join(safe_fallback_segments) if safe_fallback_segments else str(text).strip()

    lowered_question = str(question).lower()
    prefers_focused_answer = any(hint in lowered_question for hint in FOCUSED_QUESTION_HINTS)
    if len(safe_fallback_segments) <= 8 and not prefers_focused_answer:
        return "\n".join(safe_fallback_segments)

    scored_segments.sort(key=lambda item: (-item[0], item[1]))
    selected = sorted(scored_segments[:3], key=lambda item: item[1])
    return "\n".join(segment for _, _, segment in selected)


MULTI_SOURCE_HINTS = (
    "across the workflow boundary note",
    "across the folder boundary model",
    "across the scope manual",
    "across the scope board",
    "approval matrix and the war-room handover",
    "release checklist and the war-room handover",
    "approval whiteboard and the escalation whiteboard",
)


def _question_prefers_multi_source(question: str) -> bool:
    lowered = str(question).lower()
    if any(hint in lowered for hint in MULTI_SOURCE_HINTS):
        return True
    if "compare" not in lowered or " and " not in lowered:
        return False
    single_doc_compare_patterns = (
        "requested_scope_type and effective_kb_ids",
        "role of folders and the role of a knowledge base",
        "folder responsibilities with knowledge-base responsibilities",
    )
    return not any(pattern in lowered for pattern in single_doc_compare_patterns)


def _build_multi_source_answer(question: str, matches: list[SimpleNamespace]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for match in matches:
        title = str(getattr(match.node, "metadata", {}).get("file_name") or "document")
        snippet = _build_extract_answer(question, str(getattr(match.node, "text", ""))).strip()
        if not snippet:
            continue
        normalized = f"{title}: {snippet}"
        if normalized in seen:
            continue
        seen.add(normalized)
        parts.append(normalized)
    if parts:
        return "\n".join(parts)
    if matches:
        return _build_extract_answer(question, str(getattr(matches[0].node, "text", "")))
    return ""


class SemirealIndexManager:
    """åçå®ç´¢å¼ç®¡çå¨ï¼è¦çå¯¼å
¥ãæ¿æ¢ãåæ»ä¸æ£ç´¢æ¯æè½åã"""

    def __init__(self, kb_id: str, kb_dir: Path) -> None:
        self.kb_id = kb_id
        self.kb_dir = kb_dir.resolve()
        self.docstore = FakeDocStore()
        self.storage_context = FakeStorageContext(self.docstore)
        self.documents: list[dict[str, Any]] = []
        self.index = None
        self._last_ingestion_diagnostics: dict[str, Any] | None = None
        self._last_persist_diagnostics: dict[str, float] | None = None
        self._doc_counter = 0

    @staticmethod
    def _metadata_flag_truthy(value: Any) -> bool:
        """? metadata ????????????????"""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}
        return False

    @classmethod
    def _is_node_without_embedding(cls, node: SimpleNamespace | None) -> bool:
        """?????????????? embedding?????"""
        metadata = dict(getattr(node, "metadata", {}) or {})
        return cls._metadata_flag_truthy(metadata.get("simulate_nodes_without_embedding"))

    def _build_relative_path(self, path: Path | None, relative_path: str | None, title: str) -> str:
        if relative_path:
            return relative_path
        if path is None:
            return title
        resolved = path.resolve()
        if resolved.is_relative_to(self.kb_dir):
            return resolved.relative_to(self.kb_dir).as_posix()
        return path.name

    def _upsert_document_record(self, node: SimpleNamespace) -> None:
        metadata = dict(getattr(node, "metadata", {}) or {})
        doc_id = str(metadata.get("doc_id") or getattr(node, "ref_doc_id", "")).strip()
        title = str(metadata.get("file_name") or metadata.get("title") or doc_id or "document")
        relative_path = str(metadata.get("relative_path") or metadata.get("file_path") or title)
        self.documents = [item for item in self.documents if item.get("doc_id") != doc_id]
        self.documents.append(
            {
                "doc_id": doc_id,
                "relative_path": relative_path,
                "title": title,
                "text": str(getattr(node, "text", "")),
                "node": node,
            }
        )
        self.index = object()

    def register_text_document(
        self,
        *,
        path: Path | None,
        text: str,
        kb_id: str | None = None,
        relative_path: str | None = None,
        title: str | None = None,
        page_label: str = "1",
        extra_metadata: dict[str, Any] | None = None,
    ) -> SimpleNamespace:
        """把单条文本注册到 fake docstore，并生成稳定 metadata。"""
        resolved_title = title or (path.name if path is not None else f"doc-{self._doc_counter + 1}")
        resolved_relative_path = self._build_relative_path(path, relative_path, resolved_title)
        self._doc_counter += 1
        slug_base = re.sub(r"[^a-z0-9]+", "-", resolved_relative_path.lower()).strip("-") or f"doc-{self._doc_counter}"
        slug = f"{slug_base}-{self._doc_counter}"
        doc_id = f"doc-{slug}"
        node_id = f"node-{slug}"
        metadata = {
            "kb_id": kb_id or self.kb_id,
            "file_name": resolved_title,
            "title": resolved_title,
            "file_path": str(path) if path is not None else resolved_relative_path,
            "relative_path": resolved_relative_path,
            "doc_id": doc_id,
            "page_label": str(page_label),
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        node = SimpleNamespace(
            metadata=metadata,
            text=text,
            ref_doc_id=doc_id,
            node_id=node_id,
        )
        self.docstore.docs[node_id] = node
        self.docstore.ref_docs[doc_id] = FakeRefDocInfo(metadata=metadata, node_ids=[node_id])
        self._upsert_document_record(node)
        return node

    def _record_ingestion_diagnostics(
        self,
        *,
        document_count: int,
        input_text_chars: int,
        node_count: int,
        nodes: list[SimpleNamespace] | None = None,
    ) -> None:
        """?????????? embedding ????????????"""
        normalized_nodes = list(nodes or [])
        nodes_without_embedding_count = sum(1 for node in normalized_nodes if self._is_node_without_embedding(node))
        nodes_with_embedding_count = max(int(node_count) - nodes_without_embedding_count, 0)
        self._last_ingestion_diagnostics = {
            "document_count": document_count,
            "empty_document_count": 0,
            "input_text_chars": input_text_chars,
            "node_count": node_count,
            "nodes_with_embedding_count": nodes_with_embedding_count,
            "nodes_without_embedding_count": nodes_without_embedding_count,
        }

    def load_files(self, paths, chunk_size: int, chunk_overlap: int, kb_id: str | None = None, persist: bool = False):
        nodes: list[SimpleNamespace] = []
        input_text_chars = 0
        for raw_path in paths:
            path = Path(raw_path).resolve()
            if path.suffix.lower() == ".pdf":
                pdf = fitz.open(path)
                try:
                    pdf_text = "\n".join(page.get_text("text") for page in pdf).strip()
                finally:
                    pdf.close()
                text = pdf_text
            else:
                text = path.read_text(encoding="utf-8")
            node = self.register_text_document(path=path, text=text, kb_id=kb_id)
            nodes.append(node)
            input_text_chars += len(text)
        self._record_ingestion_diagnostics(
            document_count=len(nodes),
            input_text_chars=input_text_chars,
            node_count=len(nodes),
            nodes=nodes,
        )
        return nodes

    def load_documents(self, documents, chunk_size: int, chunk_overlap: int, kb_id: str | None = None, persist: bool = False):
        nodes: list[SimpleNamespace] = []
        input_text_chars = 0
        for document in documents:
            metadata = dict(getattr(document, "metadata", {}) or {})
            file_path = metadata.get("file_path")
            path = Path(file_path).resolve() if isinstance(file_path, str) and file_path else None
            node = self.register_text_document(
                path=path,
                text=str(getattr(document, "text", "")),
                kb_id=kb_id,
                relative_path=metadata.get("relative_path"),
                title=metadata.get("file_name") or metadata.get("title"),
                page_label=str(metadata.get("page_label") or metadata.get("page") or "1"),
                extra_metadata=metadata,
            )
            nodes.append(node)
            input_text_chars += len(str(getattr(document, "text", "")))
        self._record_ingestion_diagnostics(
            document_count=len(nodes),
            input_text_chars=input_text_chars,
            node_count=len(nodes),
            nodes=nodes,
        )
        return nodes

    def delete_ref_doc(self, ref_doc_id: str, *, persist: bool = True) -> None:
        del persist
        self.docstore.remove_ref_doc(ref_doc_id)
        self.documents = [item for item in self.documents if item.get("doc_id") != ref_doc_id]
        if not self.documents:
            self.index = None

    def insert_nodes(self, nodes, persist: bool = False) -> None:
        del persist
        for raw_node in list(nodes or []):
            node = SimpleNamespace(
                metadata=dict(getattr(raw_node, "metadata", {}) or {}),
                text=str(getattr(raw_node, "text", "")),
                ref_doc_id=getattr(raw_node, "ref_doc_id", None) or getattr(raw_node, "doc_id", None),
                node_id=getattr(raw_node, "node_id", None),
            )
            doc_id = str(node.ref_doc_id or node.metadata.get("doc_id") or "").strip()
            node_id = str(node.node_id or f"node-{doc_id}").strip()
            if not doc_id:
                continue
            node.ref_doc_id = doc_id
            node.node_id = node_id
            node.metadata.setdefault("doc_id", doc_id)
            self.docstore.docs[node_id] = node
            self.docstore.ref_docs[doc_id] = FakeRefDocInfo(metadata=dict(node.metadata), node_ids=[node_id])
            self._upsert_document_record(node)

    def check_index_exists(self) -> bool:
        return bool(self.documents)

    def persist(self) -> bool:
        self._last_persist_diagnostics = {
            "docstore_persist_ms": 0.0,
            "index_store_persist_ms": 0.0,
            "graph_store_persist_ms": 0.0,
            "vector_store_persist_ms": 0.0,
            "fallback_persist_ms": 0.0,
            "vector_store_namespaces_ms": {"default": 0.0},
            "total_ms": 0.0,
        }
        return True

    def persist_storage(self) -> bool:
        """兼容 import_files 当前调用的 persist_storage 别名。"""
        return self.persist()

    def consume_last_ingestion_diagnostics(self):
        payload = self._last_ingestion_diagnostics
        self._last_ingestion_diagnostics = None
        return payload

    def consume_last_persist_diagnostics(self):
        payload = self._last_persist_diagnostics
        self._last_persist_diagnostics = None
        return payload

    def search(self, question: str, top_k: int = 1) -> list[SimpleNamespace]:
        """??????????????"""
        terms = tokenize(question)
        title_terms = tokenize_title(question)
        if not terms and not title_terms:
            return []

        anchor_terms = (terms - GENERIC_POLICY_TERMS) | ((title_terms - GENERIC_POLICY_TERMS) - QUESTION_STOPWORDS)
        enforce_anchor_match = bool((terms | title_terms) & WEAK_SIGNAL_TERMS)
        title_token_frequency = _build_title_token_frequency(self.documents)
        scored: list[SimpleNamespace] = []
        for document in self.documents:
            node = document["node"]
            text_body = str(document.get("text") or "").strip()
            if not text_body:
                continue

            body_overlap = terms & tokenize(text_body)
            title_overlap = title_terms & tokenize_title(str(document.get("title") or ""))
            combined_overlap = body_overlap | title_overlap
            if not combined_overlap:
                continue

            if enforce_anchor_match and anchor_terms and not (combined_overlap & anchor_terms):
                continue

            title_bonus = sum(1.0 / float(title_token_frequency.get(token, 1)) for token in title_overlap)
            title_bonus += 0.5 * float(len(title_overlap))
            if not body_overlap:
                title_bonus *= 0.75 if len(title_overlap) >= 2 else 0.5

            score = 1.25 * float(len(body_overlap)) + title_bonus
            if self._is_node_without_embedding(node):
                # ?? embedding ????????????? + ???????????
                # ????????????? embedding ??????????
                score -= 0.25

            scored.append(
                SimpleNamespace(
                    node=document["node"],
                    score=score,
                    matched_terms=sorted(combined_overlap),
                    body_overlap=sorted(body_overlap),
                    title_overlap=sorted(title_overlap),
                )
            )
        scored.sort(
            key=lambda item: (
                -float(item.score or 0.0),
                -len(getattr(item, "body_overlap", [])),
                -len(getattr(item, "title_overlap", [])),
                item.node.metadata.get("file_name", ""),
            )
        )
        return scored[:top_k]


class SemirealQueryEngine:
    """使用半真实索引结果返回稳定 answer 与 source_nodes。"""

    def __init__(self, manager: SemirealIndexManager) -> None:
        self.manager = manager

    def query(self, question: str):
        multi_source = _question_prefers_multi_source(question)
        matches = self.manager.search(question, top_k=2 if multi_source else 1)
        if not matches:
            return SimpleNamespace(
                response=(
                    "No confirmable information is available in the current knowledge base. "
                    "Stay inside the active knowledge base and the assistant must not fabricate an answer."
                ),
                source_nodes=[],
            )
        if multi_source and len(matches) > 1:
            return SimpleNamespace(response=_build_multi_source_answer(question, matches), source_nodes=matches)
        best = matches[0]
        return SimpleNamespace(response=_build_extract_answer(question, str(best.node.text)), source_nodes=matches[:1])
