"""生成审计文档使用的 pytest bundle 计数快照。"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = (
    REPO_ROOT / "docs" / "20260821-project-audit-remediation" / "artifacts" / "audit-metrics-snapshot.json"
)

CHAT_REGRESSION_ARGS = (
    "tests/api/test_chat_qa_metrics.py tests/api/test_chat_service.py "
    "tests/api/test_chat_evidence_contract.py tests/api/test_kb_preview_route.py"
)
DOCS_CONTRACT_ARGS = (
    "tests/scripts/test_dev_startup_contracts.py tests/scripts/test_docs_entry_contracts.py "
    "tests/test_requirements_profiles.py tests/scripts/test_cleanup_local_artifacts.py "
    "tests/scripts/test_repo_hygiene_contracts.py"
)
DOCKER_HELPER_ARGS = "tests/scripts/test_docker_smoke.py"
DOCKER_BUNDLE_ARGS = (
    "tests/scripts/test_docker_smoke.py tests/scripts/test_repo_hygiene_contracts.py "
    "tests/scripts/test_dev_startup_contracts.py tests/scripts/test_webapp_contracts.py "
    "tests/scripts/test_start_dev_smoke.py tests/scripts/test_dev_all_smoke.py "
    "tests/scripts/test_docs_entry_contracts.py tests/test_legacy_streamlit_entry.py "
    "tests/test_run_api.py tests/test_requirements_profiles.py"
)
STARTUP_DESKTOP_SMOKE_ARGS = (
    "tests/scripts/test_dev_startup_contracts.py tests/scripts/test_start_dev_smoke.py "
    "tests/scripts/test_dev_all_smoke.py"
)
PROMPT_BUNDLE_1_ARGS = (
    "tests/api/test_chat_composite_answers.py tests/api/test_chat_postprocessors.py "
    "tests/api/test_chat_service.py"
)
PROMPT_BUNDLE_2_ARGS = (
    "tests/api/test_chat_question_intents.py tests/api/test_chat_targeted_fact.py "
    "tests/api/test_chat_source_answers.py tests/api/test_chat_answer_repair.py"
)
PROMPT_BUNDLE_3_ARGS = "tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py"
FULL_NON_SLOW_ARGS = 'tests/ -m "not slow"'
CLOSURE_DOCS_SYNC_ARGS = (
    "tests/scripts/test_dev_startup_contracts.py tests/scripts/test_docs_entry_contracts.py "
    "tests/test_legacy_streamlit_entry.py tests/scripts/test_build_audit_metrics_snapshot.py"
)
CLOSURE_DOCKER_STARTUP_ARGS = (
    "tests/scripts/test_docker_smoke.py tests/test_requirements_profiles.py "
    "tests/scripts/test_dev_startup_contracts.py"
)
CLOSURE_REPO_HYGIENE_ARGS = (
    "tests/scripts/test_cleanup_local_artifacts.py tests/scripts/test_repo_hygiene_contracts.py"
)
CLOSURE_QUERY_REQUEST_ARGS = 'tests/api/test_runtime_model_loading.py -k "request or overrides_config_store_defaults"'
CLOSURE_EVAL_CONTRACT_ARGS = (
    "tests/api/test_chat_eval_runner.py tests/api/test_chat_eval_contracts.py "
    "tests/test_rag_quality_eval_dataset_v8.py"
)
CLOSURE_CHAT_MAINLINE_ARGS = (
    "tests/api/test_chat_scope_contract.py tests/api/test_open_api_service.py "
    "tests/api/test_open_api_integration.py tests/api/test_chat_service.py "
    "tests/api/test_chat_routes.py"
)

AUDIT_DOCS_DIR = Path("docs") / "20260821-project-audit-remediation"
CLOSURE_DOCS_DIR = Path("docs") / "20260825-p0-p2-status-closure"

CLOSURE_STATUS_COMMAND_LINES_TAG = "<!-- audit-sync:closure-status-command-lines -->"
CLOSURE_INTERVIEW_VALIDATION_LINES_TAG = "<!-- audit-sync:closure-interview-validation-lines -->"
CLOSURE_REPORT_VALIDATION_LINES_TAG = "<!-- audit-sync:closure-report-validation-lines -->"

CHAT_WARNING_COUNT = 0
PROMPT_BUNDLE_3_WARNING_COUNT = 0
FULL_NON_SLOW_WARNING_COUNT = 0
CLOSURE_QUERY_REQUEST_WARNING_COUNT = 0
CLOSURE_EVAL_CONTRACT_WARNING_COUNT = 0
CLOSURE_CHAT_MAINLINE_WARNING_COUNT = 0


@dataclass(frozen=True, slots=True)
class PytestBundle:
    key: str
    label: str
    pytest_args: str


@dataclass(frozen=True, slots=True)
class LineSyncRule:
    relative_path: Path
    anchor: str
    build_line: Callable[[dict[str, Any]], str]
    replace_all: bool = False
    match_index: int = 0


@dataclass(frozen=True, slots=True)
class NextLineSyncRule:
    relative_path: Path
    anchor: str
    build_next_line: Callable[[dict[str, Any]], str]
    match_index: int = 0


@dataclass(frozen=True, slots=True)
class FollowingLinesSyncRule:
    relative_path: Path
    anchor: str
    build_lines: Callable[[dict[str, Any]], Sequence[str]]
    line_count: int
    match_index: int = 0


DEFAULT_PYTEST_BUNDLES = (
    PytestBundle("chat_regression", "chat 关键回归", CHAT_REGRESSION_ARGS),
    PytestBundle("docs_contract", "启动 / 文档入口 / requirements / cleanup / repo hygiene 契约", DOCS_CONTRACT_ARGS),
    PytestBundle("startup_desktop_smoke", "startup + desktop 双 smoke", STARTUP_DESKTOP_SMOKE_ARGS),
    PytestBundle("docker_helper", "Docker smoke helper 契约", DOCKER_HELPER_ARGS),
    PytestBundle("docker_bundle", "startup / docker helper / repo hygiene 回归 bundle", DOCKER_BUNDLE_ARGS),
    PytestBundle("prompt_bundle_1", "Prompt bundle 1", PROMPT_BUNDLE_1_ARGS),
    PytestBundle("prompt_bundle_2", "Prompt bundle 2", PROMPT_BUNDLE_2_ARGS),
    PytestBundle("prompt_bundle_3", "Prompt bundle 3", PROMPT_BUNDLE_3_ARGS),
    PytestBundle("full_non_slow", "全量非慢测回归", FULL_NON_SLOW_ARGS),
    PytestBundle("closure_docs_sync", "P0/P2 收口：文档入口 / legacy / audit sync", CLOSURE_DOCS_SYNC_ARGS),
    PytestBundle("closure_docker_startup", "P0/P2 收口：Docker / requirements / startup contracts", CLOSURE_DOCKER_STARTUP_ARGS),
    PytestBundle("closure_repo_hygiene", "P0/P2 收口：cleanup / repo hygiene", CLOSURE_REPO_HYGIENE_ARGS),
    PytestBundle("closure_query_request", "P0/P2 收口：QueryRequest runtime override", CLOSURE_QUERY_REQUEST_ARGS),
    PytestBundle("closure_eval_contract", "P0/P2 收口：eval contract / dataset v8", CLOSURE_EVAL_CONTRACT_ARGS),
    PytestBundle("closure_chat_mainline", "P0/P2 收口：scope / open api / chat 主链路", CLOSURE_CHAT_MAINLINE_ARGS),
)

DEFAULT_NODE_TEST_COMMANDS = (
    ("desktop_full_node", "Desktop 全量 Node 单测", "npm --prefix desktop test"),
    ("webapp_full_node", "Web 全量 Node 单测", "npm --prefix webapp test"),
)

DEFAULT_CLEANUP_METRICS = (
    ("file_mode", "根目录 file-mode dry-run", False),
    ("directory_mode", "根目录 directory-mode dry-run", True),
)


def resolve_pytest_bundles(
    bundle_keys: Sequence[str] | None = None,
    *,
    bundles: Sequence[PytestBundle] = DEFAULT_PYTEST_BUNDLES,
) -> tuple[PytestBundle, ...]:
    """按 key 解析待收集 bundle；未指定时返回默认全集。"""
    if not bundle_keys:
        return tuple(bundles)

    bundle_map = {bundle.key: bundle for bundle in bundles}
    requested_keys: list[str] = []
    for raw_key in bundle_keys:
        key = str(raw_key or "").strip()
        if key and key not in requested_keys:
            requested_keys.append(key)

    missing = [key for key in requested_keys if key not in bundle_map]
    if missing:
        available = ", ".join(sorted(bundle_map))
        missing_display = ", ".join(missing)
        raise ValueError(f"未知 pytest bundle key: {missing_display}；可选值：{available}")

    return tuple(bundle_map[key] for key in requested_keys)


def load_existing_snapshot(snapshot_path: str | Path) -> dict[str, Any] | None:
    """读取已存在的快照；不存在时返回 None。"""
    path = Path(snapshot_path)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"快照文件不是 JSON object: {path}")
    return payload


def merge_snapshot_sections(base_snapshot: dict[str, Any] | None, updates: dict[str, Any]) -> dict[str, Any]:
    """把增量收集结果覆盖进已有快照，便于快速刷新部分 bundle 后继续 sync docs。"""
    merged = dict(base_snapshot or {})
    for key in ("generated_at", "repo_root"):
        if key in updates:
            merged[key] = updates[key]

    for section in ("bundles", "cleanup", "node_commands"):
        combined: dict[str, Any] = {}
        current = merged.get(section)
        if isinstance(current, dict):
            combined.update(current)
        update_section = updates.get(section)
        if isinstance(update_section, dict):
            combined.update(update_section)
        merged[section] = combined

    return merged


def validate_snapshot_for_doc_sync(snapshot: dict[str, Any]) -> None:
    """确保 sync-docs 前的快照已经覆盖文档规则所需的全部 section。"""
    missing: list[str] = []
    bundles = snapshot.get("bundles") if isinstance(snapshot.get("bundles"), dict) else {}
    cleanup = snapshot.get("cleanup") if isinstance(snapshot.get("cleanup"), dict) else {}
    node_commands = snapshot.get("node_commands") if isinstance(snapshot.get("node_commands"), dict) else {}

    for bundle in DEFAULT_PYTEST_BUNDLES:
        if bundle.key not in bundles:
            missing.append(f"bundles.{bundle.key}")
    for key, _label, _include_directories in DEFAULT_CLEANUP_METRICS:
        if key not in cleanup:
            missing.append(f"cleanup.{key}")
    for key, _label, _command in DEFAULT_NODE_TEST_COMMANDS:
        if key not in node_commands:
            missing.append(f"node_commands.{key}")

    if missing:
        joined = ", ".join(missing)
        raise ValueError(
            "当前 snapshot 缺少 sync-docs 所需指标："
            f"{joined}。请先生成完整快照，或保留现有输出 JSON 作为 merge 基线。"
        )


def _bundle(snapshot: dict[str, Any], key: str) -> dict[str, Any]:
    return snapshot["bundles"][key]


def _node_command(snapshot: dict[str, Any], key: str) -> dict[str, Any]:
    return snapshot.get("node_commands", {}).get(key, {})


def _pass_label(snapshot: dict[str, Any], key: str) -> str:
    return _bundle(snapshot, key)["pass_label"]


def _result_label(snapshot: dict[str, Any], key: str) -> str:
    return _bundle(snapshot, key)["result_label"]


def _node_pass_label(snapshot: dict[str, Any], key: str, fallback: str) -> str:
    metric = _node_command(snapshot, key)
    return str(metric.get("pass_label") or fallback)


def _label_with_warnings(snapshot: dict[str, Any], key: str, warning_count: int) -> str:
    label = _result_label(snapshot, key)
    return f"{label}, {warning_count} warnings" if warning_count else label


def _cleanup_metric(snapshot: dict[str, Any], key: str) -> dict[str, Any]:
    return snapshot.get("cleanup", {}).get(key, {})


def _cleanup_managed_count(snapshot: dict[str, Any], key: str, fallback: int = 0) -> int:
    metric = _cleanup_metric(snapshot, key)
    value = metric.get("managed_count", fallback)
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _cleanup_result_label(snapshot: dict[str, Any], key: str, fallback: str = "managed_count = 0") -> str:
    metric = _cleanup_metric(snapshot, key)
    return str(metric.get("result_label") or fallback)


def _cleanup_backlog_status_phrase(snapshot: dict[str, Any]) -> str:
    file_count = _cleanup_managed_count(snapshot, "file_mode")
    directory_count = _cleanup_managed_count(snapshot, "directory_mode")
    if file_count == 0 and directory_count == 0:
        return "file-mode / directory-mode 均已回到 `managed_count = 0`"
    if file_count == 0:
        return f"file-mode 已回到 `managed_count = 0`，directory-mode 为 `{_cleanup_result_label(snapshot, 'directory_mode')}`"
    return (
        f"file-mode 为 `{_cleanup_result_label(snapshot, 'file_mode')}`，"
        f"directory-mode 为 `{_cleanup_result_label(snapshot, 'directory_mode')}`"
    )


def _cleanup_focus_phrase(snapshot: dict[str, Any]) -> str:
    directory_count = _cleanup_managed_count(snapshot, "directory_mode")
    if directory_count == 0:
        return "后续重点转为防回脏、定期巡检与受控 apply 预案固化"
    return f"后续重点仍是对 `{directory_count}` 个 root scratch 目录做分批治理"


def _project_baseline_line(snapshot: dict[str, Any]) -> str:
    return (
        "- 当前可信评测基线以 `docs/20260821-project-audit-remediation/` 下当前材料与 2026-08-24 复跑结果为准："
        "layered suite `153 / 153`（Smoke `24 / 24`、Main `93 / 93`、Hard `36 / 36`）；"
        f"targeted fact / preview / metrics 回归 `{_label_with_warnings(snapshot, 'chat_regression', CHAT_WARNING_COUNT)}`；"
        f"启动 / 文档入口 / requirements / cleanup / repo hygiene 契约 `{_pass_label(snapshot, 'docs_contract')}`；"
        f"startup / docker helper / repo hygiene bundle `{_pass_label(snapshot, 'docker_bundle')}`；"
        f"Docker smoke helper 契约 `{_pass_label(snapshot, 'docker_helper')}`；"
        f"Desktop 全量 Node 单测 `{_node_pass_label(snapshot, 'desktop_full_node', '109 passed')}`；"
        f"Web 全量 Node 单测 `{_node_pass_label(snapshot, 'webapp_full_node', '27 passed')}`；"
        f"全量非慢测 `{_label_with_warnings(snapshot, 'full_non_slow', FULL_NON_SLOW_WARNING_COUNT)}`。"
    )


def _issues_summary_quote_line(snapshot: dict[str, Any]) -> str:
    return (
        "> 这个项目不是一个简单的本地问答 demo，而是把多知识库 scope isolation、evidence / preview 返回和 layered eval 分层评测做成了系统能力，"
        f"当前主路径已经闭环到 `153 / 153`，chat 关键回归 `{_label_with_warnings(snapshot, 'chat_regression', CHAT_WARNING_COUNT)}`，"
        f"全量非慢测 `{_label_with_warnings(snapshot, 'full_non_slow', FULL_NON_SLOW_WARNING_COUNT)}`。"
        "但我也不会把它包装成‘项目已经完全 finished’，因为当前重点已经转成工程收口："
        "legacy 兼容入口虽然已经默认禁用，需要 `KB_ALLOW_LEGACY_STREAMLIT=1` 显式 opt-in；"
        "Docker runtime build 的真实 smoke 证据、`chat_service.py` 规则链，以及 "
        f"{_cleanup_backlog_status_phrase(snapshot)}，{_cleanup_focus_phrase(snapshot)}。"
    )


def _guide_intro_line(snapshot: dict[str, Any]) -> str:
    return (
        "> **项目的主能力闭环已经完成，"
        f"当前 semireal layered suite 是 `153 / 153`，chat 关键回归是 `{_label_with_warnings(snapshot, 'chat_regression', CHAT_WARNING_COUNT)}`，"
        f"全量非慢测回归是 `{_label_with_warnings(snapshot, 'full_non_slow', FULL_NON_SLOW_WARNING_COUNT)}`；"
        "Prompt / heuristic 方向也已经完成 source projection、answer repair、composite answers 三批模块化，"
        f"但工程尾巴还没收完，当前 cleanup 侧已经做到 {_cleanup_backlog_status_phrase(snapshot)}，{_cleanup_focus_phrase(snapshot)}；"
        "同时 targeted-fact orchestration、hook builder 分散，以及 Docker runtime baseline 虽已移除顶层 `llama_index` metapackage 但完整 smoke 仍待补齐。**"
    )


def _report_script_intro_line(snapshot: dict[str, Any]) -> str:
    return (
        "> 这个项目现在**主能力闭环已经成立**：多知识库 scope isolation、evidence / preview 返回、layered eval 分层评测都能讲；"
        f"当前 semireal layered suite 是 `153 / 153`，chat 关键回归是 `{_label_with_warnings(snapshot, 'chat_regression', CHAT_WARNING_COUNT)}`，"
        f"全量非慢测回归是 `{_label_with_warnings(snapshot, 'full_non_slow', FULL_NON_SLOW_WARNING_COUNT)}`。"
        f"但工程完成度还没有追平能力完成度：cleanup 侧已经做到 {_cleanup_backlog_status_phrase(snapshot)}，{_cleanup_focus_phrase(snapshot)}；"
        "同时 legacy 入口、Docker runtime baseline、以及 chat_service 里剩余的 targeted-fact orchestration / hook builder 还要继续收口。"
    )


def _report_script_prompt_block(snapshot: dict[str, Any]) -> tuple[str, ...]:
    return (
        f"   - `{_pass_label(snapshot, 'prompt_bundle_1')}`",
        f"   - `{_pass_label(snapshot, 'prompt_bundle_2')}`",
        f"   - `{_label_with_warnings(snapshot, 'prompt_bundle_3', PROMPT_BUNDLE_3_WARNING_COUNT)}`",
    )


def _report_script_validation_slide_lines(snapshot: dict[str, Any]) -> tuple[str, ...]:
    return (
        "- `153 / 153` layered suite",
        f"- `{_label_with_warnings(snapshot, 'chat_regression', CHAT_WARNING_COUNT)}` chat 相关关键回归",
        (
            f"- `{_pass_label(snapshot, 'prompt_bundle_1')}`、`{_pass_label(snapshot, 'prompt_bundle_2')}`、"
            f"`{_label_with_warnings(snapshot, 'prompt_bundle_3', PROMPT_BUNDLE_3_WARNING_COUNT)}` Prompt / heuristic 模块化回归"
        ),
        f"- `{_pass_label(snapshot, 'docs_contract')}` 启动 / 文档 / requirements / cleanup / repo hygiene 契约",
        f"- `{_label_with_warnings(snapshot, 'full_non_slow', FULL_NON_SLOW_WARNING_COUNT)}` 全量非慢测",
    )


def _closure_status_command_lines(snapshot: dict[str, Any]) -> tuple[str, ...]:
    return (
        f"- `python -m pytest {CLOSURE_DOCS_SYNC_ARGS} -q` → `{_pass_label(snapshot, 'closure_docs_sync')}`",
        f"- `python -m pytest {CLOSURE_DOCKER_STARTUP_ARGS} -q` → `{_pass_label(snapshot, 'closure_docker_startup')}`",
        f"- `python -m pytest {CLOSURE_REPO_HYGIENE_ARGS} -q` → `{_pass_label(snapshot, 'closure_repo_hygiene')}`",
        f"- `python -m pytest {CLOSURE_QUERY_REQUEST_ARGS} -q` → `{_label_with_warnings(snapshot, 'closure_query_request', CLOSURE_QUERY_REQUEST_WARNING_COUNT)}`",
        f"- `python -m pytest {CLOSURE_EVAL_CONTRACT_ARGS} -q` → `{_label_with_warnings(snapshot, 'closure_eval_contract', CLOSURE_EVAL_CONTRACT_WARNING_COUNT)}`",
        f"- `python -m pytest {CLOSURE_CHAT_MAINLINE_ARGS} -q` → `{_label_with_warnings(snapshot, 'closure_chat_mainline', CLOSURE_CHAT_MAINLINE_WARNING_COUNT)}`",
        "- `node --test webapp/src/domain/agentExperience.test.js webapp/src/domain/chatWorkflow.test.js` → `21 pass`",
    )


def _closure_interview_validation_lines(snapshot: dict[str, Any]) -> tuple[str, ...]:
    return (
        f"- scope / open api / chat 主链路相关测试：`{_label_with_warnings(snapshot, 'closure_chat_mainline', CLOSURE_CHAT_MAINLINE_WARNING_COUNT)}`",
        f"- QueryRequest 覆盖 runtime override：`{_label_with_warnings(snapshot, 'closure_query_request', CLOSURE_QUERY_REQUEST_WARNING_COUNT)}`",
        f"- refusal / eval contract / dataset v8：`{_label_with_warnings(snapshot, 'closure_eval_contract', CLOSURE_EVAL_CONTRACT_WARNING_COUNT)}`",
        f"- 启动 / 文档入口 / legacy / audit sync：`{_pass_label(snapshot, 'closure_docs_sync')}`",
        f"- Docker / requirements / startup contracts：`{_pass_label(snapshot, 'closure_docker_startup')}`",
        f"- cleanup / repo hygiene：`{_pass_label(snapshot, 'closure_repo_hygiene')}`",
        "- 前端 `agentExperience + chatWorkflow`：`21 pass`",
    )


def _closure_report_validation_lines(snapshot: dict[str, Any]) -> tuple[str, ...]:
    return (
        f"- scope / open api / chat 主链路相关测试是 `{_label_with_warnings(snapshot, 'closure_chat_mainline', CLOSURE_CHAT_MAINLINE_WARNING_COUNT)}`",
        f"- QueryRequest runtime override 是 `{_label_with_warnings(snapshot, 'closure_query_request', CLOSURE_QUERY_REQUEST_WARNING_COUNT)}`",
        f"- refusal / negative contract / dataset v8 是 `{_label_with_warnings(snapshot, 'closure_eval_contract', CLOSURE_EVAL_CONTRACT_WARNING_COUNT)}`",
        f"- 启动 / 文档 / legacy / audit sync 是 `{_pass_label(snapshot, 'closure_docs_sync')}`",
        f"- Docker / requirements / startup contracts 是 `{_pass_label(snapshot, 'closure_docker_startup')}`",
        f"- cleanup / repo hygiene 是 `{_pass_label(snapshot, 'closure_repo_hygiene')}`",
        "- 前端状态与 experience 契约是 `21 pass`",
    )


DEFAULT_DOC_LINE_RULES = (
    LineSyncRule(Path("docs/project.md"), "- 当前可信评测基线以 `docs/20260821-project-audit-remediation/`", _project_baseline_line),
    LineSyncRule(
        Path("docs/interview/ThinkRAG_面试问答.md"),
        f"- `python -m pytest {CHAT_REGRESSION_ARGS} -q`",
        lambda snapshot: f"- `python -m pytest {CHAT_REGRESSION_ARGS} -q` → `{_label_with_warnings(snapshot, 'chat_regression', CHAT_WARNING_COUNT)}`",
    ),
    LineSyncRule(
        Path("docs/interview/ThinkRAG_面试问答.md"),
        f"- `python -m pytest {DOCS_CONTRACT_ARGS} -q`",
        lambda snapshot: f"- `python -m pytest {DOCS_CONTRACT_ARGS} -q` → `{_pass_label(snapshot, 'docs_contract')}`",
    ),
    LineSyncRule(
        Path("docs/interview/ThinkRAG_面试问答.md"),
        "4. **再讲怎么证明**：",
        lambda snapshot: (
            "4. **再讲怎么证明**："
            f"`153 / 153`、`{_label_with_warnings(snapshot, 'chat_regression', CHAT_WARNING_COUNT)}`、"
            f"`{_pass_label(snapshot, 'docs_contract')}`、`{_label_with_warnings(snapshot, 'full_non_slow', FULL_NON_SLOW_WARNING_COUNT)}`。"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-issues-summary.md",
        "- chat 关键回归：",
        lambda snapshot: f"- chat 关键回归：`{_label_with_warnings(snapshot, 'chat_regression', CHAT_WARNING_COUNT)}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-issues-summary.md",
        "- 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约：",
        lambda snapshot: f"- 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约：`{_pass_label(snapshot, 'docs_contract')}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-issues-summary.md",
        "- 2026-08-22 startup + desktop 双 smoke：",
        lambda snapshot: (
            "- 2026-08-22 startup + desktop 双 smoke："
            f"`python -m pytest {STARTUP_DESKTOP_SMOKE_ARGS} -q` → `{_pass_label(snapshot, 'startup_desktop_smoke')}`"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-issues-summary.md",
        "- 2026-08-22 Docker smoke helper 契约：",
        lambda snapshot: (
            "- 2026-08-22 Docker smoke helper 契约："
            f"`python -m pytest {DOCKER_HELPER_ARGS} -q` → `{_pass_label(snapshot, 'docker_helper')}`"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-issues-summary.md",
        "- 2026-08-22 startup / docker helper / repo hygiene bundle：",
        lambda snapshot: (
            "- 2026-08-22 startup / docker helper / repo hygiene bundle："
            f"`python -m pytest {DOCKER_BUNDLE_ARGS} -q` → `{_pass_label(snapshot, 'docker_bundle')}`"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-issues-summary.md",
        "- 2026-08-24 Desktop 全量 Node 单测：",
        lambda snapshot: (
            "- 2026-08-24 Desktop 全量 Node 单测："
            f"`npm --prefix desktop test` → `{_node_pass_label(snapshot, 'desktop_full_node', '111 passed')}`"
            "（已把 `desktop/package.json` 的 `test` 脚本收口为覆盖全部 `desktop/src/*.test.js` + `desktop/scripts/*.test.js`，不再只是旧的子集）"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-issues-summary.md",
        "- 2026-08-22 Web 全量 Node 单测：",
        lambda snapshot: (
            "- 2026-08-22 Web 全量 Node 单测："
            f"`npm --prefix webapp test` → `{_node_pass_label(snapshot, 'webapp_full_node', '27 passed')}`"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-issues-summary.md",
        "- 全量非慢测：",
        lambda snapshot: f"- 全量非慢测：`{_label_with_warnings(snapshot, 'full_non_slow', FULL_NON_SLOW_WARNING_COUNT)}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-issues-summary.md",
        "3. 再讲我怎么证明：",
        lambda snapshot: (
            "3. 再讲我怎么证明："
            f"`153 / 153`、`{_label_with_warnings(snapshot, 'chat_regression', CHAT_WARNING_COUNT)}`、`{_pass_label(snapshot, 'docs_contract')}`、`{_label_with_warnings(snapshot, 'full_non_slow', FULL_NON_SLOW_WARNING_COUNT)}`；"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-issues-summary.md",
        "这个项目不是一个简单的本地问答 demo",
        _issues_summary_quote_line,
        replace_all=True,
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-status-matrix.md",
        f"- `python -m pytest {CHAT_REGRESSION_ARGS} -q`",
        lambda snapshot: f"- `python -m pytest {CHAT_REGRESSION_ARGS} -q` → `{_label_with_warnings(snapshot, 'chat_regression', CHAT_WARNING_COUNT)}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-status-matrix.md",
        f"- `python -m pytest {DOCS_CONTRACT_ARGS} -q`",
        lambda snapshot: f"- `python -m pytest {DOCS_CONTRACT_ARGS} -q` → `{_pass_label(snapshot, 'docs_contract')}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-status-matrix.md",
        f"- `python -m pytest {STARTUP_DESKTOP_SMOKE_ARGS} -q`",
        lambda snapshot: f"- `python -m pytest {STARTUP_DESKTOP_SMOKE_ARGS} -q` → `{_pass_label(snapshot, 'startup_desktop_smoke')}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-status-matrix.md",
        f"- `python -m pytest {DOCKER_HELPER_ARGS} -q`",
        lambda snapshot: f"- `python -m pytest {DOCKER_HELPER_ARGS} -q` → `{_pass_label(snapshot, 'docker_helper')}`",
        match_index=0,
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-status-matrix.md",
        "- startup / docker helper / repo hygiene 回归 bundle：",
        lambda snapshot: (
            "- startup / docker helper / repo hygiene 回归 bundle："
            f"`python -m pytest {DOCKER_BUNDLE_ARGS} -q` → `{_pass_label(snapshot, 'docker_bundle')}`"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-status-matrix.md",
        "- `npm --prefix desktop test`",
        lambda snapshot: (
            f"- `npm --prefix desktop test` → `{_node_pass_label(snapshot, 'desktop_full_node', '111 passed')}`"
            "（当前已覆盖全部 `desktop/src/*.test.js` + `desktop/scripts/*.test.js`，不再遗漏 package/release 相关脚本单测）"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-status-matrix.md",
        "- `npm --prefix webapp test`",
        lambda snapshot: f"- `npm --prefix webapp test` → `{_node_pass_label(snapshot, 'webapp_full_node', '27 passed')}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-status-matrix.md",
        "- `python -m pytest tests/ -q -m \"not slow\"`",
        lambda snapshot: f"- `python -m pytest tests/ -q -m \"not slow\"` → `{_label_with_warnings(snapshot, 'full_non_slow', FULL_NON_SLOW_WARNING_COUNT)}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-status-matrix.md",
        f"- `python -m pytest {PROMPT_BUNDLE_1_ARGS} -q`",
        lambda snapshot: f"- `python -m pytest {PROMPT_BUNDLE_1_ARGS} -q` → `{_pass_label(snapshot, 'prompt_bundle_1')}`",
        replace_all=True,
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-status-matrix.md",
        f"- `python -m pytest {PROMPT_BUNDLE_2_ARGS} -q`",
        lambda snapshot: f"- `python -m pytest {PROMPT_BUNDLE_2_ARGS} -q` → `{_pass_label(snapshot, 'prompt_bundle_2')}`",
        replace_all=True,
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-status-matrix.md",
        f"- `python -m pytest {PROMPT_BUNDLE_3_ARGS} -q`",
        lambda snapshot: f"- `python -m pytest {PROMPT_BUNDLE_3_ARGS} -q` → `{_label_with_warnings(snapshot, 'prompt_bundle_3', PROMPT_BUNDLE_3_WARNING_COUNT)}`",
        replace_all=True,
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-status-matrix.md",
        "| 7 | Prompt 契约偏弱，后处理 heuristic 太重 |",
        lambda snapshot: (
            "| 7 | Prompt 契约偏弱，后处理 heuristic 太重 | **部分收敛（source projection + answer repair + composite answers 已独立模块化）** | "
            "`api/services/chat_service.py`、`api/services/chat_source_answers.py`、`api/services/chat_answer_repair.py`、`api/services/chat_composite_answers.py`、"
            "`tests/api/test_chat_source_answers.py`、`tests/api/test_chat_answer_repair.py`、`tests/api/test_chat_composite_answers.py` | "
            "现在不再是所有 source-backed 修复都堆在 `chat_service.py`：table / preview / boundary / scope-definition 已在 `chat_source_answers.py`，"
            "brief-answer expansion / exact-term repair / answer-support segmentation 已在 `chat_answer_repair.py`，multi-fact merge / summary bundle 也已下沉到 "
            "`chat_composite_answers.py` 并补齐独立契约测试；对应 bundle `python -m pytest "
            f"{PROMPT_BUNDLE_1_ARGS} -q` 当前为 `{_pass_label(snapshot, 'prompt_bundle_1')}`。 "
            "`chat_service.py` 进一步从 `1585` 行降到 `1166` 行。当前剩余更重的规则链主要集中在 targeted-fact orchestration 与其邻近的 scoring / source-selection 流程 | "
            "下一步优先继续下沉 targeted-fact orchestration，并整理 hook builder / dependency registry，同时持续把可稳定的能力前移到 prompt / response contract 层 |"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-audit-evidence.md",
        f"- `python -m pytest {PROMPT_BUNDLE_1_ARGS} -q`",
        lambda snapshot: f"- `python -m pytest {PROMPT_BUNDLE_1_ARGS} -q` → `{_pass_label(snapshot, 'prompt_bundle_1')}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-audit-evidence.md",
        f"- `python -m pytest {PROMPT_BUNDLE_2_ARGS} -q`",
        lambda snapshot: f"- `python -m pytest {PROMPT_BUNDLE_2_ARGS} -q` → `{_pass_label(snapshot, 'prompt_bundle_2')}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-audit-evidence.md",
        f"- `python -m pytest {PROMPT_BUNDLE_3_ARGS} -q`",
        lambda snapshot: f"- `python -m pytest {PROMPT_BUNDLE_3_ARGS} -q` → `{_label_with_warnings(snapshot, 'prompt_bundle_3', PROMPT_BUNDLE_3_WARNING_COUNT)}`",
        replace_all=True,
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-spec.md",
        f"- `python -m pytest {PROMPT_BUNDLE_3_ARGS} -q`",
        lambda snapshot: f"- `python -m pytest {PROMPT_BUNDLE_3_ARGS} -q` → `{_label_with_warnings(snapshot, 'prompt_bundle_3', PROMPT_BUNDLE_3_WARNING_COUNT)}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-interview-pack.md",
        "- Chat 关键回归：",
        lambda snapshot: f"- Chat 关键回归：`{_label_with_warnings(snapshot, 'chat_regression', CHAT_WARNING_COUNT)}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-interview-pack.md",
        "- 全量非慢测：",
        lambda snapshot: f"- 全量非慢测：`{_label_with_warnings(snapshot, 'full_non_slow', FULL_NON_SLOW_WARNING_COUNT)}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-interview-pack.md",
        "我这轮主要做了三件事。第一，把主能力做成闭环：",
        lambda snapshot: (
            "我这轮主要做了三件事。第一，把主能力做成闭环：多知识库 scope isolation、evidence / preview 返回、以及 Smoke / Main / Hard 的 layered eval。第二，把关键契约做对：`basic` / `knowledge` 现在都要求显式 active KB，请求级 QueryRequest 参数也已经真正打进 route、query engine、semireal smoke 和 frontend API 链路，runtime 侧也有 `create_query_engine(...)` effective config 的回归证据；前端 query 成功也不会再因为 history 写回失败而被整体判错。第三，用测试、评测和治理来证明这些改动不是拍脑袋：当前 layered suite `153 / 153`，"
            f"chat 关键回归 `{_label_with_warnings(snapshot, 'chat_regression', CHAT_WARNING_COUNT)}`，"
            f"全量非慢测 `{_label_with_warnings(snapshot, 'full_non_slow', FULL_NON_SLOW_WARNING_COUNT)}`。"
            "所以我会把项目定义成：主能力闭环已经成型，但工程完成度还在继续补齐。"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-interview-pack.md",
        f"- `python -m pytest {PROMPT_BUNDLE_3_ARGS} -q`",
        lambda snapshot: f"- `python -m pytest {PROMPT_BUNDLE_3_ARGS} -q` → `{_label_with_warnings(snapshot, 'prompt_bundle_3', PROMPT_BUNDLE_3_WARNING_COUNT)}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-test-report.md",
        "| targeted fact / preview / metrics 回归 |",
        lambda snapshot: (
            f"| targeted fact / preview / metrics 回归 | `python -m pytest {CHAT_REGRESSION_ARGS} -q` | "
            f"`{_label_with_warnings(snapshot, 'chat_regression', CHAT_WARNING_COUNT)}` |"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-test-report.md",
        "| 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约 |",
        lambda snapshot: (
            f"| 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约 | `python -m pytest {DOCS_CONTRACT_ARGS} -q` | "
            f"`{_pass_label(snapshot, 'docs_contract')}` |"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-test-report.md",
        "| startup + desktop 双 smoke |",
        lambda snapshot: (
            "| startup + desktop 双 smoke | "
            f"`python -m pytest {STARTUP_DESKTOP_SMOKE_ARGS} -q` | `{_pass_label(snapshot, 'startup_desktop_smoke')}` |"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-test-report.md",
        "| Docker smoke helper 契约 |",
        lambda snapshot: f"| Docker smoke helper 契约 | `python -m pytest {DOCKER_HELPER_ARGS} -q` | `{_pass_label(snapshot, 'docker_helper')}` |",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-test-report.md",
        "| startup / docker helper / repo hygiene 回归 bundle |",
        lambda snapshot: (
            "| startup / docker helper / repo hygiene 回归 bundle | "
            f"`python -m pytest {DOCKER_BUNDLE_ARGS} -q` | `{_pass_label(snapshot, 'docker_bundle')}` |"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-test-report.md",
        "| Desktop 全量 Node 单测 |",
        lambda snapshot: f"| Desktop 全量 Node 单测 | `npm --prefix desktop test` | `{_node_pass_label(snapshot, 'desktop_full_node', '111 passed')}` |",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-test-report.md",
        "| Web 全量 Node 单测 |",
        lambda snapshot: f"| Web 全量 Node 单测 | `npm --prefix webapp test` | `{_node_pass_label(snapshot, 'webapp_full_node', '27 passed')}` |",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-test-report.md",
        "| 全量非慢测回归 |",
        lambda snapshot: (
            "| 全量非慢测回归 | `python -m pytest tests/ -q -m \"not slow\"` | "
            f"`{_label_with_warnings(snapshot, 'full_non_slow', FULL_NON_SLOW_WARNING_COUNT)}` |"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-test-report.md",
        "| Prompt bundle 1（composite answers / postprocessors / chat_service） |",
        lambda snapshot: (
            f"| Prompt bundle 1（composite answers / postprocessors / chat_service） | `python -m pytest {PROMPT_BUNDLE_1_ARGS} -q` | "
            f"`{_pass_label(snapshot, 'prompt_bundle_1')}` |"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-test-report.md",
        "| Prompt bundle 2（question intents / targeted fact / source answers / answer repair） |",
        lambda snapshot: (
            f"| Prompt bundle 2（question intents / targeted fact / source answers / answer repair） | `python -m pytest {PROMPT_BUNDLE_2_ARGS} -q` | "
            f"`{_pass_label(snapshot, 'prompt_bundle_2')}` |"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-test-report.md",
        "| Prompt bundle 3（eval runner / layered dataset） |",
        lambda snapshot: (
            f"| Prompt bundle 3（eval runner / layered dataset） | `python -m pytest {PROMPT_BUNDLE_3_ARGS} -q` | "
            f"`{_label_with_warnings(snapshot, 'prompt_bundle_3', PROMPT_BUNDLE_3_WARNING_COUNT)}` |"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-spec.md",
        f"- `python -m pytest {CHAT_REGRESSION_ARGS} -q`",
        lambda snapshot: f"- `python -m pytest {CHAT_REGRESSION_ARGS} -q` → `{_label_with_warnings(snapshot, 'chat_regression', CHAT_WARNING_COUNT)}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-spec.md",
        f"- `python -m pytest {DOCS_CONTRACT_ARGS} -q`",
        lambda snapshot: f"- `python -m pytest {DOCS_CONTRACT_ARGS} -q` → `{_pass_label(snapshot, 'docs_contract')}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-spec.md",
        '- `python -m pytest tests/ -q -m "not slow"`',
        lambda snapshot: f"- `python -m pytest tests/ -q -m \"not slow\"` → `{_label_with_warnings(snapshot, 'full_non_slow', FULL_NON_SLOW_WARNING_COUNT)}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-interview-brief.md",
        "- Chat 相关关键回归：",
        lambda snapshot: f"- Chat 相关关键回归：`{_label_with_warnings(snapshot, 'chat_regression', CHAT_WARNING_COUNT)}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-interview-brief.md",
        "- Prompt / heuristic 模块化近期回归：",
        lambda snapshot: (
            "- Prompt / heuristic 模块化近期回归："
            f"`{_pass_label(snapshot, 'prompt_bundle_1')}`、`{_pass_label(snapshot, 'prompt_bundle_2')}`、"
            f"`{_label_with_warnings(snapshot, 'prompt_bundle_3', PROMPT_BUNDLE_3_WARNING_COUNT)}`"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-interview-brief.md",
        "- 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约：",
        lambda snapshot: f"- 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约：`{_pass_label(snapshot, 'docs_contract')}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-interview-brief.md",
        "- Docker smoke helper 契约：",
        lambda snapshot: (
            f"- Docker smoke helper 契约：`{_pass_label(snapshot, 'docker_helper')}`；"
            f"startup / docker helper / repo hygiene bundle：`{_pass_label(snapshot, 'docker_bundle')}`"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-interview-brief.md",
        "- 全量非慢测：",
        lambda snapshot: f"- 全量非慢测：`{_label_with_warnings(snapshot, 'full_non_slow', FULL_NON_SLOW_WARNING_COUNT)}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-interview-brief.md",
        "当前 targeted fact / preview / metrics 相关回归",
        lambda snapshot: f"   - 当前 targeted fact / preview / metrics 相关回归 `{_label_with_warnings(snapshot, 'chat_regression', CHAT_WARNING_COUNT)}`；",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-interview-brief.md",
        "   - Prompt / heuristic 模块化回归",
        lambda snapshot: (
            "   - Prompt / heuristic 模块化回归 "
            f"`{_pass_label(snapshot, 'prompt_bundle_1')}`、`{_pass_label(snapshot, 'prompt_bundle_2')}`、"
            f"`{_label_with_warnings(snapshot, 'prompt_bundle_3', PROMPT_BUNDLE_3_WARNING_COUNT)}`；"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-interview-brief.md",
        "   - 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约",
        lambda snapshot: f"   - 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约 `{_pass_label(snapshot, 'docs_contract')}`；",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-interview-brief.md",
        "   - 全量非慢测回归",
        lambda snapshot: f"   - 全量非慢测回归 `{_label_with_warnings(snapshot, 'full_non_slow', FULL_NON_SLOW_WARNING_COUNT)}`；",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-material-pack.md",
        "- Chat 关键回归：",
        lambda snapshot: f"- Chat 关键回归：`{_label_with_warnings(snapshot, 'chat_regression', CHAT_WARNING_COUNT)}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-material-pack.md",
        "- 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约：",
        lambda snapshot: f"- 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约：`{_pass_label(snapshot, 'docs_contract')}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-material-pack.md",
        "- Docker smoke helper 契约：",
        lambda snapshot: (
            f"- Docker smoke helper 契约：`{_pass_label(snapshot, 'docker_helper')}`；"
            f"startup / docker helper / repo hygiene bundle：`{_pass_label(snapshot, 'docker_bundle')}`"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-material-pack.md",
        "- 全量非慢测：",
        lambda snapshot: f"- 全量非慢测：`{_label_with_warnings(snapshot, 'full_non_slow', FULL_NON_SLOW_WARNING_COUNT)}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-material-pack.md",
        f"  - `python -m pytest {PROMPT_BUNDLE_1_ARGS} -q`",
        lambda snapshot: f"  - `python -m pytest {PROMPT_BUNDLE_1_ARGS} -q` → `{_pass_label(snapshot, 'prompt_bundle_1')}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-material-pack.md",
        f"  - `python -m pytest {PROMPT_BUNDLE_2_ARGS} -q`",
        lambda snapshot: f"  - `python -m pytest {PROMPT_BUNDLE_2_ARGS} -q` → `{_pass_label(snapshot, 'prompt_bundle_2')}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-material-pack.md",
        f"  - `python -m pytest {PROMPT_BUNDLE_3_ARGS} -q`",
        lambda snapshot: f"  - `python -m pytest {PROMPT_BUNDLE_3_ARGS} -q` → `{_label_with_warnings(snapshot, 'prompt_bundle_3', PROMPT_BUNDLE_3_WARNING_COUNT)}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-guide.md",
        "> **项目的主能力闭环已经完成",
        _guide_intro_line,
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-guide.md",
        "- Chat 相关关键回归：",
        lambda snapshot: f"- Chat 相关关键回归：`{_label_with_warnings(snapshot, 'chat_regression', CHAT_WARNING_COUNT)}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-guide.md",
        "- Prompt / heuristic 模块化回归：",
        lambda snapshot: (
            "- Prompt / heuristic 模块化回归："
            f"`{_pass_label(snapshot, 'prompt_bundle_1')}`、`{_pass_label(snapshot, 'prompt_bundle_2')}`、"
            f"`{_label_with_warnings(snapshot, 'prompt_bundle_3', PROMPT_BUNDLE_3_WARNING_COUNT)}`"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-guide.md",
        "- 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约：",
        lambda snapshot: f"- 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约：`{_pass_label(snapshot, 'docs_contract')}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-guide.md",
        "- 全量非慢测：",
        lambda snapshot: f"- 全量非慢测：`{_label_with_warnings(snapshot, 'full_non_slow', FULL_NON_SLOW_WARNING_COUNT)}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-report-script.md",
        "> 这个项目现在**主能力闭环已经成立**",
        _report_script_intro_line,
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-report-script.md",
        "   - chat 关键回归：",
        lambda snapshot: f"   - chat 关键回归：`{_label_with_warnings(snapshot, 'chat_regression', CHAT_WARNING_COUNT)}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-report-script.md",
        "   - 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约：",
        lambda snapshot: f"   - 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约：`{_pass_label(snapshot, 'docs_contract')}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-report-script.md",
        "   - Docker smoke helper 契约：",
        lambda snapshot: f"   - Docker smoke helper 契约：`{_pass_label(snapshot, 'docker_helper')}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-report-script.md",
        "   - startup / docker helper / repo hygiene bundle：",
        lambda snapshot: f"   - startup / docker helper / repo hygiene bundle：`{_pass_label(snapshot, 'docker_bundle')}`",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-report-script.md",
        "   - 全量非慢测：",
        lambda snapshot: f"   - 全量非慢测：`{_label_with_warnings(snapshot, 'full_non_slow', FULL_NON_SLOW_WARNING_COUNT)}`",
    ),
    LineSyncRule(
        CLOSURE_DOCS_DIR / "20260825-p0-p2-status-closure-status-report.md",
        "| 1 | basic 模式和后端 single_kb 约束冲突 |",
        lambda snapshot: (
            "| 1 | basic 模式和后端 single_kb 约束冲突 | 已收口 | `webapp/src/domain/agentExperience.js` / `.test.js` 已要求 `basic` 与 `knowledge` 显式绑定 active KB；`api/services/query_scope.py` 明确把 chat 主链路收口到 `single_kb`；相关前后端测试通过（`21 pass` + "
            f"`{_label_with_warnings(snapshot, 'closure_chat_mainline', CLOSURE_CHAT_MAINLINE_WARNING_COUNT)}`） | 这一条当前不再是主阻塞，后续只需要防止新入口绕过 `kb_ids` 约束。 |"
        ),
    ),
    LineSyncRule(
        CLOSURE_DOCS_DIR / "20260825-p0-p2-status-closure-status-report.md",
        "| 3 | 项目主入口不统一 |",
        lambda snapshot: (
            "| 3 | 项目主入口不统一 | 大体收口 | README / `docs/project.md` / runbook / desktop contract 已由 `tests/scripts/test_docs_entry_contracts.py` 和 `tests/test_legacy_streamlit_entry.py` 兜底；本轮文档与 sync 脚本校验共 "
            f"`{_pass_label(snapshot, 'closure_docs_sync')}` | 当前可以明确对外口径：主入口是 FastAPI + React(Vite) + Electron；Streamlit 仅是 opt-in legacy 兼容入口。 |"
        ),
    ),
    LineSyncRule(
        CLOSURE_DOCS_DIR / "20260825-p0-p2-status-closure-status-report.md",
        "| 6 | 评测 harness 对 refusal / negative contract 覆盖不足 |",
        lambda snapshot: (
            "| 6 | 评测 harness 对 refusal / negative contract 覆盖不足 | 部分完成 | `tests/api/test_chat_eval_runner.py`、`tests/api/test_chat_eval_contracts.py`、`tests/test_rag_quality_eval_dataset_v8.py` 当前 "
            f"`{_label_with_warnings(snapshot, 'closure_eval_contract', CLOSURE_EVAL_CONTRACT_WARNING_COUNT)}`；说明 refusal / contract gate 已进入正式套件 | 负向覆盖已不是“没有”，但仍以 contract / fixture 驱动为主；后续更应该补 semireal hard negatives、真实追问型 refusal case。 |"
        ),
    ),
    LineSyncRule(
        CLOSURE_DOCS_DIR / "20260825-p0-p2-status-closure-status-report.md",
        "| 8 | Docker / requirements / 端口 / 启动脚本存在配置漂移 |",
        lambda snapshot: (
            "| 8 | Docker / requirements / 端口 / 启动脚本存在配置漂移 | 大体收口 | `tests/scripts/test_docker_smoke.py`、`tests/test_requirements_profiles.py`、`tests/scripts/test_dev_startup_contracts.py` 当前 "
            f"`{_pass_label(snapshot, 'closure_docker_startup')}`；`scripts/docker_smoke.py` 已走 Docker host port 回查口径；requirements profile 已有契约测试 | 配置漂移已经有自动化 gate，不再完全靠人工记忆；但文档和历史脚本仍需继续统一，建议继续保守表述为“大体收口”。 |"
        ),
    ),
    LineSyncRule(
        CLOSURE_DOCS_DIR / "20260825-p0-p2-status-closure-status-report.md",
        "| 9 | 仓库根目录临时文件、日志、调试脚本较多 |",
        lambda snapshot: (
            "| 9 | 仓库根目录临时文件、日志、调试脚本较多 | 部分完成 | 已存在 `scripts/cleanup_local_artifacts.py` 与 `tests/scripts/test_cleanup_local_artifacts.py` / `tests/scripts/test_repo_hygiene_contracts.py`，本轮 "
            f"`{_pass_label(snapshot, 'closure_repo_hygiene')}` | 治理规则已经建立，但仓库的脚本/文档代际较多，仍需继续做 inventory 减法，不能算完全结束。 |"
        ),
    ),
    LineSyncRule(
        CLOSURE_DOCS_DIR / "20260825-p0-p2-status-closure-status-report.md",
        "| 11 | 日志与临时产物治理需要规范化 |",
        lambda snapshot: (
            "| 11 | 日志与临时产物治理需要规范化 | 部分完成 | 已有 cleanup 脚本、repo hygiene 契约和文档约束；"
            f"`{_pass_label(snapshot, 'closure_repo_hygiene')}` 说明最基础的规则正在生效 | 规范化已经开始，但输出目录、临时产物命名和长期归档策略还可以继续统一。 |"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-audit.md",
        "| 03 | 根目录整洁度 |",
        lambda snapshot: (
            "| 03 | 根目录整洁度 | "
            f"{_cleanup_backlog_status_phrase(snapshot)}，说明 root scratch backlog 已从‘需要清理’切到‘需要防回脏’；{_cleanup_focus_phrase(snapshot)}。 | P0 |"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-audit.md",
        "| 04 | cleanup 覆盖范围 |",
        lambda snapshot: (
            "| 04 | cleanup 覆盖范围 | `scripts/cleanup_local_artifacts.py` 已支持 `--include-directories` 与显式 `--dry-run`，治理能力本身已经补齐；"
            f"当前状态是 {_cleanup_backlog_status_phrase(snapshot)}，{_cleanup_focus_phrase(snapshot)}。 | P0 |"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-interview-brief.md",
        "我做的重点不是把一个模型简单接上文档",
        lambda snapshot: (
            "我做的重点不是把一个模型简单接上文档，而是把**知识库边界、证据返回、回答质量评测**做成系统能力。"
            "现在主路径已经比较稳，当前 semireal layered suite 是 `150 / 150`，说明 scope、evidence、preview、cross-source fact 这些主能力已经闭环。"
            "同时，我也做了仓库治理：根目录文件级日志、临时探针和 OCR 草稿脚本已经完成多轮治理并清到 file-mode `0`。"
            f"现在 cleanup 侧已经做到 {_cleanup_backlog_status_phrase(snapshot)}，{_cleanup_focus_phrase(snapshot)}；"
            "legacy 入口、启动口径、文档统一、targeted-fact orchestration、hook builder 分散，以及 Docker runtime baseline 的完整 smoke 证据都还在继续收口。"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-interview-brief.md",
        "- 根目录治理：",
        lambda snapshot: f"- 根目录治理：{_cleanup_backlog_status_phrase(snapshot)}；{_cleanup_focus_phrase(snapshot)}",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-interview-brief.md",
        "> 我会把这个项目定义成：",
        lambda snapshot: (
            "> 我会把这个项目定义成：一个已经把多知识库 scope、evidence / preview 和 layered eval 做成闭环的本地知识库助手。"
            "现在最值得继续投入的，不是追求表面上的‘更多 1.0’，而是把启动链路、legacy 入口、文档统一，以及 prompt/heuristic 的边界继续做实，"
            f"并把 cleanup 侧已经做到 {_cleanup_backlog_status_phrase(snapshot)}、Docker runtime baseline 已收口但完整 Docker smoke 仍待补齐这两件事持续守住。"
            "这样讲既能体现我做出了东西，也能体现我对系统边界有真实判断。"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-status-matrix.md",
        "- 目录级治理能力也已经补上，当前",
        lambda snapshot: f"- 目录级治理能力也已经补上，当前 {_cleanup_backlog_status_phrase(snapshot)}，{_cleanup_focus_phrase(snapshot)}。",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-status-matrix.md",
        "| 9 | 仓库根目录临时文件、日志、调试脚本较多 |",
        lambda snapshot: (
            "| 9 | 仓库根目录临时文件、日志、调试脚本较多 | **已收敛** | `scripts/cleanup_local_artifacts.py`、三份 manifest、"
            "`python scripts/cleanup_local_artifacts.py --dry-run`、`python scripts/cleanup_local_artifacts.py --dry-run --include-directories` | "
            f"当前 {_cleanup_backlog_status_phrase(snapshot)}；问题已从‘根目录极乱’收敛到‘如何长期防回脏’ | {_cleanup_focus_phrase(snapshot)} |"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-status-matrix.md",
        "- file-mode / directory-mode 均已回到 `managed_count = 0`后的治理收口",
        lambda snapshot: f"- {_cleanup_backlog_status_phrase(snapshot)}后的治理收口，重点转为巡检、防回脏与 runbook 固化。",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-status-matrix.md",
        "3. 把目录治理从‘清 backlog’切到",
        lambda snapshot: f"3. 把目录治理从‘清 backlog’切到‘防回脏 + 定期巡检 + 受控 apply 预案’；当前 {_cleanup_backlog_status_phrase(snapshot)}。",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-status-matrix.md",
        "1. 这段 directory backlog sizing 属于历史留痕",
        lambda snapshot: (
            f"1. 这段 directory backlog sizing 属于历史留痕；截至最新 dry-run，{_cleanup_backlog_status_phrase(snapshot)}。"
            "后续更重要的是继续保留这套 sizing / 排序能力，避免下次回脏时只能人工平铺扫描。"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-status-matrix.md",
        "2. 当前 latest dry-run 已不再命中 root scratch 目录",
        lambda snapshot: "2. 当前 latest dry-run 已不再命中 root scratch 目录；下方 top 5 仅保留为历史 backlog sizing 留痕。",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-spec.md",
        "6. **仓库根目录临时文件、日志、调试脚本较多**",
        lambda snapshot: (
            "6. **仓库根目录临时文件、日志、调试脚本较多**：cleanup 能力已经建立起来，"
            f"当前 {_cleanup_backlog_status_phrase(snapshot)}，{_cleanup_focus_phrase(snapshot)}"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-spec.md",
        "4. 把根目录治理流程写进固定 runbook / 提交流程，并",
        lambda snapshot: f"4. 把根目录治理流程写进固定 runbook / 提交流程，并把目录治理重点切到巡检、防回脏与受控 apply 预案；当前 {_cleanup_backlog_status_phrase(snapshot)}",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-test-report.md",
        "2. 把目录治理从‘清 backlog’切到",
        lambda snapshot: f"2. 把目录治理从‘清 backlog’切到‘防回脏 + 定期巡检 + 受控 apply 预案’；当前 {_cleanup_backlog_status_phrase(snapshot)}",
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-test-report.md",
        "> **项目现在已经具备‘能力可讲、评测可讲、问题也能讲清楚’的条件。",
        lambda snapshot: (
            "> **项目现在已经具备‘能力可讲、评测可讲、问题也能讲清楚’的条件。接下来应该把重点从‘单次提分’切到‘工程收口与长期可维护性’，"
            f"并把 cleanup 侧已经做到 {_cleanup_backlog_status_phrase(snapshot)}、runtime baseline 根因已定位但完整 Docker smoke 仍待补齐这些事实讲清楚。**"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-test-report.md",
        "这段 backlog sizing 记录对应的是历史快照",
        lambda snapshot: (
            f"这段 backlog sizing 记录对应的是历史快照；截至最新 dry-run，{_cleanup_backlog_status_phrase(snapshot)}。"
            "后续保留 sizing / top offenders 视角，是为了下次回脏时仍能快速确定受控 apply 顺序。"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-test-report.md",
        "这也说明 cleanup 不该只停留在‘把 backlog 清零’",
        lambda snapshot: (
            f"这也说明 cleanup 不该只停留在‘把 backlog 清零’：既然当前 {_cleanup_backlog_status_phrase(snapshot)}，"
            "下一轮更应该把 sizing、top offenders 与受控 apply 预案沉淀为长期巡检机制。"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-guide.md",
        "也就是说，这一轮",
        lambda snapshot: (
            "也就是说，这一轮‘把这些整理完成’的目标，在材料层已经基本闭环了；以后对外优先发第 6 节这套固定四件套，再按场景补 `interview-brief` 或 `report-script` 作为辅助口播材料。"
            f"但对外口径必须同步保留 cleanup 侧已经做到 {_cleanup_backlog_status_phrase(snapshot)}、能力完成度高于工程完成度，以及 runtime baseline 已收口但完整 Docker smoke 仍待继续补齐这三个事实。"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-interview-pack.md",
        "> 这个项目已经把 **多知识库 scope isolation",
        lambda snapshot: (
            "> 这个项目已经把 **多知识库 scope isolation、evidence / preview 返回、layered eval 分层评测** 做成了主能力闭环，当前 semireal layered suite 是 `153 / 153`；"
            "但工程完成度仍低于能力完成度，剩余重点主要集中在 legacy 入口与历史文档收口、Docker runtime / eval 完整 smoke，"
            f"以及 cleanup 侧已经做到 {_cleanup_backlog_status_phrase(snapshot)} 之后的防回脏巡检，还有 `chat_service.py` 中剩余的 targeted-fact orchestration / hook builder 收口。"
        ),
    ),
    LineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-audit-evidence.md",
        "- root scratch 目录 backlog 的排序能力",
        lambda snapshot: (
            f"- root scratch 目录 backlog 的排序能力仍然有效，但截至最新 dry-run，{_cleanup_backlog_status_phrase(snapshot)}；"
            "这轮主要突破点已经转到 Docker 真实可执行收口与 cleanup 的长期防回脏机制。"
        ),
    ),
)

DEFAULT_DOC_NEXT_LINE_RULES = (

    NextLineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-audit.md",
        f"python -m pytest {CHAT_REGRESSION_ARGS} -q",
        lambda snapshot: f"# {_label_with_warnings(snapshot, 'chat_regression', CHAT_WARNING_COUNT)}",
    ),
    NextLineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-audit.md",
        f"python -m pytest {DOCS_CONTRACT_ARGS} -q",
        lambda snapshot: f"# {_pass_label(snapshot, 'docs_contract')}",
    ),
    NextLineSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-audit.md",
        'python -m pytest tests/ -q -m "not slow"',
        lambda snapshot: f"# {_label_with_warnings(snapshot, 'full_non_slow', FULL_NON_SLOW_WARNING_COUNT)}",
    ),
)

DEFAULT_DOC_FOLLOWING_LINES_RULES = (
    FollowingLinesSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-report-script.md",
        "3. **Prompt / heuristic ",
        _report_script_prompt_block,
        line_count=3,
    ),
    FollowingLinesSyncRule(
        AUDIT_DOCS_DIR / "20260821-project-audit-remediation-report-script.md",
        "### ",
        _report_script_validation_slide_lines,
        line_count=5,
        match_index=6,
    ),
    FollowingLinesSyncRule(
        CLOSURE_DOCS_DIR / "20260825-p0-p2-status-closure-status-report.md",
        CLOSURE_STATUS_COMMAND_LINES_TAG,
        _closure_status_command_lines,
        line_count=7,
    ),
    FollowingLinesSyncRule(
        CLOSURE_DOCS_DIR / "20260825-p0-p2-status-closure-interview-script.md",
        CLOSURE_INTERVIEW_VALIDATION_LINES_TAG,
        _closure_interview_validation_lines,
        line_count=7,
    ),
    FollowingLinesSyncRule(
        CLOSURE_DOCS_DIR / "20260825-p0-p2-status-closure-interview-script.md",
        CLOSURE_REPORT_VALIDATION_LINES_TAG,
        _closure_report_validation_lines,
        line_count=7,
    ),
)



def parse_pytest_collection_output(output: str) -> tuple[int, int]:
    """从 pytest --collect-only 输出中解析 selected / deselected 数量。"""
    deselected_match = re.search(r"(\d+)/(\d+) tests collected \((\d+) deselected\)", output)
    if deselected_match is not None:
        return int(deselected_match.group(1)), int(deselected_match.group(3))

    match = re.search(r"(\d+) tests collected", output)
    if match is None:
        raise ValueError(f"无法解析 pytest collect 输出: {output}")
    return int(match.group(1)), 0


def build_pytest_collect_command(pytest_args: str) -> list[str]:
    """把 pytest 参数字符串展开为 subprocess collect 命令。"""
    return ["python", "-m", "pytest", *shlex.split(pytest_args, posix=True), "--collect-only", "-q"]


def render_pytest_command(pytest_args: str) -> str:
    """保留原始参数字符串，渲染面向文档/快照展示的 pytest 命令。"""
    return f"python -m pytest {pytest_args} -q"


def collect_pytest_bundle(bundle: PytestBundle, *, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """执行一次 pytest collect，生成 bundle 计数快照。"""
    command = build_pytest_collect_command(bundle.pytest_args)
    completed = subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=True,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    selected_count, deselected_count = parse_pytest_collection_output(output)
    result_label = (
        f"{selected_count} passed, {deselected_count} deselected"
        if deselected_count
        else f"{selected_count} passed"
    )
    return {
        "label": bundle.label,
        "pytest_args": bundle.pytest_args,
        "command": render_pytest_command(bundle.pytest_args),
        "selected_count": selected_count,
        "deselected_count": deselected_count,
        "pass_label": f"{selected_count} passed",
        "result_label": result_label,
    }


def build_cleanup_command(*, include_directories: bool) -> list[str]:
    command = ["python", "scripts/cleanup_local_artifacts.py", "--dry-run"]
    if include_directories:
        command.append("--include-directories")
    return command


def render_cleanup_command(*, include_directories: bool) -> str:
    command = "python scripts/cleanup_local_artifacts.py --dry-run"
    return f"{command} --include-directories" if include_directories else command


def collect_cleanup_metric(
    key: str,
    label: str,
    include_directories: bool,
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    completed = subprocess.run(
        build_cleanup_command(include_directories=include_directories),
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=True,
    )
    payload = json.loads(completed.stdout)
    managed_count = int(payload.get("managed_count", 0))
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    return {
        "key": key,
        "label": label,
        "command": render_cleanup_command(include_directories=include_directories),
        "include_directories": include_directories,
        "managed_count": managed_count,
        "result_label": f"managed_count = {managed_count}",
        "summary": summary,
    }


def collect_node_command_metric(
    key: str,
    label: str,
    command: str,
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """执行 npm/node 默认测试入口，提取 pass 数量用于审计文档同步。"""
    completed = subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
        timeout=240,
        check=True,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    match = re.search(r"\bpass\s+(\d+)\b", output)
    if match is None:
        raise ValueError(f"无法解析 Node 测试通过数: {command}\n{output}")
    pass_count = int(match.group(1))
    return {
        "key": key,
        "label": label,
        "command": command,
        "pass_count": pass_count,
        "pass_label": f"{pass_count} passed",
        "result_label": f"{pass_count} passed",
    }


def build_audit_metrics_snapshot(
    *,
    repo_root: Path = REPO_ROOT,
    bundles: tuple[PytestBundle, ...] = DEFAULT_PYTEST_BUNDLES,
    node_commands: Sequence[tuple[str, str, str]] = DEFAULT_NODE_TEST_COMMANDS,
    cleanup_metrics: Sequence[tuple[str, str, bool]] = DEFAULT_CLEANUP_METRICS,
    node_metric_collector: Callable[[str, str, str], dict[str, Any]] | None = None,
    cleanup_metric_collector: Callable[[str, str, bool], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """生成默认审计 bundle、cleanup 与 Node 指标快照。"""
    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root.resolve()),
        "bundles": {},
        "cleanup": {},
        "node_commands": {},
    }
    for bundle in bundles:
        snapshot["bundles"][bundle.key] = collect_pytest_bundle(bundle, repo_root=repo_root)

    cleanup_collector = cleanup_metric_collector or (
        lambda key, label, include_directories: collect_cleanup_metric(
            key,
            label,
            include_directories,
            repo_root=repo_root,
        )
    )
    for key, label, include_directories in cleanup_metrics:
        snapshot["cleanup"][key] = cleanup_collector(key, label, include_directories)

    metric_collector = node_metric_collector or (
        lambda key, label, command: collect_node_command_metric(key, label, command, repo_root=repo_root)
    )
    for key, label, command in node_commands:
        snapshot["node_commands"][key] = metric_collector(key, label, command)
    return snapshot


def write_snapshot(snapshot: dict[str, Any], output_path: str | Path) -> Path:
    """把计数快照写入 JSON 文件。"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _detect_newline(content: str) -> str:
    return "\r\n" if "\r\n" in content else "\n"


def _normalize_anchor_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("`", "")).strip()


def _find_anchor_indexes(lines: Sequence[str], anchor: str) -> list[int]:
    raw_indexes = [index for index, line in enumerate(lines) if anchor in line]
    if raw_indexes:
        return raw_indexes

    normalized_anchor = _normalize_anchor_text(anchor)
    if not normalized_anchor:
        return []
    return [index for index, line in enumerate(lines) if normalized_anchor in _normalize_anchor_text(line)]


def _replace_line_with_anchor(
    content: str,
    anchor: str,
    new_line: str,
    *,
    replace_all: bool = False,
    match_index: int = 0,
) -> str:
    newline = _detect_newline(content)
    trailing_newline = content.endswith(("\n", "\r"))
    lines = content.splitlines()
    indexes = _find_anchor_indexes(lines, anchor)
    if not indexes:
        raise ValueError(f"未找到需要同步的锚点行: {anchor}")
    if replace_all:
        target_indexes = indexes
    else:
        if match_index < 0 or match_index >= len(indexes):
            raise ValueError(f"锚点命中 {len(indexes)} 行，但 match_index={match_index} 越界: {anchor}")
        target_indexes = [indexes[match_index]]

    for index in reversed(target_indexes):
        replacement_lines = new_line.splitlines() or [new_line]
        lines[index : index + 1] = replacement_lines

    rendered = newline.join(lines)
    return rendered + newline if trailing_newline else rendered


def _replace_next_line_after_anchor(content: str, anchor: str, new_line: str, *, match_index: int = 0) -> str:
    newline = _detect_newline(content)
    trailing_newline = content.endswith(("\n", "\r"))
    lines = content.splitlines()
    indexes = _find_anchor_indexes(lines, anchor)
    if not indexes:
        raise ValueError(f"未找到需要同步的命令锚点: {anchor}")
    if match_index < 0 or match_index >= len(indexes):
        raise ValueError(f"命令锚点命中 {len(indexes)} 行，但 match_index={match_index} 越界: {anchor}")

    index = indexes[match_index]
    if index + 1 >= len(lines):
        raise ValueError(f"命令锚点后缺少结果行: {anchor}")
    lines[index + 1] = new_line
    rendered = newline.join(lines)
    return rendered + newline if trailing_newline else rendered


def _replace_following_lines_after_anchor(
    content: str,
    anchor: str,
    new_lines: Sequence[str],
    *,
    line_count: int,
    match_index: int = 0,
) -> str:
    newline = _detect_newline(content)
    trailing_newline = content.endswith(("\n", "\r"))
    lines = content.splitlines()
    indexes = _find_anchor_indexes(lines, anchor)
    if not indexes:
        raise ValueError(f"未找到需要同步的区块锚点: {anchor}")
    if match_index < 0 or match_index >= len(indexes):
        raise ValueError(f"区块锚点命中 {len(indexes)} 行，但 match_index={match_index} 越界: {anchor}")

    index = indexes[match_index]
    end_index = index + 1 + line_count
    if end_index > len(lines):
        raise ValueError(f"区块锚点后的行数不足: {anchor}")
    lines[index + 1 : end_index] = list(new_lines)
    rendered = newline.join(lines)
    return rendered + newline if trailing_newline else rendered


def sync_audit_metric_docs(
    snapshot: dict[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
    line_rules: Sequence[LineSyncRule] = DEFAULT_DOC_LINE_RULES,
    next_line_rules: Sequence[NextLineSyncRule] = DEFAULT_DOC_NEXT_LINE_RULES,
    following_lines_rules: Sequence[FollowingLinesSyncRule] = DEFAULT_DOC_FOLLOWING_LINES_RULES,
) -> list[Path]:
    """根据最新 snapshot 同步 project/audit 文档中的计数口径。"""
    grouped_line_rules: dict[Path, list[LineSyncRule]] = defaultdict(list)
    grouped_next_line_rules: dict[Path, list[NextLineSyncRule]] = defaultdict(list)
    grouped_following_lines_rules: dict[Path, list[FollowingLinesSyncRule]] = defaultdict(list)
    for rule in line_rules:
        grouped_line_rules[Path(rule.relative_path)].append(rule)
    for rule in next_line_rules:
        grouped_next_line_rules[Path(rule.relative_path)].append(rule)
    for rule in following_lines_rules:
        grouped_following_lines_rules[Path(rule.relative_path)].append(rule)

    updated_paths: list[Path] = []
    relative_paths = sorted(
        {
            *grouped_line_rules.keys(),
            *grouped_next_line_rules.keys(),
            *grouped_following_lines_rules.keys(),
        },
        key=lambda path: path.as_posix(),
    )

    for relative_path in relative_paths:
        path = repo_root / relative_path
        original = path.read_text(encoding="utf-8")
        updated = original

        for rule in grouped_line_rules.get(relative_path, []):
            updated = _replace_line_with_anchor(updated, rule.anchor, rule.build_line(snapshot), replace_all=rule.replace_all, match_index=rule.match_index)
        for rule in grouped_next_line_rules.get(relative_path, []):
            updated = _replace_next_line_after_anchor(updated, rule.anchor, rule.build_next_line(snapshot), match_index=rule.match_index)
        for rule in grouped_following_lines_rules.get(relative_path, []):
            updated = _replace_following_lines_after_anchor(
                updated,
                rule.anchor,
                rule.build_lines(snapshot),
                line_count=rule.line_count,
                match_index=rule.match_index,
            )

        if updated != original:
            path.write_text(updated, encoding="utf-8")
            updated_paths.append(path)

    return updated_paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 audit remediation 文档使用的 pytest 计数快照")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"输出 JSON 路径（默认：{DEFAULT_OUTPUT_PATH.relative_to(REPO_ROOT).as_posix()}）",
    )
    parser.add_argument(
        "--bundle",
        action="append",
        default=None,
        help="只刷新指定 pytest bundle key；可重复传入多次，未指定时默认收集全部 bundle",
    )
    parser.add_argument(
        "--skip-node",
        action="store_true",
        help="跳过 Node 指标收集，便于快速刷新 pytest bundle",
    )
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="跳过 cleanup dry-run 指标，便于快速刷新 pytest bundle",
    )
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="将生成的快照 JSON 直接打印到标准输出",
    )
    parser.add_argument(
        "--sync-docs",
        action="store_true",
        help="把快照中的 bundle 计数同步回 docs/project.md 与 20260821 审计材料",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    bundles = resolve_pytest_bundles(args.bundle)
    snapshot = build_audit_metrics_snapshot(
        bundles=bundles,
        node_commands=() if args.skip_node else DEFAULT_NODE_TEST_COMMANDS,
        cleanup_metrics=() if args.skip_cleanup else DEFAULT_CLEANUP_METRICS,
    )

    partial_refresh = bool(args.bundle or args.skip_node or args.skip_cleanup)
    if partial_refresh:
        snapshot = merge_snapshot_sections(load_existing_snapshot(args.output), snapshot)

    if args.sync_docs:
        validate_snapshot_for_doc_sync(snapshot)

    output_path = write_snapshot(snapshot, args.output)
    updated_paths = sync_audit_metric_docs(snapshot) if args.sync_docs else []

    if args.print_json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    else:
        print(f"audit metrics snapshot 已生成: {output_path}")
        if updated_paths:
            print("已同步文档:")
            for path in updated_paths:
                print(f"- {path.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


