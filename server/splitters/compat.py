"""langchain_text_splitters 兼容层 — 不依赖 torch/sentence-transformers。"""

import re
from typing import Any


def _join_docs(docs: list[str], separator: str) -> str | None:
    text = separator.join(docs)
    return text if text else None


def _merge_splits(splits: list[str], separator: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """合并分割后的片段，与 langchain RecursiveCharacterTextSplitter 逻辑一致。"""
    docs: list[str] = []
    current_doc: list[str] = []
    total = 0
    for d in splits:
        _len = len(d)
        if total + _len > chunk_size:
            if total > chunk_size:
                print(f"Created a chunk of size {total}, which is longer than the specified {chunk_size}")
            if current_doc:
                doc = _join_docs(current_doc, separator)
                if doc is not None:
                    docs.append(doc)
                while total > chunk_overlap:
                    total -= len(current_doc[0])
                    current_doc.pop(0)
                    if total < 0:
                        break
            current_doc.append(d)
            total += _len
        else:
            current_doc.append(d)
            total += _len
    doc = _join_docs(current_doc, separator)
    if doc is not None:
        docs.append(doc)
    return docs


class TextSplitter:
    """迷你版 CharacterTextSplitter / RecursiveCharacterTextSplitter 替代。"""
    def __init__(self, **kwargs: Any):
        self._chunk_size = kwargs.pop("chunk_size", 2048)
        self._chunk_overlap = kwargs.pop("chunk_overlap", 200)
        self._length_function = kwargs.pop("length_function", len)
        self._kwargs = kwargs

    def split_text(self, text: str) -> list[str]:
        raise NotImplementedError

    def split_text1(self, text: str) -> list[str]:
        return [text]

    def create_documents(self, texts: list[str], metadatas: list[dict] | None = None) -> list:
        from llama_index.core.schema import Document
        return [Document(text=t, metadata=(m or {})) for t, m in zip(texts, metadatas or [{}] * len(texts))]


class CharacterTextSplitter(TextSplitter):
    pass


class RecursiveCharacterTextSplitter(TextSplitter):
    def _merge_splits(self, splits: list[str], separator: str) -> list[str]:
        return _merge_splits(splits, separator, self._chunk_size, self._chunk_overlap)
