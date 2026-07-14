"""API CORS 行为测试。"""

from fastapi.testclient import TestClient

from api.app import app


def test_frontend_dev_origin_preflight_is_allowed() -> None:
    client = TestClient(app)

    response = client.options(
        "/api/kb",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_localhost_frontend_dev_origin_preflight_is_allowed() -> None:
    client = TestClient(app)

    response = client.options(
        "/api/kb",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
