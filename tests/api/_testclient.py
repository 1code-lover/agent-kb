"""FastAPI TestClient lazy compatibility wrapper for local test runs."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient as _FastAPITestClient

_HTTPX_INCOMPAT_REASON = (
    "当前环境的 FastAPI/Starlette TestClient 与已安装的 httpx 版本不兼容，"
    "通常会报 `Client.__init__() got an unexpected keyword argument 'app'`。"
    "建议执行 `python -m pip install -r requirements-runtime.txt`，"
    "或最小化执行 `python -m pip install httpx==0.27.2`。"
)


class _HttpxASGITestClient:
    """httpx>=0.28 下的轻量同步兼容层，避免 TestClient 构造参数漂移。"""

    def __init__(self, app: Any, **kwargs: Any) -> None:
        self._app = app
        self._base_url = str(kwargs.pop("base_url", "http://testserver"))
        self._headers = kwargs.pop("headers", None)
        self._cookies = kwargs.pop("cookies", None)
        self._follow_redirects = bool(kwargs.pop("follow_redirects", True))
        self._client_kwargs = dict(kwargs)
        self._runner: asyncio.Runner | None = None
        self._client: httpx.AsyncClient | None = None
        self._lifespan_cm: Any = None

    @staticmethod
    def _runner_is_usable(runner: asyncio.Runner | None) -> bool:
        if runner is None:
            return False
        state = getattr(runner, "_state", None)
        if getattr(state, "name", None) == "CLOSED":
            return False
        loop = getattr(runner, "_loop", None)
        return loop is None or not loop.is_closed()

    @classmethod
    def _run_on_runner(cls, runner: asyncio.Runner | None, coro: Any) -> bool:
        if not cls._runner_is_usable(runner):
            with suppress(Exception):
                coro.close()
            return False
        ran = False
        try:
            runner.run(coro)
            ran = True
            return True
        except RuntimeError:
            return False
        finally:
            if not ran:
                with suppress(Exception):
                    coro.close()

    async def _async_start(self) -> None:
        self._lifespan_cm = self._app.router.lifespan_context(self._app)
        await self._lifespan_cm.__aenter__()
        self._client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self._app),
            base_url=self._base_url,
            headers=self._headers,
            cookies=self._cookies,
            follow_redirects=self._follow_redirects,
            **self._client_kwargs,
        )

    def _ensure_started(self) -> None:
        if self._client is not None:
            return
        self._runner = asyncio.Runner()
        try:
            self._runner.run(self._async_start())
        except Exception:
            with suppress(Exception):
                self.close()
            raise

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self._ensure_started()
        assert self._runner is not None and self._client is not None
        return self._runner.run(self._client.request(method, url, **kwargs))

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)

    def options(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("OPTIONS", url, **kwargs)

    def close(self) -> None:
        runner = self._runner
        client = self._client
        lifespan_cm = self._lifespan_cm
        self._runner = None
        self._client = None
        self._lifespan_cm = None
        if runner is None:
            return
        try:
            if client is not None:
                self._run_on_runner(runner, client.aclose())
        finally:
            try:
                if lifespan_cm is not None:
                    self._run_on_runner(runner, lifespan_cm.__aexit__(None, None, None))
            finally:
                if self._runner_is_usable(runner):
                    runner.close()

    def __enter__(self) -> _HttpxASGITestClient:
        self._ensure_started()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def __del__(self) -> None:
        # 避免在 GC/解释器收尾阶段触发 asyncio.Runner 清理噪音；
        # 常规释放由显式 close() 或外层 TestClient.__del__ 负责。
        return None


class TestClient:
    """延迟创建真实 TestClient；httpx 漂移时回退到 ASGITransport 兼容层。"""

    __test__ = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._args = args
        self._kwargs = kwargs
        self._client: _FastAPITestClient | _HttpxASGITestClient | None = None

    def _ensure_client(self) -> _FastAPITestClient | _HttpxASGITestClient:
        if self._client is None:
            try:
                self._client = _FastAPITestClient(*self._args, **self._kwargs)
            except TypeError as exc:
                if "unexpected keyword argument 'app'" not in str(exc):
                    raise
                if not self._args:
                    raise
                app = self._args[0]
                self._client = _HttpxASGITestClient(app, **self._kwargs)
        return self._client

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        client = self._ensure_client()
        response = client.request(method, url, **kwargs)
        if isinstance(client, _HttpxASGITestClient):
            client.close()
        return response

    def get(self, url: str, **kwargs: Any) -> Any:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Any:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> Any:
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> Any:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> Any:
        return self.request("DELETE", url, **kwargs)

    def options(self, url: str, **kwargs: Any) -> Any:
        return self.request("OPTIONS", url, **kwargs)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") or name.startswith("_pytest"):
            raise AttributeError(name)
        return getattr(self._ensure_client(), name)

    def __enter__(self) -> _FastAPITestClient | _HttpxASGITestClient:
        return self._ensure_client().__enter__()

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        return self._ensure_client().__exit__(exc_type, exc, tb)

    def close(self) -> None:
        client = self._client
        if client is None:
            return
        close = getattr(client, "close", None)
        if callable(close):
            close()

    def __del__(self) -> None:
        client = self._client
        close = getattr(client, "close", None)
        if callable(close):
            with suppress(Exception):
                close()

    def __repr__(self) -> str:
        client_state = "ready" if self._client is not None else "deferred"
        return f"TestClient({client_state})"
