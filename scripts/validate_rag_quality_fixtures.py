"""校验 RAG QA fixture schema 与防污染约束。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_BASE = {"id", "query", "expected_answer", "status"}
FIXTURE_PARTS = ("tests", "fixtures", "rag_quality")


def _has_subsequence(parts: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    normalized = tuple(part.replace("\\", "/") for part in parts)
    for idx in range(0, len(normalized) - len(needle) + 1):
        if normalized[idx : idx + len(needle)] == needle:
            return True
    return False


def validate_record(record: dict[str, Any], *, source: Path) -> None:
    """校验单条 QA fixture。"""
    missing = REQUIRED_BASE - record.keys()
    if missing:
        raise ValueError(f"{source}: 缺少字段 {sorted(missing)}")

    status = record["status"]
    if status not in {"draft", "verified"}:
        raise ValueError(f"{source}: status 必须是 draft 或 verified")

    if status == "draft":
        return

    if not record.get("search_kb_ids"):
        raise ValueError(f"{source}: verified 必须提供 search_kb_ids")
    relevant = record.get("relevant_documents") or []
    if not relevant:
        raise ValueError(f"{source}: verified 必须提供 relevant_documents")

    for doc in relevant:
        for field in ["kb_id", "file_name", "evidence"]:
            if not doc.get(field):
                raise ValueError(f"{source}: relevant_documents 缺少 {field}")
        file_path = doc.get("file_path")
        if file_path:
            path = Path(file_path)
            if _has_subsequence(path.parts, FIXTURE_PARTS):
                raise ValueError(f"{source}: relevant_documents.file_path 不能指向 fixture 目录")
            parts = path.parts
            if "data" not in parts:
                raise ValueError(f"{source}: relevant_documents.file_path 必须指向 data 下的知识库文件")


def validate_files(paths: list[str | Path]) -> None:
    """校验多个 jsonl fixture，并检查 ID 唯一性。"""
    seen: set[str] = set()
    for raw_path in paths:
        path = Path(raw_path)
        if "data" in path.parts:
            raise ValueError(f"fixture 不能放在 data 目录: {path}")
        if not path.exists():
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            record = json.loads(line)
            validate_record(record, source=path)
            record_id = record["id"]
            if record_id in seen:
                raise ValueError(f"duplicate id: {record_id}")
            seen.add(record_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="校验 RAG QA fixture")
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    validate_files(args.paths)
    print("fixture 校验通过")


if __name__ == "__main__":
    main()
