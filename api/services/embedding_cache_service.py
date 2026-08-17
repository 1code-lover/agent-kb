"""Embedding 本地缓存后台恢复服务。"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from threading import RLock, Thread
from typing import Any

from api.runtime import RuntimeState, runtime_state
from scripts.prepare_embedding_model_cache import prepare_embedding_model_cache

_ALLOWED_PROVIDERS = {"modelscope"}


def _utc_now_iso() -> str:
    """返回 UTC ISO 时间字符串。"""
    return datetime.now(timezone.utc).isoformat()


def _new_status() -> dict[str, Any]:
    """创建缓存恢复状态默认结构。"""
    return {
        "state": "idle",
        "provider": "modelscope",
        "model_name": None,
        "attempt_count": 0,
        "started_at": None,
        "finished_at": None,
        "last_duration_ms": None,
        "last_error": None,
        "result": None,
        "warmup_started": False,
        "thread_alive": False,
    }


class EmbeddingCacheService:
    """串行执行 embedding 缓存下载，并提供可轮询状态。"""

    def __init__(self, *, runtime: RuntimeState = runtime_state) -> None:
        self.runtime = runtime
        self._lock = RLock()
        self._thread: Thread | None = None
        self._status = _new_status()

    def get_status(self) -> dict[str, Any]:
        """返回不包含内部对象的状态快照。"""
        with self._lock:
            status = dict(self._status)
            status["thread_alive"] = self._thread is not None and self._thread.is_alive()
            return status

    def start_prepare(self, *, provider: str = "modelscope") -> tuple[dict[str, Any], bool]:
        """幂等启动缓存准备线程，返回状态与是否实际启动。"""
        normalized_provider = provider.strip().lower()
        if normalized_provider not in _ALLOWED_PROVIDERS:
            raise ValueError(f"Unsupported embedding cache provider: {provider}")

        with self._lock:
            if self._thread is not None:
                return self.get_status(), False

            model_name = self.runtime._get_configured_embedding_model_name()
            self._status.update(
                state="downloading",
                provider=normalized_provider,
                model_name=model_name,
                attempt_count=int(self._status.get("attempt_count") or 0) + 1,
                started_at=_utc_now_iso(),
                finished_at=None,
                last_duration_ms=None,
                last_error=None,
                result=None,
                warmup_started=False,
                thread_alive=True,
            )
            thread = Thread(
                target=self._run_prepare,
                args=(normalized_provider, model_name),
                name="thinkrag-embedding-cache-prepare",
                daemon=True,
            )
            self._thread = thread
            try:
                thread.start()
            except Exception as exc:
                self._status.update(
                    state="failed",
                    finished_at=_utc_now_iso(),
                    last_error=f"Failed to start embedding cache preparation: {exc}",
                    thread_alive=False,
                )
                self._thread = None
                raise
        return self.get_status(), True

    def _run_prepare(self, provider: str, model_name: str) -> None:
        """执行下载并在成功后重新启动 embedding 预热。"""
        started = time.perf_counter()
        try:
            result = prepare_embedding_model_cache(model_name, download=True, provider=provider)
            error = result.get("error")
            cache_ready = bool((result.get("after") or {}).get("local_path_exists"))
            if error or not cache_ready:
                raise RuntimeError(str(error or "Embedding cache is still unavailable after preparation."))

            self.runtime.reset_embedding_runtime()
            warmup_started = self.runtime.start_embedding_warmup_in_background()
        except Exception as exc:
            with self._lock:
                self._status.update(
                    state="failed",
                    finished_at=_utc_now_iso(),
                    last_duration_ms=round((time.perf_counter() - started) * 1000, 3),
                    last_error=str(exc),
                    result=locals().get("result"),
                    warmup_started=False,
                    thread_alive=False,
                )
                self._thread = None
            return

        with self._lock:
            self._status.update(
                state="ready",
                finished_at=_utc_now_iso(),
                last_duration_ms=round((time.perf_counter() - started) * 1000, 3),
                last_error=None,
                result=result,
                warmup_started=warmup_started,
                thread_alive=False,
            )
            self._thread = None


embedding_cache_service = EmbeddingCacheService()

__all__ = ["EmbeddingCacheService", "embedding_cache_service"]
