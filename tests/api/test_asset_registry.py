"""资产注册表测试。"""

from __future__ import annotations

import json
from pathlib import Path

from server.asset_registry import KBAssetRegistry


def _build_asset(asset_id: str, *, kb_id: str, relative_path: str, title: str, asset_role: str = "standalone") -> dict:
    return {
        "asset_id": asset_id,
        "kb_id": kb_id,
        "asset_type": "image",
        "asset_role": asset_role,
        "title": title,
        "path": f"/tmp/{kb_id}/{relative_path}",
        "relative_path": relative_path,
        "mime_type": "image/png",
        "source_doc_id": None,
        "source_doc_path": f"/tmp/{kb_id}/{relative_path}",
        "source_doc_relative_path": relative_path,
        "locator": None,
        "status": "active",
    }


def test_asset_registry_upserts_assets_and_keeps_kb_isolation(tmp_path: Path) -> None:
    """资产注册表应支持 upsert，并按 KB 分文件隔离持久化。"""
    registry = KBAssetRegistry(base_dir=tmp_path / "storage" / "kb_assets")

    registry.upsert_assets(
        "kb-a",
        [
            _build_asset("asset-1", kb_id="kb-a", relative_path="docs/flow.png", title="流程图"),
            _build_asset(
                "asset-2",
                kb_id="kb-a",
                relative_path="docs/images/arch.png",
                title="架构图",
                asset_role="embedded",
            ),
        ],
    )
    registry.upsert_assets(
        "kb-a",
        [_build_asset("asset-1", kb_id="kb-a", relative_path="docs/flow.png", title="更新后的流程图")],
    )
    registry.upsert_assets(
        "kb-b",
        [_build_asset("asset-9", kb_id="kb-b", relative_path="ops/runbook.png", title="运维图")],
    )

    items_a = registry.list_assets("kb-a")
    items_b = registry.list_assets("kb-b")
    assert {item["asset_id"] for item in items_a} == {"asset-1", "asset-2"}
    assert {item["asset_id"] for item in items_b} == {"asset-9"}
    assert next(item for item in items_a if item["asset_id"] == "asset-1")["title"] == "更新后的流程图"

    payload_a = json.loads((tmp_path / "storage" / "kb_assets" / "kb-a.json").read_text(encoding="utf-8"))
    payload_b = json.loads((tmp_path / "storage" / "kb_assets" / "kb-b.json").read_text(encoding="utf-8"))
    assert len(payload_a) == 2
    assert len(payload_b) == 1
    assert all(item["kb_id"] == "kb-a" for item in payload_a)
    assert all(item["kb_id"] == "kb-b" for item in payload_b)


def test_asset_registry_delete_kb_removes_registry_file(tmp_path: Path) -> None:
    """删除 KB 资产注册表时，应移除对应的存储文件。"""
    registry = KBAssetRegistry(base_dir=tmp_path / "storage" / "kb_assets")
    registry.upsert_assets(
        "kb-a",
        [_build_asset("asset-1", kb_id="kb-a", relative_path="docs/flow.png", title="流程图")],
    )

    storage_path = tmp_path / "storage" / "kb_assets" / "kb-a.json"
    assert storage_path.exists() is True

    registry.delete_kb("kb-a")

    assert storage_path.exists() is False
    assert registry.list_assets("kb-a") == []
