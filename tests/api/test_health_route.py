"""?????????"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app
from api.routers import health as health_router


client = TestClient(app)


def test_health_returns_ocr_warmup_status(monkeypatch) -> None:
    """??????? OCR ???????????????"""
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

    resp = client.get('/api/health')

    assert resp.status_code == 200
    payload = resp.json()['data']
    assert payload['status'] == 'ok'
    assert payload['ocr_warmup']['state'] == 'warming'
    assert payload['ocr_warmup']['is_ready'] is False
