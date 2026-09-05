from __future__ import annotations

from pathlib import Path
import warnings

import pytest

from api.app import app
import tests.api._testclient as compat
from tests.api._testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_API_DIR = REPO_ROOT / "tests" / "api"


def test_lazy_testclient_delays_real_client_creation_until_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            calls.append((args, kwargs))
            self.headers = {"x": "ok"}

    monkeypatch.setattr(compat, "_FastAPITestClient", FakeClient)

    client = TestClient("app", base_url="http://testserver")

    assert calls == []
    assert client.headers == {"x": "ok"}
    assert calls == [(("app",), {"base_url": "http://testserver"})]



def test_lazy_testclient_falls_back_to_httpx_asgi_transport_when_fastapi_client_is_incompatible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenClient:
        def __init__(self, *args, **kwargs):
            raise TypeError("Client.__init__() got an unexpected keyword argument 'app'")

    class FakeFallback:
        def __init__(self, app, **kwargs):
            self.app = app
            self.kwargs = kwargs
            self.headers = {"transport": "httpx-asgi"}

    monkeypatch.setattr(compat, "_FastAPITestClient", BrokenClient)
    monkeypatch.setattr(compat, "_HttpxASGITestClient", FakeFallback)

    client = TestClient("app", base_url="http://testserver")

    assert client.headers == {"transport": "httpx-asgi"}
    fallback = client._ensure_client()
    assert isinstance(fallback, FakeFallback)
    assert fallback.app == "app"
    assert fallback.kwargs == {"base_url": "http://testserver"}



def test_api_tests_use_compat_testclient_wrapper() -> None:
    offenders: list[str] = []
    for path in TEST_API_DIR.glob('*.py'):
        if path.name in {'_testclient.py', 'test_testclient_contract.py'}:
            continue
        text = path.read_text(encoding='utf-8')
        if 'from fastapi.testclient import TestClient' in text:
            offenders.append(path.name)

    assert offenders == []


def test_httpx_fallback_close_tolerates_closed_runner_without_runtime_warnings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenClient:
        def __init__(self, *args, **kwargs):
            raise TypeError("Client.__init__() got an unexpected keyword argument 'app'")

    monkeypatch.setattr(compat, "_FastAPITestClient", BrokenClient)

    client = TestClient(app)
    fallback = client._ensure_client()
    assert isinstance(fallback, compat._HttpxASGITestClient)

    response = fallback.get("/api/health")
    assert response.status_code == 200

    runner = fallback._runner
    assert runner is not None
    runner.get_loop().close()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fallback.close()

    runtime_warnings = [item for item in caught if issubclass(item.category, RuntimeWarning)]
    assert runtime_warnings == []
    assert fallback._runner is None
    assert fallback._client is None
    assert fallback._lifespan_cm is None
