"""校验 Stage 3 测试报告、产物清单与最小提交集的一致性。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "docs" / "20260722-local-multi-kb-assistant"
REPORT_PATH = DOCS_DIR / "20260722-local-multi-kb-assistant-test-report.md"
MANIFEST_PATH = DOCS_DIR / "20260722-local-multi-kb-assistant-artifacts-manifest.md"
SUBMIT_SCOPE_PATH = DOCS_DIR / "20260722-local-multi-kb-assistant-spec-submit-scope.md"
MANIFEST_SECTION_HEADING = "## 2. \u5f53\u524d\u9636\u6bb5\u5e94\u6b63\u5f0f\u4fdd\u7559\u7684\u4ea7\u7269"
SUBMIT_SCOPE_SECTION_HEADING = "## 3. \u6587\u4ef6\u7ea7\u201c\u5efa\u8bae\u6309\u6700\u5c0f\u96c6\u5408\u9009\u62e9\u6027\u63d0\u4ea4\u201d\u7684 artifacts"
REPORT_REQUIRED_TOKENS = [
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
_PATH_RE = re.compile(r"`([^`]+)`")


def _section_lines(markdown_text: str, heading: str) -> list[str]:
    """返回指定二级标题下、直到下一个二级标题前的所有行。"""
    lines = markdown_text.splitlines()
    try:
        start = lines.index(heading)
    except ValueError as exc:
        raise ValueError(f"Missing section heading: {heading}") from exc

    section: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        section.append(line)
    return section


def _extract_bullet_paths(markdown_text: str, heading: str) -> list[str]:
    """提取目标章节中以反引号包裹的路径型条目。"""
    results: list[str] = []
    for raw_line in _section_lines(markdown_text, heading):
        line = raw_line.strip()
        if not line.startswith("- "):
            continue
        for match in _PATH_RE.findall(line):
            normalized = match.strip()
            if "/" not in normalized and "\\" not in normalized:
                continue
            if normalized.startswith("python "):
                continue
            results.append(normalized)
    return results


def _read_text(path: Path) -> str:
    """以 UTF-8 读取必需文件，不存在时直接抛错。"""
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return path.read_text(encoding="utf-8")


def verify_stage3_artifacts(repo_root: Path | None = None) -> dict[str, Any]:
    """校验当前仓库 Stage 3 正式产物是否齐备且与文档引用一致。"""
    root = (repo_root or REPO_ROOT).resolve()
    docs_dir = root / "docs" / "20260722-local-multi-kb-assistant"
    report_path = docs_dir / REPORT_PATH.name
    manifest_path = docs_dir / MANIFEST_PATH.name
    submit_scope_path = docs_dir / SUBMIT_SCOPE_PATH.name

    manifest_text = _read_text(manifest_path)
    submit_scope_text = _read_text(submit_scope_path)
    report_text = _read_text(report_path)

    manifest_paths = _extract_bullet_paths(manifest_text, MANIFEST_SECTION_HEADING)
    submit_scope_paths = _extract_bullet_paths(submit_scope_text, SUBMIT_SCOPE_SECTION_HEADING)

    manifest_set = set(manifest_paths)
    submit_scope_set = set(submit_scope_paths)

    missing_files = [path for path in manifest_paths if not (root / Path(path)).exists()]
    missing_report_refs = [path for path in manifest_paths if path not in report_text]
    missing_report_tokens = [token for token in REPORT_REQUIRED_TOKENS if token not in report_text]

    summary = {
        "repo_root": str(root),
        "report_path": str(report_path.relative_to(root)),
        "manifest_path": str(manifest_path.relative_to(root)),
        "submit_scope_path": str(submit_scope_path.relative_to(root)),
        "manifest_count": len(manifest_paths),
        "submit_scope_count": len(submit_scope_paths),
        "manifest_paths": manifest_paths,
        "submit_scope_paths": submit_scope_paths,
        "missing_files": missing_files,
        "missing_report_refs": missing_report_refs,
        "missing_report_tokens": missing_report_tokens,
        "manifest_only": sorted(manifest_set - submit_scope_set),
        "submit_scope_only": sorted(submit_scope_set - manifest_set),
    }
    summary["ok"] = not any(
        [
            summary["missing_files"],
            summary["missing_report_refs"],
            summary["missing_report_tokens"],
            summary["manifest_only"],
            summary["submit_scope_only"],
        ]
    )
    return summary


def main() -> int:
    """提供命令行入口，输出人类可读摘要或 JSON 结果。"""
    parser = argparse.ArgumentParser(description="Validate Stage 3 report artifact consistency")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="Repository root path")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    args = parser.parse_args()

    summary = verify_stage3_artifacts(args.repo_root)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"ok={summary['ok']}")
        print(f"manifest_count={summary['manifest_count']}")
        print(f"submit_scope_count={summary['submit_scope_count']}")
        for key in ["missing_files", "missing_report_refs", "missing_report_tokens", "manifest_only", "submit_scope_only"]:
            if not summary[key]:
                continue
            print(f"{key}:")
            for item in summary[key]:
                print(f"- {item}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
