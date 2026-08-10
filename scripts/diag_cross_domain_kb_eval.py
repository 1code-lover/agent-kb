"""跨知识库与跨领域真实问答诊断脚本。"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_API_BASE = "http://127.0.0.1:18080"
DEFAULT_TIMEOUT = 120.0

DEFAULT_CASES: list[dict[str, Any]] = [
    {
        "id": "grain-positive-safety-policy",
        "kind": "positive",
        "kb_ids": ["grain-knowledge-base"],
        "question": "《粮油安全储存守则》制定的安全储粮方针是什么？",
        "expected_terms": ["预防为主", "综合防治"],
        "allowed_source_kb_ids": ["grain-knowledge-base"],
        "required_source_kb_ids": ["grain-knowledge-base"],
    },
    {
        "id": "desktop-positive-passcode",
        "kind": "positive",
        "kb_ids": ["diag-desktop-e2e-1786353063"],
        "question": "What is the unique desktop workflow passcode in the diagnostic document?",
        "expected_terms": ["northagent-desktop-e2e-1786353063"],
        "allowed_source_kb_ids": ["diag-desktop-e2e-1786353063"],
        "required_source_kb_ids": ["diag-desktop-e2e-1786353063"],
    },
    {
        "id": "utf8-positive-boundary",
        "kind": "positive",
        "kb_ids": ["diag-kb-utf8-1785505921"],
        "question": "这份 UTF-8 诊断文档如何描述知识库和文件夹的边界？",
        "expected_terms": ["知识库", "授权边界", "组织作用"],
        "allowed_source_kb_ids": ["diag-kb-utf8-1785505921"],
        "required_source_kb_ids": ["diag-kb-utf8-1785505921"],
    },
    {
        "id": "desktop-negative-grain-question",
        "kind": "negative",
        "kb_ids": ["diag-desktop-e2e-1786353063"],
        "question": "《粮油安全储存守则》制定的安全储粮方针是什么？",
        "forbidden_terms": ["预防为主", "综合防治", "粮油安全储存守则"],
        "allowed_source_kb_ids": ["diag-desktop-e2e-1786353063"],
        "forbidden_source_kb_ids": ["grain-knowledge-base"],
    },
    {
        "id": "grain-negative-desktop-passcode",
        "kind": "negative",
        "kb_ids": ["grain-knowledge-base"],
        "question": "What is the unique desktop workflow passcode in the diagnostic document?",
        "forbidden_terms": ["northagent-desktop-e2e-1786353063"],
        "allowed_source_kb_ids": ["grain-knowledge-base"],
        "forbidden_source_kb_ids": ["diag-desktop-e2e-1786353063"],
    },
    {
        "id": "grain-negative-utf8-exact-boundary",
        "kind": "negative",
        "kb_ids": ["grain-knowledge-base"],
        "question": "这份 UTF-8 诊断文档如何描述知识库和文件夹的边界？",
        "forbidden_terms": ["文件夹只承担组织作用", "不承担权限隔离"],
        "allowed_source_kb_ids": ["grain-knowledge-base"],
        "forbidden_source_kb_ids": ["diag-kb-utf8-1785505921"],
        "note": "允许 grain KB 回答相似的授权边界概念，但不能泄漏 UTF-8 诊断文档的精确证据短语。",
    },
]


def _now_iso() -> str:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc).isoformat()


def load_cases(path: str | Path | None = None) -> list[dict[str, Any]]:
    """读取 JSON 用例；未传路径时返回内置诊断用例。"""
    if path is None:
        return [dict(item) for item in DEFAULT_CASES]
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("cross-domain cases file must be a JSON list")
    return [dict(item) for item in payload if isinstance(item, dict)]


def _post_json(api_base: str, path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    """向 API 发送 JSON 请求并解析响应。"""
    url = api_base.rstrip("/") + path
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {"code": exc.code, "message": detail}
    except urllib.error.URLError as exc:
        return {"code": -1, "message": str(exc)}


def _as_list(value: Any) -> list[str]:
    """把用例字段规整为字符串列表。"""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [str(value)] if str(value) else []


def _contains_all(haystack: str, terms: list[str]) -> bool:
    """检查文本是否包含全部关键词。"""
    return all(term in haystack for term in terms)


def _contains_any(haystack: str, terms: list[str]) -> bool:
    """检查文本是否包含任一关键词。"""
    return any(term in haystack for term in terms)


def _extract_records(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """从 data 中读取 sources/evidence 记录。"""
    value = data.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _extract_source_kb_ids(data: dict[str, Any]) -> tuple[list[str], int]:
    """从 sources 和 evidence 中抽取 kb_id。"""
    records = _extract_records(data, "sources") + _extract_records(data, "evidence")
    kb_ids: list[str] = []
    for item in records:
        kb_id = item.get("kb_id")
        if isinstance(kb_id, str) and kb_id:
            kb_ids.append(kb_id)
    return kb_ids, len(records)


def _payload_text(data: dict[str, Any]) -> str:
    """合并 answer、sources 和 evidence，用于精确泄漏词检测。"""
    answer = str(data.get("answer") or "")
    sources = _extract_records(data, "sources")
    evidence = _extract_records(data, "evidence")
    return answer + "\n" + json.dumps({"sources": sources, "evidence": evidence}, ensure_ascii=False)


def evaluate_case(case: dict[str, Any], api_base: str, timeout: float) -> dict[str, Any]:
    """执行单条跨领域用例并计算通过状态。"""
    case_id = str(case.get("id") or "case")
    kind = str(case.get("kind") or "positive")
    kb_ids = _as_list(case.get("kb_ids"))
    if not kb_ids:
        raise ValueError(f"{case_id}: kb_ids is required")
    question = str(case.get("question") or "").strip()
    if not question:
        raise ValueError(f"{case_id}: question is required")

    response = _post_json(
        api_base,
        "/api/chat/query",
        {
            "question": question,
            "session_id": f"cross-domain-eval::{case_id}",
            "kb_ids": kb_ids,
            "top_k": int(case.get("top_k") or 5),
        },
        timeout,
    )

    data: dict[str, Any] = {}
    error: str | None = None
    if response.get("code") == 0 and isinstance(response.get("data"), dict):
        data = response["data"]
    else:
        error = str(response.get("message") or response)

    expected_terms = _as_list(case.get("expected_terms"))
    forbidden_terms = _as_list(case.get("forbidden_terms"))
    allowed_source_kb_ids = set(_as_list(case.get("allowed_source_kb_ids")))
    required_source_kb_ids = set(_as_list(case.get("required_source_kb_ids")))
    forbidden_source_kb_ids = set(_as_list(case.get("forbidden_source_kb_ids")))

    answer = str(data.get("answer") or "")
    combined_text = _payload_text(data)
    source_kb_ids, source_record_count = _extract_source_kb_ids(data)
    source_kb_set = set(source_kb_ids)
    source_kb_id_missing_count = max(source_record_count - len(source_kb_ids), 0)

    require_sources = bool(case.get("require_sources", kind == "positive"))
    source_presence_ok = (source_record_count > 0) if require_sources else True
    source_kb_known = source_record_count == len(source_kb_ids)
    source_kb_allowed = (
        True
        if not allowed_source_kb_ids
        else source_kb_known and all(kb_id in allowed_source_kb_ids for kb_id in source_kb_ids)
    )
    required_source_kb_hit = required_source_kb_ids.issubset(source_kb_set)
    forbidden_source_kb_clean = not bool(source_kb_set & forbidden_source_kb_ids)
    expected_terms_hit = _contains_all(answer, expected_terms)
    forbidden_terms_clean = not _contains_any(combined_text, forbidden_terms)

    checks = {
        "http_ok": error is None,
        "expected_terms_hit": expected_terms_hit,
        "forbidden_terms_clean": forbidden_terms_clean,
        "source_presence_ok": source_presence_ok,
        "source_kb_known": source_kb_known,
        "source_kb_allowed": source_kb_allowed,
        "required_source_kb_hit": required_source_kb_hit,
        "forbidden_source_kb_clean": forbidden_source_kb_clean,
    }
    passed = all(checks.values())

    return {
        "id": case_id,
        "kind": kind,
        "kb_ids": kb_ids,
        "question": question,
        "expected_terms": expected_terms,
        "forbidden_terms": forbidden_terms,
        "allowed_source_kb_ids": sorted(allowed_source_kb_ids),
        "required_source_kb_ids": sorted(required_source_kb_ids),
        "forbidden_source_kb_ids": sorted(forbidden_source_kb_ids),
        "answer_preview": answer[:240],
        "source_record_count": source_record_count,
        "source_kb_ids": source_kb_ids,
        "source_kb_id_missing_count": source_kb_id_missing_count,
        "checks": checks,
        "passed": passed,
        "error": error,
        "note": case.get("note"),
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总跨领域用例结果。"""
    total = len(results)
    passed = [item for item in results if item.get("passed")]
    positive = [item for item in results if item.get("kind") == "positive"]
    negative = [item for item in results if item.get("kind") == "negative"]
    failed = [item for item in results if not item.get("passed")]

    def _rate(rows: list[dict[str, Any]]) -> float | None:
        if not rows:
            return None
        return round(sum(1 for item in rows if item.get("passed")) / len(rows), 4)

    return {
        "total": total,
        "passed": len(passed),
        "failed": len(failed),
        "pass_rate": _rate(results) if results else 0.0,
        "positive_total": len(positive),
        "positive_pass_rate": _rate(positive),
        "negative_total": len(negative),
        "negative_pass_rate": _rate(negative),
        "failed_case_ids": [str(item.get("id")) for item in failed],
    }


def build_report(*, cases: list[dict[str, Any]], api_base: str, timeout: float) -> dict[str, Any]:
    """执行全部用例并构造报告。"""
    results = [evaluate_case(case, api_base, timeout) for case in cases]
    return {
        "generated_at": _now_iso(),
        "api_base": api_base.rstrip("/"),
        "timeout": timeout,
        "summary": summarize(results),
        "cases": results,
    }


def run_evaluation(
    *,
    api_base: str,
    timeout: float,
    output: str,
    cases_path: str | None = None,
) -> tuple[dict[str, Any], int]:
    """执行跨领域评测并写出报告。"""
    cases = load_cases(cases_path)
    if not cases:
        return {"summary": {"total": 0, "passed": 0, "failed": 0}}, 2
    report = build_report(cases=cases, api_base=api_base, timeout=timeout)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report, 0 if report["summary"]["failed"] == 0 else 1


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="跨知识库、跨领域真实问答诊断")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="API 根地址")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="单条问答超时秒数")
    parser.add_argument("--cases", default=None, help="可选；JSON list 格式用例文件")
    parser.add_argument(
        "--output",
        default="docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report.json",
        help="评测报告输出路径",
    )
    args = parser.parse_args()

    report, exit_code = run_evaluation(
        api_base=args.api_base,
        timeout=args.timeout,
        output=args.output,
        cases_path=args.cases,
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"报告已写入: {Path(args.output)}")
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("评测已中断", file=sys.stderr)
        raise SystemExit(130)
