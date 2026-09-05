from __future__ import annotations

import json
from pathlib import Path

from scripts.cleanup_local_artifacts import move_root_artifacts

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_gitignore_blocks_legacy_desktop_log_transcript() -> None:
    content = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "desktop/log.txt" in content


def test_legacy_desktop_log_transcript_is_not_kept_in_repo() -> None:
    assert not (REPO_ROOT / "desktop" / "log.txt").exists()


def test_desktop_npm_test_covers_all_current_node_test_files() -> None:
    package_json = json.loads((REPO_ROOT / "desktop" / "package.json").read_text(encoding="utf-8"))
    test_script = package_json["scripts"]["test"]

    expected_test_files = sorted(
        str(path.relative_to(REPO_ROOT / "desktop")).replace("\\", "/")
        for pattern in ("scripts/*.test.js", "src/*.test.js")
        for path in (REPO_ROOT / "desktop").glob(pattern)
    )

    for relative_path in expected_test_files:
        assert relative_path in test_script


def test_webapp_npm_test_covers_all_current_node_test_files() -> None:
    package_json = json.loads((REPO_ROOT / "webapp" / "package.json").read_text(encoding="utf-8"))
    test_script = package_json["scripts"]["test"]

    expected_test_files = sorted(
        str(path.relative_to(REPO_ROOT / "webapp")).replace("\\", "/")
        for path in (REPO_ROOT / "webapp" / "src").rglob("*.test.js")
    )

    for relative_path in expected_test_files:
        assert relative_path in test_script


def test_repo_declares_line_ending_policy() -> None:
    content = (REPO_ROOT / '.gitattributes').read_text(encoding='utf-8')

    assert '* text=auto' in content
    assert '*.ps1 text eol=crlf' in content
    assert '*.py text eol=lf' in content
    assert '*.md text eol=lf' in content


def test_root_artifact_backlog_stays_within_current_ceiling() -> None:
    manifest = move_root_artifacts(
        repo_root=REPO_ROOT,
        output_root=REPO_ROOT / "temp" / "root-artifacts",
        apply=False,
        include_directories=True,
    )

    summary = manifest["summary"]
    by_category = summary["by_category"]
    by_prefix = summary["count_by_prefix"]

    assert manifest["managed_count"] == 0
    assert summary["total_size_bytes"] == 0
    assert by_category == {}
    assert by_prefix == {}

