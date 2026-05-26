"""
模块功能：
- 提供系统设置、模型配置、存储信息查询接口。

执行逻辑：
1. 设置接口由 settings_service 负责读写。
2. 模型接口由 model_service 负责 provider 与模型管理。
3. 存储接口由 storage_service 返回运行时存储信息。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import (
    CustomProviderConnectionTestRequest,
    CustomProviderCreateRequest,
    ModelSelectRequest,
    SettingsUpdateRequest,
)
from api.services import model_service, settings_service, storage_service
from utils.api_response import success_response

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings")
def get_settings() -> dict:
    """
    读取当前系统设置。

    输出：
    - dict: 标准化 API 响应，data 为设置对象。
    """
    return success_response(settings_service.get_settings())


@router.put("/settings")
def update_settings(request: SettingsUpdateRequest) -> dict:
    """
    更新系统设置。

    输入：
    - request(SettingsUpdateRequest): 设置更新参数。

    输出：
    - dict: 标准化 API 响应，data 为更新后设置。
    """
    return success_response(settings_service.update_settings(request))


@router.get("/model/options")
def model_options() -> dict:
    """
    查询模型候选项和 provider 信息。

    输出：
    - dict: 标准化 API 响应，data 包含可选模型与 provider。
    """
    return success_response(model_service.get_model_options())


@router.post("/model/select")
def select_model(request: ModelSelectRequest) -> dict:
    """
    选择并应用当前模型配置。

    输入：
    - request(ModelSelectRequest): provider 与 model 选择参数。

    输出：
    - dict: 标准化 API 响应，data 为应用结果。
    """
    return success_response(model_service.select_model(request))


@router.post("/model/providers")
def add_custom_provider(request: CustomProviderCreateRequest) -> dict:
    """
    新增或更新自定义 provider。

    输入：
    - request(CustomProviderCreateRequest): provider 连接与模型配置。

    输出：
    - dict: 标准化 API 响应，data 为保存结果。
    """
    try:
        return success_response(model_service.add_custom_provider(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/model/providers/{provider_name}")
def delete_custom_provider(provider_name: str) -> dict:
    """
    删除指定自定义 provider。

    输入：
    - provider_name(str): provider 名称。

    输出：
    - dict: 标准化 API 响应，data 为删除结果。
    """
    try:
        return success_response(model_service.delete_custom_provider(provider_name))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/model/providers/test")
def test_custom_provider(request: CustomProviderConnectionTestRequest) -> dict:
    """
    测试自定义 provider 连通性。

    输入：
    - request(CustomProviderConnectionTestRequest): 测试连接参数。

    输出：
    - dict: 标准化 API 响应，data 为连通性结果。
    """
    return success_response(model_service.test_custom_provider_connection(request))


@router.get("/storage/info")
def storage_info() -> dict:
    """
    读取当前存储运行信息。

    输出：
    - dict: 标准化 API 响应，data 为存储状态摘要。
    """
    return success_response(storage_service.get_storage_info())
