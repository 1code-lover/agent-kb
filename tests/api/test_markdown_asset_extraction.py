"""Markdown 内嵌图片解析与导入回执测试。"""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from api.services import asset_service, kb_service
from server.asset_registry import KBAssetRegistry
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


def _patch_asset_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> KBAssetRegistry:
    registry = KBAssetRegistry(base_dir=tmp_path / "storage" / "kb_assets")
    monkeypatch.setattr(asset_service, "_registry", registry)
    return registry


def _patch_runtime(monkeypatch: pytest.MonkeyPatch, manager: MagicMock | None = None) -> MagicMock:
    manager = manager or MagicMock()
    manager.load_files.return_value = [SimpleNamespace(metadata={})]

    def _load_documents(documents, chunk_size, chunk_overlap, kb_id=None, persist=True):
        nodes = []
        for document in documents:
            metadata = dict(getattr(document, "metadata", {}) or {})
            if kb_id is not None:
                metadata["kb_id"] = kb_id
            nodes.append(SimpleNamespace(metadata=metadata, text=getattr(document, "text", "")))
        return nodes

    manager.load_documents.side_effect = _load_documents
    manager.persist_storage.return_value = True
    monkeypatch.setattr(kb_service.runtime_state, "ensure_models_ready", MagicMock())
    monkeypatch.setattr(kb_service.runtime_state, "get_index_manager", MagicMock(return_value=manager))
    return manager


def _patch_image_ocr(
    monkeypatch: pytest.MonkeyPatch,
    *,
    status: str,
    text: str = "",
    error: str | None = None,
    attempted: bool | None = None,
    engine: str = "mock-paddleocr",
) -> None:
    """替换图片 OCR 依赖，便于稳定验证导入链路。"""

    def _fake_extract_image_ocr_result(path: Path, content_type: str) -> dict[str, object]:
        return {
            "status": status,
            "text": text,
            "error": error,
            "attempted": attempted if attempted is not None else status != "skipped",
            "engine": engine,
        }

    monkeypatch.setattr(kb_service, "_extract_image_ocr_result", _fake_extract_image_ocr_result)


@pytest.fixture(autouse=True)
def _reset_registry_state():
    yield
    kb_service._registry = None
    asset_service._registry = None


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


def test_extract_markdown_assets_from_gb18030_file_preserves_non_utf8_image_path(tmp_path: Path) -> None:
    """GB18030 Markdown 文件中的中文图片路径不应被 utf-8 ignore 吞字。"""
    kb_root = tmp_path / "data" / "kb-a"
    doc_path = kb_root / "docs" / "readme.md"
    image_name = "流程图.png"
    image_path = kb_root / "docs" / "images" / image_name
    image_path.parent.mkdir(parents=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"png")
    markdown_text = "产品说明\n![流程图](./images/流程图.png)\n"
    doc_path.write_bytes(markdown_text.encode("gb18030"))

    assets = kb_service.extract_markdown_embedded_assets_from_file(doc_path, kb_root, "docs/readme.md")

    assert len(assets) == 1
    assert assets[0]["referenced_path"] == "./images/流程图.png"
    assert assets[0]["status"] == "ready"
    assert assets[0]["resolved_relative_path"] == "docs/images/流程图.png"


def test_extract_markdown_assets_from_utf16_file_preserves_non_utf8_image_path(tmp_path: Path) -> None:
    """UTF-16 Markdown 文件中的中文图片路径也应保持原样。"""
    kb_root = tmp_path / "data" / "kb-a"
    doc_path = kb_root / "docs" / "readme.md"
    image_name = "流程图.png"
    image_path = kb_root / "docs" / "images" / image_name
    image_path.parent.mkdir(parents=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"png")
    markdown_text = "产品说明\n![流程图](./images/流程图.png)\n"
    doc_path.write_bytes(markdown_text.encode("utf-16"))

    assets = kb_service.extract_markdown_embedded_assets_from_file(doc_path, kb_root, "docs/readme.md")

    assert len(assets) == 1
    assert assets[0]["referenced_path"] == "./images/流程图.png"
    assert assets[0]["status"] == "ready"
    assert assets[0]["resolved_relative_path"] == "docs/images/流程图.png"


def test_extract_markdown_assets_prefers_logical_relative_path_and_batch_alias_when_files_are_flattened(
    tmp_path: Path,
) -> None:
    """flatten 落盘时，Markdown 仍应按逻辑相对路径解析，再映射到实际改名文件。"""
    kb_root = tmp_path / "data" / "kb-a"
    doc_path = kb_root / "readme_flat.md"
    asset_path = kb_root / "flow_flat.png"
    kb_root.mkdir(parents=True)
    doc_path.write_text("![流程图](./images/flow.png)\n", encoding="utf-8")
    asset_path.write_bytes(b"png")

    assets = extract_markdown_embedded_assets(
        markdown_text=doc_path.read_text(encoding="utf-8"),
        source_doc_path=doc_path,
        kb_root=kb_root,
        source_doc_relative_path="docs/readme.md",
        path_aliases={"docs/images/flow.png": "flow_flat.png"},
    )

    assert len(assets) == 1
    assert assets[0]["referenced_path"] == "./images/flow.png"
    assert assets[0]["logical_relative_path"] == "docs/images/flow.png"
    assert assets[0]["resolved_relative_path"] == "flow_flat.png"
    assert assets[0]["status"] == "ready"
    assert Path(assets[0]["path"]).name == "flow_flat.png"
