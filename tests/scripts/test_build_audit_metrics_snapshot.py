from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.build_audit_metrics_snapshot import (
    CLOSURE_INTERVIEW_VALIDATION_LINES_TAG,
    CLOSURE_REPORT_VALIDATION_LINES_TAG,
    CLOSURE_STATUS_COMMAND_LINES_TAG,
    DEFAULT_CLEANUP_METRICS,
    DEFAULT_DOC_FOLLOWING_LINES_RULES,
    DEFAULT_DOC_LINE_RULES,
    DEFAULT_PYTEST_BUNDLES,
    FollowingLinesSyncRule,
    LineSyncRule,
    NextLineSyncRule,
    PytestBundle,
    build_audit_metrics_snapshot,
    build_cleanup_command,
    build_parser,
    build_pytest_collect_command,
    collect_cleanup_metric,
    collect_pytest_bundle,
    load_existing_snapshot,
    merge_snapshot_sections,
    parse_pytest_collection_output,
    render_cleanup_command,
    render_pytest_command,
    resolve_pytest_bundles,
    sync_audit_metric_docs,
    validate_snapshot_for_doc_sync,
    write_snapshot,
)


def _sample_snapshot() -> dict[str, object]:
    return {
        "bundles": {
            "chat_regression": {
                "pass_label": "201 passed",
                "result_label": "201 passed",
            },
            "docs_contract": {
                "pass_label": "71 passed",
                "result_label": "71 passed",
            },
            "startup_desktop_smoke": {
                "pass_label": "17 passed",
                "result_label": "17 passed",
            },
            "docker_helper": {
                "pass_label": "19 passed",
                "result_label": "19 passed",
            },
            "docker_bundle": {
                "pass_label": "93 passed",
                "result_label": "93 passed",
            },
            "prompt_bundle_1": {
                "pass_label": "86 passed",
                "result_label": "86 passed",
            },
            "prompt_bundle_2": {
                "pass_label": "29 passed",
                "result_label": "29 passed",
            },
            "prompt_bundle_3": {
                "pass_label": "31 passed",
                "result_label": "31 passed",
            },
            "full_non_slow": {
                "pass_label": "1300 passed",
                "result_label": "1300 passed, 8 deselected",
            },
            "closure_docs_sync": {
                "pass_label": "47 passed",
                "result_label": "47 passed",
            },
            "closure_docker_startup": {
                "pass_label": "41 passed",
                "result_label": "41 passed",
            },
            "closure_repo_hygiene": {
                "pass_label": "18 passed",
                "result_label": "18 passed",
            },
            "closure_query_request": {
                "pass_label": "2 passed",
                "result_label": "2 passed, 32 deselected",
            },
            "closure_eval_contract": {
                "pass_label": "35 passed",
                "result_label": "35 passed",
            },
            "closure_chat_mainline": {
                "pass_label": "107 passed",
                "result_label": "107 passed",
            },
        },
        "cleanup": {
            "file_mode": {
                "managed_count": 0,
                "result_label": "managed_count = 0",
            },
            "directory_mode": {
                "managed_count": 0,
                "result_label": "managed_count = 0",
            },
        },
    }


def test_parse_pytest_collection_output_supports_plain_and_deselected_cases() -> None:
    assert parse_pytest_collection_output("12 tests collected") == (12, 0)
    assert parse_pytest_collection_output("9/11 tests collected (2 deselected)") == (9, 2)



def test_build_pytest_collect_command_preserves_marker_argument() -> None:
    command = build_pytest_collect_command('tests/ -m "not slow"')

    assert command == ["python", "-m", "pytest", "tests/", "-m", "not slow", "--collect-only", "-q"]



def test_render_pytest_command_preserves_original_cli_text() -> None:
    command = render_pytest_command('tests/ -m "not slow"')

    assert command == 'python -m pytest tests/ -m "not slow" -q'



def test_collect_pytest_bundle_returns_labels(monkeypatch, tmp_path: Path) -> None:
    bundle = PytestBundle(key="sample", label="示例 bundle", pytest_args="tests/api/test_chat_service.py")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=kwargs.get("args") or args[0],
            returncode=0,
            stdout="14 tests collected\n",
            stderr="",
        )

    monkeypatch.setattr("scripts.build_audit_metrics_snapshot.subprocess.run", fake_run)

    result = collect_pytest_bundle(bundle, repo_root=tmp_path)

    assert result == {
        "label": "示例 bundle",
        "pytest_args": "tests/api/test_chat_service.py",
        "command": "python -m pytest tests/api/test_chat_service.py -q",
        "selected_count": 14,
        "deselected_count": 0,
        "pass_label": "14 passed",
        "result_label": "14 passed",
    }



def test_build_cleanup_command_and_render_cleanup_command_cover_directory_mode() -> None:
    assert build_cleanup_command(include_directories=False) == [
        "python",
        "scripts/cleanup_local_artifacts.py",
        "--dry-run",
    ]
    assert build_cleanup_command(include_directories=True) == [
        "python",
        "scripts/cleanup_local_artifacts.py",
        "--dry-run",
        "--include-directories",
    ]
    assert render_cleanup_command(include_directories=False) == "python scripts/cleanup_local_artifacts.py --dry-run"
    assert render_cleanup_command(include_directories=True) == (
        "python scripts/cleanup_local_artifacts.py --dry-run --include-directories"
    )



def test_collect_cleanup_metric_returns_managed_count_and_summary(monkeypatch, tmp_path: Path) -> None:
    def fake_run(*args, **kwargs):
        payload = {
            "managed_count": 3,
            "summary": {
                "total_size_bytes": 42,
                "largest_records": [{"name": "tmp_eval_out"}],
            },
        }
        return subprocess.CompletedProcess(
            args=kwargs.get("args") or args[0],
            returncode=0,
            stdout=json.dumps(payload, ensure_ascii=False),
            stderr="",
        )

    monkeypatch.setattr("scripts.build_audit_metrics_snapshot.subprocess.run", fake_run)

    result = collect_cleanup_metric("directory_mode", "根目录 directory-mode dry-run", True, repo_root=tmp_path)

    assert result == {
        "key": "directory_mode",
        "label": "根目录 directory-mode dry-run",
        "command": "python scripts/cleanup_local_artifacts.py --dry-run --include-directories",
        "include_directories": True,
        "managed_count": 3,
        "result_label": "managed_count = 3",
        "summary": {
            "total_size_bytes": 42,
            "largest_records": [{"name": "tmp_eval_out"}],
        },
    }



def test_build_audit_metrics_snapshot_collects_cleanup_metrics(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "scripts.build_audit_metrics_snapshot.collect_pytest_bundle",
        lambda bundle, *, repo_root: {"pass_label": f"{bundle.key} passed", "result_label": f"{bundle.key} passed"},
    )

    calls: list[tuple[str, str, bool]] = []

    def fake_cleanup_metric_collector(key: str, label: str, include_directories: bool) -> dict[str, object]:
        calls.append((key, label, include_directories))
        return {
            "key": key,
            "label": label,
            "command": render_cleanup_command(include_directories=include_directories),
            "include_directories": include_directories,
            "managed_count": 0 if not include_directories else 2,
            "result_label": "managed_count = 0" if not include_directories else "managed_count = 2",
            "summary": {},
        }

    snapshot = build_audit_metrics_snapshot(
        repo_root=tmp_path,
        node_commands=(),
        cleanup_metric_collector=fake_cleanup_metric_collector,
    )

    assert calls == list(DEFAULT_CLEANUP_METRICS)
    assert snapshot["cleanup"]["file_mode"]["managed_count"] == 0
    assert snapshot["cleanup"]["directory_mode"]["managed_count"] == 2
    assert snapshot["cleanup"]["directory_mode"]["command"].endswith("--include-directories")


def test_build_audit_metrics_snapshot_aggregates_all_default_bundles(monkeypatch, tmp_path: Path) -> None:
    def fake_collect(bundle, *, repo_root):
        return {
            "label": bundle.label,
            "pytest_args": bundle.pytest_args,
            "command": f"python -m pytest {bundle.pytest_args} -q",
            "selected_count": len(bundle.key),
            "deselected_count": 0,
            "pass_label": f"{len(bundle.key)} passed",
            "result_label": f"{len(bundle.key)} passed",
        }

    monkeypatch.setattr("scripts.build_audit_metrics_snapshot.collect_pytest_bundle", fake_collect)

    snapshot = build_audit_metrics_snapshot(repo_root=tmp_path, node_commands=(), cleanup_metrics=())

    assert snapshot["repo_root"] == str(tmp_path.resolve())
    assert set(snapshot["bundles"]) == {bundle.key for bundle in DEFAULT_PYTEST_BUNDLES}
    assert snapshot["node_commands"] == {}
    assert snapshot["bundles"]["chat_regression"]["pass_label"] == f"{len('chat_regression')} passed"
    assert snapshot["bundles"]["full_non_slow"]["command"] == 'python -m pytest tests/ -m "not slow" -q'



def test_build_audit_metrics_snapshot_collects_node_command_metrics(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "scripts.build_audit_metrics_snapshot.collect_pytest_bundle",
        lambda bundle, *, repo_root: {"pass_label": f"{bundle.key} passed", "result_label": f"{bundle.key} passed"},
    )

    calls: list[tuple[str, str, str]] = []

    def fake_node_metric_collector(key: str, label: str, command: str) -> dict[str, object]:
        calls.append((key, label, command))
        return {
            "key": key,
            "label": label,
            "command": command,
            "pass_count": len(key),
            "pass_label": f"{len(key)} passed",
            "result_label": f"{len(key)} passed",
        }

    snapshot = build_audit_metrics_snapshot(
        repo_root=tmp_path,
        bundles=(),
        node_commands=(("desktop_full_node", "Desktop 全量 Node 单测", "npm --prefix desktop test"),),
        node_metric_collector=fake_node_metric_collector,
        cleanup_metrics=(),
    )

    assert calls == [("desktop_full_node", "Desktop 全量 Node 单测", "npm --prefix desktop test")]
    assert snapshot["bundles"] == {}
    assert snapshot["node_commands"]["desktop_full_node"]["pass_label"] == f"{len('desktop_full_node')} passed"



def test_write_snapshot_creates_parent_directory(tmp_path: Path) -> None:
    snapshot = {"bundles": {"sample": {"pass_label": "3 passed"}}}
    output_path = tmp_path / "nested" / "audit-metrics-snapshot.json"

    written = write_snapshot(snapshot, output_path)

    assert written == output_path
    assert json.loads(output_path.read_text(encoding="utf-8")) == snapshot



def test_load_existing_snapshot_returns_none_when_missing(tmp_path: Path) -> None:
    assert load_existing_snapshot(tmp_path / "missing.json") is None



def test_merge_snapshot_sections_preserves_uncollected_sections() -> None:
    base_snapshot = {
        "generated_at": "old-ts",
        "repo_root": "old-root",
        "bundles": {
            "chat_regression": {"pass_label": "108 passed"},
            "docs_contract": {"pass_label": "81 passed"},
        },
        "cleanup": {"file_mode": {"result_label": "managed_count = 0"}},
        "node_commands": {"desktop_full_node": {"pass_label": "136 passed"}},
    }
    updates = {
        "generated_at": "new-ts",
        "repo_root": "new-root",
        "bundles": {"chat_regression": {"pass_label": "112 passed"}},
        "cleanup": {},
        "node_commands": {},
    }

    merged = merge_snapshot_sections(base_snapshot, updates)

    assert merged["generated_at"] == "new-ts"
    assert merged["repo_root"] == "new-root"
    assert merged["bundles"]["chat_regression"]["pass_label"] == "112 passed"
    assert merged["bundles"]["docs_contract"]["pass_label"] == "81 passed"
    assert merged["cleanup"]["file_mode"]["result_label"] == "managed_count = 0"
    assert merged["node_commands"]["desktop_full_node"]["pass_label"] == "136 passed"



def test_resolve_pytest_bundles_supports_subset_and_dedupes() -> None:
    bundles = resolve_pytest_bundles(["docs_contract", "chat_regression", "docs_contract"])

    assert [bundle.key for bundle in bundles] == ["docs_contract", "chat_regression"]



def test_resolve_pytest_bundles_rejects_unknown_key() -> None:
    try:
        resolve_pytest_bundles(["unknown_bundle"])
    except ValueError as exc:
        message = str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ValueError")

    assert "unknown_bundle" in message
    assert "chat_regression" in message



def test_validate_snapshot_for_doc_sync_requires_full_sections() -> None:
    snapshot = {
        "bundles": {"chat_regression": {"pass_label": "112 passed"}},
        "cleanup": {},
        "node_commands": {},
    }

    try:
        validate_snapshot_for_doc_sync(snapshot)
    except ValueError as exc:
        message = str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ValueError")

    assert "bundles.docs_contract" in message
    assert "cleanup.file_mode" in message
    assert "node_commands.desktop_full_node" in message



def test_sync_audit_metric_docs_matches_markdown_code_span_variants_in_anchor(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)

    closure_path = docs_dir / "closure.md"
    closure_path.write_text(
        "| 1 | basic 模式和后端 `single_kb` 约束冲突 | stale |\n",
        encoding="utf-8",
    )

    snapshot = _sample_snapshot()
    updated_paths = sync_audit_metric_docs(
        snapshot,
        repo_root=tmp_path,
        line_rules=(
            LineSyncRule(
                Path("docs/closure.md"),
                "| 1 | basic 模式和后端 single_kb 约束冲突 |",
                lambda current_snapshot: (
                    "| 1 | basic 模式和后端 `single_kb` 约束冲突 | 当前为 "
                    f"`{current_snapshot['bundles']['closure_chat_mainline']['pass_label']}` |"
                ),
            ),
        ),
        next_line_rules=(),
        following_lines_rules=(),
    )

    assert {path.relative_to(tmp_path).as_posix() for path in updated_paths} == {"docs/closure.md"}
    assert "`107 passed`" in closure_path.read_text(encoding="utf-8")


def test_sync_audit_metric_docs_supports_match_index_for_repeated_anchors(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)

    repeated_path = docs_dir / "repeated.md"
    repeated_path.write_text(
        "- anchor: old-first\n"
        "- anchor: old-second\n",
        encoding="utf-8",
    )

    snapshot = _sample_snapshot()
    updated_paths = sync_audit_metric_docs(
        snapshot,
        repo_root=tmp_path,
        line_rules=(
            LineSyncRule(
                Path("docs/repeated.md"),
                "- anchor:",
                lambda current_snapshot: f"- anchor: {current_snapshot['bundles']['docker_helper']['pass_label']}",
                match_index=1,
            ),
        ),
        next_line_rules=(),
        following_lines_rules=(),
    )

    assert {path.relative_to(tmp_path).as_posix() for path in updated_paths} == {"docs/repeated.md"}
    assert repeated_path.read_text(encoding="utf-8").splitlines() == [
        "- anchor: old-first",
        "- anchor: 19 passed",
    ]


def test_sync_audit_metric_docs_updates_line_next_line_and_block_rules(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    audit_dir = docs_dir / "20260821-project-audit-remediation"
    audit_dir.mkdir(parents=True)

    project_path = docs_dir / "project.md"
    project_path.write_text(
        "# project\n"
        "- 当前可信评测基线以 `docs/20260821-project-audit-remediation/` 下当前材料与 2026-08-24 复跑结果为准：旧值\n",
        encoding="utf-8",
    )
    audit_path = audit_dir / "audit.md"
    audit_path.write_text(
        "python -m pytest tests/scripts/test_docker_smoke.py -q\n"
        "# 18 passed\n",
        encoding="utf-8",
    )
    report_script_path = audit_dir / "report-script.md"
    report_script_path.write_text(
        "3. **Prompt / heuristic 增量回归**\n"
        "   - `85 passed`\n"
        "   - `28 passed`\n"
        "   - `30 passed`\n",
        encoding="utf-8",
    )

    snapshot = _sample_snapshot()
    updated_paths = sync_audit_metric_docs(
        snapshot,
        repo_root=tmp_path,
        line_rules=(
            LineSyncRule(
                Path("docs/project.md"),
                "- 当前可信评测基线以 `docs/20260821-project-audit-remediation/`",
                lambda current_snapshot: (
                    "- 当前可信评测基线以 `docs/20260821-project-audit-remediation/` 下当前材料与 2026-08-24 复跑结果为准："
                    f"chat `{current_snapshot['bundles']['chat_regression']['pass_label']}`；"
                    f"full `{current_snapshot['bundles']['full_non_slow']['result_label']}`。"
                ),
            ),
        ),
        next_line_rules=(
            NextLineSyncRule(
                Path("docs/20260821-project-audit-remediation/audit.md"),
                "python -m pytest tests/scripts/test_docker_smoke.py -q",
                lambda current_snapshot: f"# {current_snapshot['bundles']['docker_helper']['pass_label']}",
            ),
        ),
        following_lines_rules=(
            FollowingLinesSyncRule(
                Path("docs/20260821-project-audit-remediation/report-script.md"),
                "3. **Prompt / heuristic 增量回归**",
                lambda current_snapshot: (
                    f"   - `{current_snapshot['bundles']['prompt_bundle_1']['pass_label']}`",
                    f"   - `{current_snapshot['bundles']['prompt_bundle_2']['pass_label']}`",
                    f"   - `{current_snapshot['bundles']['prompt_bundle_3']['result_label']}`",
                ),
                line_count=3,
            ),
        ),
    )

    assert {path.relative_to(tmp_path).as_posix() for path in updated_paths} == {
        "docs/project.md",
        "docs/20260821-project-audit-remediation/audit.md",
        "docs/20260821-project-audit-remediation/report-script.md",
    }
    assert "chat `201 passed`；full `1300 passed, 8 deselected`。" in project_path.read_text(encoding="utf-8")
    assert "# 19 passed" in audit_path.read_text(encoding="utf-8")
    assert report_script_path.read_text(encoding="utf-8").splitlines()[1:] == [
        "   - `86 passed`",
        "   - `29 passed`",
        "   - `31 passed`",
    ]



def test_sync_audit_metric_docs_updates_status_matrix_prompt_bundle_lines(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs" / "20260821-project-audit-remediation"
    docs_dir.mkdir(parents=True)

    status_matrix_path = docs_dir / "20260821-project-audit-remediation-status-matrix.md"
    status_matrix_path.write_text(
        "# status matrix\n"
        "| 7 | Prompt 契约偏弱，后处理 heuristic 太重 | stale `85 passed` |\n"
        "- `python -m pytest tests/api/test_chat_composite_answers.py tests/api/test_chat_postprocessors.py tests/api/test_chat_service.py -q` → `stale`\n"
        "- `python -m pytest tests/api/test_chat_question_intents.py tests/api/test_chat_targeted_fact.py tests/api/test_chat_source_answers.py tests/api/test_chat_answer_repair.py -q` → `stale`\n"
        "- `python -m pytest tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py -q` → `stale first`\n"
        "- `python -m pytest tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py -q` → `stale second`\n",
        encoding="utf-8",
    )

    prompt_status_rules = tuple(
        rule
        for rule in DEFAULT_DOC_LINE_RULES
        if rule.relative_path.as_posix() == "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-status-matrix.md"
        and (
            "| 7 | Prompt 契约偏弱" in rule.anchor
            or "tests/api/test_chat_composite_answers.py" in rule.anchor
            or "tests/api/test_chat_question_intents.py" in rule.anchor
            or "tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py" in rule.anchor
        )
    )

    updated_paths = sync_audit_metric_docs(
        _sample_snapshot(),
        repo_root=tmp_path,
        line_rules=prompt_status_rules,
        next_line_rules=(),
        following_lines_rules=(),
    )

    assert {path.relative_to(tmp_path).as_posix() for path in updated_paths} == {
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-status-matrix.md"
    }
    status_text = status_matrix_path.read_text(encoding="utf-8")
    assert "当前为 `86 passed`" in status_text
    assert "`86 passed`" in status_text
    assert "`29 passed`" in status_text
    assert status_text.count("`31 passed`") == 2



def test_sync_audit_metric_docs_updates_20260825_closure_docs(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs" / "20260825-p0-p2-status-closure"
    docs_dir.mkdir(parents=True)

    status_report_path = docs_dir / "20260825-p0-p2-status-closure-status-report.md"
    status_report_path.write_text(
        "# status report\n"
        "### 2.1 本轮实际执行的命令\n"
        f"{CLOSURE_STATUS_COMMAND_LINES_TAG}\n"
        "- stale 1\n"
        "- stale 2\n"
        "- stale 3\n"
        "- stale 4\n"
        "- stale 5\n"
        "- stale 6\n"
        "- stale 7\n"
        "| 1 | basic 模式和后端 single_kb 约束冲突 | stale |\n"
        "| 3 | 项目主入口不统一 | stale |\n"
        "| 6 | 评测 harness 对 refusal / negative contract 覆盖不足 | stale |\n"
        "| 8 | Docker / requirements / 端口 / 启动脚本存在配置漂移 | stale |\n"
        "| 9 | 仓库根目录临时文件、日志、调试脚本较多 | stale |\n"
        "| 11 | 日志与临时产物治理需要规范化 | stale |\n",
        encoding="utf-8",
    )
    interview_script_path = docs_dir / "20260825-p0-p2-status-closure-interview-script.md"
    interview_script_path.write_text(
        "# interview script\n"
        "这些不是口头约定，我用测试和评测去证明：\n"
        f"{CLOSURE_INTERVIEW_VALIDATION_LINES_TAG}\n"
        "- stale 1\n"
        "- stale 2\n"
        "- stale 3\n"
        "- stale 4\n"
        "- stale 5\n"
        "- stale 6\n"
        "- stale 7\n"
        "当前这轮核查里：\n"
        f"{CLOSURE_REPORT_VALIDATION_LINES_TAG}\n"
        "- stale a\n"
        "- stale b\n"
        "- stale c\n"
        "- stale d\n"
        "- stale e\n"
        "- stale f\n"
        "- stale g\n",
        encoding="utf-8",
    )

    closure_line_rules = tuple(
        rule for rule in DEFAULT_DOC_LINE_RULES if "20260825-p0-p2-status-closure" in rule.relative_path.as_posix()
    )
    closure_following_rules = tuple(
        rule for rule in DEFAULT_DOC_FOLLOWING_LINES_RULES if "20260825-p0-p2-status-closure" in rule.relative_path.as_posix()
    )

    updated_paths = sync_audit_metric_docs(
        _sample_snapshot(),
        repo_root=tmp_path,
        line_rules=closure_line_rules,
        next_line_rules=(),
        following_lines_rules=closure_following_rules,
    )

    assert {path.relative_to(tmp_path).as_posix() for path in updated_paths} == {
        "docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-status-report.md",
        "docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md",
    }

    status_text = status_report_path.read_text(encoding="utf-8")
    assert "`python -m pytest tests/scripts/test_dev_startup_contracts.py tests/scripts/test_docs_entry_contracts.py tests/test_legacy_streamlit_entry.py tests/scripts/test_build_audit_metrics_snapshot.py -q` → `47 passed`" in status_text
    assert "`python -m pytest tests/api/test_runtime_model_loading.py -k \"request or overrides_config_store_defaults\" -q` → `2 passed, 32 deselected`" in status_text
    assert "`python -m pytest tests/api/test_chat_scope_contract.py tests/api/test_open_api_service.py tests/api/test_open_api_integration.py tests/api/test_chat_service.py tests/api/test_chat_routes.py -q` → `107 passed`" in status_text
    assert status_text.count("- `node --test webapp/src/domain/agentExperience.test.js webapp/src/domain/chatWorkflow.test.js` → `21 pass`") == 1
    assert "`21 pass` + `107 passed`" in status_text
    assert "本轮文档与 sync 脚本校验共 `47 passed`" in status_text
    assert "当前 `35 passed`；说明 refusal / contract gate 已进入正式套件" in status_text
    assert "当前 `41 passed`；`scripts/docker_smoke.py` 已走 Docker host port 回查口径" in status_text
    assert "本轮 `18 passed`" in status_text
    assert "；`18 passed` 说明最基础的规则正在生效" in status_text

    interview_text = interview_script_path.read_text(encoding="utf-8")
    assert "- scope / open api / chat 主链路相关测试：`107 passed`" in interview_text
    assert "- QueryRequest 覆盖 runtime override：`2 passed, 32 deselected`" in interview_text
    assert "- refusal / eval contract / dataset v8：`35 passed`" in interview_text
    assert "- 启动 / 文档入口 / legacy / audit sync：`47 passed`" in interview_text
    assert "- Docker / requirements / startup contracts：`41 passed`" in interview_text
    assert "- cleanup / repo hygiene：`18 passed`" in interview_text
    assert interview_text.count("- 前端 `agentExperience + chatWorkflow`：`21 pass`") == 1
    assert "- scope / open api / chat 主链路相关测试是 `107 passed`" in interview_text
    assert "- QueryRequest runtime override 是 `2 passed, 32 deselected`" in interview_text
    assert "- refusal / negative contract / dataset v8 是 `35 passed`" in interview_text
    assert "- 启动 / 文档 / legacy / audit sync 是 `47 passed`" in interview_text
    assert "- Docker / requirements / startup contracts 是 `41 passed`" in interview_text
    assert "- cleanup / repo hygiene 是 `18 passed`" in interview_text
    assert interview_text.count("- 前端状态与 experience 契约是 `21 pass`") == 1


def test_sync_audit_metric_docs_uses_closure_machine_tags_for_following_blocks(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs" / "20260825-p0-p2-status-closure"
    docs_dir.mkdir(parents=True)

    status_report_path = docs_dir / "20260825-p0-p2-status-closure-status-report.md"
    status_report_path.write_text(
        "# status report\n"
        "### renamed heading\n"
        f"{CLOSURE_STATUS_COMMAND_LINES_TAG}\n"
        "- stale 1\n"
        "- stale 2\n"
        "- stale 3\n"
        "- stale 4\n"
        "- stale 5\n"
        "- stale 6\n"
        "- stale 7\n",
        encoding="utf-8",
    )
    interview_script_path = docs_dir / "20260825-p0-p2-status-closure-interview-script.md"
    interview_script_path.write_text(
        "# interview script\n"
        "validation title changed\n"
        f"{CLOSURE_INTERVIEW_VALIDATION_LINES_TAG}\n"
        "- stale 1\n"
        "- stale 2\n"
        "- stale 3\n"
        "- stale 4\n"
        "- stale 5\n"
        "- stale 6\n"
        "- stale 7\n"
        "report title changed\n"
        f"{CLOSURE_REPORT_VALIDATION_LINES_TAG}\n"
        "- stale a\n"
        "- stale b\n"
        "- stale c\n"
        "- stale d\n"
        "- stale e\n"
        "- stale f\n"
        "- stale g\n",
        encoding="utf-8",
    )

    closure_following_rules = tuple(
        rule for rule in DEFAULT_DOC_FOLLOWING_LINES_RULES if "20260825-p0-p2-status-closure" in rule.relative_path.as_posix()
    )

    updated_paths = sync_audit_metric_docs(
        _sample_snapshot(),
        repo_root=tmp_path,
        line_rules=(),
        next_line_rules=(),
        following_lines_rules=closure_following_rules,
    )

    assert {path.relative_to(tmp_path).as_posix() for path in updated_paths} == {
        "docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-status-report.md",
        "docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md",
    }
    status_text = status_report_path.read_text(encoding="utf-8")
    assert CLOSURE_STATUS_COMMAND_LINES_TAG in status_text
    assert "`python -m pytest tests/scripts/test_dev_startup_contracts.py tests/scripts/test_docs_entry_contracts.py tests/test_legacy_streamlit_entry.py tests/scripts/test_build_audit_metrics_snapshot.py -q` → `47 passed`" in status_text
    interview_text = interview_script_path.read_text(encoding="utf-8")
    assert CLOSURE_INTERVIEW_VALIDATION_LINES_TAG in interview_text
    assert CLOSURE_REPORT_VALIDATION_LINES_TAG in interview_text
    assert "- scope / open api / chat 主链路相关测试：`107 passed`" in interview_text
    assert "- scope / open api / chat 主链路相关测试是 `107 passed`" in interview_text



def test_build_parser_supports_partial_refresh_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(["--bundle", "chat_regression", "--bundle", "docs_contract", "--skip-node", "--skip-cleanup", "--sync-docs"])

    assert args.output.name == "audit-metrics-snapshot.json"
    assert args.bundle == ["chat_regression", "docs_contract"]
    assert args.skip_node is True
    assert args.skip_cleanup is True
    assert args.print_json is False
    assert args.sync_docs is True




def test_sync_audit_metric_docs_updates_interview_pack_audit_evidence_and_spec(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs" / "20260821-project-audit-remediation"
    docs_dir.mkdir(parents=True)

    interview_pack_path = docs_dir / "20260821-project-audit-remediation-interview-pack.md"
    interview_pack_path.write_text(
        "# interview pack\n"
        "- Chat 关键回归：`old chat`\n"
        "- 全量非慢测：`old full`\n"
        "我这轮主要做了三件事。第一，把主能力做成闭环：stale paragraph\n"
        "- `python -m pytest tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py -q` → `old prompt3`\n",
        encoding="utf-8",
    )
    audit_evidence_path = docs_dir / "20260821-project-audit-remediation-audit-evidence.md"
    audit_evidence_path.write_text(
        "# audit evidence\n"
        "- `python -m pytest tests/api/test_chat_composite_answers.py tests/api/test_chat_postprocessors.py tests/api/test_chat_service.py -q` → `old prompt1`\n"
        "- `python -m pytest tests/api/test_chat_question_intents.py tests/api/test_chat_targeted_fact.py tests/api/test_chat_source_answers.py tests/api/test_chat_answer_repair.py -q` → `old prompt2`\n"
        "- `python -m pytest tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py -q` → `old prompt3 first`\n"
        "- `python -m pytest tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py -q` → `old prompt3 second`\n",
        encoding="utf-8",
    )
    spec_path = docs_dir / "20260821-project-audit-remediation-spec.md"
    spec_path.write_text(
        "# spec\n"
        "- `python -m pytest tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py -q` → `old spec prompt3`\n",
        encoding="utf-8",
    )

    selected_rules = tuple(
        rule
        for rule in DEFAULT_DOC_LINE_RULES
        if (
            rule.relative_path.as_posix() == "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-interview-pack.md"
            and (
                rule.anchor == "- Chat 关键回归："
                or rule.anchor == "- 全量非慢测："
                or "我这轮主要做了三件事。第一，把主能力做成闭环：" in rule.anchor
                or "tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py" in rule.anchor
            )
        )
        or (
            rule.relative_path.as_posix() == "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-audit-evidence.md"
            and (
                "tests/api/test_chat_composite_answers.py" in rule.anchor
                or "tests/api/test_chat_question_intents.py" in rule.anchor
                or "tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py" in rule.anchor
            )
        )
        or (
            rule.relative_path.as_posix() == "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-spec.md"
            and "tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py" in rule.anchor
        )
    )

    updated_paths = sync_audit_metric_docs(
        _sample_snapshot(),
        repo_root=tmp_path,
        line_rules=selected_rules,
        next_line_rules=(),
        following_lines_rules=(),
    )

    assert {path.relative_to(tmp_path).as_posix() for path in updated_paths} == {
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-interview-pack.md",
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-audit-evidence.md",
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-spec.md",
    }

    interview_pack_text = interview_pack_path.read_text(encoding="utf-8")
    assert "`201 passed`" in interview_pack_text
    assert "`1300 passed, 8 deselected`" in interview_pack_text
    assert interview_pack_text.count("`201 passed`") >= 2
    assert interview_pack_text.count("`1300 passed, 8 deselected`") >= 2
    assert "`31 passed`" in interview_pack_text

    audit_evidence_text = audit_evidence_path.read_text(encoding="utf-8")
    assert "`86 passed`" in audit_evidence_text
    assert "`29 passed`" in audit_evidence_text
    assert audit_evidence_text.count("`31 passed`") == 2

    spec_text = spec_path.read_text(encoding="utf-8")
    assert "`31 passed`" in spec_text



def test_sync_audit_metric_docs_updates_cleanup_backlog_narratives(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs" / "20260821-project-audit-remediation"
    docs_dir.mkdir(parents=True)

    interview_brief_path = docs_dir / "20260821-project-audit-remediation-interview-brief.md"
    interview_brief_path.write_text(
        "- 根目录治理：old cleanup line\n",
        encoding="utf-8",
    )
    audit_path = docs_dir / "20260821-project-audit-remediation-audit.md"
    audit_path.write_text(
        "| 03 | 根目录整洁度 | old | P0 |\n"
        "| 04 | cleanup 覆盖范围 | old | P0 |\n",
        encoding="utf-8",
    )
    status_matrix_path = docs_dir / "20260821-project-audit-remediation-status-matrix.md"
    status_matrix_path.write_text(
        "- 目录级治理能力也已经补上，当前 old cleanup status\n"
        "| 9 | 仓库根目录临时文件、日志、调试脚本较多 | old | old | old | old |\n",
        encoding="utf-8",
    )

    selected_rules = tuple(
        rule
        for rule in DEFAULT_DOC_LINE_RULES
        if (
            rule.relative_path.as_posix() == "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-interview-brief.md"
            and rule.anchor == "- 根目录治理："
        )
        or (
            rule.relative_path.as_posix() == "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-audit.md"
            and rule.anchor in {"| 03 | 根目录整洁度 |", "| 04 | cleanup 覆盖范围 |"}
        )
        or (
            rule.relative_path.as_posix() == "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-status-matrix.md"
            and rule.anchor in {
                "- 目录级治理能力也已经补上，当前",
                "| 9 | 仓库根目录临时文件、日志、调试脚本较多 |",
            }
        )
    )

    updated_paths = sync_audit_metric_docs(
        _sample_snapshot(),
        repo_root=tmp_path,
        line_rules=selected_rules,
        next_line_rules=(),
        following_lines_rules=(),
    )

    assert {path.relative_to(tmp_path).as_posix() for path in updated_paths} == {
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-audit.md",
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-interview-brief.md",
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-status-matrix.md",
    }
    interview_text = interview_brief_path.read_text(encoding="utf-8")
    assert "managed_count = 0" in interview_text
    assert "防回脏" in interview_text
    audit_text = audit_path.read_text(encoding="utf-8")
    assert audit_text.count("managed_count = 0") >= 2
    assert "防回脏" in audit_text
    status_text = status_matrix_path.read_text(encoding="utf-8")
    assert "managed_count = 0" in status_text
    assert "受控 apply 预案" in status_text

def test_sync_audit_metric_docs_updates_startup_desktop_smoke_lines(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs" / "20260821-project-audit-remediation"
    docs_dir.mkdir(parents=True)

    issues_summary_path = docs_dir / "20260821-project-audit-remediation-issues-summary.md"
    issues_summary_path.write_text(
        "# issues summary\n"
        "- 2026-08-22 startup + desktop 双 smoke：`python -m pytest tests/scripts/test_dev_startup_contracts.py tests/scripts/test_start_dev_smoke.py tests/scripts/test_dev_all_smoke.py -q` → `old smoke`\n",
        encoding="utf-8",
    )
    status_matrix_path = docs_dir / "20260821-project-audit-remediation-status-matrix.md"
    status_matrix_path.write_text(
        "# status matrix\n"
        "- `python -m pytest tests/scripts/test_dev_startup_contracts.py tests/scripts/test_start_dev_smoke.py tests/scripts/test_dev_all_smoke.py -q` → `old smoke`\n",
        encoding="utf-8",
    )
    test_report_path = docs_dir / "20260821-project-audit-remediation-test-report.md"
    test_report_path.write_text(
        "# test report\n"
        "| startup + desktop 双 smoke | `python -m pytest tests/scripts/test_dev_startup_contracts.py tests/scripts/test_start_dev_smoke.py tests/scripts/test_dev_all_smoke.py -q` | `old smoke` |\n",
        encoding="utf-8",
    )

    selected_rules = tuple(
        rule
        for rule in DEFAULT_DOC_LINE_RULES
        if (
            rule.relative_path.as_posix() == "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-issues-summary.md"
            and rule.anchor == "- 2026-08-22 startup + desktop 双 smoke："
        )
        or (
            rule.relative_path.as_posix() == "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-status-matrix.md"
            and "tests/scripts/test_dev_startup_contracts.py tests/scripts/test_start_dev_smoke.py tests/scripts/test_dev_all_smoke.py -q" in rule.anchor
        )
        or (
            rule.relative_path.as_posix() == "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-test-report.md"
            and rule.anchor == "| startup + desktop 双 smoke |"
        )
    )

    updated_paths = sync_audit_metric_docs(
        _sample_snapshot(),
        repo_root=tmp_path,
        line_rules=selected_rules,
        next_line_rules=(),
        following_lines_rules=(),
    )

    assert {path.relative_to(tmp_path).as_posix() for path in updated_paths} == {
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-issues-summary.md",
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-status-matrix.md",
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-test-report.md",
    }
    assert "`17 passed`" in issues_summary_path.read_text(encoding="utf-8")
    assert "`17 passed`" in status_matrix_path.read_text(encoding="utf-8")
    assert "`17 passed`" in test_report_path.read_text(encoding="utf-8")

def test_sync_audit_metric_docs_keeps_chat_warning_labels_in_summary_and_status(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs" / "20260821-project-audit-remediation"
    docs_dir.mkdir(parents=True)

    issues_summary_path = docs_dir / "20260821-project-audit-remediation-issues-summary.md"
    issues_summary_path.write_text(
        "# issues summary\n"
        "> 这个项目不是一个简单的本地问答 demo，stale quote\n"
        "> stale quote\n"
        "3. 再讲我怎么证明：stale proof\n",
        encoding="utf-8",
    )
    status_matrix_path = docs_dir / "20260821-project-audit-remediation-status-matrix.md"
    status_matrix_path.write_text(
        "# status matrix\n"
        "- `python -m pytest tests/api/test_chat_qa_metrics.py tests/api/test_chat_service.py tests/api/test_chat_evidence_contract.py tests/api/test_kb_preview_route.py -q` → `stale chat`\n",
        encoding="utf-8",
    )

    selected_rules = tuple(
        rule
        for rule in DEFAULT_DOC_LINE_RULES
        if (
            rule.relative_path.as_posix() == "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-issues-summary.md"
            and rule.anchor in {"这个项目不是一个简单的本地问答 demo", "3. 再讲我怎么证明："}
        )
        or (
            rule.relative_path.as_posix() == "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-status-matrix.md"
            and "tests/api/test_chat_qa_metrics.py tests/api/test_chat_service.py tests/api/test_chat_evidence_contract.py tests/api/test_kb_preview_route.py -q" in rule.anchor
        )
    )

    updated_paths = sync_audit_metric_docs(
        _sample_snapshot(),
        repo_root=tmp_path,
        line_rules=selected_rules,
        next_line_rules=(),
        following_lines_rules=(),
    )

    assert {path.relative_to(tmp_path).as_posix() for path in updated_paths} == {
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-issues-summary.md",
        "docs/20260821-project-audit-remediation/20260821-project-audit-remediation-status-matrix.md",
    }

    issues_summary_text = issues_summary_path.read_text(encoding="utf-8")
    assert "chat 关键回归 `201 passed`" in issues_summary_text
    assert "`153 / 153`、`201 passed`、`71 passed`、`1300 passed, 8 deselected`；" in issues_summary_text

    status_matrix_text = status_matrix_path.read_text(encoding="utf-8")
    assert "`python -m pytest tests/api/test_chat_qa_metrics.py tests/api/test_chat_service.py tests/api/test_chat_evidence_contract.py tests/api/test_kb_preview_route.py -q` → `201 passed`" in status_matrix_text




