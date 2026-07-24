"""图片资产导入与接口测试。"""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.services import asset_service, kb_service
from server.asset_registry import KBAssetRegistry
from server.kb_registry import KBRegistry

client = TestClient(app)


class FakeUploadFile:
    """简化版上传文件对象，用于导入链路测试。"""

    def __init__(self, filename: str, content: bytes, content_type: str) -> None:
        self.filename = filename
        self.content_type = content_type
        self.file = io.BytesIO(content)


@pytest.fixture(autouse=True)
def _reset_registry_state() -> None:
    yield
    kb_service._registry = None
    asset_service._registry = None


def _patch_kb_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> KBRegistry:
    registry = KBRegistry(storage_path=tmp_path / "storage" / "kb_registry.json")
    monkeypatch.setattr(kb_service, "_registry", registry)
    return registry


def _patch_asset_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> KBAssetRegistry:
    registry = KBAssetRegistry(base_dir=tmp_path / "storage" / "kb_assets")
    monkeypatch.setattr(asset_service, "_registry", registry)
    return registry


def _patch_runtime(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    manager = MagicMock()

    def _load_files(paths, chunk_size, chunk_overlap, kb_id=None):
        path = Path(paths[0])
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
            return []
        return [SimpleNamespace(metadata={})]

    manager.load_files.side_effect = _load_files
    monkeypatch.setattr(kb_service.runtime_state, "ensure_models_ready", MagicMock())
    monkeypatch.setattr(kb_service.runtime_state, "get_index_manager", MagicMock(return_value=manager))
    return manager


def test_image_import_registers_standalone_asset_even_when_index_returns_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """纯图片文件即使没有文本切块，也应登记为 standalone asset。"""
    monkeypatch.chdir(tmp_path)
    kb_registry = _patch_kb_registry(monkeypatch, tmp_path)
    _patch_asset_registry(monkeypatch, tmp_path)
    kb_registry.create_kb("kb-a", "KB A")
    _patch_runtime(monkeypatch)

    result = kb_service.import_files(
        [FakeUploadFile("flow.png", b"png", content_type="image/png")],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["docs/flow.png"],
        import_mode="preserve_tree",
    )

    assert result["file_results"][0]["status"] == "empty"

    assets = asset_service.list_assets("kb-a")
    assert len(assets) == 1
    assert assets[0]["asset_role"] == "standalone"
    assert assets[0]["status"] == "active"
    assert assets[0]["relative_path"] == "docs/flow.png"
    assert assets[0]["mime_type"] == "image/png"


def test_asset_routes_list_and_preview_registered_assets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """导入图片与 Markdown 后，应能通过资产接口列出并预览。"""
    monkeypatch.chdir(tmp_path)
    kb_registry = _patch_kb_registry(monkeypatch, tmp_path)
    _patch_asset_registry(monkeypatch, tmp_path)
    kb_registry.create_kb("kb-a", "KB A")
    kb_registry.create_kb("kb-b", "KB B")
    _patch_runtime(monkeypatch)

    kb_service.import_files(
        [
            FakeUploadFile("readme.md", "![流程图](./images/flow.png)".encode("utf-8"), content_type="text/markdown"),
            FakeUploadFile("flow.png", b"png", content_type="image/png"),
        ],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["docs/readme.md", "docs/images/flow.png"],
        import_mode="preserve_tree",
    )

    registered_assets = asset_service.list_assets("kb-a")
    embedded_asset = next(item for item in registered_assets if item["asset_role"] == "embedded")

    resp = client.get("/api/kb/assets", params={"kb_id": "kb-a"})
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert len(items) == 2
    assert {item["asset_role"] for item in items} == {"standalone", "embedded"}

    isolated = client.get("/api/kb/assets", params={"kb_id": "kb-b"})
    assert isolated.status_code == 200
    assert isolated.json()["data"]["items"] == []

    preview = client.get(f"/api/kb/assets/{embedded_asset['asset_id']}", params={"kb_id": "kb-a"})
    assert preview.status_code == 200
    payload = preview.json()["data"]
    assert payload["asset_id"] == embedded_asset["asset_id"]
    assert payload["source_doc_relative_path"] == "docs/readme.md"
    assert payload["locator"]["referenced_path"] == "./images/flow.png"
    assert payload["status"] == "active"

    blocked = client.get(f"/api/kb/assets/{embedded_asset['asset_id']}", params={"kb_id": "kb-b"})
    assert blocked.status_code == 404
