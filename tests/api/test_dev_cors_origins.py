"""???????? CORS ?????"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app import app

client = TestClient(app)


@pytest.mark.parametrize(
    "origin",
    [
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://[::1]:4173",
    ],
)
def test_local_dev_origins_are_allowed(origin: str) -> None:
    """????????????????? CORS ???"""
    response = client.get("/api/health", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


def test_non_local_origin_is_not_allowed() -> None:
    """??????????? CORS ??????"""
    response = client.get("/api/health", headers={"Origin": "http://example.com"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
