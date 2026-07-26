"""本地文本文件解码工具。"""

from __future__ import annotations

from codecs import BOM_UTF16_BE, BOM_UTF16_LE, BOM_UTF8
from dataclasses import dataclass
from pathlib import Path

_PRIMARY_TEXT_ENCODINGS = ("utf-8-sig", "utf-8")
_FALLBACK_TEXT_ENCODINGS = ("gb18030", "cp1252")


@dataclass(frozen=True)
class DecodedTextFile:
    """记录文本文件解码结果，便于上层补充诊断信息。"""

    text: str
    encoding: str
    used_fallback: bool


def _looks_like_utf16(raw: bytes) -> bool:
    """根据 BOM 与空字节分布，粗略判断内容是否更像 UTF-16。"""
    if raw.startswith((BOM_UTF16_LE, BOM_UTF16_BE)):
        return True

    sample = raw[:256]
    if len(sample) < 4:
        return False

    even_bytes = sample[0::2]
    odd_bytes = sample[1::2]
    even_null_ratio = even_bytes.count(0) / max(len(even_bytes), 1)
    odd_null_ratio = odd_bytes.count(0) / max(len(odd_bytes), 1)
    return max(even_null_ratio, odd_null_ratio) >= 0.30


def _iter_candidate_encodings(raw: bytes) -> list[str]:
    """按项目场景返回优先尝试的编码顺序。"""
    if raw.startswith(BOM_UTF8):
        return ["utf-8-sig"]

    candidates: list[str] = ["utf-8", "utf-8-sig"]
    if raw.startswith((BOM_UTF16_LE, BOM_UTF16_BE)):
        candidates.append("utf-16")
    elif _looks_like_utf16(raw):
        candidates.extend(["utf-16-le", "utf-16-be"])

    candidates.extend(_FALLBACK_TEXT_ENCODINGS)

    unique_candidates: list[str] = []
    for encoding in candidates:
        if encoding not in unique_candidates:
            unique_candidates.append(encoding)
    return unique_candidates


def read_text_file_with_fallback(path: str | Path) -> DecodedTextFile:
    """按预设编码顺序严格解码文本文件，避免 utf-8 ignore 静默吞字。"""
    raw = Path(path).read_bytes()
    if not raw:
        return DecodedTextFile(text="", encoding="utf-8", used_fallback=False)

    for encoding in _iter_candidate_encodings(raw):
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        return DecodedTextFile(
            text=text,
            encoding=encoding,
            used_fallback=encoding not in _PRIMARY_TEXT_ENCODINGS,
        )

    return DecodedTextFile(
        text=raw.decode("utf-8", errors="replace"),
        encoding="utf-8-replace",
        used_fallback=True,
    )
