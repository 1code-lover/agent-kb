"""清理仓库根目录散落的本地临时产物。"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "temp" / "root-artifacts"
ROOT_ARTIFACT_PATTERNS = (
    ".tmp*",
    "tmp_*",
    "temp_*",
    "tmp-*",
    "temp-*",
    "server_*.log",
    "_test_ocr*.py",
)
ROOT_ARTIFACT_DIR_PATTERNS = (
    ".pytest-locks",
    "tmp_*",
    "temp_*",
    "tmp-*",
    "temp-*",
)
ROOT_ARTIFACT_DIR_EXCLUDES = {
    ".dev-runtime",
    "logs",
    "temp",
    "test_output",
}


@dataclass(slots=True)
class ArtifactDisposition:
    category: str
    recommended_action: str
    reason: str


@dataclass(slots=True)
class ArtifactRecord:
    name: str
    relative_path: str
    size_bytes: int
    action: str
    destination: str | None = None
    reason: str | None = None
    category: str | None = None
    recommended_action: str | None = None
    kind: str | None = None


def _relative_key(path: Path, repo_root: Path) -> str:
    """把路径归一化为相对仓库根目录的 POSIX key。"""
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _render_manifest_path(path: Path, repo_root: Path) -> str:
    """优先输出仓库内相对路径，仓库外回退绝对路径，统一为 POSIX 风格便于 manifest 跨平台对比。"""
    resolved_path = path.resolve()
    resolved_repo_root = repo_root.resolve()
    try:
        return resolved_path.relative_to(resolved_repo_root).as_posix()
    except ValueError:
        return resolved_path.as_posix()


def should_manage_root_artifact(path: Path, *, repo_root: Path = REPO_ROOT) -> bool:
    """判断是否属于需要治理的根目录临时文件。"""
    if not path.is_file():
        return False
    if path.resolve().parent != repo_root.resolve():
        return False
    return any(path.match(pattern) for pattern in ROOT_ARTIFACT_PATTERNS)


def list_tracked_relative_paths(repo_root: Path = REPO_ROOT) -> set[str]:
    """一次性读取 git 已跟踪文件列表，避免逐文件调用 git。"""
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        return set()

    return {
        entry.replace("\\", "/")
        for entry in result.stdout.decode("utf-8", errors="ignore").split("\x00")
        if entry
    }


def _directory_contains_tracked_paths(
    path: Path,
    *,
    tracked_relative_paths: set[str],
    repo_root: Path,
) -> bool:
    prefix = _relative_key(path, repo_root)
    return any(relative_path == prefix or relative_path.startswith(prefix + "/") for relative_path in tracked_relative_paths)


def should_manage_root_artifact_directory(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
    tracked_relative_paths: set[str] | None = None,
) -> bool:
    """判断是否属于需要治理的根目录临时目录。"""
    if not path.is_dir():
        return False
    if path.resolve().parent != repo_root.resolve():
        return False
    if path.name in ROOT_ARTIFACT_DIR_EXCLUDES:
        return False
    if not any(path.match(pattern) for pattern in ROOT_ARTIFACT_DIR_PATTERNS):
        return False

    tracked = tracked_relative_paths if tracked_relative_paths is not None else list_tracked_relative_paths(repo_root)
    return not _directory_contains_tracked_paths(path, tracked_relative_paths=tracked, repo_root=repo_root)


def classify_root_artifact(path: Path) -> ArtifactDisposition:
    """给根目录临时文件打标签，便于后续决定是归档、删除还是转正。"""
    lower_name = path.name.lower()
    suffixes = {suffix.lower() for suffix in path.suffixes}

    if lower_name.startswith("_test_ocr") and lower_name.endswith(".py"):
        return ArtifactDisposition(
            category="scratch_ocr_script",
            recommended_action="review_or_promote",
            reason="根目录 OCR 调试脚本应迁回 scripts/tests 或归档，避免继续暴露在主入口目录。",
        )

    if any(token in lower_name for token in ("uvicorn", "runapi", "server")) and suffixes & {".log"}:
        return ArtifactDisposition(
            category="runtime_log",
            recommended_action="archive_or_delete",
            reason="运行期日志可用于追查问题，但不应长期滞留在仓库根目录。",
        )

    if suffixes & {".log"}:
        return ArtifactDisposition(
            category="diagnostic_log",
            recommended_action="archive_or_delete",
            reason="诊断日志属于临时产物，应统一归档到 temp/root-artifacts 或删除。",
        )

    return ArtifactDisposition(
        category="temp_probe",
        recommended_action="review_then_archive",
        reason="临时探针文件需要人工确认是否应转正为正式脚本，否则应归档移出根目录。",
    )


def classify_root_artifact_directory(path: Path) -> ArtifactDisposition:
    """给根目录 scratch 目录打标签，便于区分评测、调试和普通探针工作区。"""
    lower_name = path.name.lower()

    if lower_name == ".pytest-locks":
        return ArtifactDisposition(
            category="pytest_lock_dir",
            recommended_action="delete_or_archive",
            reason="历史 pytest 锁目录不应滞留在仓库根目录；新逻辑已迁到 temp/pytest-locks，可直接清理残留目录。",
        )

    if "eval" in lower_name:
        return ArtifactDisposition(
            category="scratch_eval_dir",
            recommended_action="review_then_archive",
            reason="评测 scratch 目录通常只用于短期对比与回归试验，应在结论沉淀后归档到 temp/root-artifacts。",
        )

    if any(token in lower_name for token in ("diag", "debug", "probe")):
        return ArtifactDisposition(
            category="scratch_debug_dir",
            recommended_action="review_then_archive",
            reason="调试/诊断目录不应长期挂在仓库根目录，确认无继续使用价值后应统一归档。",
        )

    return ArtifactDisposition(
        category="scratch_temp_dir",
        recommended_action="review_then_archive",
        reason="根目录 scratch 目录通常只服务一次性实验，应在人审后归档或删除，避免长期堆积。",
    )


def describe_root_artifact(path: Path) -> ArtifactDisposition:
    """按文件/目录类型统一返回治理建议。"""
    if path.is_dir():
        return classify_root_artifact_directory(path)
    return classify_root_artifact(path)


def infer_artifact_prefix(name: str) -> str:
    """提取临时产物族前缀，帮助定位同一批次 scratch/backlog。"""
    suffixes = Path(name).suffixes
    stem = name[:-sum(len(suffix) for suffix in suffixes)] if suffixes else name
    dotted = stem.startswith(".")
    normalized_stem = stem[1:] if dotted else stem

    for delimiter in ("_", "-"):
        parts = [part for part in normalized_stem.split(delimiter) if part]
        if len(parts) >= 2 and parts[0] in {"tmp", "temp", "server", "test"}:
            prefix = f"{parts[0]}{delimiter}{parts[1]}"
            return f".{prefix}" if dotted else prefix

    return stem


def _build_record_snapshot(record: ArtifactRecord) -> dict[str, object]:
    return {
        "relative_path": record.relative_path,
        "size_bytes": record.size_bytes,
        "category": record.category,
        "kind": record.kind,
    }


def summarize_artifact_records(records: list[ArtifactRecord], *, top_n: int = 5) -> dict[str, object]:
    """汇总分类、体积与建议动作，方便 dry-run 后直接做人审。"""
    normalized_top_n = max(1, int(top_n))
    category_counter = Counter(record.category for record in records if record.category)
    action_counter = Counter(record.recommended_action for record in records if record.recommended_action)
    kind_counter = Counter(record.kind for record in records if record.kind)
    size_by_category = Counter()
    prefix_counter = Counter()
    size_by_prefix = Counter()
    records_by_category: dict[str, list[ArtifactRecord]] = defaultdict(list)
    for record in records:
        prefix = infer_artifact_prefix(record.name)
        prefix_counter[prefix] += 1
        size_by_prefix[prefix] += record.size_bytes
        if record.category:
            size_by_category[record.category] += record.size_bytes
            records_by_category[record.category].append(record)

    sorted_records = sorted(records, key=lambda item: (-item.size_bytes, item.relative_path))
    largest_records = [_build_record_snapshot(record) for record in sorted_records[:normalized_top_n]]
    largest_records_by_category = {
        category: [_build_record_snapshot(record) for record in sorted(category_records, key=lambda item: (-item.size_bytes, item.relative_path))[:normalized_top_n]]
        for category, category_records in sorted(records_by_category.items())
    }
    top_prefixes = [
        {
            "prefix": prefix,
            "count": prefix_counter[prefix],
            "size_bytes": size_by_prefix[prefix],
        }
        for prefix in sorted(
            prefix_counter,
            key=lambda item: (-size_by_prefix[item], -prefix_counter[item], item),
        )[:normalized_top_n]
    ]

    return {
        "top_n": normalized_top_n,
        "total_size_bytes": sum(record.size_bytes for record in records),
        "by_category": dict(sorted(category_counter.items())),
        "by_recommended_action": dict(sorted(action_counter.items())),
        "by_kind": dict(sorted(kind_counter.items())),
        "size_bytes_by_category": dict(sorted(size_by_category.items())),
        "count_by_prefix": dict(sorted(prefix_counter.items())),
        "size_bytes_by_prefix": dict(sorted(size_by_prefix.items())),
        "largest_records": largest_records,
        "largest_records_by_category": largest_records_by_category,
        "top_prefixes": top_prefixes,
    }

def normalize_cli_filters(values: Iterable[str] | None) -> tuple[str, ...]:
    """把命令行多值过滤器归一化，便于 manifest 落盘与测试。"""
    normalized = []
    for value in values or ():
        raw = str(value or "").strip()
        if raw:
            normalized.append(raw)
    return tuple(normalized)


def collect_root_artifacts(repo_root: Path = REPO_ROOT, *, include_directories: bool = False) -> list[Path]:
    """收集仓库根目录中符合规则且未被 git 跟踪的临时文件/目录。"""
    tracked_relative_paths = list_tracked_relative_paths(repo_root)
    artifacts: list[Path] = []
    for candidate in sorted(repo_root.iterdir(), key=lambda item: item.name.lower()):
        candidate_relative = _relative_key(candidate, repo_root)
        if candidate_relative in tracked_relative_paths:
            continue
        if should_manage_root_artifact(candidate, repo_root=repo_root):
            artifacts.append(candidate)
            continue
        if include_directories and should_manage_root_artifact_directory(
            candidate,
            repo_root=repo_root,
            tracked_relative_paths=tracked_relative_paths,
        ):
            artifacts.append(candidate)
    return artifacts


def ensure_unique_destination(destination_dir: Path, file_name: str) -> Path:
    """生成不冲突的目标路径。"""
    base = destination_dir / file_name
    if not base.exists():
        return base

    stem = Path(file_name).stem
    suffix = Path(file_name).suffix
    index = 1
    while True:
        candidate = destination_dir / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def measure_artifact_size(path: Path) -> int:
    """估算文件/目录占用大小，目录按递归文件大小求和。"""
    if path.is_file():
        return path.stat().st_size

    if not path.is_dir():
        return 0

    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def infer_artifact_kind(path: Path) -> str:
    """返回 artifact 类型，便于 manifest 汇总。"""
    return "directory" if path.is_dir() else "file"


def should_include_artifact(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
    categories: tuple[str, ...] = (),
    recommended_actions: tuple[str, ...] = (),
    artifact_names: tuple[str, ...] = (),
) -> bool:
    """根据分类、建议动作或显式名称过滤待治理对象。"""
    if artifact_names:
        relative_path = _relative_key(path, repo_root)
        if path.name not in artifact_names and relative_path not in artifact_names:
            return False

    disposition = describe_root_artifact(path)
    if categories and disposition.category not in categories:
        return False
    if recommended_actions and disposition.recommended_action not in recommended_actions:
        return False
    return True


def move_root_artifacts(
    *,
    repo_root: Path = REPO_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    apply: bool = False,
    categories: Iterable[str] | None = None,
    recommended_actions: Iterable[str] | None = None,
    artifact_names: Iterable[str] | None = None,
    include_directories: bool = False,
    top_n: int = 5,
    write_report: Path | None = None,
) -> dict[str, object]:
    """移动根目录临时文件/目录到 temp/root-artifacts 下，并生成 manifest。"""
    normalized_categories = normalize_cli_filters(categories)
    normalized_actions = normalize_cli_filters(recommended_actions)
    normalized_artifact_names = normalize_cli_filters(artifact_names)
    normalized_top_n = max(1, int(top_n))
    artifacts = [
        artifact
        for artifact in collect_root_artifacts(repo_root=repo_root, include_directories=include_directories)
        if should_include_artifact(
            artifact,
            repo_root=repo_root,
            categories=normalized_categories,
            recommended_actions=normalized_actions,
            artifact_names=normalized_artifact_names,
        )
    ]
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    batch_dir = output_root / timestamp
    records: list[ArtifactRecord] = []

    if apply and artifacts:
        batch_dir.mkdir(parents=True, exist_ok=True)

    for artifact in artifacts:
        destination = ensure_unique_destination(batch_dir, artifact.name) if apply else batch_dir / artifact.name
        destination_relative = _render_manifest_path(destination, repo_root)
        disposition = describe_root_artifact(artifact)
        record = ArtifactRecord(
            name=artifact.name,
            relative_path=str(artifact.relative_to(repo_root)),
            size_bytes=measure_artifact_size(artifact),
            action="move" if apply else "plan",
            destination=destination_relative,
            reason=disposition.reason,
            category=disposition.category,
            recommended_action=disposition.recommended_action,
            kind=infer_artifact_kind(artifact),
        )
        if apply:
            shutil.move(str(artifact), str(destination))
        records.append(record)

    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "repo_root": str(repo_root),
        "output_root": str(output_root),
        "apply": apply,
        "include_directories": include_directories,
        "selected_categories": list(normalized_categories),
        "selected_recommended_actions": list(normalized_actions),
        "selected_artifact_names": list(normalized_artifact_names),
        "top_n": normalized_top_n,
        "pattern_count": len(ROOT_ARTIFACT_PATTERNS),
        "directory_pattern_count": len(ROOT_ARTIFACT_DIR_PATTERNS) if include_directories else 0,
        "managed_count": len(records),
        "summary": summarize_artifact_records(records, top_n=normalized_top_n),
        "records": [asdict(record) for record in records],
    }

    if apply:
        manifest_path = batch_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest["manifest_path"] = _render_manifest_path(manifest_path, repo_root)

    if write_report is not None:
        report_path = write_report.resolve() if not write_report.is_absolute() else write_report
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest["report_path"] = _render_manifest_path(report_path, repo_root)

    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Move root-level temp/debug artifacts into temp/root-artifacts.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Actually move files/directories instead of printing a dry-run plan.")
    mode.add_argument("--dry-run", action="store_true", help="Explicitly keep plan mode; this is also the default when --apply is omitted.")
    parser.add_argument(
        "--include-directories",
        action="store_true",
        help="Also scan root-level tmp_*/temp_* or tmp-*/temp-* scratch directories that are not tracked by git; hidden .tmp* probe files are always included by the file scanner.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Target directory for archived root artifacts.",
    )
    parser.add_argument(
        "--category",
        action="append",
        default=[],
        help="Only include specific artifact categories; repeat for multiple values.",
    )
    parser.add_argument(
        "--recommended-action",
        action="append",
        default=[],
        help="Only include specific recommended actions; repeat for multiple values.",
    )
    parser.add_argument(
        "--artifact-name",
        action="append",
        default=[],
        help="Only include explicit root artifact names/relative paths; repeat for small-batch archive runs.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=5,
        help="How many largest records / dominant prefixes to keep in the summary; values below 1 are clamped to 1.",
    )
    parser.add_argument(
        "--write-report",
        type=Path,
        default=None,
        help="Optional path to persist the manifest even in dry-run mode,方便做 backlog 快照留档。",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    manifest = move_root_artifacts(
        output_root=args.output_root,
        apply=args.apply,
        categories=args.category,
        recommended_actions=args.recommended_action,
        artifact_names=args.artifact_name,
        include_directories=args.include_directories,
        top_n=args.top_n,
        write_report=args.write_report,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



