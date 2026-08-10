"""粮仓 QA 期望文件覆盖诊断脚本。

本脚本读取 verified.jsonl、storage/docstore.json、kb asset registry 和
既有 QA eval 报告，逐个检查 QA 期望文件是否完成了本地文件、
docstore 节点、kb_id metadata 与 top5 召回覆盖。kb asset registry
只作为图片/嵌入资产的辅助信息，不作为普通 PDF/DOCX 导入成功条件。
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_HASH_SUFFIX_RE = re.compile(r"_[0-9a-f]{6,16}(?=\.[A-Za-z0-9]+$)")
_FULLWIDTH_TRANSLATION = str.maketrans({"（": "(", "）": ")"})

FAILURE_REASON_ORDER = (
    "missing_local_file",
    "missing_asset_registry",
    "missing_docstore_nodes",
    "missing_or_wrong_kb_id",
    "retrieval_not_top5",
    "ok",
)

ASSET_REGISTRY_EXTENSIONS = {
    ".avif",
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".tif",
    ".tiff",
    ".webp",
}


def normalize_file_name(name: str) -> str:
    """归一化文件名，剥离导入 hash 后缀并统一全角/半角括号。"""
    return _HASH_SUFFIX_RE.sub("", os.path.basename(name)).translate(_FULLWIDTH_TRANSLATION)


def load_json(path: str | Path, default: Any) -> Any:
    """读取 JSON 文件；不存在或为空时返回 default。"""
    target = Path(path)
    if not target.exists() or target.stat().st_size == 0:
        return default
    return json.loads(target.read_text(encoding="utf-8"))


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    """读取 verified.jsonl 用例。"""
    cases: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue
            item = json.loads(line)
            item.setdefault("_line_no", line_no)
            cases.append(item)
    return cases


def _iter_string_values(value: Any) -> list[str]:
    """递归收集 JSON 结构中的字符串值，用于兼容不同 asset registry 形态。"""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for child in value.values():
            strings.extend(_iter_string_values(child))
        return strings
    if isinstance(value, list):
        strings = []
        for child in value:
            strings.extend(_iter_string_values(child))
        return strings
    return []


def build_asset_name_index(asset_registry: Any) -> set[str]:
    """从 asset registry 中抽取可匹配的归一化文件名集合。"""
    names: set[str] = set()
    for value in _iter_string_values(asset_registry):
        if "." not in value:
            continue
        name = normalize_file_name(value)
        if Path(name).suffix:
            names.add(name)
    return names


def build_local_name_index(data_root: str | Path) -> dict[str, list[str]]:
    """扫描本地资料目录，建立归一化文件名到实际路径的映射。"""
    root = Path(data_root)
    index: dict[str, list[str]] = {}
    if not root.exists():
        return index
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        name = normalize_file_name(path.name)
        index.setdefault(name, []).append(str(path))
    return index


def build_eval_top5_index(eval_report: Any) -> dict[str, set[str]]:
    """从 QA eval 报告中提取每个 case 的 top5 来源文件集合。"""
    index: dict[str, set[str]] = {}
    if not isinstance(eval_report, dict):
        return index
    for case in eval_report.get("cases", []) or []:
        if not isinstance(case, dict):
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id:
            continue
        files = {
            normalize_file_name(item)
            for item in case.get("source_files_top5", []) or []
            if isinstance(item, str) and item
        }
        index[case_id] = files
    return index


def is_asset_registry_applicable(file_name: str) -> bool:
    """判断期望文件是否应出现在 asset registry。"""
    return Path(file_name).suffix.lower() in ASSET_REGISTRY_EXTENSIONS


def build_docstore_name_index(docstore: Any) -> dict[str, list[dict[str, Any]]]:
    """从 docstore/data 中抽取文件名到节点 metadata 的映射。"""
    index: dict[str, list[dict[str, Any]]] = {}
    if not isinstance(docstore, dict):
        return index
    data = docstore.get("docstore/data") or {}
    if not isinstance(data, dict):
        return index
    for wrapper in data.values():
        if not isinstance(wrapper, dict):
            continue
        node = wrapper.get("__data__") or {}
        if not isinstance(node, dict):
            continue
        metadata = node.get("metadata") or {}
        if not isinstance(metadata, dict):
            continue
        candidates = [
            metadata.get("file_name"),
            metadata.get("filename"),
            metadata.get("file_path"),
            metadata.get("source_path"),
        ]
        seen: set[str] = set()
        for candidate in candidates:
            if not isinstance(candidate, str) or not candidate:
                continue
            normalized = normalize_file_name(candidate)
            if not normalized or normalized in seen:
                continue
            index.setdefault(normalized, []).append(metadata)
            seen.add(normalized)
    return index


def resolve_expected_path(
    *,
    doc: dict[str, Any],
    data_root: Path,
    local_index: dict[str, list[str]],
) -> tuple[str, bool]:
    """解析标注中的期望路径，并返回路径字符串和是否存在。"""
    file_name = str(doc.get("file_name") or "")
    file_path = str(doc.get("file_path") or "")
    candidates: list[Path] = []
    if file_path:
        raw = Path(file_path)
        candidates.append(raw if raw.is_absolute() else Path.cwd() / raw)
        if "data/grain-knowledge-base/" in file_path:
            suffix = file_path.split("data/grain-knowledge-base/", 1)[1]
            candidates.append(data_root / suffix)
    if file_name:
        for local_path in local_index.get(normalize_file_name(file_name), []):
            candidates.append(Path(local_path))
    for candidate in candidates:
        if candidate.exists():
            return str(candidate), True
    if candidates:
        return str(candidates[0]), False
    return file_name, False


def diagnose_expected_document(
    *,
    case: dict[str, Any],
    doc: dict[str, Any],
    kb_id: str,
    data_root: Path,
    local_index: dict[str, list[str]],
    asset_names: set[str],
    docstore_index: dict[str, list[dict[str, Any]]],
    eval_top5_index: dict[str, set[str]],
) -> dict[str, Any]:
    """诊断单个 QA 期望文档覆盖状态。"""
    file_name = str(doc.get("file_name") or "")
    normalized_name = normalize_file_name(file_name)
    expected_path, local_exists = resolve_expected_path(
        doc=doc,
        data_root=data_root,
        local_index=local_index,
    )
    node_metadata = docstore_index.get(normalized_name, [])
    metadata_file_name_variants = sorted(
        {
            str(meta.get("file_name") or meta.get("filename") or meta.get("file_path") or "")
            for meta in node_metadata
            if meta
        }
    )
    docstore_kb_id_count = sum(1 for meta in node_metadata if meta.get("kb_id") == kb_id)
    asset_registry_applicable = is_asset_registry_applicable(normalized_name)
    asset_registry_hit = normalized_name in asset_names
    eval_case_present = str(case.get("id") or "") in eval_top5_index
    top5_hit = normalized_name in eval_top5_index.get(str(case.get("id") or ""), set())

    if not local_exists:
        failure_reason = "missing_local_file"
    elif asset_registry_applicable and not asset_registry_hit:
        failure_reason = "missing_asset_registry"
    elif not node_metadata:
        failure_reason = "missing_docstore_nodes"
    elif docstore_kb_id_count == 0:
        failure_reason = "missing_or_wrong_kb_id"
    elif eval_case_present and not top5_hit:
        failure_reason = "retrieval_not_top5"
    else:
        failure_reason = "ok"

    return {
        "case_id": case.get("id"),
        "query": case.get("query"),
        "answerable": bool(case.get("answerable", True)),
        "file_name": file_name,
        "normalized_file_name": normalized_name,
        "expected_path": expected_path,
        "local_exists": local_exists,
        "asset_registry_applicable": asset_registry_applicable,
        "asset_registry_hit": asset_registry_hit,
        "docstore_node_count": len(node_metadata),
        "docstore_kb_id_count": docstore_kb_id_count,
        "metadata_file_name_variants": metadata_file_name_variants,
        "eval_case_present": eval_case_present,
        "top5_hit": top5_hit,
        "failure_reason": failure_reason,
    }


def build_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总覆盖诊断结果。"""
    reason_counts = Counter(str(item.get("failure_reason") or "") for item in records)
    return {
        "total_expected_documents": len(records),
        "local_exists_count": sum(1 for item in records if item.get("local_exists")),
        "asset_registry_applicable_count": sum(
            1 for item in records if item.get("asset_registry_applicable")
        ),
        "asset_registry_hit_count": sum(1 for item in records if item.get("asset_registry_hit")),
        "docstore_hit_count": sum(1 for item in records if item.get("docstore_node_count", 0) > 0),
        "docstore_kb_id_hit_count": sum(
            1 for item in records if item.get("docstore_kb_id_count", 0) > 0
        ),
        "eval_case_present_count": sum(1 for item in records if item.get("eval_case_present")),
        "top5_hit_count": sum(1 for item in records if item.get("top5_hit")),
        "failure_reason_counts": {reason: reason_counts.get(reason, 0) for reason in FAILURE_REASON_ORDER},
    }


def diagnose_coverage(
    *,
    cases_path: str | Path,
    kb_id: str,
    storage_dir: str | Path,
    data_root: str | Path,
    eval_report_path: str | Path | None = None,
) -> dict[str, Any]:
    """执行粮仓 QA 覆盖诊断并返回报告对象。"""
    storage_root = Path(storage_dir)
    data_root_path = Path(data_root)
    cases = load_cases(cases_path)
    local_index = build_local_name_index(data_root_path)
    asset_registry = load_json(storage_root / "kb_assets" / f"{kb_id}.json", [])
    asset_names = build_asset_name_index(asset_registry)
    kb_docstore_path = storage_root / "kbs" / kb_id / "docstore.json"
    root_docstore_path = storage_root / "docstore.json"
    docstore_path = kb_docstore_path if kb_docstore_path.exists() else root_docstore_path
    docstore = load_json(docstore_path, {})
    docstore_index = build_docstore_name_index(docstore)
    eval_report = load_json(eval_report_path, {}) if eval_report_path else {}
    eval_top5_index = build_eval_top5_index(eval_report)

    records: list[dict[str, Any]] = []
    for case in cases:
        for doc in case.get("relevant_documents", []) or []:
            if not isinstance(doc, dict):
                continue
            records.append(
                diagnose_expected_document(
                    case=case,
                    doc=doc,
                    kb_id=kb_id,
                    data_root=data_root_path,
                    local_index=local_index,
                    asset_names=asset_names,
                    docstore_index=docstore_index,
                    eval_top5_index=eval_top5_index,
                )
            )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kb_id": kb_id,
        "cases_path": str(cases_path),
        "storage_dir": str(storage_dir),
        "docstore_path": str(docstore_path),
        "data_root": str(data_root),
        "eval_report_path": str(eval_report_path) if eval_report_path else None,
        "summary": build_summary(records),
        "records": records,
    }


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="粮仓 QA 期望文件覆盖诊断")
    parser.add_argument("--cases", default="data/grain-knowledge-base/qa/verified.jsonl")
    parser.add_argument("--kb-id", default="grain-knowledge-base")
    parser.add_argument("--storage-dir", default="storage")
    parser.add_argument("--data-root", default="data/grain-knowledge-base")
    parser.add_argument(
        "--eval-report",
        default="docs/20260722-local-multi-kb-assistant/artifacts/grain-qa/qa-eval-report.json",
    )
    parser.add_argument(
        "--output",
        default="docs/20260807-grain-index-coverage-repair/artifacts/grain-coverage-diagnostic.json",
    )
    return parser.parse_args()


def main() -> None:
    """脚本入口。"""
    args = parse_args()
    report = diagnose_coverage(
        cases_path=args.cases,
        kb_id=args.kb_id,
        storage_dir=args.storage_dir,
        data_root=args.data_root,
        eval_report_path=args.eval_report,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"report: {output_path}")


if __name__ == "__main__":
    main()
