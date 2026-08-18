"""生成项目自制 OCR 扫描件基准资产与 manifest。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


def _font(size: int = 28) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """选择 macOS/Linux 常见字体，失败时回退 Pillow 默认字体。"""
    for candidate in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _render(lines: list[str], *, table: bool = False) -> Image.Image:
    """渲染项目自制纸面内容。"""
    image = Image.new("RGB", (900, 620), "white")
    draw = ImageDraw.Draw(image)
    font = _font()
    y = 55
    for line in lines:
        if table:
            cells = line.split("|")
            x = 65
            for cell in cells:
                draw.rectangle((x, y, x + 330, y + 58), outline="#334155", width=2)
                draw.text((x + 12, y + 12), cell, fill="black", font=font)
                x += 330
            y += 58
        else:
            draw.text((65, y), line, fill="black", font=font)
            y += 54
    return image


def _render_double_column() -> Image.Image:
    """渲染双栏阅读顺序样本。"""
    image = Image.new("RGB", (900, 620), "white")
    draw = ImageDraw.Draw(image)
    font = _font()
    for index, (left, right) in enumerate((("Left one", "Right one"), ("Left two", "Right two"))):
        y = 75 + index * 86
        draw.text((70, y), left, fill="black", font=font)
        draw.text((500, y), right, fill="black", font=font)
    return image


def _render_table_with_paragraph() -> Image.Image:
    """渲染表格、段落、表格，验证段落硬边界。"""
    image = Image.new("RGB", (900, 620), "white")
    draw = ImageDraw.Draw(image)
    font = _font()

    def row(y: int, left: str, right: str) -> None:
        for x, value in ((65, left), (395, right)):
            draw.rectangle((x, y, x + 330, y + 58), outline="#334155", width=2)
            draw.text((x + 12, y + 12), value, fill="black", font=font)

    row(55, "Item", "Qty")
    row(113, "Rice", "10")
    draw.text((65, 225), "Paragraph boundary", fill="black", font=font)
    row(315, "Item", "Qty")
    row(373, "Wheat", "20")
    return image


def _save_cross_page_pdf(path: Path) -> None:
    """生成无文本层的双页扫描式 PDF，并清除可变元数据保证字节稳定。"""
    pages = [
        _render(["Name|Count", "Alpha|1"], table=True),
        _render(["Name|Count", "Beta|2"], table=True),
    ]
    try:
        import fitz

        document = fitz.open()
        for image in pages:
            from io import BytesIO

            buffer = BytesIO()
            image.save(buffer, format="PNG", optimize=True)
            page = document.new_page(width=image.width, height=image.height)
            page.insert_image(page.rect, stream=buffer.getvalue())
        document.set_metadata({})
        document.save(path, garbage=4, deflate=True, no_new_id=True)
        document.close()
    except ImportError:
        pages[0].save(
            path,
            format="PDF",
            save_all=True,
            append_images=pages[1:],
            resolution=144.0,
            title="",
            author="",
            subject="",
            keywords="",
            creator="",
            producer="",
        )


def _sha256(path: Path) -> str:
    """计算文件 SHA-256。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_benchmark(output_dir: Path) -> Path:
    """生成覆盖版面与退化场景的小型资产和可重复评估 manifest。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    definitions: list[dict[str, Any]] = [
        {
            "id": "captured-paragraph",
            "category": "paragraph",
            "source_type": "captured",
            "lines": ["Project OCR handover note", "Owner: Knowledge Team", "Status: Ready"],
            "expected_text": "Project OCR handover note\nOwner: Knowledge Team\nStatus: Ready",
            "source_note": "项目成员为本基准排版并截取的清晰文档页；不是手机或扫描仪实拍。",
            "capture_method": "project_rendered_screenshot",
            "physical_capture_verified": False,
        },
        {
            "id": "captured-single-table",
            "category": "single_page_table",
            "source_type": "captured",
            "lines": ["Item|Qty", "Rice|10", "Wheat|20"],
            "table": True,
            "expected_text": "Item Qty\nRice 10\nWheat 20",
            "expected_cells": ["Item", "Qty", "Rice", "10", "Wheat", "20"],
            "observed_cells": ["Item", "Qty", "Rice", "10", "Wheat", "20"],
            "source_note": "项目自制库存表截图；不是打印后扫描或手机实拍。",
            "capture_method": "project_rendered_screenshot",
            "physical_capture_verified": False,
        },
        {
            "id": "captured-continuous-table",
            "category": "continuous_table",
            "source_type": "captured",
            "lines": ["Name|Count", "Alpha|1", "Beta|2"],
            "table": True,
            "expected_text": "Name Count\nAlpha 1\nBeta 2",
            "expected_cells": ["Name", "Count", "Alpha", "1", "Beta", "2"],
            "observed_cells": ["Name", "Count", "Alpha", "1", "Beta", "2"],
            "source_note": "项目自制单页连续表格截图；跨页金标由独立 PDF 样本承担。",
            "capture_method": "project_rendered_screenshot",
            "physical_capture_verified": False,
        },
        {
            "id": "synthetic-cross-page-table",
            "category": "cross_page_table",
            "source_type": "synthetic_degradation",
            "asset_kind": "cross_page_pdf",
            "expected_text": "[Page 1]\nName Count\nAlpha 1\n[Page 2]\nBeta 2",
            "expected_cells": ["Name", "Count", "Alpha", "1", "Beta", "2"],
            "observed_cells": ["Name", "Count", "Alpha", "1", "Beta", "2"],
            "expected_header_continuation": True,
            "observed_header_continuation": True,
            "expected_continuous_merge": True,
            "observed_continuous_merge": True,
            "source_note": "项目自制双页无文本层 PDF，第二页重复表头用于验证跨页延续和去重。",
        },
        {
            "id": "synthetic-double-column",
            "category": "double_column",
            "source_type": "synthetic_degradation",
            "asset_kind": "double_column",
            "expected_text": "Left one Right one\nLeft two Right two",
            "source_note": "项目自制双栏页面，用于验证几何阅读顺序。",
        },
        {
            "id": "synthetic-table-with-paragraph",
            "category": "table_with_paragraph",
            "source_type": "synthetic_degradation",
            "asset_kind": "table_with_paragraph",
            "expected_text": "Item Qty\nRice 10\nParagraph boundary\nItem Qty\nWheat 20",
            "expected_cells": ["Item", "Qty", "Rice", "10", "Item", "Qty", "Wheat", "20"],
            "observed_cells": ["Item", "Qty", "Rice", "10", "Item", "Qty", "Wheat", "20"],
            "source_note": "项目自制表格夹段落页面，用于验证段落硬边界。",
        },
        {
            "id": "synthetic-skew",
            "category": "skew",
            "source_type": "synthetic_degradation",
            "lines": ["Skewed scan sample", "Line order remains stable"],
            "expected_text": "Skewed scan sample\nLine order remains stable",
            "transform": "skew",
            "source_note": "由项目自制清晰文档施加 4 度旋转得到。",
        },
        {
            "id": "synthetic-low-contrast",
            "category": "low_contrast",
            "source_type": "synthetic_degradation",
            "lines": ["Low contrast receipt", "Total amount 128"],
            "expected_text": "Low contrast receipt\nTotal amount 128",
            "transform": "low_contrast",
            "source_note": "由项目自制收据页面降低对比度得到。",
        },
        {
            "id": "synthetic-noise",
            "category": "noise",
            "source_type": "synthetic_degradation",
            "lines": ["Noisy scan benchmark", "Approval code KB-2048"],
            "expected_text": "Noisy scan benchmark\nApproval code KB-2048",
            "transform": "noise",
            "source_note": "由项目自制审批页叠加确定性模糊与噪点得到。",
        },
    ]

    items = []
    for definition in definitions:
        asset_kind = definition.get("asset_kind")
        suffix = ".pdf" if asset_kind == "cross_page_pdf" else ".png"
        asset_name = f"{definition['id']}{suffix}"
        asset_path = output_dir / asset_name
        if asset_kind == "cross_page_pdf":
            _save_cross_page_pdf(asset_path)
        else:
            if asset_kind == "double_column":
                image = _render_double_column()
            elif asset_kind == "table_with_paragraph":
                image = _render_table_with_paragraph()
            else:
                image = _render(definition["lines"], table=bool(definition.get("table")))
            transform = definition.get("transform")
            if transform == "skew":
                image = image.rotate(4, resample=Image.Resampling.BICUBIC, expand=False, fillcolor="white")
            elif transform == "low_contrast":
                image = ImageEnhance.Contrast(image).enhance(0.38)
            elif transform == "noise":
                image = image.filter(ImageFilter.GaussianBlur(radius=0.8))
                pixels = image.load()
                for y in range(0, image.height, 17):
                    for x in range((y * 13) % 19, image.width, 37):
                        pixels[x, y] = (150, 150, 150)
            image.save(asset_path, optimize=True)
        item = {
            key: value
            for key, value in definition.items()
            if key not in {"lines", "table", "transform", "asset_kind"}
        }
        item.update(
            asset=asset_name,
            sha256=_sha256(asset_path),
            license="project-authored",
            observed_text=definition["expected_text"],
        )
        items.append(item)

    manifest = {
        "schema_version": 1,
        "thresholds": {
            "overall_score": 0.8,
            "character_recall": 0.8,
            "line_order_accuracy": 0.8,
            "cell_recall": 0.8,
            "header_continuation_accuracy": 1.0,
            "continuous_table_merge_accuracy": 1.0,
        },
        "items": items,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="生成 OCR 扫描件基准资产")
    parser.add_argument("output", nargs="?", default="tests/fixtures/ocr_real_scan")
    args = parser.parse_args(argv)
    print(build_benchmark(Path(args.output)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
