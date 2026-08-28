"""系统设置与模型配置路由测试。"""

from __future__ import annotations

from unittest.mock import patch

from tests.api._testclient import TestClient

from api.app import app

client = TestClient(app)


def test_get_settings_route_returns_service_payload() -> None:
    """系统设置查询路由应直接返回服务层结果。"""
    payload = {"temperature": 0.2, "top_k": 4}
    with patch("api.routers.settings.settings_service.get_settings", return_value=payload) as mock_get:
        resp = client.get("/api/settings")

    assert resp.status_code == 200
    assert resp.json()["data"] == payload
    mock_get.assert_called_once_with()


def test_update_settings_route_passes_request_to_service() -> None:
    """系统设置更新路由应把请求对象透传给服务层。"""
    payload = {"temperature": 0.5, "top_k": 8}
    with patch("api.routers.settings.settings_service.update_settings", return_value=payload) as mock_update:
        resp = client.put(
            "/api/settings",
            json={"temperature": 0.5, "top_k": 8, "system_prompt": "你是测试助手"},
        )

    assert resp.status_code == 200
    assert resp.json()["data"] == payload
    request = mock_update.call_args.args[0]
    assert request.temperature == 0.5
    assert request.top_k == 8
    assert request.system_prompt == "你是测试助手"


def test_model_options_route_returns_service_payload() -> None:
    """模型选项路由应返回服务层给出的模型列表。"""
    payload = {"current": {"service_provider": "openai"}, "options": [{"value": "gpt-4o-mini"}]}
    with patch("api.routers.settings.model_service.get_model_options", return_value=payload) as mock_get:
        resp = client.get("/api/model/options")

    assert resp.status_code == 200
    assert resp.json()["data"] == payload
    mock_get.assert_called_once_with()


def test_model_health_route_returns_service_payload() -> None:
    """模型健康路由应返回服务层健康状态。"""
    payload = {"state": "fallback_applied", "current_model": "qwen-plus"}
    with patch("api.routers.settings.model_service.get_model_health", return_value=payload) as mock_get:
        resp = client.get("/api/model/health")

    assert resp.status_code == 200
    assert resp.json()["data"] == payload
    mock_get.assert_called_once_with()


def test_select_model_route_returns_service_payload() -> None:
    """模型切换路由应返回服务层切换结果。"""
    payload = {"service_provider": "custom", "model": "deepseek-chat"}
    with patch("api.routers.settings.model_service.select_model", return_value=payload) as mock_select:
        resp = client.post(
            "/api/model/select",
            json={"service_provider": "custom", "model": "deepseek-chat", "session_id": "desktop-default"},
        )

    assert resp.status_code == 200
    assert resp.json()["data"] == payload
    request = mock_select.call_args.args[0]
    assert request.service_provider == "custom"
    assert request.model == "deepseek-chat"


def test_select_model_route_maps_value_error_to_400() -> None:
    """模型切换路由应把参数错误映射为 400。"""
    with patch("api.routers.settings.model_service.select_model", side_effect=ValueError("模型不存在")):
        resp = client.post(
            "/api/model/select",
            json={"service_provider": "custom", "model": "unknown", "session_id": "desktop-default"},
        )

    assert resp.status_code == 400
    assert resp.json()["message"] == "模型不存在"


def test_add_custom_provider_route_returns_service_payload() -> None:
    """自定义供应商新增路由应返回服务层写入结果。"""
    payload = {"name": "local-openai", "models": ["qwen-max"]}
    with patch("api.routers.settings.model_service.add_custom_provider", return_value=payload) as mock_add:
        resp = client.post(
            "/api/model/providers",
            json={"name": "local-openai", "api_base": "http://localhost:8001/v1", "models": ["qwen-max"], "api_key": "sk-test"},
        )

    assert resp.status_code == 200
    assert resp.json()["data"] == payload
    request = mock_add.call_args.args[0]
    assert request.name == "local-openai"
    assert request.api_base == "http://localhost:8001/v1"
    assert request.models == ["qwen-max"]


def test_add_custom_provider_route_maps_value_error_to_400() -> None:
    """自定义供应商新增路由应把参数错误映射为 400。"""
    with patch("api.routers.settings.model_service.add_custom_provider", side_effect=ValueError("供应商已存在")):
        resp = client.post(
            "/api/model/providers",
            json={"name": "local-openai", "api_base": "http://localhost:8001/v1", "models": [], "api_key": ""},
        )

    assert resp.status_code == 400
    assert resp.json()["message"] == "供应商已存在"


def test_delete_custom_provider_route_returns_service_payload() -> None:
    """自定义供应商删除路由应返回服务层删除回执。"""
    payload = {"deleted": True, "provider_name": "local-openai"}
    with patch("api.routers.settings.model_service.delete_custom_provider", return_value=payload) as mock_delete:
        resp = client.delete("/api/model/providers/local-openai")

    assert resp.status_code == 200
    assert resp.json()["data"] == payload
    mock_delete.assert_called_once_with("local-openai")


def test_delete_custom_provider_route_maps_value_error_to_404() -> None:
    """自定义供应商删除路由应把不存在错误映射为 404。"""
    with patch("api.routers.settings.model_service.delete_custom_provider", side_effect=ValueError("供应商不存在")):
        resp = client.delete("/api/model/providers/missing")

    assert resp.status_code == 404
    assert resp.json()["message"] == "供应商不存在"


def test_test_custom_provider_route_returns_service_payload() -> None:
    """供应商探活路由应返回服务层探活结果。"""
    payload = {"ok": True, "provider_name": "local-openai"}
    with patch("api.routers.settings.model_service.test_custom_provider_connection", return_value=payload) as mock_test:
        resp = client.post(
            "/api/model/providers/test",
            json={"api_base": "http://localhost:8001/v1", "api_key": "sk-test", "provider_name": "local-openai", "model": "qwen-max"},
        )

    assert resp.status_code == 200
    assert resp.json()["data"] == payload
    request = mock_test.call_args.args[0]
    assert request.provider_name == "local-openai"
    assert request.model == "qwen-max"


def test_export_custom_providers_route_returns_service_payload() -> None:
    """供应商导出路由应直接返回服务层导出结果。"""
    payload = {"custom_llm_providers": [{"name": "local-openai"}], "current_llm_info": None}
    with patch("api.routers.settings.model_service.export_provider_config", return_value=payload) as mock_export:
        resp = client.get("/api/model/providers/export")

    assert resp.status_code == 200
    assert resp.json()["data"] == payload
    mock_export.assert_called_once_with()


def test_import_custom_providers_route_returns_service_payload() -> None:
    """供应商导入路由应把导入请求透传给服务层。"""
    payload = {"imported": 2, "mode": "merge"}
    with patch("api.routers.settings.model_service.import_provider_config", return_value=payload) as mock_import:
        resp = client.post(
            "/api/model/providers/import",
            json={
                "mode": "merge",
                "custom_llm_providers": [
                    {
                        "name": "local-openai",
                        "api_base": "http://localhost:8001/v1",
                        "models": ["qwen-max"],
                        "api_key": "sk-test",
                    }
                ],
                "current_llm_info": None,
            },
        )

    assert resp.status_code == 200
    assert resp.json()["data"] == payload
    request = mock_import.call_args.args[0]
    assert request.mode == "merge"
    assert request.custom_llm_providers[0].name == "local-openai"


def test_import_custom_providers_route_maps_value_error_to_400() -> None:
    """供应商导入路由应把非法导入请求映射为 400。"""
    with patch("api.routers.settings.model_service.import_provider_config", side_effect=ValueError("导入文件不合法")):
        resp = client.post(
            "/api/model/providers/import",
            json={"mode": "replace", "custom_llm_providers": [], "current_llm_info": None},
        )

    assert resp.status_code == 400
    assert resp.json()["message"] == "导入文件不合法"


def test_storage_info_route_returns_service_payload() -> None:
    """存储信息路由应直接返回服务层结果。"""
    payload = {"storage_root": "storage", "used_bytes": 1024}
    with patch("api.routers.settings.storage_service.get_storage_info", return_value=payload) as mock_info:
        resp = client.get("/api/storage/info")

    assert resp.status_code == 200
    assert resp.json()["data"] == payload
    mock_info.assert_called_once_with()
