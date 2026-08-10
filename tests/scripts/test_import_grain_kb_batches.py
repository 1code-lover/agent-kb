"""粮仓知识库分批导入脚本测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from scripts import import_grain_kb_batches as importer


def _write_file(path: Path, content: bytes = b"content") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _make_kb_root(tmp_path: Path) -> Path:
    root = tmp_path / "grain-knowledge-base"
    _write_file(root / "docs" / "01-standards-regulations" / "policy.docx")
    _write_file(root / "docs" / "01-standards-regulations" / "manual.pdf")
    _write_file(root / "docs" / "01-standards-regulations" / "README.md")
    _write_file(root / "docs" / "02-storage-operations" / "operation.docx")
    _write_file(root / "docs" / "07-templates-samples" / "sample.txt")
    _write_file(root / "docs" / "08-out-of-scope" / "ignored.docx")
    _write_file(root / "docs" / "98-duplicates-to-review" / "duplicate.docx")
    _write_file(root / "docs" / "99-other" / "other.docx")
    _write_file(root / "docs" / "01-standards-regulations" / "unsupported.xlsx")
    return root


def test_discover_files_scans_only_primary_categories_by_default(tmp_path: Path) -> None:
    root = _make_kb_root(tmp_path)

    files = importer.discover_files(root)

    names = [item.file_name for item in files]
    assert names == ["manual.pdf", "policy.docx", "operation.docx", "sample.txt"]
    assert {item.category for item in files} == {
        "01-standards-regulations",
        "02-storage-operations",
        "07-templates-samples",
    }


def test_discover_files_skips_readme_duplicates_other_and_unsupported(tmp_path: Path) -> None:
    root = _make_kb_root(tmp_path)

    files = importer.discover_files(root)

    names = {item.file_name for item in files}
    assert "README.md" not in names
    assert "duplicate.docx" not in names
    assert "other.docx" not in names
    assert "unsupported.xlsx" not in names


def test_discover_files_honors_category_filter(tmp_path: Path) -> None:
    root = _make_kb_root(tmp_path)

    files = importer.discover_files(root, categories=["02-storage-operations"])

    assert [item.file_name for item in files] == ["operation.docx"]
    assert {item.category for item in files} == {"02-storage-operations"}


def test_discover_files_honors_extension_filter(tmp_path: Path) -> None:
    root = _make_kb_root(tmp_path)

    files = importer.discover_files(root, extensions={".docx"})

    assert [item.file_name for item in files] == ["policy.docx", "operation.docx"]
    assert {item.extension for item in files} == {".docx"}


def test_discover_explicit_files_uses_exact_paths_and_deduplicates(tmp_path: Path) -> None:
    root = _make_kb_root(tmp_path)
    source = root / "docs" / "99-other" / "other.docx"

    files = importer.discover_explicit_files(root, [str(source), str(source)])

    assert len(files) == 1
    assert files[0].file_name == "other.docx"
    assert files[0].category == "99-other"
    assert files[0].path == str(source.resolve())


def test_discover_explicit_files_rejects_unsupported_extension(tmp_path: Path) -> None:
    root = _make_kb_root(tmp_path)
    source = root / "docs" / "01-standards-regulations" / "unsupported.xlsx"

    with pytest.raises(ValueError, match="不支持的导入文件类型"):
        importer.discover_explicit_files(root, [str(source)])


def test_build_batches_groups_by_category_and_respects_batch_size() -> None:
    files = [
        importer.ImportFile("/tmp/a1.docx", "02-b", "a1.docx", ".docx", 1),
        importer.ImportFile("/tmp/a2.docx", "02-b", "a2.docx", ".docx", 1),
        importer.ImportFile("/tmp/a3.docx", "02-b", "a3.docx", ".docx", 1),
        importer.ImportFile("/tmp/b1.docx", "01-a", "b1.docx", ".docx", 1),
    ]

    batches = importer.build_batches(files, batch_size=2)

    assert [(batch.batch_no, batch.category, len(batch.files)) for batch in batches] == [
        (1, "01-a", 1),
        (2, "02-b", 2),
        (3, "02-b", 1),
    ]


def test_build_batches_rejects_non_positive_batch_size() -> None:
    with pytest.raises(ValueError, match="batch_size"):
        importer.build_batches([], batch_size=0)


def test_build_plan_reports_counts_and_skip_policy(tmp_path: Path) -> None:
    root = _make_kb_root(tmp_path)

    plan = importer.build_plan(
        kb_root=root,
        kb_id="grain-knowledge-base",
        chunk_size=512,
        chunk_overlap=50,
        batch_size=2,
        limit=3,
    )

    assert plan["mode"] == "dry-run"
    assert plan["kb_id"] == "grain-knowledge-base"
    assert plan["file_count"] == 3
    assert plan["batch_count"] == 2
    assert plan["skip_policy"] == {
        "duplicates": True,
        "other": True,
        "readme_files": True,
        "explicit_files": False,
    }
    assert plan["categories"] == ["01-standards-regulations", "02-storage-operations"]


def test_build_plan_uses_explicit_files_instead_of_directory_filters(tmp_path: Path) -> None:
    root = _make_kb_root(tmp_path)
    source = root / "docs" / "99-other" / "other.docx"

    plan = importer.build_plan(
        kb_root=root,
        kb_id="grain-knowledge-base",
        chunk_size=512,
        chunk_overlap=50,
        batch_size=2,
        file_paths=[str(source)],
    )

    assert plan["file_count"] == 1
    assert plan["categories"] == ["99-other"]
    assert plan["skip_policy"]["explicit_files"] is True
    assert plan["batches"][0]["files"][0]["file_name"] == "other.docx"


def test_build_multipart_body_contains_fields_and_file_content(tmp_path: Path) -> None:
    source = _write_file(tmp_path / "policy.docx", b"docx-bytes")
    file_item = importer.ImportFile(str(source), "01-standards-regulations", source.name, ".docx", 10)
    batch = importer.ImportBatch(batch_no=1, category="01-standards-regulations", files=[file_item])

    body = importer._build_multipart_body(  # noqa: SLF001 - 覆盖脚本内部 multipart 构造。
        batch=batch,
        kb_id="grain-knowledge-base",
        chunk_size=512,
        chunk_overlap=50,
        boundary="boundary-test",
    )

    assert b'name="kb_id"' in body
    assert b"grain-knowledge-base" in body
    assert b'name="chunk_size"' in body
    assert b"512" in body
    assert b'name="chunk_overlap"' in body
    assert b"50" in body
    assert b'name="files"; filename="policy.docx"' in body
    assert b"docx-bytes" in body
    assert body.endswith(b"--boundary-test--\r\n")


def test_run_import_uses_post_batch_and_stops_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    plan: dict[str, Any] = {
        "mode": "dry-run",
        "kb_id": "grain-knowledge-base",
        "chunk_size": 512,
        "chunk_overlap": 50,
        "batches": [
            {
                "batch_no": 1,
                "category": "01-a",
                "files": [
                    {
                        "path": "/tmp/a.docx",
                        "category": "01-a",
                        "file_name": "a.docx",
                        "extension": ".docx",
                        "size": 1,
                    }
                ],
            },
            {
                "batch_no": 2,
                "category": "02-b",
                "files": [
                    {
                        "path": "/tmp/b.docx",
                        "category": "02-b",
                        "file_name": "b.docx",
                        "extension": ".docx",
                        "size": 1,
                    }
                ],
            },
        ],
    }
    calls: list[int] = []

    def fake_post_batch(**kwargs: Any) -> importer.BatchResult:
        batch = kwargs["batch"]
        calls.append(batch.batch_no)
        return importer.BatchResult(
            batch_no=batch.batch_no,
            category=batch.category,
            file_count=len(batch.files),
            status="failed",
            error="boom",
        )

    monkeypatch.setattr(importer, "post_batch", fake_post_batch)

    report = importer.run_import(
        api_base_url="http://127.0.0.1:18080",
        plan=plan,
        timeout=1,
        stop_on_error=True,
    )

    assert calls == [1]
    assert report["mode"] == "apply"
    assert report["executed_batch_count"] == 1
    assert report["passed_batch_count"] == 0
    assert report["failed_batch_count"] == 1
    assert report["status"] == "failed"
