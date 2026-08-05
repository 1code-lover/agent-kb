"""KB 路由契约补充测试。"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.app import app
from api.routers import kb as kb_router
from server.kb_errors import (
    KBConflictError,
    KBConsistencyError,
    KBNotFoundError,
    KBServiceError,
    KBUnavailableError,
    KBValidationError,
)

client = TestClient(app)


class GenericKBError(KBServiceError):
    """用于覆盖路由层兜底映射分支的通用异常。"""


@pytest.mark.parametrize(
    ("exc", "expected_status"),
    [
        (KBValidationError("参数非法"), 400),
        (KBUnavailableError("知识库不可用"), 400),
        (KBNotFoundError("知识库不存在"), 404),
        (KBConflictError("知识库冲突"), 409),
        (KBConsistencyError("知识库状态不一致"), 500),
        (GenericKBError("未知知识库异常"), 400),
    ],
)
def test_raise_http_from_kb_error_maps_status_code(exc: KBServiceError, expected_status: int) -> None:
    """稳定知识库异常应被映射为明确的 HTTP 状态码。"""
    with pytest.raises(HTTPException) as caught:
        kb_router._raise_http_from_kb_error(exc)

    assert caught.value.status_code == expected_status
    assert caught.value.detail == exc.message


def test_list_docs_route_passes_kb_id_to_service() -> None:
    """文档列表路由应把 kb_id 原样透传给服务层。"""
    docs = [{"doc_id": "doc-1", "kb_id": "kb-a"}]
    with patch("api.routers.kb.kb_service.list_docs", return_value=docs) as mock_list:
        resp = client.get("/api/kb/list", params={"kb_id": "kb-a"})

    assert resp.status_code == 200
    assert resp.json()["data"]["docs"] == docs
    mock_list.assert_called_once_with(kb_id="kb-a")


def test_list_docs_route_maps_runtime_error_to_503() -> None:
    """文档列表路由遇到运行时错误时应返回 503。"""
    with patch("api.routers.kb.kb_service.list_docs", side_effect=RuntimeError("index unavailable")):
        resp = client.get("/api/kb/list", params={"kb_id": "kb-a"})

    assert resp.status_code == 503
    assert resp.json()["message"] == "index unavailable"


def test_list_folders_route_maps_runtime_error_to_503() -> None:
    """目录树路由遇到运行时错误时应返回 503。"""
    with patch("api.routers.kb.folder_service.list_folders", side_effect=RuntimeError("folder unavailable")):
        resp = client.get("/api/kb/folders", params={"kb_id": "kb-a"})

    assert resp.status_code == 503
    assert resp.json()["message"] == "folder unavailable"


def test_delete_docs_route_returns_service_payload() -> None:
    """文档删除路由应返回服务层回执。"""
    payload = {"deleted_doc_ids": ["doc-1"], "deleted_count": 1}
    with patch("api.routers.kb.kb_service.delete_docs", return_value=payload) as mock_delete:
        resp = client.request(
            "DELETE",
            "/api/kb/docs",
            json={"kb_id": "kb-a", "doc_ids": ["doc-1"], "paths": []},
        )

    assert resp.status_code == 200
    assert resp.json()["data"] == payload
    request = mock_delete.call_args.args[0]
    assert request.kb_id == "kb-a"
    assert request.doc_ids == ["doc-1"]
    assert request.paths == []


def test_delete_docs_route_maps_runtime_error_to_503() -> None:
    """文档删除路由遇到运行时错误时应返回 503。"""
    with patch("api.routers.kb.kb_service.delete_docs", side_effect=RuntimeError("delete unavailable")):
        resp = client.request(
            "DELETE",
            "/api/kb/docs",
            json={"kb_id": "kb-a", "doc_ids": ["doc-1"], "paths": []},
        )

    assert resp.status_code == 503
    assert resp.json()["message"] == "delete unavailable"


def test_import_files_route_passes_relative_paths_and_import_mode() -> None:
    """文件导入路由应透传相对路径与导入模式。"""
    payload = {"imported": 1, "kb_id": "kb-a", "receipt_id": "r-1"}
    with patch("api.routers.kb.kb_service.import_files", return_value=payload) as mock_import:
        resp = client.post(
            "/api/kb/file/import",
            data={
                "chunk_size": "1024",
                "chunk_overlap": "128",
                "kb_id": "kb-a",
                "relative_paths": "docs/notes.md",
                "import_mode": "preserve_tree",
            },
            files=[("files", ("notes.md", b"# notes", "text/markdown"))],
        )

    assert resp.status_code == 200
    assert resp.json()["data"] == payload
    args = mock_import.call_args.args
    kwargs = mock_import.call_args.kwargs
    assert [uploaded.filename for uploaded in args[0]] == ["notes.md"]
    assert args[1] == 1024
    assert args[2] == 128
    assert kwargs == {
        "kb_id": "kb-a",
        "relative_paths": ["docs/notes.md"],
        "import_mode": "preserve_tree",
    }


def test_import_files_route_maps_runtime_error_to_503() -> None:
    """文件导入路由遇到运行时错误时应返回 503。"""
    with patch("api.routers.kb.kb_service.import_files", side_effect=RuntimeError("import unavailable")):
        resp = client.post(
            "/api/kb/file/import",
            data={"kb_id": "kb-a"},
            files=[("files", ("notes.md", b"# notes", "text/markdown"))],
        )

    assert resp.status_code == 503
    assert resp.json()["message"] == "import unavailable"


def test_web_import_route_maps_runtime_error_to_503() -> None:
    """网页导入路由遇到运行时错误时应返回 503。"""
    with patch("api.routers.kb.kb_service.import_urls", side_effect=RuntimeError("crawler unavailable")):
        resp = client.post(
            "/api/kb/web/import",
            json={"urls": ["https://example.com"], "kb_id": "kb-a"},
        )

    assert resp.status_code == 503
    assert resp.json()["message"] == "crawler unavailable"


def test_latest_import_receipt_route_maps_runtime_error_to_503() -> None:
    """最近导入回执路由遇到运行时错误时应返回 503。"""
    with patch("api.routers.kb.kb_service.get_latest_import_receipt", side_effect=RuntimeError("receipt unavailable")):
        resp = client.get("/api/kb/import-receipt/latest", params={"kb_id": "kb-a"})

    assert resp.status_code == 503
    assert resp.json()["message"] == "receipt unavailable"


def test_preview_route_maps_runtime_error_to_503() -> None:
    """预览路由遇到运行时错误时应返回 503。"""
    with patch("api.routers.kb.kb_service.preview_document", side_effect=RuntimeError("preview unavailable")):
        resp = client.post("/api/kb/preview", json={"kb_id": "kb-a", "doc_id": "doc-1"})

    assert resp.status_code == 503
    assert resp.json()["message"] == "preview unavailable"


def test_list_assets_route_returns_service_payload() -> None:
    """资产列表路由应返回指定知识库的资产集合。"""
    payload = [{"asset_id": "asset-1", "kb_id": "kb-a"}]
    with patch("api.routers.kb.asset_service.list_assets", return_value=payload) as mock_list:
        resp = client.get("/api/kb/assets", params={"kb_id": "kb-a"})

    assert resp.status_code == 200
    assert resp.json()["data"]["items"] == payload
    mock_list.assert_called_once_with("kb-a")


def test_list_assets_route_maps_runtime_error_to_503() -> None:
    """资产列表路由遇到运行时错误时应返回 503。"""
    with patch("api.routers.kb.asset_service.list_assets", side_effect=RuntimeError("asset list unavailable")):
        resp = client.get("/api/kb/assets", params={"kb_id": "kb-a"})

    assert resp.status_code == 503
    assert resp.json()["message"] == "asset list unavailable"


def test_get_asset_preview_route_returns_service_payload() -> None:
    """资产预览路由应返回最小预览对象。"""
    payload = {"asset_id": "asset-1", "kb_id": "kb-a", "preview_type": "image_asset"}
    with patch("api.routers.kb.asset_service.get_asset_preview", return_value=payload) as mock_get:
        resp = client.get("/api/kb/assets/asset-1", params={"kb_id": "kb-a"})

    assert resp.status_code == 200
    assert resp.json()["data"] == payload
    mock_get.assert_called_once_with("kb-a", "asset-1")


def test_get_asset_preview_route_maps_runtime_error_to_503() -> None:
    """资产预览路由遇到运行时错误时应返回 503。"""
    with patch("api.routers.kb.asset_service.get_asset_preview", side_effect=RuntimeError("asset preview unavailable")):
        resp = client.get("/api/kb/assets/asset-1", params={"kb_id": "kb-a"})

    assert resp.status_code == 503
    assert resp.json()["message"] == "asset preview unavailable"


def test_get_kb_route_maps_service_error() -> None:
    """知识库详情路由应把稳定服务异常映射为 HTTP 错误。"""
    with patch("api.routers.kb.kb_service.get_kb", side_effect=KBUnavailableError("知识库未激活")):
        resp = client.get("/api/kb/kb-a")

    assert resp.status_code == 400
    assert resp.json()["message"] == "知识库未激活"


def test_list_docs_route_maps_kb_error() -> None:
    """文档列表路由应把稳定知识库错误映射为约定状态码。"""
    with patch("api.routers.kb.kb_service.list_docs", side_effect=KBNotFoundError("知识库不存在")):
        resp = client.get("/api/kb/list", params={"kb_id": "missing"})

    assert resp.status_code == 404
    assert resp.json()["message"] == "知识库不存在"


def test_list_folders_route_maps_kb_error() -> None:
    """目录树路由应把稳定知识库错误映射为约定状态码。"""
    with patch("api.routers.kb.folder_service.list_folders", side_effect=KBUnavailableError("知识库未激活")):
        resp = client.get("/api/kb/folders", params={"kb_id": "kb-a"})

    assert resp.status_code == 400
    assert resp.json()["message"] == "知识库未激活"


def test_delete_docs_route_maps_kb_error() -> None:
    """文档删除路由应把稳定知识库错误映射为约定状态码。"""
    with patch("api.routers.kb.kb_service.delete_docs", side_effect=KBValidationError("删除请求非法")):
        resp = client.request(
            "DELETE",
            "/api/kb/docs",
            json={"kb_id": "kb-a", "doc_ids": ["doc-1"], "paths": []},
        )

    assert resp.status_code == 400
    assert resp.json()["message"] == "删除请求非法"


def test_import_files_route_maps_kb_error() -> None:
    """文件导入路由应把稳定知识库错误映射为约定状态码。"""
    with patch("api.routers.kb.kb_service.import_files", side_effect=KBNotFoundError("知识库不存在")):
        resp = client.post(
            "/api/kb/file/import",
            data={"kb_id": "missing"},
            files=[("files", ("notes.md", b"# notes", "text/markdown"))],
        )

    assert resp.status_code == 404
    assert resp.json()["message"] == "知识库不存在"


def test_list_assets_route_maps_kb_error() -> None:
    """资产列表路由应把稳定知识库错误映射为约定状态码。"""
    with patch("api.routers.kb.asset_service.list_assets", side_effect=KBNotFoundError("知识库不存在")):
        resp = client.get("/api/kb/assets", params={"kb_id": "missing"})

    assert resp.status_code == 404
    assert resp.json()["message"] == "知识库不存在"


def test_get_asset_preview_route_maps_kb_error() -> None:
    """资产预览路由应把稳定知识库错误映射为约定状态码。"""
    with patch("api.routers.kb.asset_service.get_asset_preview", side_effect=KBNotFoundError("资产不存在")):
        resp = client.get("/api/kb/assets/asset-1", params={"kb_id": "kb-a"})

    assert resp.status_code == 404
    assert resp.json()["message"] == "资产不存在"
