"""校验 RAG QA fixture schema、半真实样本约束与问答评测数据集。"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVAL_SCHEMA_PATH = REPO_ROOT / "tests" / "fixtures" / "rag_quality" / "eval_v1" / "schema.json"
REQUIRED_BASE = {"id", "query", "expected_answer", "status"}
FIXTURE_PARTS = ("tests", "fixtures", "rag_quality")
SEMIREAL_REQUIRED_FIELDS = {
    "case_id",
    "question",
    "expected_doc",
    "expected_keypoints",
    "must_not_contain",
    "preview_terms",
    "expected_source_count",
    "category",
}
SEMIREAL_ALLOWED_CATEGORIES = {
    "fact",
    "summary",
    "policy",
    "architecture",
    "no-evidence",
    "roadmap",
    "metrics",
}
EVAL_SCHEMA_REQUIRED_FIELDS = {
    "dataset_name",
    "required_fields",
    "allowed_modalities",
    "allowed_answer_styles",
    "allowed_difficulties",
    "allowed_categories",
    "allowed_scope_types",
    "allowed_isolation_levels",
    "allowed_judge_dimensions",
    "quality_gates",
    "run_gates",
    "rubric_dimensions",
}
EVAL_ALLOWED_MODES = {"healthy", "diagnostic"}
EVAL_ALLOWED_FAILURE_STAGES = {"chat_query", "preview", "quality_gate"}


def _has_subsequence(parts: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    normalized = tuple(part.replace("\\", "/") for part in parts)
    for idx in range(0, len(normalized) - len(needle) + 1):
        if normalized[idx : idx + len(needle)] == needle:
            return True
    return False


def _resolve_repo_path(raw_path: str | Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()



def _contains_cjk(value: Any) -> bool:
    """判断任意嵌套值里是否包含 CJK 字符。"""
    if isinstance(value, str):
        return bool(re.search(r"[㐀-䶿一-鿿]", value))
    if isinstance(value, list):
        return any(_contains_cjk(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_cjk(item) for item in value.values())
    return False


def _validate_string_list(values: Any, *, field_name: str, source: Path, allow_empty: bool = False) -> list[str]:
    if not isinstance(values, list):
        raise ValueError(f"{source}: {field_name} 必须是列表")
    normalized = [str(item).strip() for item in values]
    if any(not item for item in normalized):
        raise ValueError(f"{source}: {field_name} 不能包含空字符串")
    if not allow_empty and not normalized:
        raise ValueError(f"{source}: {field_name} 必须是非空列表")
    return normalized


def validate_record(record: dict[str, Any], *, source: Path) -> None:
    """校验单条 jsonl QA fixture。"""
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
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            validate_record(record, source=path)
            record_id = record["id"]
            if record_id in seen:
                raise ValueError(f"duplicate id: {record_id}")
            seen.add(record_id)



def validate_semireal_case_record(record: dict[str, Any], *, source: Path, markdown_dir: Path) -> None:
    """校验单条半真实 Markdown QA case。"""
    missing = SEMIREAL_REQUIRED_FIELDS - record.keys()
    if missing:
        raise ValueError(f"{source}: semireal case 缺少字段 {sorted(missing)}")

    case_id = str(record["case_id"]).strip()
    if not case_id:
        raise ValueError(f"{source}: case_id 不能为空")

    question = str(record["question"]).strip()
    if not question:
        raise ValueError(f"{source}: question 不能为空")

    category = str(record["category"]).strip()
    if category not in SEMIREAL_ALLOWED_CATEGORIES:
        raise ValueError(f"{source}: category 不合法: {category}")

    expected_keypoints = record.get("expected_keypoints")
    if not isinstance(expected_keypoints, list) or not expected_keypoints:
        raise ValueError(f"{source}: expected_keypoints 必须是非空列表")

    must_not_contain = record.get("must_not_contain")
    if not isinstance(must_not_contain, list):
        raise ValueError(f"{source}: must_not_contain 必须是列表")

    preview_terms = record.get("preview_terms")
    if not isinstance(preview_terms, list):
        raise ValueError(f"{source}: preview_terms 必须是列表")

    expected_source_count = record.get("expected_source_count")
    if not isinstance(expected_source_count, int) or expected_source_count < 0:
        raise ValueError(f"{source}: expected_source_count 必须是非负整数")

    expected_doc = record.get("expected_doc")
    if expected_doc is None:
        if expected_source_count != 0:
            raise ValueError(f"{source}: 无 expected_doc 时 expected_source_count 必须为 0")
        if preview_terms:
            raise ValueError(f"{source}: 无 expected_doc 时 preview_terms 必须为空")
        return

    doc_path = markdown_dir / str(expected_doc)
    if not doc_path.exists():
        raise ValueError(f"{source}: expected_doc 不存在: {expected_doc}")
    if doc_path.suffix.lower() != ".md":
        raise ValueError(f"{source}: expected_doc 必须指向 Markdown 文件")
    if expected_source_count <= 0:
        raise ValueError(f"{source}: 有 expected_doc 时 expected_source_count 必须大于 0")



def validate_semireal_cases_file(path: str | Path, *, markdown_dir: str | Path | None = None) -> None:
    """校验半真实 Markdown case 文件，并检查 case_id 唯一性。"""
    case_path = Path(path)
    if not case_path.exists():
        raise ValueError(f"semireal case 文件不存在: {case_path}")
    if "data" in case_path.parts:
        raise ValueError(f"semireal case 不能放在 data 目录: {case_path}")

    resolved_markdown_dir = Path(markdown_dir) if markdown_dir is not None else case_path.parent
    records = json.loads(case_path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        raise ValueError(f"{case_path}: semireal case 文件必须是非空数组")

    seen: set[str] = set()
    for record in records:
        validate_semireal_case_record(record, source=case_path, markdown_dir=resolved_markdown_dir)
        case_id = str(record["case_id"])
        if case_id in seen:
            raise ValueError(f"duplicate semireal case id: {case_id}")
        seen.add(case_id)



def summarize_semireal_cases(path: str | Path) -> dict[str, Any]:
    """汇总半真实 Markdown case 的分布与基础指标。"""
    case_path = Path(path)
    records = json.loads(case_path.read_text(encoding="utf-8"))
    counter = Counter(str(record.get("category", "uncategorized")) for record in records)
    expected_with_evidence = sum(1 for record in records if record.get("expected_doc") is not None)
    explicit_no_evidence = sum(1 for record in records if record.get("expected_doc") is None)
    preview_required = sum(1 for record in records if record.get("preview_terms"))

    return {
        "total_cases": len(records),
        "category_breakdown": dict(sorted(counter.items())),
        "expected_with_evidence": expected_with_evidence,
        "explicit_no_evidence": explicit_no_evidence,
        "preview_required": preview_required,
    }



def load_eval_schema(schema_path: str | Path | None = None) -> dict[str, Any]:
    """???????????? schema?"""
    path = _resolve_repo_path(schema_path or DEFAULT_EVAL_SCHEMA_PATH)
    if not path.exists():
        raise ValueError(f"eval schema ?????: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: eval schema ?????")

    missing = EVAL_SCHEMA_REQUIRED_FIELDS - data.keys()
    if missing:
        raise ValueError(f"{path}: eval schema ???? {sorted(missing)}")

    _validate_string_list(data.get("required_fields"), field_name="required_fields", source=path)
    _validate_string_list(data.get("allowed_modalities"), field_name="allowed_modalities", source=path)
    _validate_string_list(data.get("allowed_answer_styles"), field_name="allowed_answer_styles", source=path)
    _validate_string_list(data.get("allowed_difficulties"), field_name="allowed_difficulties", source=path)
    _validate_string_list(data.get("allowed_categories"), field_name="allowed_categories", source=path)
    _validate_string_list(data.get("allowed_scope_types"), field_name="allowed_scope_types", source=path)
    _validate_string_list(data.get("allowed_isolation_levels"), field_name="allowed_isolation_levels", source=path)
    _validate_string_list(data.get("allowed_judge_dimensions"), field_name="allowed_judge_dimensions", source=path)

    evaluation_mode = str(data.get("evaluation_mode") or "healthy").strip().lower()
    if evaluation_mode not in EVAL_ALLOWED_MODES:
        raise ValueError(f"{path}: evaluation_mode ???: {evaluation_mode}")
    data["evaluation_mode"] = evaluation_mode

    required_weak_signal_tags = data.get("required_weak_signal_tags")
    if required_weak_signal_tags is not None:
        data["required_weak_signal_tags"] = _validate_string_list(
            required_weak_signal_tags,
            field_name="required_weak_signal_tags",
            source=path,
        )

    quality_gates = data.get("quality_gates")
    if not isinstance(quality_gates, dict):
        raise ValueError(f"{path}: quality_gates ?????")
    required_quality_gate_keys = [
        "minimum_total_cases",
        "minimum_cases_per_modality",
        "minimum_cases_per_difficulty",
        "minimum_no_evidence_cases",
        "minimum_preview_required_cases",
    ]
    optional_quality_gate_keys = [
        "minimum_cases_per_answer_style",
        "minimum_cases_per_category",
        "minimum_weak_signal_cases",
    ]
    for key in required_quality_gate_keys + [
        name for name in optional_quality_gate_keys if name in quality_gates
    ]:
        value = quality_gates.get(key)
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"{path}: quality_gates.{key} ??????")

    run_gates = data.get("run_gates")
    if not isinstance(run_gates, dict):
        raise ValueError(f"{path}: run_gates ?????")
    for key, value in run_gates.items():
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"{path}: run_gates.{key} ??????")

    diagnostic_gates = data.get("diagnostic_gates")
    if diagnostic_gates is not None:
        if not isinstance(diagnostic_gates, dict):
            raise ValueError(f"{path}: diagnostic_gates ?????")
        for key, value in diagnostic_gates.items():
            if key == "required_signal_tags":
                _validate_string_list(value, field_name=f"diagnostic_gates.{key}", source=path)
                continue
            if key in {"minimum_weak_signal_kb_count", "minimum_weak_signal_modality_count"}:
                if not isinstance(value, int) or value <= 0:
                    raise ValueError(f"{path}: diagnostic_gates.{key} ??????")
                continue
            if key == "case_expectation_match_rate_min":
                if not isinstance(value, (int, float)) or value < 0:
                    raise ValueError(f"{path}: diagnostic_gates.{key} ??????")
                continue
            raise ValueError(f"{path}: diagnostic_gates.{key} ??????")

    rubric_dimensions = data.get("rubric_dimensions")
    if not isinstance(rubric_dimensions, dict) or not rubric_dimensions:
        raise ValueError(f"{path}: rubric_dimensions ???????")

    return data



def _validate_source_locator(locator: str, *, source: Path) -> None:
    base = locator.split("::", 1)[0]
    target = _resolve_repo_path(base)
    if not target.exists():
        raise ValueError(f"{source}: source_locator 指向的文件不存在: {base}")
    if "data" in target.parts:
        raise ValueError(f"{source}: source_locator 不能指向 data 目录: {base}")



def validate_eval_case_record(record: dict[str, Any], *, source: Path, schema: dict[str, Any]) -> None:
    """???????? case?"""
    required_fields = set(schema["required_fields"])
    missing = required_fields - record.keys()
    if missing:
        raise ValueError(f"{source}: eval case ???? {sorted(missing)}")

    for field in [
        "case_id",
        "dataset",
        "kb_id",
        "question",
        "expected_scope_type",
        "expected_isolation_level",
        "modality",
        "answer_style",
        "difficulty",
        "category",
    ]:
        value = str(record.get(field, "")).strip()
        if not value:
            raise ValueError(f"{source}: {field} ????")

    if record["dataset"] != schema["dataset_name"]:
        raise ValueError(f"{source}: dataset ???? {schema['dataset_name']}")

    if str(record["modality"]) not in set(schema["allowed_modalities"]):
        raise ValueError(f"{source}: modality ???: {record['modality']}")
    if str(record["answer_style"]) not in set(schema["allowed_answer_styles"]):
        raise ValueError(f"{source}: answer_style ???: {record['answer_style']}")
    if str(record["difficulty"]) not in set(schema["allowed_difficulties"]):
        raise ValueError(f"{source}: difficulty ???: {record['difficulty']}")
    if str(record["category"]) not in set(schema["allowed_categories"]):
        raise ValueError(f"{source}: category ???: {record['category']}")
    if str(record["expected_scope_type"]) not in set(schema["allowed_scope_types"]):
        raise ValueError(f"{source}: expected_scope_type ???: {record['expected_scope_type']}")
    if str(record["expected_isolation_level"]) not in set(schema["allowed_isolation_levels"]):
        raise ValueError(f"{source}: expected_isolation_level ???: {record['expected_isolation_level']}")

    answerable = record.get("answerable")
    if not isinstance(answerable, bool):
        raise ValueError(f"{source}: answerable ??????")

    preview_required = record.get("preview_required")
    if not isinstance(preview_required, bool):
        raise ValueError(f"{source}: preview_required ??????")

    expected_source_count = record.get("expected_source_count")
    if not isinstance(expected_source_count, int) or expected_source_count < 0:
        raise ValueError(f"{source}: expected_source_count ???????")

    expected_keypoints = _validate_string_list(record.get("expected_keypoints"), field_name="expected_keypoints", source=source)
    forbidden_terms = _validate_string_list(record.get("forbidden_terms"), field_name="forbidden_terms", source=source)
    judge_focus = _validate_string_list(record.get("judge_focus"), field_name="judge_focus", source=source)
    required_evidence_docs = _validate_string_list(
        record.get("required_evidence_docs"),
        field_name="required_evidence_docs",
        source=source,
        allow_empty=not answerable,
    )
    if "weak_signal_tags" in record:
        _validate_string_list(record.get("weak_signal_tags"), field_name="weak_signal_tags", source=source, allow_empty=True)

    expected_case_passed = record.get("expected_case_passed")
    if expected_case_passed is not None and not isinstance(expected_case_passed, bool):
        raise ValueError(f"{source}: expected_case_passed ??????")

    expected_failure_stage = record.get("expected_failure_stage")
    if expected_failure_stage is not None:
        normalized_stage = str(expected_failure_stage).strip()
        if not normalized_stage:
            raise ValueError(f"{source}: expected_failure_stage ????")
        if normalized_stage not in EVAL_ALLOWED_FAILURE_STAGES:
            raise ValueError(f"{source}: expected_failure_stage ???: {normalized_stage}")
        if expected_case_passed is not False:
            raise ValueError(f"{source}: expected_failure_stage ???? expected_case_passed=false ???")

    allowed_dimensions = set(schema["allowed_judge_dimensions"])
    invalid_dimensions = [item for item in judge_focus if item not in allowed_dimensions]
    if invalid_dimensions:
        raise ValueError(f"{source}: judge_focus ?????? {sorted(invalid_dimensions)}")
    if not answerable and "refusal_correctness" not in judge_focus:
        raise ValueError(f"{source}: no-evidence case judge_focus ???? refusal_correctness")

    source_doc = record.get("source_doc")
    source_locator = record.get("source_locator")

    if answerable:
        if not str(source_doc or "").strip():
            raise ValueError(f"{source}: answerable case ???? source_doc")
        if not str(source_locator or "").strip():
            raise ValueError(f"{source}: answerable case ???? source_locator")
        if expected_source_count <= 0:
            raise ValueError(f"{source}: answerable case ? expected_source_count ???? 0")
        if not preview_required:
            raise ValueError(f"{source}: answerable case ???? preview")
        if str(source_doc) not in required_evidence_docs:
            raise ValueError(f"{source}: required_evidence_docs ???? source_doc")
        if record["answer_style"] == "refusal":
            raise ValueError(f"{source}: answerable case ???? refusal answer_style")
        _validate_source_locator(str(source_locator), source=source)
    else:
        if source_doc is not None:
            raise ValueError(f"{source}: no-evidence case ? source_doc ??? null")
        if source_locator is not None:
            raise ValueError(f"{source}: no-evidence case ? source_locator ??? null")
        if expected_source_count != 0:
            raise ValueError(f"{source}: no-evidence case ? expected_source_count ??? 0")
        if preview_required:
            raise ValueError(f"{source}: no-evidence case ???? preview")
        if required_evidence_docs:
            raise ValueError(f"{source}: no-evidence case ? required_evidence_docs ??????")
        if expected_keypoints and record["answer_style"] != "refusal":
            raise ValueError(f"{source}: no-evidence case ???? refusal answer_style")



def validate_eval_cases_file(path: str | Path, *, schema_path: str | Path | None = None) -> None:
    """校验问答评测数据集文件，并检查 case_id 唯一性。"""
    case_path = _resolve_repo_path(path)
    if not case_path.exists():
        raise ValueError(f"eval case 文件不存在: {case_path}")
    if "data" in case_path.parts:
        raise ValueError(f"eval case 不能放在 data 目录: {case_path}")

    schema = load_eval_schema(schema_path)
    records = json.loads(case_path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        raise ValueError(f"{case_path}: eval case 文件必须是非空数组")

    seen: set[str] = set()
    for record in records:
        validate_eval_case_record(record, source=case_path, schema=schema)
        case_id = str(record["case_id"])
        if case_id in seen:
            raise ValueError(f"duplicate eval case id: {case_id}")
        seen.add(case_id)



def summarize_eval_cases(path: str | Path, *, schema_path: str | Path | None = None) -> dict[str, Any]:
    """?????????????????????"""
    case_path = _resolve_repo_path(path)
    schema = load_eval_schema(schema_path)
    records = json.loads(case_path.read_text(encoding="utf-8"))

    modality_counter = Counter(str(record["modality"]) for record in records)
    difficulty_counter = Counter(str(record["difficulty"]) for record in records)
    answer_style_counter = Counter(str(record["answer_style"]) for record in records)
    category_counter = Counter(str(record["category"]) for record in records)
    answerable_counter = Counter("answerable" if record.get("answerable") else "no_evidence" for record in records)
    weak_signal_records = [record for record in records if list(record.get("weak_signal_tags") or [])]
    weak_signal_counter = Counter(
        str(signal)
        for record in records
        for signal in list(record.get("weak_signal_tags") or [])
    )
    weak_signal_modality_counter = Counter(str(record["modality"]) for record in weak_signal_records)
    cjk_records = [
        record
        for record in records
        if _contains_cjk(record.get("question")) or _contains_cjk(record.get("expected_keypoints"))
    ]
    cjk_modality_counter = Counter(str(record["modality"]) for record in cjk_records)

    modality_difficulty_breakdown: dict[str, dict[str, int]] = {}
    for modality in schema["allowed_modalities"]:
        modality_records = [record for record in records if str(record["modality"]) == modality]
        modality_difficulty_breakdown[modality] = dict(
            sorted(Counter(str(record["difficulty"]) for record in modality_records).items())
        )

    quality_gates = schema["quality_gates"]
    preview_required_cases = sum(1 for record in records if record.get("preview_required"))
    gate_checks = {
        "minimum_total_cases": len(records) >= quality_gates["minimum_total_cases"],
        "minimum_cases_per_modality": all(
            modality_counter.get(modality, 0) >= quality_gates["minimum_cases_per_modality"]
            for modality in schema["allowed_modalities"]
        ),
        "minimum_cases_per_difficulty": all(
            difficulty_counter.get(difficulty, 0) >= quality_gates["minimum_cases_per_difficulty"]
            for difficulty in schema["allowed_difficulties"]
        ),
        "minimum_no_evidence_cases": answerable_counter.get("no_evidence", 0) >= quality_gates["minimum_no_evidence_cases"],
        "minimum_preview_required_cases": preview_required_cases >= quality_gates["minimum_preview_required_cases"],
    }
    if "minimum_cases_per_answer_style" in quality_gates:
        gate_checks["minimum_cases_per_answer_style"] = all(
            answer_style_counter.get(answer_style, 0) >= quality_gates["minimum_cases_per_answer_style"]
            for answer_style in schema["allowed_answer_styles"]
        )
    if "minimum_cases_per_category" in quality_gates:
        gate_checks["minimum_cases_per_category"] = all(
            category_counter.get(category, 0) >= quality_gates["minimum_cases_per_category"]
            for category in schema["allowed_categories"]
        )
    if "minimum_cjk_cases" in quality_gates:
        gate_checks["minimum_cjk_cases"] = len(cjk_records) >= quality_gates["minimum_cjk_cases"]
    if "minimum_cjk_cases_per_modality" in quality_gates:
        gate_checks["minimum_cjk_cases_per_modality"] = all(
            cjk_modality_counter.get(modality, 0) >= quality_gates["minimum_cjk_cases_per_modality"]
            for modality in schema["allowed_modalities"]
        )
    if "minimum_weak_signal_cases" in quality_gates:
        gate_checks["minimum_weak_signal_cases"] = len(weak_signal_records) >= quality_gates["minimum_weak_signal_cases"]
    if schema.get("required_weak_signal_tags"):
        required_tags = [str(item) for item in schema["required_weak_signal_tags"]]
        gate_checks["required_weak_signal_tags"] = all(weak_signal_counter.get(tag, 0) > 0 for tag in required_tags)

    return {
        "dataset_name": schema["dataset_name"],
        "total_cases": len(records),
        "modality_breakdown": dict(sorted(modality_counter.items())),
        "difficulty_breakdown": dict(sorted(difficulty_counter.items())),
        "answer_style_breakdown": dict(sorted(answer_style_counter.items())),
        "category_breakdown": dict(sorted(category_counter.items())),
        "answerable_breakdown": dict(sorted(answerable_counter.items())),
        "weak_signal_case_count": len(weak_signal_records),
        "weak_signal_breakdown": dict(sorted(weak_signal_counter.items())),
        "weak_signal_modality_breakdown": dict(sorted(weak_signal_modality_counter.items())),
        "preview_required_cases": preview_required_cases,
        "cjk_case_count": len(cjk_records),
        "cjk_modality_breakdown": dict(sorted(cjk_modality_counter.items())),
        "modality_difficulty_breakdown": modality_difficulty_breakdown,
        "gate_checks": gate_checks,
    }



def main() -> None:
    parser = argparse.ArgumentParser(description="校验 RAG QA fixture")
    parser.add_argument("paths", nargs="*", default=[])
    parser.add_argument("--semireal-cases", nargs="*", default=[])
    parser.add_argument("--eval-cases", nargs="*", default=[])
    parser.add_argument("--eval-schema", default=None)
    parser.add_argument("--print-eval-summary", action="store_true")
    args = parser.parse_args()

    if not args.paths and not args.semireal_cases and not args.eval_cases:
        parser.error("至少提供一种待校验输入")

    if args.paths:
        validate_files(args.paths)
    for case_path in args.semireal_cases:
        validate_semireal_cases_file(case_path)
    for case_path in args.eval_cases:
        validate_eval_cases_file(case_path, schema_path=args.eval_schema)
        if args.print_eval_summary:
            summary = summarize_eval_cases(case_path, schema_path=args.eval_schema)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("fixture 校验通过")


if __name__ == "__main__":
    main()
