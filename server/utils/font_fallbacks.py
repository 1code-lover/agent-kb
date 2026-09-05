"""跨平台 OCR 诊断/测试字体候选与加载 helper。"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

_CJK_PRIORITY_FONT_CANDIDATES = (
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/System/Library/Fonts/STHeiti Light.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"),
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),
)

_LATIN_FALLBACK_FONT_CANDIDATES = (
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/System/Library/Fonts/Supplemental/Verdana.ttf"),
    Path("/System/Library/Fonts/Helvetica.ttc"),
    Path("/Library/Fonts/Arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("C:/Windows/Fonts/calibri.ttf"),
)


def _dedupe_candidates(candidates: Iterable[Path]) -> tuple[Path, ...]:
    """按声明顺序去重字体候选，避免多处重复维护。"""
    ordered: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        normalized = Path(candidate)
        if normalized in seen:
            continue
        ordered.append(normalized)
        seen.add(normalized)
    return tuple(ordered)


OCR_FONT_CANDIDATES: tuple[Path, ...] = _dedupe_candidates(
    (*_CJK_PRIORITY_FONT_CANDIDATES, *_LATIN_FALLBACK_FONT_CANDIDATES)
)


def load_first_available_font(size: int, *, candidates: Iterable[Path] | None = None):
    """选择首个可用 TrueType 字体；都不可用时回退 PIL 默认字体。"""
    from PIL import ImageFont

    for candidate in candidates or OCR_FONT_CANDIDATES:
        path = Path(candidate)
        try:
            if path.exists():
                return ImageFont.truetype(str(path), size=size), str(path)
        except Exception:
            continue
    return ImageFont.load_default(), "default"
