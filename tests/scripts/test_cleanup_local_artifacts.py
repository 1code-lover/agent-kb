from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.cleanup_local_artifacts import (
    ArtifactRecord,
    build_parser,
    classify_root_artifact,
    classify_root_artifact_directory,
    collect_root_artifacts,
    infer_artifact_prefix,
    list_tracked_relative_paths,
    move_root_artifacts,
    normalize_cli_filters,
    should_include_artifact,
    should_manage_root_artifact,
    should_manage_root_artifact_directory,
    summarize_artifact_records,
)


def test_should_manage_root_artifact_only_accepts_root_level_temp_files(tmp_path: Path) -> None:
    root_candidate = tmp_path / "tmp_eval_probe.json"
    root_candidate.write_text("{}", encoding="utf-8")
    nested_candidate = tmp_path / "nested" / "tmp_eval_probe.json"
    nested_candidate.parent.mkdir(parents=True, exist_ok=True)
    nested_candidate.write_text("{}", encoding="utf-8")
    normal_file = tmp_path / "README.md"
    normal_file.write_text("x", encoding="utf-8")

    assert should_manage_root_artifact(root_candidate) is False  # repo root is fixed; tmp_path root should not match
    assert should_manage_root_artifact(root_candidate, repo_root=tmp_path) is True
    assert should_manage_root_artifact(nested_candidate, repo_root=tmp_path) is False
    assert should_manage_root_artifact(normal_file, repo_root=tmp_path) is False


def test_should_manage_root_artifact_accepts_hidden_and_hyphenated_root_temp_files(tmp_path: Path) -> None:
    hidden_probe = tmp_path / ".tmp_node_utf8_probe.txt"
    hidden_probe.write_text("probe", encoding="utf-8")
    hyphenated_probe = tmp_path / "temp-eval-notes.txt"
    hyphenated_probe.write_text("note", encoding="utf-8")

    assert should_manage_root_artifact(hidden_probe, repo_root=tmp_path) is True
    assert should_manage_root_artifact(hyphenated_probe, repo_root=tmp_path) is True


def test_should_manage_root_artifact_directory_only_accepts_root_level_temp_dirs(tmp_path: Path) -> None:
    root_candidate = tmp_path / "tmp_eval_out"
    root_candidate.mkdir()
    hidden_lock_dir = tmp_path / ".pytest-locks"
    hidden_lock_dir.mkdir()
    nested_candidate = tmp_path / "nested" / "tmp_eval_out"
    nested_candidate.mkdir(parents=True)
    normal_dir = tmp_path / "logs"
    normal_dir.mkdir()

    assert should_manage_root_artifact_directory(root_candidate, repo_root=tmp_path, tracked_relative_paths=set()) is True
    assert should_manage_root_artifact_directory(hidden_lock_dir, repo_root=tmp_path, tracked_relative_paths=set()) is True
    assert should_manage_root_artifact_directory(nested_candidate, repo_root=tmp_path, tracked_relative_paths=set()) is False
    assert should_manage_root_artifact_directory(normal_dir, repo_root=tmp_path, tracked_relative_paths=set()) is False


def test_list_tracked_relative_paths_splits_git_nul_output(monkeypatch, tmp_path: Path) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=kwargs.get("args") or args[0],
            returncode=0,
            stdout=b"temp-eval-out/report.json\x00temp-v6/report.json\x00",
            stderr=b"",
        )

    monkeypatch.setattr("scripts.cleanup_local_artifacts.subprocess.run", fake_run)

    tracked = list_tracked_relative_paths(tmp_path)

    assert tracked == {"temp-eval-out/report.json", "temp-v6/report.json"}


def test_collect_root_artifacts_honors_repo_root_argument(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    artifact = repo_root / "tmp_eval_probe.json"
    artifact.write_text("{}", encoding="utf-8")
    nested = repo_root / "nested" / "tmp_eval_probe.json"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("scripts.cleanup_local_artifacts.list_tracked_relative_paths", lambda repo_root: set())

    artifacts = collect_root_artifacts(repo_root=repo_root)

    assert [item.name for item in artifacts] == ["tmp_eval_probe.json"]


def test_collect_root_artifacts_includes_hidden_temp_probe_files(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    hidden_probe = repo_root / ".tmp_node_repl_utf8_probe.txt"
    hidden_probe.write_text("probe", encoding="utf-8")
    regular_probe = repo_root / "tmp_eval_probe.json"
    regular_probe.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("scripts.cleanup_local_artifacts.list_tracked_relative_paths", lambda repo_root: set())

    artifacts = collect_root_artifacts(repo_root=repo_root)

    assert [item.name for item in artifacts] == [".tmp_node_repl_utf8_probe.txt", "tmp_eval_probe.json"]


def test_collect_root_artifacts_can_include_root_directories_but_skips_tracked_ones(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    artifact = repo_root / "tmp_eval_probe.json"
    artifact.write_text("{}", encoding="utf-8")
    scratch_dir = repo_root / "tmp_eval_out"
    scratch_dir.mkdir()
    (scratch_dir / "report.json").write_text("{}", encoding="utf-8")
    tracked_dir = repo_root / "temp-debug-v4"
    tracked_dir.mkdir()
    (tracked_dir / "report.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "scripts.cleanup_local_artifacts.list_tracked_relative_paths",
        lambda repo_root: {"temp-debug-v4/report.json"},
    )

    artifacts = collect_root_artifacts(repo_root=repo_root, include_directories=True)

    assert [item.name for item in artifacts] == ["tmp_eval_out", "tmp_eval_probe.json"]


def test_classify_root_artifact_distinguishes_scratch_scripts_and_logs(tmp_path: Path) -> None:
    ocr_script = tmp_path / "_test_ocr_1.py"
    ocr_script.write_text("print('ocr')", encoding="utf-8")
    run_log = tmp_path / "tmp_uvicorn_18080.err.log"
    run_log.write_text("err", encoding="utf-8")
    temp_file = tmp_path / "tmp_eval_probe.json"
    temp_file.write_text("{}", encoding="utf-8")

    assert classify_root_artifact(ocr_script).category == "scratch_ocr_script"
    assert classify_root_artifact(run_log).category == "runtime_log"
    assert classify_root_artifact(temp_file).category == "temp_probe"


def test_classify_root_artifact_directory_distinguishes_eval_debug_temp_and_lock_dirs(tmp_path: Path) -> None:
    eval_dir = tmp_path / "tmp_eval_out"
    eval_dir.mkdir()
    debug_dir = tmp_path / "tmp_diag_server"
    debug_dir.mkdir()
    temp_dir = tmp_path / "temp-run-workspace"
    temp_dir.mkdir()
    lock_dir = tmp_path / ".pytest-locks"
    lock_dir.mkdir()

    assert classify_root_artifact_directory(eval_dir).category == "scratch_eval_dir"
    assert classify_root_artifact_directory(debug_dir).category == "scratch_debug_dir"
    assert classify_root_artifact_directory(temp_dir).category == "scratch_temp_dir"
    assert classify_root_artifact_directory(lock_dir).category == "pytest_lock_dir"


def test_normalize_cli_filters_drops_empty_values() -> None:
    assert normalize_cli_filters([" runtime_log ", "", "  ", "diagnostic_log"]) == ("runtime_log", "diagnostic_log")


def test_should_include_artifact_honors_category_action_and_name_filters(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    run_log = repo_root / "tmp_uvicorn_18080.err.log"
    run_log.write_text("err", encoding="utf-8")
    probe = repo_root / "tmp_eval_probe.json"
    probe.write_text("{}", encoding="utf-8")
    debug_dir = repo_root / "tmp_diag_server"
    debug_dir.mkdir()

    assert should_include_artifact(run_log, repo_root=repo_root, categories=("runtime_log",)) is True
    assert should_include_artifact(run_log, repo_root=repo_root, categories=("temp_probe",)) is False
    assert should_include_artifact(run_log, repo_root=repo_root, recommended_actions=("archive_or_delete",)) is True
    assert should_include_artifact(probe, repo_root=repo_root, recommended_actions=("archive_or_delete",)) is False
    assert should_include_artifact(debug_dir, repo_root=repo_root, categories=("scratch_debug_dir",)) is True
    assert should_include_artifact(run_log, repo_root=repo_root, artifact_names=("tmp_uvicorn_18080.err.log",)) is True
    assert should_include_artifact(run_log, repo_root=repo_root, artifact_names=("tmp_eval_probe.json",)) is False


def test_move_root_artifacts_adds_summary_and_reason(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    artifact = repo_root / "tmp_live_api.log"
    artifact.write_text("hello", encoding="utf-8")
    tracked = repo_root / "tmp_tracked.log"
    tracked.write_text("tracked", encoding="utf-8")

    monkeypatch.setattr(
        "scripts.cleanup_local_artifacts.REPO_ROOT",
        repo_root,
        raising=False,
    )
    monkeypatch.setattr(
        "scripts.cleanup_local_artifacts.DEFAULT_OUTPUT_ROOT",
        repo_root / "temp" / "root-artifacts",
        raising=False,
    )
    monkeypatch.setattr(
        "scripts.cleanup_local_artifacts.list_tracked_relative_paths",
        lambda repo_root: {"tmp_tracked.log"},
    )

    manifest = move_root_artifacts(repo_root=repo_root, output_root=repo_root / "temp" / "root-artifacts", apply=True)

    assert manifest["managed_count"] == 1
    assert manifest["summary"]["by_category"] == {"diagnostic_log": 1}
    assert manifest["summary"]["by_recommended_action"] == {"archive_or_delete": 1}
    assert manifest["summary"]["by_kind"] == {"file": 1}
    manifest_path = repo_root / manifest["manifest_path"]
    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["managed_count"] == 1
    assert payload["records"][0]["reason"]
    assert payload["records"][0]["category"] == "diagnostic_log"
    assert payload["records"][0]["kind"] == "file"
    assert not artifact.exists()
    moved_relative = payload["records"][0]["destination"]
    assert (repo_root / moved_relative).read_text(encoding="utf-8") == "hello"
    assert tracked.exists()


def test_move_root_artifacts_uses_absolute_paths_when_output_root_is_outside_repo(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    artifact = repo_root / "tmp_eval_probe.json"
    artifact.write_text("{}", encoding="utf-8")
    external_output_root = tmp_path / "archives"

    monkeypatch.setattr(
        "scripts.cleanup_local_artifacts.list_tracked_relative_paths",
        lambda repo_root: set(),
    )

    manifest = move_root_artifacts(
        repo_root=repo_root,
        output_root=external_output_root,
        apply=False,
    )

    assert manifest["managed_count"] == 1
    assert Path(manifest["records"][0]["destination"]).is_absolute()


def test_move_root_artifacts_can_plan_directory_items(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    scratch_dir = repo_root / "tmp_eval_out"
    scratch_dir.mkdir()
    report = scratch_dir / "report.json"
    report.write_text('{"ok": true}', encoding="utf-8")

    monkeypatch.setattr(
        "scripts.cleanup_local_artifacts.list_tracked_relative_paths",
        lambda repo_root: set(),
    )

    manifest = move_root_artifacts(
        repo_root=repo_root,
        output_root=repo_root / "temp" / "root-artifacts",
        apply=False,
        include_directories=True,
    )

    assert manifest["include_directories"] is True
    assert manifest["managed_count"] == 1
    assert manifest["summary"]["by_category"] == {"scratch_eval_dir": 1}
    assert manifest["summary"]["by_kind"] == {"directory": 1}
    assert manifest["summary"]["total_size_bytes"] >= report.stat().st_size
    assert manifest["summary"]["size_bytes_by_category"] == {"scratch_eval_dir": manifest["summary"]["total_size_bytes"]}
    assert manifest["summary"]["largest_records"] == [
        {
            "relative_path": "tmp_eval_out",
            "size_bytes": manifest["records"][0]["size_bytes"],
            "category": "scratch_eval_dir",
            "kind": "directory",
        }
    ]
    assert manifest["records"][0]["relative_path"] == "tmp_eval_out"
    assert manifest["records"][0]["kind"] == "directory"
    assert manifest["records"][0]["size_bytes"] >= report.stat().st_size


def test_infer_artifact_prefix_groups_same_family_names() -> None:
    assert infer_artifact_prefix("tmp_eval_debug_codex_fix") == "tmp_eval"
    assert infer_artifact_prefix("temp-eval-out.txt") == "temp-eval"
    assert infer_artifact_prefix(".tmp_node_repl_utf8_probe.txt") == ".tmp_node"
    assert infer_artifact_prefix("_test_ocr_probe.py") == "test_ocr"


def test_summarize_artifact_records_groups_categories_and_prefixes() -> None:
    records = [
        ArtifactRecord(
            name="tmp_uvicorn_1.log",
            relative_path="tmp_uvicorn_1.log",
            size_bytes=11,
            action="plan",
            category="runtime_log",
            recommended_action="archive_or_delete",
            reason="x",
            kind="file",
        ),
        ArtifactRecord(
            name="tmp_eval_probe.json",
            relative_path="tmp_eval_probe.json",
            size_bytes=7,
            action="plan",
            category="temp_probe",
            recommended_action="review_then_archive",
            reason="y",
            kind="file",
        ),
        ArtifactRecord(
            name="tmp_eval_debug",
            relative_path="tmp_eval_debug",
            size_bytes=5,
            action="plan",
            category="scratch_eval_dir",
            recommended_action="review_then_archive",
            reason="z",
            kind="directory",
        ),
    ]

    summary = summarize_artifact_records(records, top_n=2)

    assert summary["top_n"] == 2
    assert summary["total_size_bytes"] == 23
    assert summary["by_category"] == {"runtime_log": 1, "scratch_eval_dir": 1, "temp_probe": 1}
    assert summary["by_recommended_action"] == {"archive_or_delete": 1, "review_then_archive": 2}
    assert summary["by_kind"] == {"directory": 1, "file": 2}
    assert summary["size_bytes_by_category"] == {"runtime_log": 11, "scratch_eval_dir": 5, "temp_probe": 7}
    assert summary["count_by_prefix"] == {"tmp_eval": 2, "tmp_uvicorn": 1}
    assert summary["size_bytes_by_prefix"] == {"tmp_eval": 12, "tmp_uvicorn": 11}
    assert summary["largest_records"] == [
        {
            "relative_path": "tmp_uvicorn_1.log",
            "size_bytes": 11,
            "category": "runtime_log",
            "kind": "file",
        },
        {
            "relative_path": "tmp_eval_probe.json",
            "size_bytes": 7,
            "category": "temp_probe",
            "kind": "file",
        },
    ]
    assert summary["largest_records_by_category"] == {
        "runtime_log": [
            {
                "relative_path": "tmp_uvicorn_1.log",
                "size_bytes": 11,
                "category": "runtime_log",
                "kind": "file",
            }
        ],
        "scratch_eval_dir": [
            {
                "relative_path": "tmp_eval_debug",
                "size_bytes": 5,
                "category": "scratch_eval_dir",
                "kind": "directory",
            }
        ],
        "temp_probe": [
            {
                "relative_path": "tmp_eval_probe.json",
                "size_bytes": 7,
                "category": "temp_probe",
                "kind": "file",
            }
        ],
    }
    assert summary["top_prefixes"] == [
        {"prefix": "tmp_eval", "count": 2, "size_bytes": 12},
        {"prefix": "tmp_uvicorn", "count": 1, "size_bytes": 11},
    ]


def test_move_root_artifacts_filters_by_selected_artifact_names(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    log_file = repo_root / "tmp_live_api.log"
    log_file.write_text("hello", encoding="utf-8")
    probe_file = repo_root / "tmp_eval_probe.json"
    probe_file.write_text("{}", encoding="utf-8")
    debug_dir = repo_root / "tmp_eval_debug"
    debug_dir.mkdir()
    (debug_dir / "report.json").write_text('{"ok": true}', encoding="utf-8")

    monkeypatch.setattr(
        "scripts.cleanup_local_artifacts.list_tracked_relative_paths",
        lambda repo_root: set(),
    )

    manifest = move_root_artifacts(
        repo_root=repo_root,
        output_root=repo_root / "temp" / "root-artifacts",
        include_directories=True,
        artifact_names=["tmp_eval_debug", "tmp_eval_probe.json"],
        apply=False,
    )

    assert manifest["selected_artifact_names"] == ["tmp_eval_debug", "tmp_eval_probe.json"]
    assert manifest["managed_count"] == 2
    assert [record["relative_path"] for record in manifest["records"]] == ["tmp_eval_debug", "tmp_eval_probe.json"]
    assert manifest["summary"]["by_category"] == {"scratch_eval_dir": 1, "temp_probe": 1}


def test_move_root_artifacts_filters_by_recommended_action(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    log_file = repo_root / "tmp_live_api.log"
    log_file.write_text("hello", encoding="utf-8")
    probe_file = repo_root / "tmp_eval_probe.json"
    probe_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "scripts.cleanup_local_artifacts.list_tracked_relative_paths",
        lambda repo_root: set(),
    )

    manifest = move_root_artifacts(
        repo_root=repo_root,
        output_root=repo_root / "temp" / "root-artifacts",
        recommended_actions=["archive_or_delete"],
        apply=False,
    )

    assert manifest["selected_recommended_actions"] == ["archive_or_delete"]
    assert manifest["managed_count"] == 1
    assert manifest["records"][0]["relative_path"] == "tmp_live_api.log"
    assert manifest["summary"]["by_category"] == {"diagnostic_log": 1}


def test_move_root_artifacts_apply_uses_absolute_manifest_path_when_output_root_is_outside_repo(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    artifact = repo_root / "tmp_eval_probe.json"
    artifact.write_text("{}", encoding="utf-8")
    external_output_root = tmp_path / "archives"

    monkeypatch.setattr(
        "scripts.cleanup_local_artifacts.list_tracked_relative_paths",
        lambda repo_root: set(),
    )

    manifest = move_root_artifacts(
        repo_root=repo_root,
        output_root=external_output_root,
        apply=True,
    )

    manifest_path = Path(manifest["manifest_path"])
    assert manifest_path.is_absolute()
    assert manifest_path.exists()
    assert not artifact.exists()


def test_move_root_artifacts_can_write_dry_run_report_and_limit_top_n(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    (repo_root / "tmp_eval_probe.json").write_text("{}", encoding="utf-8")
    (repo_root / "tmp_eval_debug").mkdir()
    (repo_root / "tmp_eval_debug" / "report.json").write_text('{"ok": true}', encoding="utf-8")
    (repo_root / "tmp_uvicorn_1.log").write_text("hello world", encoding="utf-8")
    report_path = repo_root / "temp" / "reports" / "root-artifacts-dry-run.json"

    monkeypatch.setattr(
        "scripts.cleanup_local_artifacts.list_tracked_relative_paths",
        lambda repo_root: set(),
    )

    manifest = move_root_artifacts(
        repo_root=repo_root,
        output_root=repo_root / "temp" / "root-artifacts",
        apply=False,
        include_directories=True,
        top_n=2,
        write_report=report_path,
    )

    assert manifest["top_n"] == 2
    assert manifest["report_path"] == "temp/reports/root-artifacts-dry-run.json"
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["summary"]["top_n"] == 2
    assert len(payload["summary"]["largest_records"]) == 2
    assert len(payload["summary"]["top_prefixes"]) == 2
    assert payload["summary"]["top_prefixes"][0]["prefix"] == "tmp_eval"


def test_build_parser_accepts_explicit_dry_run_include_directories_and_artifact_names() -> None:
    parser = build_parser()
    args = parser.parse_args([
        "--dry-run",
        "--include-directories",
        "--artifact-name",
        "tmp_eval_debug",
        "--artifact-name",
        "tmp_eval_probe.json",
        "--top-n",
        "2",
        "--write-report",
        "temp/report.json",
    ])

    assert args.dry_run is True
    assert args.apply is False
    assert args.include_directories is True
    assert args.artifact_name == ["tmp_eval_debug", "tmp_eval_probe.json"]
    assert args.top_n == 2
    assert args.write_report == Path("temp/report.json")


