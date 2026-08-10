"""粮仓知识库检索-only 实验矩阵。

本脚本绕过 LLM 生成，直接加载 KB-scoped index 并调用现有融合检索器，
用于快速比较 top_k、fusion mode 与 reranker 对 Recall/MRR/source_noise 的影响。
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llama_index.core.schema import QueryBundle

from server.models.reranker import create_reranker_model
from server.retriever import FUSION_MODES, SimpleFusionRetriever

_HASH_SUFFIX_RE = re.compile(r"_[0-9a-f]{6,16}(?=\.[A-Za-z0-9]+$)")
_FULLWIDTH_TRANSLATION = str.maketrans({"（": "(", "）": ")"})


def normalize_file_name(name: str) -> str:
    """剥离导入 hash 后缀并统一括号，得到稳定可比较文件名。"""
    return _HASH_SUFFIX_RE.sub("", os.path.basename(str(name or ""))).translate(_FULLWIDTH_TRANSLATION)


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


def relevant_file_names(case: dict[str, Any]) -> set[str]:
    """抽取单条用例的期望来源文件名集合。"""
    return {
        normalize_file_name(doc.get("file_name", ""))
        for doc in case.get("relevant_documents", []) or []
        if isinstance(doc, dict) and doc.get("file_name")
    }


def source_file_name(node: Any) -> str:
    """从 NodeWithScore 中抽取归一化来源文件名。"""
    metadata = getattr(getattr(node, "node", None), "metadata", {}) or {}
    return normalize_file_name(
        metadata.get("file_name")
        or metadata.get("filename")
        or metadata.get("file_path")
        or metadata.get("source_path")
        or ""
    )


def dedupe_source_files(files: list[str]) -> list[str]:
    """按归一化文件名去重，保留首次出现顺序。"""
    deduped: list[str] = []
    seen: set[str] = set()
    for file_name in files:
        normalized = normalize_file_name(file_name)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def hit_rank(source_files: list[str], relevant_files: set[str], *, top_n: int = 5) -> int | None:
    """返回首个命中的 1-based rank；未命中返回 None。"""
    for rank, file_name in enumerate(source_files[:top_n], start=1):
        if normalize_file_name(file_name) in relevant_files:
            return rank
    return None


def classify_source_noise(source_files: list[str], recall_at_5: int, mrr_at_5: float) -> int:
    """沿用 QA eval 的轻量 source_noise 判定。"""
    source_count = len(source_files)
    unique_sources = len({name for name in source_files if name})
    if source_count >= 4 and (not recall_at_5 or mrr_at_5 < 1.0):
        return 1
    if unique_sources >= 4 and not recall_at_5:
        return 1
    return 0


@dataclass(frozen=True)
class ExperimentConfig:
    """单组检索实验配置。"""

    top_k: int
    mode: str
    use_reranker: bool = False
    top_n: int = 5

    @property
    def name(self) -> str:
        rerank = f"rerank{self.top_n}" if self.use_reranker else "no-rerank"
        return f"top{self.top_k}-{self.mode}-{rerank}"


def evaluate_sources(
    *,
    case: dict[str, Any],
    source_files: list[str],
) -> dict[str, Any]:
    """基于来源文件列表计算单条检索指标。"""
    relevant = relevant_file_names(case)
    answerable = bool(case.get("answerable", True))
    rank = hit_rank(source_files, relevant)
    recall_at_5 = 1 if rank is not None else 0
    mrr_at_5 = round(1.0 / rank, 4) if rank is not None else 0.0
    return {
        "id": case.get("id"),
        "query": case.get("query"),
        "answerable": answerable,
        "relevant_files": sorted(relevant),
        "source_files_top5": source_files[:5],
        "source_count": len(source_files),
        "hit_rank": rank,
        "recall_at_5": recall_at_5,
        "mrr_at_5": mrr_at_5,
        "source_noise": classify_source_noise(source_files[:5], recall_at_5, mrr_at_5) if answerable else 0,
    }


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总检索-only 指标。"""
    answerable = [item for item in results if item.get("answerable")]
    if not answerable:
        return {"total": len(results), "answerable_total": 0}

    retrieval_miss = [item for item in answerable if not item.get("recall_at_5")]
    rank_miss = [
        item
        for item in answerable
        if item.get("recall_at_5") and float(item.get("mrr_at_5") or 0.0) < 1.0
    ]
    source_noise = [item for item in answerable if item.get("source_noise")]
    return {
        "total": len(results),
        "answerable_total": len(answerable),
        "recall_at_5": round(sum(item["recall_at_5"] for item in answerable) / len(answerable), 4),
        "mrr_at_5": round(sum(item["mrr_at_5"] for item in answerable) / len(answerable), 4),
        "retrieval_miss_count": len(retrieval_miss),
        "rank_miss_count": len(rank_miss),
        "source_noise_count": len(source_noise),
        "retrieval_miss_ids": [item["id"] for item in retrieval_miss],
        "rank_miss_ids": [item["id"] for item in rank_miss],
        "source_noise_ids": [item["id"] for item in source_noise],
    }


def _mode_from_name(name: str) -> FUSION_MODES:
    """把 CLI mode 字符串转换为 FUSION_MODES。"""
    for mode in FUSION_MODES:
        if mode.value == name or mode.name.lower() == name.lower():
            return mode
    raise ValueError(f"未知 fusion mode: {name}")


def _node_excerpt(node: Any, max_chars: int = 180) -> str:
    text = getattr(getattr(node, "node", None), "text", "") or ""
    return " ".join(str(text).split())[:max_chars]


def _json_safe_score(score: Any) -> float | None:
    """把 numpy/torch 标量分数转换为 JSON 可序列化 float。"""
    if score is None:
        return None
    try:
        return float(score)
    except (TypeError, ValueError):
        return None


def run_single_experiment(
    *,
    index: Any,
    cases: list[dict[str, Any]],
    kb_id: str,
    config: ExperimentConfig,
    focus_case_ids: set[str] | None = None,
) -> dict[str, Any]:
    """运行一组检索实验。"""
    retriever = SimpleFusionRetriever(
        index,
        top_k=config.top_k,
        mode=_mode_from_name(config.mode),
        kb_ids=[kb_id],
    )
    reranker = create_reranker_model(top_n=config.top_n) if config.use_reranker else None
    selected_cases = [case for case in cases if not focus_case_ids or case.get("id") in focus_case_ids]
    results: list[dict[str, Any]] = []
    diagnostics: dict[str, list[dict[str, Any]]] = {}

    for case in selected_cases:
        query = str(case.get("query") or "")
        nodes = retriever.retrieve(query)
        if reranker is not None:
            nodes = reranker.postprocess_nodes(nodes, query_bundle=QueryBundle(query_str=query))
        raw_files = [source_file_name(node) for node in nodes]
        files = dedupe_source_files(raw_files)
        result = evaluate_sources(case=case, source_files=files)
        results.append(result)

        if focus_case_ids and case.get("id") in focus_case_ids:
            diagnostics[str(case.get("id"))] = [
                {
                    "rank": index + 1,
                    "score": _json_safe_score(getattr(node, "score", None)),
                    "file_name": source_file_name(node),
                    "raw_file_name": (getattr(getattr(node, "node", None), "metadata", {}) or {}).get("file_name"),
                    "excerpt": _node_excerpt(node),
                }
                for index, node in enumerate(nodes[: max(config.top_k, 10)])
            ]

    return {
        "config": asdict(config) | {"name": config.name},
        "summary": summarize_results(results),
        "cases": results,
        "diagnostics": diagnostics,
    }


def run_experiments(
    *,
    cases_path: str | Path,
    kb_id: str,
    top_ks: list[int],
    modes: list[str],
    include_reranker: bool,
    reranker_top_n: int,
    focus_case_ids: set[str] | None = None,
) -> dict[str, Any]:
    """加载 index 并运行实验矩阵。"""
    from api.runtime import runtime_state

    runtime_state.ensure_models_ready(require_llm=False)
    manager = runtime_state.get_index_manager(kb_id)
    if manager.index is None and manager.check_index_exists():
        manager.load_index()
    if manager.index is None:
        raise RuntimeError(f"知识库索引不可用: {kb_id}")

    cases = load_cases(cases_path)
    configs: list[ExperimentConfig] = []
    for top_k in top_ks:
        for mode in modes:
            configs.append(ExperimentConfig(top_k=top_k, mode=mode, use_reranker=False))
            if include_reranker:
                configs.append(
                    ExperimentConfig(
                        top_k=top_k,
                        mode=mode,
                        use_reranker=True,
                        top_n=reranker_top_n,
                    )
                )

    experiments = [
        run_single_experiment(
            index=manager.index,
            cases=cases,
            kb_id=kb_id,
            config=config,
            focus_case_ids=focus_case_ids,
        )
        for config in configs
    ]
    ranked = sorted(
        experiments,
        key=lambda item: (
            item["summary"].get("retrieval_miss_count", 999),
            item["summary"].get("rank_miss_count", 999),
            item["summary"].get("source_noise_count", 999),
            -item["summary"].get("mrr_at_5", 0),
        ),
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kb_id": kb_id,
        "cases_path": str(cases_path),
        "focus_case_ids": sorted(focus_case_ids or []),
        "experiments": experiments,
        "recommended": ranked[0]["config"] if ranked else None,
        "leaderboard": [
            {"config": item["config"], "summary": item["summary"]}
            for item in ranked
        ],
    }


def write_markdown_report(report: dict[str, Any], output_path: Path) -> Path:
    """写入便于人工阅读的 Markdown 报告。"""
    md_path = output_path.with_suffix(".md")
    lines = [
        "# Grain Retrieval Experiment Report",
        "",
        f"- KB: `{report['kb_id']}`",
        f"- Generated: `{report['generated_at']}`",
        f"- Recommended: `{(report.get('recommended') or {}).get('name')}`",
        "",
        "## Leaderboard",
        "",
        "| Config | Recall@5 | MRR@5 | Retrieval Miss | Rank Miss | Source Noise |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in report.get("leaderboard", []):
        config = item["config"]
        summary = item["summary"]
        lines.append(
            "| {name} | {recall} | {mrr} | {retrieval} | {rank} | {noise} |".format(
                name=config["name"],
                recall=summary.get("recall_at_5"),
                mrr=summary.get("mrr_at_5"),
                retrieval=summary.get("retrieval_miss_count"),
                rank=summary.get("rank_miss_count"),
                noise=summary.get("source_noise_count"),
            )
        )
    lines.extend(["", "## Focus Diagnostics", ""])
    for experiment in report.get("experiments", []):
        diagnostics = experiment.get("diagnostics") or {}
        if not diagnostics:
            continue
        lines.append(f"### {experiment['config']['name']}")
        for case_id, rows in diagnostics.items():
            lines.append(f"#### {case_id}")
            for row in rows[:10]:
                lines.append(
                    f"- {row['rank']}. `{row['file_name']}` score={row['score']} excerpt={row['excerpt']}"
                )
        lines.append("")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="粮仓知识库检索-only 实验矩阵")
    parser.add_argument("--cases", default="data/grain-knowledge-base/qa/verified.jsonl")
    parser.add_argument("--kb-id", default="grain-knowledge-base")
    parser.add_argument("--top-k", action="append", type=int, dest="top_ks")
    parser.add_argument("--mode", action="append", dest="modes")
    parser.add_argument("--include-reranker", action="store_true")
    parser.add_argument("--reranker-top-n", type=int, default=5)
    parser.add_argument("--focus-case", action="append", dest="focus_cases")
    parser.add_argument(
        "--output",
        default="docs/20260810-grain-retrieval-quality-tuning/artifacts/grain-retrieval-experiments.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    top_ks = args.top_ks or [5, 8, 10]
    modes = args.modes or [FUSION_MODES.DIST_BASED_SCORE.value]
    focus_case_ids = set(args.focus_cases or [])
    report = run_experiments(
        cases_path=args.cases,
        kb_id=args.kb_id,
        top_ks=top_ks,
        modes=modes,
        include_reranker=args.include_reranker,
        reranker_top_n=args.reranker_top_n,
        focus_case_ids=focus_case_ids or None,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path = write_markdown_report(report, output_path)
    print(json.dumps(report["leaderboard"], ensure_ascii=False, indent=2))
    print(f"report: {output_path}")
    print(f"markdown: {md_path}")


if __name__ == "__main__":
    main()
