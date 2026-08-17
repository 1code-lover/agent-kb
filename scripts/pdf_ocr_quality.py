"""
PDF OCR 解析质量评估脚本：按关键词召回率衡量 OCR 文本质量。
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class LineOrderResult:
    """期望文本片段的阅读顺序准确率。"""

    total: int
    matched_pairs: int
    accuracy: float
    missing_lines: list[str]


@dataclass(frozen=True)
class TableCellRecallResult:
    """表格单元格召回统计。"""

    total: int
    hit_count: int
    miss_count: int
    missed_cells: list[str]
    recall: float


@dataclass(frozen=True)
class KeywordRecallResult:
    """关键词召回统计结果。"""

    total: int
    hit_count: int
    miss_count: int
    hit_terms: list[str]
    missed_terms: list[str]
    recall: float


def evaluate_keyword_recall(text: str, keywords: Iterable[str]) -> KeywordRecallResult:
    """根据关键词列表统计 OCR 文本的召回情况。"""
    keyword_list = [keyword for keyword in keywords if keyword]
    hit_terms = [keyword for keyword in keyword_list if keyword in text]
    missed_terms = [keyword for keyword in keyword_list if keyword not in text]
    total = len(keyword_list)
    hit_count = len(hit_terms)
    recall = hit_count / total if total else 0.0
    return KeywordRecallResult(
        total=total,
        hit_count=hit_count,
        miss_count=len(missed_terms),
        hit_terms=hit_terms,
        missed_terms=missed_terms,
        recall=recall,
    )


def evaluate_line_order(text: str, expected_lines: Iterable[str]) -> LineOrderResult:
    """统计期望片段是否按给定顺序出现在 OCR 文本中。"""
    lines = [line for line in expected_lines if line]
    cursor = 0
    matched = 0
    missing: list[str] = []
    for line in lines:
        position = text.find(line, cursor)
        if position < 0:
            missing.append(line)
            continue
        matched += 1
        cursor = position + len(line)
    total = len(lines)
    return LineOrderResult(total=total, matched_pairs=matched, accuracy=matched / total if total else 0.0, missing_lines=missing)


def evaluate_table_cell_recall(text: str, expected_rows: Iterable[Iterable[str]]) -> TableCellRecallResult:
    """把期望表格展平为单元格，统计 OCR 文本中的召回。"""
    cells = [str(cell) for row in expected_rows for cell in row if str(cell)]
    missed = [cell for cell in cells if cell not in text]
    hit_count = len(cells) - len(missed)
    total = len(cells)
    return TableCellRecallResult(
        total=total,
        hit_count=hit_count,
        miss_count=len(missed),
        missed_cells=missed,
        recall=hit_count / total if total else 0.0,
    )


def evaluate_pdf(
    pdf_path: Path,
    keywords: Iterable[str],
    *,
    expected_lines: Iterable[str] = (),
    expected_table_rows: Iterable[Iterable[str]] = (),
) -> dict:
    """读取 PDF 并返回关键词、阅读顺序和表格单元格质量报告。"""
    from server.readers.pdf_ocr import PDFOCRReader

    reader = PDFOCRReader()
    docs = reader.load_data(str(pdf_path))
    text = "\n".join(doc.text for doc in docs)
    recall = evaluate_keyword_recall(text, keywords)
    line_order = evaluate_line_order(text, expected_lines)
    table_recall = evaluate_table_cell_recall(text, expected_table_rows)
    return {
        "pdf_path": str(pdf_path),
        "document_count": len(docs),
        "text_length": len(text),
        "keyword_recall": asdict(recall),
        "line_order": asdict(line_order),
        "table_cell_recall": asdict(table_recall),
        "text_preview": text[:500],
    }


def main() -> int:
    """命令行入口：输出 JSON 格式的 PDF OCR 质量报告。"""
    parser = argparse.ArgumentParser(description="评估 PDF OCR 解析质量")
    parser.add_argument("pdf", type=Path, help="待评估的 PDF 文件路径")
    parser.add_argument("--keywords", nargs="+", required=True, help="期望召回的关键词列表")
    parser.add_argument("--output", type=Path, help="可选：质量报告输出路径")
    args = parser.parse_args()

    report = evaluate_pdf(args.pdf, args.keywords)
    content = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
