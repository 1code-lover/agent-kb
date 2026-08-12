"""/api/health 路由测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app
from api.routers import health as health_router


client = TestClient(app)


def test_build_import_capabilities_reports_dependency_readiness(monkeypatch) -> None:
    """依赖就绪态应汇总为可读的导入能力摘要。"""

    monkeypatch.setattr(
        health_router,
        "_is_module_installed",
        lambda name: name in {"fitz", "PIL"},
    )

    payload = health_router._build_import_capabilities()

    assert payload["pdf_text_extraction"]["ready"] is True
    assert payload["image_ocr"]["ready"] is False
    assert payload["dependencies"]["fitz"] == {
        "installed": True,
        "package": "PyMuPDF",
        "import_name": "fitz",
        "used_for": ["pdf_text_extraction"],
    }
    assert payload["dependencies"]["paddleocr"]["installed"] is False
    assert payload["dependencies"]["paddle"]["package"] == "paddlepaddle"
    assert payload["dependencies"]["pillow"] == {
        "installed": True,
        "package": "Pillow",
        "import_name": "PIL",
        "used_for": ["image_ocr"],
    }


def test_build_runtime_metadata_contains_process_context() -> None:
    """运行时元信息应暴露最小必要的诊断字段。"""

    payload = health_router._build_runtime_metadata()

    assert payload["pid"] > 0
    assert payload["python_executable"]
    assert payload["python_version"]
    assert payload["python_implementation"]
    assert payload["cwd"]


def test_health_returns_embedding_ocr_and_runtime_status(monkeypatch) -> None:
    """健康检查应同时返回 embedding/OCR 状态、依赖摘要和运行时信息。"""

    class FakeRuntimeState:
        @staticmethod
        def get_embedding_warmup_status() -> dict:
            return {
                "state": "ready",
                "is_ready": True,
                "attempt_count": 1,
                "last_error": None,
                "last_duration_ms": 1234.5,
                "started_at": "2026-07-29T10:00:00+00:00",
                "finished_at": "2026-07-29T10:00:01+00:00",
                "current_model": "bge-small-zh-v1.5",
                "loaded_model": "bge-small-zh-v1.5",
            }

    monkeypatch.setattr(health_router, "runtime_state", FakeRuntimeState())
    monkeypatch.setattr(
        health_router,
        "get_ocr_warmup_status",
        lambda: {
            "state": "warming",
            "is_ready": False,
            "attempt_count": 1,
            "last_error": None,
            "last_duration_ms": None,
            "started_at": "2026-07-26T10:00:00+00:00",
            "finished_at": None,
        },
    )
    monkeypatch.setattr(
        health_router,
        "_build_import_capabilities",
        lambda: {
            "pdf_text_extraction": {"ready": False, "dependencies": ["fitz"]},
            "image_ocr": {"ready": False, "dependencies": ["paddleocr", "paddle", "pillow"]},
            "dependencies": {
                "fitz": {
                    "installed": False,
                    "package": "PyMuPDF",
                    "import_name": "fitz",
                    "used_for": ["pdf_text_extraction"],
                }
            },
        },
    )
    monkeypatch.setattr(
        health_router,
        "get_embedding_model_diagnostics",
        lambda model_name: {
            "model_name": model_name,
            "load_source": "local",
            "local_path_exists": True,
            "recommendations": [],
        },
    )
    monkeypatch.setattr(
        health_router,
        "_build_runtime_metadata",
        lambda: {
            "pid": 12345,
            "python_executable": "C:/Python312/python.exe",
            "python_version": "3.12.10",
            "python_implementation": "CPython",
            "cwd": "C:/repo/github-agent-kb",
        },
    )

    resp = client.get("/api/health")

    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["status"] == "ok"
    assert payload["runtime"] == {
        "pid": 12345,
        "python_executable": "C:/Python312/python.exe",
        "python_version": "3.12.10",
        "python_implementation": "CPython",
        "cwd": "C:/repo/github-agent-kb",
    }
    assert payload["embedding_warmup"]["state"] == "ready"
    assert payload["embedding_warmup"]["is_ready"] is True
    assert payload["embedding_warmup"]["current_model"] == "bge-small-zh-v1.5"
    assert payload["embedding_diagnostics"] == {
        "model_name": "bge-small-zh-v1.5",
        "load_source": "local",
        "local_path_exists": True,
        "recommendations": [],
    }
    assert payload["ocr_warmup"]["state"] == "warming"
    assert payload["ocr_warmup"]["is_ready"] is False
    assert payload["import_capabilities"]["pdf_text_extraction"]["ready"] is False
    assert payload["import_capabilities"]["dependencies"]["fitz"]["package"] == "PyMuPDF"
