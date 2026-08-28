"""粮仓知识库真实问答评测脚本。

读取 data/grain-knowledge-base/qa/verified.jsonl（30 条人工标注用例），
对已运行的 API（默认按 KB_API_BASE_URL / KB_API_PORT 合同解析，未配置时 fallback 到 http://127.0.0.1:18080）逐条发起 /api/chat/query，
统计检索与问答指标：

- Recall@5：relevant_documents 是否出现在 top5 引用来源里。
- MRR@5：首个命中的相关文档的倒数排名。
- Citation hit rate：answerable 用例是否给出引用来源。
- Refusal accuracy：answerable=false 用例是否给出"无相关信息"式拒绝。
- KB isolation：返回来源是否全部限定在目标 kb_id。

用法::

    python -m scripts.run_grain_qa_eval \\
        --cases data/grain-knowledge-base/qa/verified.jsonl \\
        --api-base http://127.0.0.1:18080 \\
        --kb-id grain-knowledge-base \\
        --output data/grain-knowledge-base/qa/qa-eval-report.json

也可以先设置 `KB_API_BASE_URL` 或 `KB_API_PORT`，再省略 `--api-base`。

评测不依赖 LLM 主观打分，只校验检索命中与引用正确性，因此可在无 LLM
裁判的情况下复跑。LLM 仅用于生成 answer（决定 refusal 文案），不影响
检索指标本身。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

try:
    from scripts.diag_roundtrip_support import DEFAULT_LOCAL_API_PORT, resolve_api_base_url
except ModuleNotFoundError:
    from diag_roundtrip_support import DEFAULT_LOCAL_API_PORT, resolve_api_base_url


# 导入落盘时会给文件名追加 `_<8 位十六进制>` 后缀（如 AAA粮油安全储存守则_a68a17f8.docx）。
# 评测比较时统一剥掉这个后缀，避免与 verified.jsonl 里不带后缀的原始文件名错配。
_HASH_SUFFIX_RE = re.compile(r"_[0-9a-f]{6,16}(?=\.[A-Za-z0-9]+$)")


def _normalize_file_name(name: str) -> str:
    """剥掉导入时追加的 hash 后缀，返回归一化后的原始文件名。

    同时把全角圆括号统一成半角，避免标注集（全角）与落盘文件名（半角）
    在比较时错配。
    """
    no_hash = _HASH_SUFFIX_RE.sub("", name)
    return no_hash.translate(str.maketrans({"（": "(", "）": ")"}))



def _now_iso() -> str:
    """返回当前 UTC 时间的 ISO8601 字符串。"""
    return datetime.now(timezone.utc).isoformat()


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    """读取 verified.jsonl 形式的逐行 JSON 评测集。"""
    cases: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue
            record = json.loads(line)
            record.setdefault("_line_no", line_no)
            cases.append(record)
    return cases


def file_sha256(path: str | Path) -> str:
    """计算文件 SHA256，便于评测报告追溯用例版本。"""
    digest = sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _post_json(api_base: str, path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    """向 API 发送 JSON 请求并解析响应。"""
    url = api_base.rstrip("/") + path
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - 仅真实 API 报错时触发
        text = exc.read().decode("utf-8", errors="replace")
        return {"code": exc.code, "message": text}
    except urllib.error.URLError as exc:  # pragma: no cover - 连接失败时触发
        return {"code": -1, "message": str(exc)}


def _extract_source_files(result: dict[str, Any]) -> list[str]:
    """从单条问答结果里抽取引用来源文件名列表（保持排名顺序）。"""
    files: list[str] = []
    for source in result.get("sources", []) or []:
        if not isinstance(source, dict):
            continue
        # 优先用扁平 file 字段（本仓库 normalize_evidence 的输出形态）。
        candidate = source.get("file") or source.get("file_name")
        meta = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
        candidate = candidate or meta.get("file_name") or meta.get("file_path")
        if isinstance(candidate, str) and candidate:
            files.append(_normalize_file_name(os.path.basename(candidate)))
    return files


def _extract_source_kb_ids(result: dict[str, Any]) -> list[str]:
    """抽取返回来源的 kb_id 列表，用于校验知识库隔离。"""
    kb_ids: list[str] = []
    for source in result.get("sources", []) or []:
        if isinstance(source, dict):
            kb_id = source.get("kb_id")
            if isinstance(kb_id, str) and kb_id:
                kb_ids.append(kb_id)
    return kb_ids


def _extract_source_count(result: dict[str, Any]) -> int:
    """返回 sources 中 dict 来源条目的数量，用于识别 kb_id 缺失。"""
    return sum(1 for source in result.get("sources", []) or [] if isinstance(source, dict))


def _extract_relevant_doc_types(case: dict[str, Any]) -> list[str]:
    """抽取用例中相关文档的文件类型，便于按 PDF / 表格 / 线索类分组。"""
    types: list[str] = []
    for doc in case.get("relevant_documents", []) or []:
        if not isinstance(doc, dict):
            continue
        file_name = doc.get("file_name")
        if isinstance(file_name, str) and file_name:
            suffix = Path(file_name).suffix.lower()
            if suffix:
                types.append(suffix)
        file_path = doc.get("file_path")
        if isinstance(file_path, str) and file_path:
            suffix = Path(file_path).suffix.lower()
            if suffix:
                types.append(suffix)
    return types


# 强拒绝标记：命中任一即可判定为边界型拒绝（"超出范围 / 建议转权威渠道 / 不保证覆盖"）。
# 这些措辞只在系统明确放弃回答时出现，不会在正常作答里误命中。
_STRONG_REFUSAL_MARKERS = (
    "无法提供",
    "无法根据现有信息",
    "超出",
    "覆盖范围",
    "范围内",
    "不保证",
    "建议通过",
    "权威渠道",
    "建议咨询",
    "建议查阅",
    "未包含",
    "不在当前知识库",
    "不在本知识库",
    "不应返回",
    "不应该返回",
    "不应当返回",
)

FAILURE_GROUP_ORDER = (
    "api_error",
    "retrieval_miss",
    "rank_miss",
    "source_noise",
    "ocr_text_quality",
    "duplicate_or_conflict",
    "kb_isolation_failure",
    "refusal_miss",
)

# 弱拒绝标记：单凭它们不足以判定拒绝——正常部分作答里也可能出现 hedging
# （如"未明确提及""无法确定具体数值"）。只有当答案整体很短、缺乏实质内容时，
# 才把它们视作拒绝信号，避免把"召回到正确文档但 hedged 的长答案"误判为拒绝。
_WEAK_REFUSAL_MARKERS = (
    "未提及",
    "未提供",
    "未明确",
    "无法回答",
    "不知道",
    "没有相关",
    "未找到",
    "没有找到",
    "无法确定",
)

# 当答案命中弱标记时，只有答案不超过这个字符数才视作拒绝（缺实质内容的简短兜底）。
_WEAK_REFUSAL_MAX_LEN = 60


def _answer_is_refusal_like(answer: str) -> bool:
    """判断 answer 是否属于"无相关信息 / 超出范围"式拒绝。

    规则：
    - 强标记命中任意一个 → 判为拒绝。
    - 仅弱标记命中，且答案简短（<= _WEAK_REFUSAL_MAX_LEN 字）→ 判为拒绝。
    - 仅弱标记命中但答案较长（通常含实质内容）→ 不判为拒绝，避免误伤部分作答。
    """
    if not answer:
        return True
    text = answer.strip()
    if text.lower() in {"empty response", "no response"}:
        return True
    if any(marker in text for marker in _STRONG_REFUSAL_MARKERS):
        return True
    if len(text) <= _WEAK_REFUSAL_MAX_LEN and any(
        marker in text for marker in _WEAK_REFUSAL_MARKERS
    ):
        return True
    return False


def evaluate_case(
    case: dict[str, Any],
    api_base: str,
    kb_id: str,
    timeout: float,
) -> dict[str, Any]:
    """对单条用例发起问答并计算检索/引用指标。"""
    question = case["query"]
    requested_kb_ids = case.get("search_kb_ids") or [kb_id]
    if not isinstance(requested_kb_ids, list) or not requested_kb_ids:
        requested_kb_ids = [kb_id]
    tags = case.get("tags", [])
    if not isinstance(tags, list):
        tags = [str(tags)]
    relevant_names = {
        _normalize_file_name(os.path.basename(doc.get("file_name", "")))
        for doc in case.get("relevant_documents", [])
        if doc.get("file_name")
    }
    relevant_doc_types = _extract_relevant_doc_types(case)
    answerable = bool(case.get("answerable", True))

    response = _post_json(
        api_base,
        "/api/chat/query",
        {
            "question": question,
            "session_id": f"grain-eval::{case.get('id', case.get('_line_no'))}",
            "kb_ids": requested_kb_ids,
        },
        timeout=timeout,
    )

    error_message: str | None = None
    source_files: list[str] = []
    source_kb_ids: list[str] = []
    source_count = 0
    answer = ""

    if response.get("code") == 0 and isinstance(response.get("data"), dict):
        data = response["data"]
        answer = str(data.get("answer", "") or "")
        source_files = _extract_source_files(data)
        source_kb_ids = _extract_source_kb_ids(data)
        source_count = _extract_source_count(data)
    else:
        error_message = str(response.get("message") or response)

    # Recall / MRR @5：在 top5 引用里找首个命中的相关文档。
    top_k_view = source_files[:5]
    hit_rank = None
    for rank, name in enumerate(top_k_view, start=1):
        if name in relevant_names:
            hit_rank = rank
            break
    recall_at_5 = 1 if hit_rank is not None else 0
    mrr_at_5 = (1.0 / hit_rank) if hit_rank is not None else 0.0

    citation_hit = 1 if (answerable and bool(source_files)) else 0
    refusal_correct = 1 if (not answerable and _answer_is_refusal_like(answer)) else 0

    kb_id_missing_count = max(source_count - len(source_kb_ids), 0)
    allowed_kb_ids = {str(item) for item in requested_kb_ids if item}
    kb_isolation = (
        1
        if source_count == len(source_kb_ids) and all(kb in allowed_kb_ids for kb in source_kb_ids)
        else 0
    )

    return {
        "id": case.get("id"),
        "query": question,
        "requested_kb_ids": requested_kb_ids,
        "answerable": answerable,
        "difficulty": case.get("difficulty"),
        "tags": tags,
        "relevant_files": sorted(relevant_names),
        "relevant_doc_types": sorted(set(relevant_doc_types)),
        "answer_preview": answer[:160],
        "source_files_top5": top_k_view,
        "source_count": source_count,
        "source_kb_ids": source_kb_ids,
        "kb_id_missing_count": kb_id_missing_count,
        "error": error_message,
        "recall_at_5": recall_at_5,
        "mrr_at_5": round(mrr_at_5, 4),
        "citation_hit": citation_hit,
        "refusal_correct": refusal_correct,
        "kb_isolation": kb_isolation,
    }


def classify_failure_groups(result: dict[str, Any]) -> list[str]:
    """基于评测结果给单条用例打失败分组标签。"""
    if result.get("error"):
        return ["api_error"]

    groups: list[str] = []
    answerable = bool(result.get("answerable", True))
    tags = set(result.get("tags", []) or [])
    relevant_types = set(result.get("relevant_doc_types", []) or [])

    if not answerable:
        if not result.get("refusal_correct"):
            groups.append("refusal_miss")
        if not result.get("kb_isolation"):
            groups.append("kb_isolation_failure")
        return groups

    if not result.get("kb_isolation"):
        groups.append("kb_isolation_failure")

    if not result.get("recall_at_5"):
        if {"pdf", "scan", "ocr"} & tags or ".pdf" in relevant_types:
            groups.append("ocr_text_quality")
        elif {"duplicate", "conflict", "repeat"} & tags:
            groups.append("duplicate_or_conflict")
        else:
            groups.append("retrieval_miss")
    elif result.get("mrr_at_5", 0.0) < 1.0:
        groups.append("rank_miss")

    source_count = int(result.get("source_count", 0) or 0)
    source_files = result.get("source_files_top5", []) or []
    unique_sources = len({name for name in source_files if name})
    if source_count >= 4 and (not result.get("recall_at_5") or result.get("mrr_at_5", 0.0) < 1.0):
        groups.append("source_noise")
    elif unique_sources >= 4 and not result.get("recall_at_5"):
        groups.append("source_noise")

    return groups


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总逐条结果为整体指标。"""
    if not results:
        return {"total": 0}

    total = len(results)
    answerable = [r for r in results if r["answerable"]]
    unanswerable = [r for r in results if not r["answerable"]]

    def _mean(rows: list[dict[str, Any]], key: str) -> float:
        return sum(r[key] for r in rows) / len(rows) if rows else 0.0

    errors = [r for r in results if r.get("error")]

    return {
        "total": total,
        "answerable_total": len(answerable),
        "unanswerable_total": len(unanswerable),
        "error_count": len(errors),
        "recall_at_5": round(_mean(answerable, "recall_at_5"), 4),
        "mrr_at_5": round(_mean(answerable, "mrr_at_5"), 4),
        "citation_hit_rate": round(_mean(answerable, "citation_hit"), 4),
        "refusal_accuracy": round(_mean(unanswerable, "refusal_correct"), 4) if unanswerable else None,
        "kb_isolation_rate": round(_mean(results, "kb_isolation"), 4),
    }


def build_failure_groups(results: list[dict[str, Any]], limit: int = 8) -> dict[str, Any]:
    """按失败类型聚合评测结果，并保留少量样例。"""
    grouped: dict[str, list[dict[str, Any]]] = {group: [] for group in FAILURE_GROUP_ORDER}
    for result in results:
        groups = classify_failure_groups(result)
        if not groups:
            continue
        enriched = {
            "id": result.get("id"),
            "query": result.get("query"),
            "answerable": result.get("answerable"),
            "tags": result.get("tags", []),
            "difficulty": result.get("difficulty"),
            "source_files_top5": result.get("source_files_top5", []),
            "source_count": result.get("source_count", 0),
            "mrr_at_5": result.get("mrr_at_5", 0.0),
            "recall_at_5": result.get("recall_at_5", 0),
            "kb_isolation": result.get("kb_isolation", 0),
            "answer_preview": result.get("answer_preview", ""),
            "error": result.get("error"),
            "groups": groups,
        }
        for group in groups:
            grouped.setdefault(group, []).append(enriched)

    return {
        group: {
            "count": len(items),
            "samples": items[:limit],
        }
        for group, items in grouped.items()
    }


def _load_resume_results(output_path: Path, cases_sha: str) -> dict[str, dict[str, Any]]:
    """读取已有报告中可安全复用的成功 case 结果。"""
    if not output_path.exists():
        return {}
    try:
        report = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if report.get("cases_sha256") != cases_sha:
        return {}
    reusable: dict[str, dict[str, Any]] = {}
    for item in report.get("cases", []) or []:
        if not isinstance(item, dict) or item.get("error"):
            continue
        case_id = item.get("id")
        if isinstance(case_id, str) and case_id:
            reusable[case_id] = item
    return reusable


def _write_report(
    *,
    output_path: Path,
    api_base: str,
    timeout: float,
    kb_id: str,
    cases_path: str,
    cases_sha: str,
    per_case: list[dict[str, Any]],
    resume_meta: dict[str, Any],
) -> dict[str, Any]:
    """写出完整或部分评测报告。"""
    summary = summarize(per_case)
    failure_groups = build_failure_groups(per_case)
    report = {
        "generated_at": _now_iso(),
        "api_base": api_base,
        "timeout": timeout,
        "kb_id": kb_id,
        "cases_path": cases_path,
        "cases_sha256": cases_sha,
        "resume": resume_meta,
        "summary": summary,
        "failure_groups": failure_groups,
        "cases": per_case,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def run_evaluation(
    *,
    cases_path: str,
    api_base: str,
    kb_id: str,
    timeout: float,
    output: str,
    resume: bool = False,
    stop_on_api_error: bool = False,
) -> tuple[dict[str, Any], int]:
    """执行评测并返回报告与进程退出码。"""
    cases = load_cases(cases_path)
    if not cases:
        print(f"未读取到评测用例: {cases_path}", file=sys.stderr)
        return {"summary": {"total": 0}}, 2

    output_path = Path(output)
    cases_sha = file_sha256(cases_path)
    reusable = _load_resume_results(output_path, cases_sha) if resume else {}
    reused_count = 0
    executed_count = 0
    per_case: list[dict[str, Any]] = []

    print(f"加载 {len(cases)} 条评测用例，目标 KB={kb_id}")
    for index, case in enumerate(cases, start=1):
        case_id = str(case.get("id") or case.get("_line_no"))
        if case_id in reusable:
            result = reusable[case_id]
            reused_count += 1
            per_case.append(result)
            print(f"[{index}/{len(cases)}] ↻ {result['id']} reused -> {result['source_files_top5'][:2]}")
            continue

        result = evaluate_case(case, api_base, kb_id, timeout)
        executed_count += 1
        per_case.append(result)
        hit_mark = "✓" if result["recall_at_5"] else "✗"
        print(
            f"[{index}/{len(cases)}] {hit_mark} {result['id']} "
            f"recall@5={result['recall_at_5']} mrr={result['mrr_at_5']} "
            f"-> {result['source_files_top5'][:2]}"
        )
        if stop_on_api_error and result.get("error"):
            report = _write_report(
                output_path=output_path,
                api_base=api_base,
                timeout=timeout,
                kb_id=kb_id,
                cases_path=cases_path,
                cases_sha=cases_sha,
                per_case=per_case,
                resume_meta={
                    "enabled": resume,
                    "reused_count": reused_count,
                    "executed_count": executed_count,
                    "stopped_on_api_error": True,
                    "completed": False,
                },
            )
            return report, 1

    report = _write_report(
        output_path=output_path,
        api_base=api_base,
        timeout=timeout,
        kb_id=kb_id,
        cases_path=cases_path,
        cases_sha=cases_sha,
        per_case=per_case,
        resume_meta={
            "enabled": resume,
            "reused_count": reused_count,
            "executed_count": executed_count,
            "stopped_on_api_error": False,
            "completed": True,
        },
    )
    return report, 0


def _build_arg_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="粮仓知识库真实问答评测")
    parser.add_argument(
        "--cases",
        default="data/grain-knowledge-base/qa/verified.jsonl",
        help="verified.jsonl 评测集路径",
    )
    parser.add_argument(
        "--api-base",
        default=resolve_api_base_url(default_port=DEFAULT_LOCAL_API_PORT),
        help="API 根地址；优先读取 KB_API_BASE_URL，未设置时回退到 KB_API_PORT（默认 18080）",
    )
    parser.add_argument(
        "--kb-id",
        default="grain-knowledge-base",
        help="目标知识库 ID",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="单条问答超时秒数",
    )
    parser.add_argument(
        "--output",
        default="data/grain-knowledge-base/qa/qa-eval-report.json",
        help="评测报告输出路径",
    )
    parser.add_argument("--resume", action="store_true", help="复用已有报告中无 API error 的 case 结果")
    parser.add_argument("--stop-on-api-error", action="store_true", help="遇到 API error 时写出部分报告并退出")
    return parser


def main() -> None:
    """命令行入口。"""
    parser = _build_arg_parser()
    args = parser.parse_args()

    report, exit_code = run_evaluation(
        cases_path=args.cases,
        api_base=args.api_base,
        kb_id=args.kb_id,
        timeout=args.timeout,
        output=args.output,
        resume=args.resume,
        stop_on_api_error=args.stop_on_api_error,
    )

    print("\n=== 评测汇总 ===")
    print(json.dumps(report.get("summary", {}), ensure_ascii=False, indent=2))
    failure_groups = report.get("failure_groups", {})
    if failure_groups:
        print("\n=== 失败分组 ===")
        print(json.dumps(failure_groups, ensure_ascii=False, indent=2))
    print(f"\n报告已写入: {Path(args.output)}")
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
