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


def evaluate_pdf(pdf_path: Path, keywords: Iterable[str]) -> dict:
    """读取 PDF 并返回 OCR 解析质量报告。"""
    from server.readers.pdf_ocr import PDFOCRReader

    reader = PDFOCRReader()
    docs = reader.load_data(str(pdf_path))
    text = "\n".join(doc.text for doc in docs)
    recall = evaluate_keyword_recall(text, keywords)
    return {
        "pdf_path": str(pdf_path),
        "document_count": len(docs),
        "text_length": len(text),
        "keyword_recall": asdict(recall),
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
