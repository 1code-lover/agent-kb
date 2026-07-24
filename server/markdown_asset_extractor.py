"""Markdown 内嵌图片提取器。"""

from __future__ import annotations

import hashlib
import mimetypes
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote

_MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\((?P<target>[^)]+)\)")
_HTML_IMAGE_PATTERN = re.compile(r'<img\b[^>]*\bsrc=["\'](?P<target>[^"\']+)["\'][^>]*>', re.IGNORECASE)
_REMOTE_PREFIXES = ("http://", "https://", "data:", "//")


def _iter_image_candidates(markdown_text: str) -> list[tuple[int, str]]:
    """按源码出现顺序收集 Markdown / HTML 图片引用。"""
    matches: list[tuple[int, str]] = []
    for match in _MARKDOWN_IMAGE_PATTERN.finditer(markdown_text):
        target = match.group("target").strip()
        if target.startswith("<") and target.endswith(">"):
            target = target[1:-1].strip()
        else:
            target = target.split()[0]
        matches.append((match.start(), target))
    for match in _HTML_IMAGE_PATTERN.finditer(markdown_text):
        matches.append((match.start(), match.group("target").strip()))
    matches.sort(key=lambda item: item[0])
    return matches


def _is_ignored_target(target: str) -> bool:
    """远程 URL 与 data URI 不纳入本地 KB 资产解析。"""
    lowered = target.lower()
    return lowered.startswith(_REMOTE_PREFIXES)


def _is_absolute_target(target: str) -> bool:
    """绝对路径或盘符路径视为非法本地资产引用。"""
    if target.startswith(("/", "\\")):
        return True
    return bool(re.match(r"^[a-zA-Z]:[\/]", target))


def _build_asset_id(source_doc_relative_path: str, occurrence_index: int, referenced_path: str) -> str:
    """生成稳定的 embedded asset 标识。"""
    seed = f"{source_doc_relative_path}|{occurrence_index}|{referenced_path}".encode("utf-8")
    return f"embedded-{hashlib.sha1(seed).hexdigest()[:16]}"


def extract_markdown_embedded_assets(
    *,
    markdown_text: str,
    source_doc_path: Path,
    kb_root: Path,
    source_doc_relative_path: str | None = None,
) -> list[dict[str, Any]]:
    """从 Markdown 文本中提取属于当前知识库的本地图片资产。"""
    source_doc_path = Path(source_doc_path).resolve()
    kb_root = Path(kb_root).resolve()
    if source_doc_relative_path is None:
        try:
            source_doc_relative_path = source_doc_path.relative_to(kb_root).as_posix()
        except ValueError:
            source_doc_relative_path = source_doc_path.name

    assets: list[dict[str, Any]] = []
    occurrence_index = 0
    for _, raw_target in _iter_image_candidates(markdown_text):
        target = unquote(raw_target.strip())
        if not target or _is_ignored_target(target):
            continue

        occurrence_index += 1
        asset = {
            "asset_id": _build_asset_id(source_doc_relative_path, occurrence_index, target),
            "asset_type": "image",
            "asset_role": "embedded",
            "source_type": "embedded",
            "source_doc_path": str(source_doc_path),
            "source_doc_relative_path": source_doc_relative_path,
            "referenced_path": target,
            "occurrence_index": occurrence_index,
        }

        if _is_absolute_target(target):
            asset.update(
                {
                    "status": "invalid",
                    "path": None,
                    "resolved_relative_path": None,
                    "mime_type": None,
                    "message": "absolute asset path is not allowed",
                }
            )
            assets.append(asset)
            continue

        resolved_path = (source_doc_path.parent / Path(target)).resolve(strict=False)
        try:
            resolved_relative_path = resolved_path.relative_to(kb_root).as_posix()
        except ValueError:
            asset.update(
                {
                    "status": "invalid",
                    "path": None,
                    "resolved_relative_path": None,
                    "mime_type": None,
                    "message": "asset path escapes kb root",
                }
            )
            assets.append(asset)
            continue

        mime_type, _ = mimetypes.guess_type(resolved_path.name)
        asset.update(
            {
                "status": "ready" if resolved_path.is_file() else "missing",
                "path": str(resolved_path),
                "resolved_relative_path": resolved_relative_path,
                "mime_type": mime_type,
            }
        )
        if not resolved_path.is_file():
            asset["message"] = "asset file not found"
        assets.append(asset)

    return assets


def extract_markdown_embedded_assets_from_file(
    source_doc_path: Path,
    kb_root: Path,
    source_doc_relative_path: str | None = None,
) -> list[dict[str, Any]]:
    """从 Markdown 文件读取内容并提取本地图片资产。"""
    markdown_text = Path(source_doc_path).read_text(encoding="utf-8", errors="ignore")
    return extract_markdown_embedded_assets(
        markdown_text=markdown_text,
        source_doc_path=source_doc_path,
        kb_root=kb_root,
        source_doc_relative_path=source_doc_relative_path,
    )
