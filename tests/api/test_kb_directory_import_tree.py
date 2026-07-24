"""目录导入保留树结构测试。"""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.services import kb_service
from server.kb_errors import KBValidationError
from server.kb_registry import KBRegistry

client = TestClient(app)


class FakeUploadFile:
    """简化版上传文件对象，用于目录导入服务测试。"""

    def __init__(self, filename: str = "a.md", content: bytes = b"hello", content_type: str = "text/markdown"):
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


def test_import_files_preserve_tree_writes_nested_path_and_echoes_relative_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """preserve_tree 模式应按 relative_path 落盘，并回显 folder 语义。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    manager = _patch_runtime(monkeypatch)

    result = kb_service.import_files(
        [FakeUploadFile("a.md", b"alpha")],
        128,
        16,
        kb_id="kb-a",
        relative_paths=["design/specs/a.md"],
        import_mode="preserve_tree",
    )

    target = tmp_path / "data" / "kb-a" / "design" / "specs" / "a.md"
    assert target.is_file()
    assert manager.load_files.call_args.args[0] == [target.resolve()]
    assert result["file_results"][0]["relative_path"] == "design/specs/a.md"
    assert result["file_results"][0]["folder_path"] == "design/specs"


def test_import_files_preserve_tree_rejects_relative_path_count_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """relative_paths 数量必须与 files 一一对应。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    _patch_runtime(monkeypatch)

    with pytest.raises(KBValidationError):
        kb_service.import_files(
            [FakeUploadFile("a.md"), FakeUploadFile("b.md")],
            128,
            16,
            kb_id="kb-a",
            relative_paths=["design/a.md"],
            import_mode="preserve_tree",
        )


def test_import_files_preserve_tree_rejects_path_traversal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """目录导入不得接受越界 relative_path。"""
    monkeypatch.chdir(tmp_path)
    registry = _patch_registry(monkeypatch, tmp_path)
    registry.create_kb("kb-a", "KB A")
    _patch_runtime(monkeypatch)

    with pytest.raises(KBValidationError):
        kb_service.import_files(
            [FakeUploadFile("a.md")],
            128,
            16,
            kb_id="kb-a",
            relative_paths=["../escape.md"],
            import_mode="preserve_tree",
        )


def test_kb_file_import_route_passes_relative_paths_and_import_mode() -> None:
    """路由层应把 relative_paths 与 import_mode 原样转给服务层。"""
    with patch("api.routers.kb.kb_service.import_files") as mock_import_files:
        mock_import_files.return_value = {"success_count": 1, "kb_id": "kb-a"}

        resp = client.post(
            "/api/kb/file/import",
            data={
                "chunk_size": "128",
                "chunk_overlap": "16",
                "kb_id": "kb-a",
                "relative_paths": "design/specs/a.md",
                "import_mode": "preserve_tree",
            },
            files={"files": ("a.md", b"alpha", "text/markdown")},
        )

    assert resp.status_code == 200
    mock_import_files.assert_called_once()
    args = mock_import_files.call_args.args
    kwargs = mock_import_files.call_args.kwargs
    assert len(args[0]) == 1
    assert args[1:] == (128, 16)
    assert kwargs == {
        "kb_id": "kb-a",
        "relative_paths": ["design/specs/a.md"],
        "import_mode": "preserve_tree",
    }
