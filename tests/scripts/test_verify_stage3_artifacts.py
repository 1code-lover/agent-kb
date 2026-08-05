"""Stage 3 产物一致性校验脚本的回归测试。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.verify_stage3_artifacts import verify_stage3_artifacts

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_stage3_docs(root: Path, *, manifest_paths: list[str], submit_scope_paths: list[str], report_extra: str = "") -> None:
    docs_dir = root / "docs" / "20260722-local-multi-kb-assistant"
    docs_dir.mkdir(parents=True, exist_ok=True)

    report_lines = [
        "# report",
        "54/54 passed",
        "72/72 passed",
        "329 passed, 2 warnings",
        "626 passed, 2 warnings",
        "TOTAL 6565 / Miss 1117 / Cover 83%",
        "diag-utf8-after-answer-expand.json",
        "20260731-live-18082-utf8.json",
        "20260731-live-18082-pdf-text.json",
        "20260731-live-18082-pdf-scan.json",
        "20260731-live-18082-image-ocr.json",
        "20260731-live-18082-mixed-batch.json",
    ]
    report_lines.extend(manifest_paths)
    if report_extra:
        report_lines.append(report_extra)
    (docs_dir / "20260722-local-multi-kb-assistant-test-report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    manifest_lines = [
        "# manifest",
        "",
        "## 2. \u5f53\u524d\u9636\u6bb5\u5e94\u6b63\u5f0f\u4fdd\u7559\u7684\u4ea7\u7269",
    ]
    manifest_lines.extend([f"- `{path}`" for path in manifest_paths])
    (docs_dir / "20260722-local-multi-kb-assistant-artifacts-manifest.md").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    submit_scope_lines = [
        "# submit scope",
        "",
        "## 3. \u6587\u4ef6\u7ea7\u201c\u5efa\u8bae\u6309\u6700\u5c0f\u96c6\u5408\u9009\u62e9\u6027\u63d0\u4ea4\u201d\u7684 artifacts",
    ]
    submit_scope_lines.extend([f"- `{path}`" for path in submit_scope_paths])
    (docs_dir / "20260722-local-multi-kb-assistant-spec-submit-scope.md").write_text("\n".join(submit_scope_lines) + "\n", encoding="utf-8")


def test_verify_stage3_artifacts_passes_against_current_repo() -> None:
    summary = verify_stage3_artifacts(REPO_ROOT)

    assert summary["ok"] is True
    assert summary["manifest_count"] == 9
    assert summary["submit_scope_count"] == 9
    assert summary["missing_files"] == []
    assert summary["missing_report_refs"] == []
    assert summary["missing_report_tokens"] == []
    assert summary["manifest_only"] == []
    assert summary["submit_scope_only"] == []


def test_verify_stage3_artifacts_reports_missing_file(tmp_path: Path) -> None:
    manifest_paths = [
        "docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/example.json",
        "docs/20260722-local-multi-kb-assistant/artifacts/live-roundtrip/example-live.json",
    ]
    _write_stage3_docs(tmp_path, manifest_paths=manifest_paths, submit_scope_paths=manifest_paths)
    existing = tmp_path / manifest_paths[0]
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("{}\n", encoding="utf-8")

    summary = verify_stage3_artifacts(tmp_path)

    assert summary["ok"] is False
    assert summary["missing_files"] == [manifest_paths[1]]
    assert summary["manifest_only"] == []
    assert summary["submit_scope_only"] == []


def test_verify_stage3_artifacts_reports_manifest_submit_scope_mismatch(tmp_path: Path) -> None:
    manifest_paths = ["docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/a.json"]
    submit_scope_paths = ["docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/b.json"]
    _write_stage3_docs(tmp_path, manifest_paths=manifest_paths, submit_scope_paths=submit_scope_paths)
    for path in {manifest_paths[0], submit_scope_paths[0]}:
        file_path = tmp_path / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("{}\n", encoding="utf-8")

    summary = verify_stage3_artifacts(tmp_path)

    assert summary["ok"] is False
    assert summary["manifest_only"] == manifest_paths
    assert summary["submit_scope_only"] == submit_scope_paths


def test_verify_stage3_artifacts_cli_json_output(tmp_path: Path) -> None:
    manifest_paths = ["docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/example.json"]
    _write_stage3_docs(tmp_path, manifest_paths=manifest_paths, submit_scope_paths=manifest_paths)
    file_path = tmp_path / manifest_paths[0]
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("{}\n", encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "-m", "scripts.verify_stage3_artifacts", "--repo-root", str(tmp_path), "--json"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    summary = json.loads(completed.stdout)
    assert summary["ok"] is True
    assert summary["missing_report_tokens"] == []


def test_verify_stage3_artifacts_cli_json_failure_output(tmp_path: Path) -> None:
    manifest_paths = ["docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/example.json"]
    submit_scope_paths = ["docs/20260722-local-multi-kb-assistant/artifacts/qa-eval/other.json"]
    _write_stage3_docs(tmp_path, manifest_paths=manifest_paths, submit_scope_paths=submit_scope_paths)
    for path in {manifest_paths[0], submit_scope_paths[0]}:
        file_path = tmp_path / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("{}\n", encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "-m", "scripts.verify_stage3_artifacts", "--repo-root", str(tmp_path), "--json"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    summary = json.loads(completed.stdout)
    assert summary["ok"] is False
    assert summary["manifest_only"] == manifest_paths
    assert summary["submit_scope_only"] == submit_scope_paths
