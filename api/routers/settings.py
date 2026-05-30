"""
系统设置、模型配置、存储信息接口。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import (
    CustomProviderConnectionTestRequest,
    CustomProviderCreateRequest,
    ModelSelectRequest,
    ProviderConfigImportRequest,
    SettingsUpdateRequest,
)
from api.services import model_service, settings_service, storage_service
from utils.api_response import success_response

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings")
def get_settings() -> dict:
    return success_response(settings_service.get_settings())


@router.put("/settings")
def update_settings(request: SettingsUpdateRequest) -> dict:
    return success_response(settings_service.update_settings(request))


@router.get("/model/options")
def model_options() -> dict:
    return success_response(model_service.get_model_options())


@router.post("/model/select")
def select_model(request: ModelSelectRequest) -> dict:
    try:
        return success_response(model_service.select_model(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/model/providers")
def add_custom_provider(request: CustomProviderCreateRequest) -> dict:
    try:
        return success_response(model_service.add_custom_provider(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/model/providers/{provider_name}")
def delete_custom_provider(provider_name: str) -> dict:
    try:
        return success_response(model_service.delete_custom_provider(provider_name))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/model/providers/test")
def test_custom_provider(request: CustomProviderConnectionTestRequest) -> dict:
    return success_response(model_service.test_custom_provider_connection(request))


@router.get("/model/providers/export")
def export_custom_providers() -> dict:
    return success_response(model_service.export_provider_config())


@router.post("/model/providers/import")
def import_custom_providers(request: ProviderConfigImportRequest) -> dict:
    try:
        return success_response(model_service.import_provider_config(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/storage/info")
def storage_info() -> dict:
    return success_response(storage_service.get_storage_info())
