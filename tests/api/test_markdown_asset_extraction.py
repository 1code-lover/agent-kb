"""Markdown 内嵌图片解析与导入回执测试。"""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from api.services import kb_service
from server.kb_registry import KBRegistry
from server.markdown_asset_extractor import extract_markdown_embedded_assets


class FakeUploadFile:
    """简化版上传文件对象，用于导入链路测试。"""

    def __init__(self, filename: str, content: bytes, content_type: str = "text/markdown"):
        self.filename = filename
        self.content_type = content_type
        self.file = io.BytesIO(content)


def _patch_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> KBRegistry:
    registry = KBRegistry(storage_path=tmp_path / "storage" / "kb_registry.json")
    monkeypatch.setattr(kb_service, "_registry", registry)
    return registry


def _patch_runtime(monkeypatch: pytest.MonkeyPatch, manager: MagicMock | None = None) -> MagicMock:
    manager = manager or MagicMock()
    manager.load_files.return_value = [SimpleNamespace(metadata={})]
    monkeypatch.setattr(kb_service.runtime_state, "ensure_models_ready", MagicMock())
    monkeypatch.setattr(kb_service.runtime_state, "get_index_manager", MagicMock(return_value=manager))
    return manager


@pytest.fixture(autouse=True)
def _reset_registry_state():
    yield
    kb_service._registry = None


def test_extract_markdown_assets_resolves_local_and_parent_relative_refs(tmp_path: Path) -> None:
    """应能解析 Markdown/HTML 图片，并解析到 KB 内相对路径。"""
    kb_root = tmp_path / "data" / "kb-a"
    doc_path = kb_root / "docs" / "readme.md"
    doc_path.parent.mkdir(parents=True)
    (kb_root / "docs" / "images").mkdir(parents=True)
    (kb_root / "shared").mkdir(parents=True)
    (kb_root / "docs" / "images" / "flow.png").write_bytes(b"png")
    (kb_root / "shared" / "arch.jpg").write_bytes(b"jpg")

    text = """
# Title
![流程图](./images/flow.png)
<img src="../shared/arch.jpg" alt="arch" />
"""

    assets = extract_markdown_embedded_assets(
        markdown_text=text,
        source_doc_path=doc_path,
        kb_root=kb_root,
        source_doc_relative_path="docs/readme.md",
    )

    assert [item["referenced_path"] for item in assets] == ["./images/flow.png", "../shared/arch.jpg"]
    assert [item["status"] for item in assets] == ["ready", "ready"]
    assert assets[0]["resolved_relative_path"] == "docs/images/flow.png"
    assert assets[0]["mime_type"] == "image/png"
    assert assets[0]["source_doc_relative_path"] == "docs/readme.md"
    assert assets[1]["resolved_relative_path"] == "shared/arch.jpg"
    assert assets[1]["mime_type"] == "image/jpeg"


def test_extract_markdown_assets_ignores_remote_and_data_uri_but_marks_invalid_or_missing(tmp_path: Path) -> None:
    """远程资源应忽略，本地越界与缺失资源要显式标注状态。"""
    kb_root = tmp_path / "data" / "kb-a"
    doc_path = kb_root / "docs" / "readme.md"
    doc_path.parent.mkdir(parents=True)

    text = """
![remote](https://example.com/a.png)
![inline](data:image/png;base64,AAAA)
![escape](../../outside.png)
<img src="/absolute/path.png" />
![missing](./missing.png)
"""

    assets = extract_markdown_embedded_assets(
        markdown_text=text,
        source_doc_path=doc_path,
        kb_root=kb_root,
        source_doc_relative_path="docs/readme.md",
    )

    assert [item["referenced_path"] for item in assets] == ["../../outside.png", "/absolute/path.png", "./missing.png"]
    assert [item["status"] for item in assets] == ["invalid", "invalid", "missing"]
    assert assets[0]["message"] == "asset path escapes kb root"
    assert assets[1]["message"] == "absolute asset path is not allowed"
    assert assets[2]["resolved_relative_path"] == "docs/missing.png"


def test_import_files_returns_embedded_assets_for_markdown_with_sibling_image_in_same_batch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Markdown 先上传、图片后上传时，也应基于最终落盘结果解析到 ready 资产。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)

    result = kb_service.import_files(
        [
            FakeUploadFile("readme.md", "![流程图](./images/flow.png)".encode("utf-8")),
            FakeUploadFile("flow.png", b"png", content_type="image/png"),
        ],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["docs/readme.md", "docs/images/flow.png"],
        import_mode="preserve_tree",
    )

    assert manager.load_files.call_count == 2
    markdown_result = result["file_results"][0]
    image_result = result["file_results"][1]

    assert markdown_result["status"] == "indexed"
    assert markdown_result["asset_warning_count"] == 0
    assert len(markdown_result["embedded_assets"]) == 1
    assert markdown_result["embedded_assets"][0]["status"] == "ready"
    assert markdown_result["embedded_assets"][0]["resolved_relative_path"] == "docs/images/flow.png"
    assert image_result["embedded_assets"] == []


def test_import_files_missing_markdown_asset_becomes_warning_not_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """缺失图片不应阻断 Markdown 导入，只应体现在回执 warning。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    _patch_runtime(monkeypatch)

    result = kb_service.import_files(
        [FakeUploadFile("readme.md", "![缺图](./images/missing.png)".encode("utf-8"))],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["docs/readme.md"],
        import_mode="preserve_tree",
    )

    assert result["success_count"] == 1
    assert result["failed_count"] == 0
    assert result["file_results"][0]["status"] == "indexed"
    assert result["file_results"][0]["asset_warning_count"] == 1
    assert result["file_results"][0]["embedded_assets"][0]["status"] == "missing"
    assert result["file_results"][0]["embedded_assets"][0]["resolved_relative_path"] == "docs/images/missing.png"
