"""粮仓知识库分批导入脚本。

脚本默认只生成 dry-run 计划；只有显式传入 --apply 才会调用后端
/api/kb/file/import 接口上传文件。设计目标是按分类分批导入
 data/grain-knowledge-base/docs/01-* 到 07-* 主资料，默认跳过重复副本目录。
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PRIMARY_CATEGORY_PREFIXES = tuple(f"{idx:02d}-" for idx in range(1, 8))
DEFAULT_EXCLUDED_PREFIXES = ("98-duplicates-to-review", "99-other")
SUPPORTED_EXTENSIONS = {".docx", ".pdf", ".txt", ".md"}


@dataclass(frozen=True)
class ImportFile:
    """待导入文件描述。"""

    path: str
    category: str
    file_name: str
    extension: str
    size: int


@dataclass(frozen=True)
class ImportBatch:
    """单批导入计划。"""

    batch_no: int
    category: str
    files: list[ImportFile]


@dataclass(frozen=True)
class BatchResult:
    """单批导入结果。"""

    batch_no: int
    category: str
    file_count: int
    status: str
    response: Any | None = None
    error: str | None = None


def utc_timestamp() -> str:
    """返回适合文件名和报告记录的 UTC 时间戳。"""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _is_supported_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def discover_files(
    kb_root: str | Path,
    *,
    categories: list[str] | None = None,
    include_other: bool = False,
    include_duplicates: bool = False,
    extensions: set[str] | None = None,
) -> list[ImportFile]:
    """扫描粮仓知识库主资料文件。"""
    root = Path(kb_root).resolve()
    docs_root = root / "docs"
    if not docs_root.exists():
        raise FileNotFoundError(f"docs 目录不存在: {docs_root}")

    allowed_categories = set(categories or [])
    allowed_extensions = {ext.lower() for ext in (extensions or SUPPORTED_EXTENSIONS)}
    discovered: list[ImportFile] = []

    for category_dir in sorted(path for path in docs_root.iterdir() if path.is_dir()):
        category = category_dir.name
        is_primary = category.startswith(PRIMARY_CATEGORY_PREFIXES)
        if allowed_categories and category not in allowed_categories:
            continue
        if category.startswith("98-") and not include_duplicates:
            continue
        if category.startswith("99-") and not include_other:
            continue
        if not allowed_categories and not is_primary and category.startswith(DEFAULT_EXCLUDED_PREFIXES):
            continue
        if not allowed_categories and not is_primary:
            continue

        for file_path in sorted(category_dir.rglob("*")):
            if file_path.name.lower() == "readme.md":
                continue
            if not _is_supported_file(file_path):
                continue
            extension = file_path.suffix.lower()
            if extension not in allowed_extensions:
                continue
            discovered.append(
                ImportFile(
                    path=str(file_path),
                    category=category,
                    file_name=file_path.name,
                    extension=extension,
                    size=file_path.stat().st_size,
                )
            )

    return discovered


def _import_file_from_path(path: Path, kb_root: Path, allowed_extensions: set[str]) -> ImportFile:
    """从精确路径构建导入文件描述。"""
    file_path = path.expanduser().resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"待导入文件不存在: {file_path}")
    if not _is_supported_file(file_path):
        raise ValueError(f"不支持的导入文件类型: {file_path}")
    extension = file_path.suffix.lower()
    if extension not in allowed_extensions:
        raise ValueError(f"文件扩展名不在允许范围内: {file_path}")

    docs_root = kb_root / "docs"
    try:
        relative_to_docs = file_path.relative_to(docs_root)
        category = relative_to_docs.parts[0] if len(relative_to_docs.parts) > 1 else docs_root.name
    except ValueError:
        category = file_path.parent.name
    return ImportFile(
        path=str(file_path),
        category=category,
        file_name=file_path.name,
        extension=extension,
        size=file_path.stat().st_size,
    )


def discover_explicit_files(
    kb_root: str | Path,
    file_paths: list[str],
    *,
    extensions: set[str] | None = None,
) -> list[ImportFile]:
    """按用户显式传入的文件路径构建导入列表。"""
    root = Path(kb_root).resolve()
    allowed_extensions = {ext.lower() for ext in (extensions or SUPPORTED_EXTENSIONS)}
    discovered: list[ImportFile] = []
    seen: set[Path] = set()
    for raw_path in file_paths:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        file_path = candidate.resolve()
        if file_path in seen:
            continue
        discovered.append(_import_file_from_path(file_path, root, allowed_extensions))
        seen.add(file_path)
    return discovered


def build_batches(files: list[ImportFile], batch_size: int) -> list[ImportBatch]:
    """按分类和 batch_size 构建导入批次。"""
    if batch_size <= 0:
        raise ValueError("batch_size 必须大于 0")

    batches: list[ImportBatch] = []
    batch_no = 1
    categories = sorted({item.category for item in files})
    for category in categories:
        category_files = [item for item in files if item.category == category]
        for start in range(0, len(category_files), batch_size):
            batches.append(
                ImportBatch(
                    batch_no=batch_no,
                    category=category,
                    files=category_files[start : start + batch_size],
                )
            )
            batch_no += 1
    return batches


def build_plan(
    *,
    kb_root: str | Path,
    kb_id: str,
    chunk_size: int,
    chunk_overlap: int,
    batch_size: int,
    categories: list[str] | None = None,
    include_other: bool = False,
    include_duplicates: bool = False,
    extensions: set[str] | None = None,
    limit: int | None = None,
    file_paths: list[str] | None = None,
) -> dict[str, Any]:
    """生成导入计划。"""
    explicit_files = bool(file_paths)
    if file_paths:
        files = discover_explicit_files(kb_root, file_paths, extensions=extensions)
    else:
        files = discover_files(
            kb_root,
            categories=categories,
            include_other=include_other,
            include_duplicates=include_duplicates,
            extensions=extensions,
        )
    if limit is not None:
        files = files[:limit]
    batches = build_batches(files, batch_size)
    return {
        "mode": "dry-run",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kb_id": kb_id,
        "kb_root": str(Path(kb_root).resolve()),
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "batch_size": batch_size,
        "file_count": len(files),
        "batch_count": len(batches),
        "categories": sorted({item.category for item in files}),
        "skip_policy": {
            "duplicates": not include_duplicates,
            "other": not include_other,
            "readme_files": True,
            "explicit_files": explicit_files,
        },
        "batches": [
            {
                "batch_no": batch.batch_no,
                "category": batch.category,
                "file_count": len(batch.files),
                "files": [asdict(item) for item in batch.files],
            }
            for batch in batches
        ],
    }


def _build_multipart_body(
    *,
    batch: ImportBatch,
    kb_id: str,
    chunk_size: int,
    chunk_overlap: int,
    boundary: str,
) -> bytes:
    """构造 multipart/form-data 请求体。"""
    chunks: list[bytes] = []

    def add_field(name: str, value: str) -> None:
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        chunks.append(value.encode("utf-8"))
        chunks.append(b"\r\n")

    def add_file(field_name: str, file_item: ImportFile) -> None:
        file_path = Path(file_item.path)
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            (
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{file_path.name}"\r\n'
            ).encode("utf-8")
        )
        chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        chunks.append(file_path.read_bytes())
        chunks.append(b"\r\n")

    add_field("kb_id", kb_id)
    add_field("chunk_size", str(chunk_size))
    add_field("chunk_overlap", str(chunk_overlap))
    for file_item in batch.files:
        add_file("files", file_item)
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks)


def post_batch(
    *,
    api_base_url: str,
    batch: ImportBatch,
    kb_id: str,
    chunk_size: int,
    chunk_overlap: int,
    timeout: int,
) -> BatchResult:
    """上传单个批次。"""
    boundary = f"----grain-kb-{uuid.uuid4().hex}"
    body = _build_multipart_body(
        batch=batch,
        kb_id=kb_id,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        boundary=boundary,
    )
    url = api_base_url.rstrip("/") + "/api/kb/file/import"
    request = Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - local operator tool.
            text = response.read().decode("utf-8")
        try:
            parsed: Any = json.loads(text)
        except json.JSONDecodeError:
            parsed = text
        return BatchResult(
            batch_no=batch.batch_no,
            category=batch.category,
            file_count=len(batch.files),
            status="passed",
            response=parsed,
        )
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return BatchResult(
            batch_no=batch.batch_no,
            category=batch.category,
            file_count=len(batch.files),
            status="failed",
            error=f"HTTP {exc.code}: {detail}",
        )
    except URLError as exc:
        return BatchResult(
            batch_no=batch.batch_no,
            category=batch.category,
            file_count=len(batch.files),
            status="failed",
            error=f"URL error: {exc.reason}",
        )


def run_import(
    *,
    api_base_url: str,
    plan: dict[str, Any],
    timeout: int,
    stop_on_error: bool,
) -> dict[str, Any]:
    """按计划执行导入。"""
    batches = [
        ImportBatch(
            batch_no=item["batch_no"],
            category=item["category"],
            files=[ImportFile(**file_item) for file_item in item["files"]],
        )
        for item in plan["batches"]
    ]
    results: list[BatchResult] = []
    for batch in batches:
        result = post_batch(
            api_base_url=api_base_url,
            batch=batch,
            kb_id=plan["kb_id"],
            chunk_size=plan["chunk_size"],
            chunk_overlap=plan["chunk_overlap"],
            timeout=timeout,
        )
        results.append(result)
        if result.status == "failed" and stop_on_error:
            break

    passed = sum(1 for item in results if item.status == "passed")
    failed = sum(1 for item in results if item.status == "failed")
    report = dict(plan)
    report["mode"] = "apply"
    report["api_base_url"] = api_base_url
    report["executed_batch_count"] = len(results)
    report["passed_batch_count"] = passed
    report["failed_batch_count"] = failed
    report["status"] = "passed" if failed == 0 and len(results) == len(batches) else "failed"
    report["results"] = [asdict(item) for item in results]
    return report


def write_report(report: dict[str, Any], output_dir: str | Path) -> Path:
    """写入 JSON 报告。"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    path = output_path / f"grain-kb-import-report-{utc_timestamp()}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="粮仓知识库分批导入工具")
    parser.add_argument("--kb-root", default="data/grain-knowledge-base")
    parser.add_argument("--kb-id", default="grain-knowledge-base")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--chunk-overlap", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--category", action="append", dest="categories")
    parser.add_argument("--extension", action="append", dest="extensions")
    parser.add_argument("--file", action="append", dest="file_paths")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--include-other", action="store_true")
    parser.add_argument("--include-duplicates", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument("--output-dir", default="data/grain-knowledge-base/qa")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    extensions = {ext if ext.startswith(".") else f".{ext}" for ext in args.extensions or []} or None
    plan = build_plan(
        kb_root=args.kb_root,
        kb_id=args.kb_id,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        batch_size=args.batch_size,
        categories=args.categories,
        include_other=args.include_other,
        include_duplicates=args.include_duplicates,
        extensions=extensions,
        limit=args.limit,
        file_paths=args.file_paths,
    )
    if args.apply:
        report = run_import(
            api_base_url=args.api_base_url,
            plan=plan,
            timeout=args.timeout,
            stop_on_error=args.stop_on_error,
        )
    else:
        report = plan
    report_path = write_report(report, args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report: {report_path}")


if __name__ == "__main__":
    main()
