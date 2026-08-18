"""粮仓 QA 覆盖诊断脚本测试。"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import diagnose_grain_qa_coverage as diag


def _write_json(path: Path, data: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _write_cases(path: Path, records: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in records) + "\n",
        encoding="utf-8",
    )
    return path


def _write_docstore(path: Path, nodes: list[dict[str, object]]) -> Path:
    data = {}
    for index, metadata in enumerate(nodes):
        data[f"node-{index}"] = {"__data__": {"metadata": metadata}}
    return _write_json(path, {"docstore/data": data})


def test_normalize_file_name_strips_hash_and_parentheses() -> None:
    """文件名归一化应处理 hash 后缀与全角括号。"""
    assert diag.normalize_file_name("中储粮（暂行）_0880c2cd.docx") == "中储粮(暂行).docx"


def test_diagnose_reports_local_file_but_missing_docstore(tmp_path: Path) -> None:
    """本地文件存在但 docstore 缺节点时，应输出 missing_docstore_nodes。"""
    data_root = tmp_path / "data" / "grain-knowledge-base"
    source = data_root / "docs" / "02-storage-operations" / "operation.docx"
    source.parent.mkdir(parents=True)
    source.write_text("content", encoding="utf-8")
    cases = _write_cases(
        tmp_path / "verified.jsonl",
        [
            {
                "id": "case-1",
                "query": "q",
                "relevant_documents": [
                    {"file_name": "operation.docx", "file_path": str(source)}
                ],
            }
        ],
    )
    storage = tmp_path / "storage"
    _write_json(storage / "kb_assets" / "grain-knowledge-base.json", [{"path": str(source)}])
    _write_docstore(storage / "docstore.json", [])
    _write_json(tmp_path / "eval.json", {"cases": []})

    report = diag.diagnose_coverage(
        cases_path=cases,
        kb_id="grain-knowledge-base",
        storage_dir=storage,
        data_root=data_root,
        eval_report_path=tmp_path / "eval.json",
    )

    record = report["records"][0]
    assert record["local_exists"] is True
    assert record["asset_registry_hit"] is True
    assert record["docstore_node_count"] == 0
    assert record["failure_reason"] == "missing_docstore_nodes"


def test_diagnose_prefers_kb_scoped_docstore(tmp_path: Path) -> None:
    """存在 KB 独立 docstore 时，应优先读取该目录。"""
    data_root = tmp_path / "grain"
    source = data_root / "docs" / "01-a" / "policy.docx"
    source.parent.mkdir(parents=True)
    source.write_text("content", encoding="utf-8")
    cases = _write_cases(
        tmp_path / "verified.jsonl",
        [{"id": "case-1", "query": "q", "relevant_documents": [{"file_name": "policy.docx"}]}],
    )
    storage = tmp_path / "storage"
    _write_json(storage / "kb_assets" / "grain-knowledge-base.json", [{"file_name": "policy.docx"}])
    _write_docstore(storage / "docstore.json", [])
    _write_docstore(
        storage / "kbs" / "grain-knowledge-base" / "docstore.json",
        [{"file_name": "policy.docx", "kb_id": "grain-knowledge-base"}],
    )
    _write_json(tmp_path / "eval.json", {"cases": [{"id": "case-1", "source_files_top5": ["policy.docx"]}]})

    report = diag.diagnose_coverage(
        cases_path=cases,
        kb_id="grain-knowledge-base",
        storage_dir=storage,
        data_root=data_root,
        eval_report_path=tmp_path / "eval.json",
    )

    assert Path(report["docstore_path"]).as_posix().endswith("storage/kbs/grain-knowledge-base/docstore.json")
    assert report["records"][0]["docstore_kb_id_count"] == 1


def test_diagnose_reports_wrong_kb_id(tmp_path: Path) -> None:
    """docstore 有节点但 kb_id 错误时，应输出 missing_or_wrong_kb_id。"""
    data_root = tmp_path / "grain"
    source = data_root / "docs" / "01-a" / "policy.docx"
    source.parent.mkdir(parents=True)
    source.write_text("content", encoding="utf-8")
    cases = _write_cases(
        tmp_path / "verified.jsonl",
        [{"id": "case-1", "query": "q", "relevant_documents": [{"file_name": "policy.docx"}]}],
    )
    storage = tmp_path / "storage"
    _write_json(storage / "kb_assets" / "grain-knowledge-base.json", [{"file_name": "policy.docx"}])
    _write_docstore(
        storage / "docstore.json",
        [{"file_name": "policy.docx", "kb_id": "default"}],
    )
    _write_json(tmp_path / "eval.json", {"cases": [{"id": "case-1", "source_files_top5": ["policy.docx"]}]})

    report = diag.diagnose_coverage(
        cases_path=cases,
        kb_id="grain-knowledge-base",
        storage_dir=storage,
        data_root=data_root,
        eval_report_path=tmp_path / "eval.json",
    )

    record = report["records"][0]
    assert record["docstore_node_count"] == 1
    assert record["docstore_kb_id_count"] == 0
    assert record["top5_hit"] is True
    assert record["failure_reason"] == "missing_or_wrong_kb_id"


def test_diagnose_treats_empty_asset_registry_as_informational_for_documents(tmp_path: Path) -> None:
    """普通文档不依赖 asset registry，空 registry 不应覆盖 docstore/top5 成功状态。"""
    data_root = tmp_path / "grain"
    source = data_root / "docs" / "01-a" / "policy.docx"
    source.parent.mkdir(parents=True)
    source.write_text("content", encoding="utf-8")
    cases = _write_cases(
        tmp_path / "verified.jsonl",
        [{"id": "case-1", "query": "q", "relevant_documents": [{"file_name": "policy.docx"}]}],
    )
    storage = tmp_path / "storage"
    _write_json(storage / "kb_assets" / "grain-knowledge-base.json", [])
    _write_docstore(
        storage / "docstore.json",
        [{"file_name": "policy.docx", "kb_id": "grain-knowledge-base"}],
    )
    _write_json(tmp_path / "eval.json", {"cases": [{"id": "case-1", "source_files_top5": ["policy.docx"]}]})

    report = diag.diagnose_coverage(
        cases_path=cases,
        kb_id="grain-knowledge-base",
        storage_dir=storage,
        data_root=data_root,
        eval_report_path=tmp_path / "eval.json",
    )

    record = report["records"][0]
    assert record["asset_registry_applicable"] is False
    assert record["asset_registry_hit"] is False
    assert record["docstore_node_count"] == 1
    assert record["top5_hit"] is True
    assert record["failure_reason"] == "ok"


def test_diagnose_reports_missing_asset_registry_for_image_assets(tmp_path: Path) -> None:
    """图片等资产类文件缺少 asset registry 时，仍应输出 missing_asset_registry。"""
    data_root = tmp_path / "grain"
    source = data_root / "docs" / "01-a" / "sensor.png"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"image")
    cases = _write_cases(
        tmp_path / "verified.jsonl",
        [{"id": "case-1", "query": "q", "relevant_documents": [{"file_name": "sensor.png"}]}],
    )
    storage = tmp_path / "storage"
    _write_json(storage / "kb_assets" / "grain-knowledge-base.json", [])
    _write_docstore(
        storage / "docstore.json",
        [{"file_name": "sensor.png", "kb_id": "grain-knowledge-base"}],
    )
    _write_json(tmp_path / "eval.json", {"cases": [{"id": "case-1", "source_files_top5": ["sensor.png"]}]})

    report = diag.diagnose_coverage(
        cases_path=cases,
        kb_id="grain-knowledge-base",
        storage_dir=storage,
        data_root=data_root,
        eval_report_path=tmp_path / "eval.json",
    )

    record = report["records"][0]
    assert record["asset_registry_applicable"] is True
    assert record["asset_registry_hit"] is False
    assert record["failure_reason"] == "missing_asset_registry"


def test_diagnose_matches_hash_suffix_and_fullwidth_parentheses(tmp_path: Path) -> None:
    """带 hash 后缀或括号差异的文件名仍应匹配同一文档。"""
    data_root = tmp_path / "grain"
    source = data_root / "docs" / "01-a" / "中储粮（暂行）.docx"
    source.parent.mkdir(parents=True)
    source.write_text("content", encoding="utf-8")
    cases = _write_cases(
        tmp_path / "verified.jsonl",
        [
            {
                "id": "case-1",
                "query": "q",
                "relevant_documents": [{"file_name": "中储粮(暂行).docx"}],
            }
        ],
    )
    storage = tmp_path / "storage"
    _write_json(
        storage / "kb_assets" / "grain-knowledge-base.json",
        [{"path": "中储粮（暂行）_0880c2cd.docx"}],
    )
    _write_docstore(
        storage / "docstore.json",
        [{"file_name": "中储粮（暂行）_0880c2cd.docx", "kb_id": "grain-knowledge-base"}],
    )
    _write_json(
        tmp_path / "eval.json",
        {"cases": [{"id": "case-1", "source_files_top5": ["中储粮（暂行）_0880c2cd.docx"]}]},
    )

    report = diag.diagnose_coverage(
        cases_path=cases,
        kb_id="grain-knowledge-base",
        storage_dir=storage,
        data_root=data_root,
        eval_report_path=tmp_path / "eval.json",
    )

    record = report["records"][0]
    assert record["local_exists"] is True
    assert record["asset_registry_hit"] is True
    assert record["docstore_kb_id_count"] == 1
    assert record["top5_hit"] is True
    assert record["failure_reason"] == "ok"


def test_summary_counts_all_failure_reasons(tmp_path: Path) -> None:
    """汇总应稳定输出所有 failure_reason 计数。"""
    summary = diag.build_summary([{"failure_reason": "ok", "local_exists": True, "top5_hit": True}])

    assert summary["failure_reason_counts"]["ok"] == 1
    assert summary["failure_reason_counts"]["missing_local_file"] == 0
    assert summary["asset_registry_applicable_count"] == 0
    assert summary["eval_case_present_count"] == 0
    assert set(summary["failure_reason_counts"]) == set(diag.FAILURE_REASON_ORDER)
