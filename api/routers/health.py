"""健康检查路由。"""

from __future__ import annotations

import importlib.util
import os
import platform
import sys
from typing import Any

from fastapi import APIRouter

from api.runtime import runtime_state
from server.readers.image_ocr import get_ocr_warmup_status
from utils.api_response import success_response

router = APIRouter(prefix="/api", tags=["health"])


_IMPORT_DEPENDENCY_SPECS: dict[str, dict[str, Any]] = {
    "fitz": {
        "package": "PyMuPDF",
        "import_name": "fitz",
        "used_for": ["pdf_text_extraction"],
    },
    "paddleocr": {
        "package": "paddleocr",
        "import_name": "paddleocr",
        "used_for": ["image_ocr"],
    },
    "paddle": {
        "package": "paddlepaddle",
        "import_name": "paddle",
        "used_for": ["image_ocr"],
    },
    "pillow": {
        "package": "Pillow",
        "import_name": "PIL",
        "used_for": ["image_ocr"],
    },
}


def _is_module_installed(module_name: str) -> bool:
    """判断 Python 模块是否可导入。"""
    return importlib.util.find_spec(module_name) is not None


def _build_import_capabilities() -> dict[str, Any]:
    """汇总导入链路依赖状态，供前端与诊断脚本使用。"""
    dependencies: dict[str, dict[str, Any]] = {}
    for key, spec in _IMPORT_DEPENDENCY_SPECS.items():
        dependencies[key] = {
            "installed": _is_module_installed(spec["import_name"]),
            "package": spec["package"],
            "import_name": spec["import_name"],
            "used_for": list(spec["used_for"]),
        }

    return {
        "pdf_text_extraction": {
            "ready": dependencies["fitz"]["installed"],
            "dependencies": ["fitz"],
        },
        "image_ocr": {
            "ready": all(dependencies[name]["installed"] for name in ("paddleocr", "paddle", "pillow")),
            "dependencies": ["paddleocr", "paddle", "pillow"],
        },
        "dependencies": dependencies,
    }


def _build_runtime_metadata() -> dict[str, Any]:
    """返回当前服务进程的运行时元信息，便于定位环境漂移问题。"""
    return {
        "pid": os.getpid(),
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "cwd": os.getcwd(),
    }


@router.get("/health")
def health() -> dict:
    """返回服务健康状态、模型/OCR 预热状态、导入依赖摘要与运行时信息。"""
    return success_response(
        {
            "status": "ok",
            "runtime": _build_runtime_metadata(),
            "embedding_warmup": runtime_state.get_embedding_warmup_status(),
            "ocr_warmup": get_ocr_warmup_status(),
            "import_capabilities": _build_import_capabilities(),
        }
    )
