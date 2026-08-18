"""Embedding 本地缓存后台恢复服务。"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from threading import Event, RLock, Thread
from typing import Any

from api.runtime import RuntimeState, runtime_state
from api.services.embedding_download_adapter import (
    EmbeddingDownloadAdapter,
    EmbeddingDownloadCancelled,
)
from scripts.prepare_embedding_model_cache import prepare_embedding_model_cache

_ALLOWED_PROVIDERS = {"modelscope"}
_ACTIVE_STATES = {"checking_space", "downloading", "verifying", "cancelling"}


class InsufficientDiskSpaceError(RuntimeError):
    """表示模型下载预检发现磁盘空间不足。"""

    def __init__(self, preflight: dict[str, Any]) -> None:
        self.preflight = dict(preflight)
        super().__init__(
            "Insufficient disk space for embedding cache download "
            f"(shortfall_bytes={int(preflight.get('shortfall_bytes') or 0)})."
        )


class EmbeddingDownloadConflictError(RuntimeError):
    """表示下载任务当前状态与请求冲突。"""


def _utc_now_iso() -> str:
    """返回 UTC ISO 时间字符串。"""
    return datetime.now(timezone.utc).isoformat()


def _new_status() -> dict[str, Any]:
    """创建缓存恢复状态默认结构。"""
    return {
        "state": "idle",
        "phase": None,
        "provider": "modelscope",
        "model_name": None,
        "attempt_count": 0,
        "started_at": None,
        "finished_at": None,
        "updated_at": _utc_now_iso(),
        "last_duration_ms": None,
        "last_error": None,
        "result": None,
        "warmup_started": False,
        "thread_alive": False,
        "bytes_downloaded": 0,
        "bytes_total": 0,
        "progress_percent": 0.0,
        "progress_mode": "estimated",
        "current_file": None,
        "free_bytes": None,
        "required_bytes": None,
        "reserve_bytes": None,
        "shortfall_bytes": 0,
        "enough_space": None,
        "target_dir": None,
        "cancel_requested": False,
    }


class EmbeddingCacheService:
    """串行执行 embedding 缓存下载，并提供可轮询状态。"""

    def __init__(
        self,
        *,
        runtime: RuntimeState = runtime_state,
        adapter: EmbeddingDownloadAdapter | Any | None = None,
    ) -> None:
        self.runtime = runtime
        self._lock = RLock()
        self._thread: Thread | None = None
        self._cancel_event = Event()
        # 间接调用模块级函数，保留旧测试和部署侧 monkeypatch 的兼容性。
        self.adapter = adapter or EmbeddingDownloadAdapter(
            prepare_func=lambda model_name, **kwargs: prepare_embedding_model_cache(model_name, **kwargs)
        )
        self._status = _new_status()

    def get_status(self) -> dict[str, Any]:
        """返回不包含内部对象的状态快照。"""
        with self._lock:
            status = dict(self._status)
            status["thread_alive"] = self._thread is not None and self._thread.is_alive()
            return status

    def preflight(self, *, provider: str = "modelscope") -> dict[str, Any]:
        """执行无下载副作用的磁盘空间预检。"""
        normalized_provider = self._normalize_provider(provider)
        with self._lock:
            if self._thread is not None and self._status.get("state") in _ACTIVE_STATES:
                raise EmbeddingDownloadConflictError("Embedding cache preparation is already running.")
            model_name = self.runtime._get_configured_embedding_model_name()
            self._status.update(
                phase="checking_space",
                provider=normalized_provider,
                model_name=model_name,
                updated_at=_utc_now_iso(),
                last_error=None,
            )
        result = self.adapter.preflight(model_name, provider=normalized_provider)
        with self._lock:
            self._apply_preflight(result)
            return self.get_status()

    def start_prepare(self, *, provider: str = "modelscope") -> tuple[dict[str, Any], bool]:
        """幂等启动缓存准备线程，返回状态与是否实际启动。"""
        normalized_provider = self._normalize_provider(provider)
        with self._lock:
            if self._thread is not None:
                return self.get_status(), False
            model_name = self.runtime._get_configured_embedding_model_name()

        preflight = self.adapter.preflight(model_name, provider=normalized_provider)
        if not preflight.get("enough_space"):
            with self._lock:
                self._status.update(phase="checking_space", model_name=model_name, provider=normalized_provider)
                self._apply_preflight(preflight)
                self._status.update(last_error="Insufficient disk space.", updated_at=_utc_now_iso())
            raise InsufficientDiskSpaceError(preflight)

        with self._lock:
            if self._thread is not None:
                return self.get_status(), False
            self._cancel_event = Event()
            self._apply_preflight(preflight)
            self._status.update(
                state="downloading",
                phase="downloading",
                provider=normalized_provider,
                model_name=model_name,
                attempt_count=int(self._status.get("attempt_count") or 0) + 1,
                started_at=_utc_now_iso(),
                finished_at=None,
                updated_at=_utc_now_iso(),
                last_duration_ms=None,
                last_error=None,
                result=None,
                warmup_started=False,
                thread_alive=True,
                bytes_downloaded=0,
                progress_percent=0.0,
                current_file=None,
                cancel_requested=False,
            )
            thread = Thread(
                target=self._run_prepare,
                args=(normalized_provider, model_name, preflight),
                name="thinkrag-embedding-cache-prepare",
                daemon=True,
            )
            self._thread = thread
            try:
                thread.start()
            except Exception as exc:
                self._status.update(
                    state="failed",
                    phase="failed",
                    finished_at=_utc_now_iso(),
                    updated_at=_utc_now_iso(),
                    last_error=f"Failed to start embedding cache preparation: {exc}",
                    thread_alive=False,
                )
                self._thread = None
                raise
        return self.get_status(), True

    def request_cancel(self) -> dict[str, Any]:
        """幂等请求取消当前任务；非运行状态不保留取消标记。"""
        with self._lock:
            running = self._thread is not None and self._status.get("state") in _ACTIVE_STATES
            if not running:
                self._status.update(cancel_requested=False, updated_at=_utc_now_iso())
                return self.get_status()
            self._cancel_event.set()
            self._status.update(
                state="cancelling",
                phase="cancelling",
                cancel_requested=True,
                updated_at=_utc_now_iso(),
            )
            return self.get_status()

    def _run_prepare(
        self,
        provider: str,
        model_name: str,
        preflight: dict[str, Any] | None = None,
    ) -> None:
        """执行下载并在完整校验成功后重新启动 embedding 预热。"""
        started = time.perf_counter()
        with self._lock:
            if self._thread is None and self._cancel_event.is_set():
                self._cancel_event = Event()
        try:
            effective_preflight = preflight or self.adapter.preflight(model_name, provider=provider)
            if not effective_preflight.get("enough_space"):
                raise InsufficientDiskSpaceError(effective_preflight)
            result = self.adapter.prepare(
                model_name,
                provider=provider,
                preflight=effective_preflight,
                progress_callback=self._update_progress,
                cancel_event=self._cancel_event,
            )
            if self._cancel_event.is_set():
                raise EmbeddingDownloadCancelled("Embedding download was cancelled.")
            error = result.get("error")
            cache_ready = bool((result.get("after") or {}).get("local_path_exists"))
            if error or not cache_ready:
                raise RuntimeError(str(error or "Embedding cache is still unavailable after preparation."))

            self.runtime.reset_embedding_runtime()
            warmup_started = self.runtime.start_embedding_warmup_in_background()
        except EmbeddingDownloadCancelled as exc:
            with self._lock:
                self._status.update(
                    state="cancelled",
                    phase="cancelled",
                    finished_at=_utc_now_iso(),
                    updated_at=_utc_now_iso(),
                    last_duration_ms=round((time.perf_counter() - started) * 1000, 3),
                    last_error=str(exc),
                    result=locals().get("result"),
                    warmup_started=False,
                    thread_alive=False,
                    cancel_requested=True,
                )
                self._thread = None
            return
        except Exception as exc:
            with self._lock:
                self._status.update(
                    state="failed",
                    phase="failed",
                    finished_at=_utc_now_iso(),
                    updated_at=_utc_now_iso(),
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
                phase="ready",
                finished_at=_utc_now_iso(),
                updated_at=_utc_now_iso(),
                last_duration_ms=round((time.perf_counter() - started) * 1000, 3),
                last_error=None,
                result=result,
                warmup_started=warmup_started,
                thread_alive=False,
                bytes_downloaded=max(
                    int(self._status.get("bytes_downloaded") or 0),
                    int(self._status.get("bytes_total") or 0),
                ),
                progress_percent=100.0,
                current_file=None,
                cancel_requested=False,
            )
            self._thread = None

    def _update_progress(self, event: dict[str, Any]) -> None:
        """将下载回调转换为单调、校验前不超过 99% 的公开状态。"""
        with self._lock:
            previous_bytes = int(self._status.get("bytes_downloaded") or 0)
            downloaded = max(previous_bytes, int(event.get("bytes_downloaded") or 0))
            total = int(event.get("bytes_total") or self._status.get("bytes_total") or 0)
            phase = str(event.get("phase") or "downloading")
            if total > 0:
                percent = min(99.0, round(downloaded * 100 / total, 2))
            else:
                percent = float(self._status.get("progress_percent") or 0.0)
            percent = max(float(self._status.get("progress_percent") or 0.0), percent)
            state = "verifying" if phase == "verifying" else self._status.get("state")
            if state not in {"cancelling"}:
                state = "verifying" if phase == "verifying" else "downloading"
            self._status.update(
                state=state,
                phase="cancelling" if state == "cancelling" else phase,
                bytes_downloaded=downloaded,
                bytes_total=total,
                progress_percent=percent,
                progress_mode=event.get("progress_mode") or self._status.get("progress_mode") or "estimated",
                current_file=event.get("current_file"),
                updated_at=_utc_now_iso(),
            )

    def _apply_preflight(self, preflight: dict[str, Any]) -> None:
        """把预检结果复制到公开状态。调用方必须持锁。"""
        self._status.update(
            target_dir=preflight.get("target_dir"),
            free_bytes=preflight.get("free_bytes"),
            required_bytes=preflight.get("required_bytes"),
            reserve_bytes=preflight.get("reserve_bytes"),
            shortfall_bytes=preflight.get("shortfall_bytes", 0),
            enough_space=preflight.get("enough_space"),
            bytes_total=preflight.get("bytes_total", preflight.get("required_bytes", 0)),
            progress_mode=preflight.get("progress_mode") or "estimated",
            updated_at=_utc_now_iso(),
        )

    @staticmethod
    def _normalize_provider(provider: str) -> str:
        """校验并标准化下载来源。"""
        normalized_provider = provider.strip().lower()
        if normalized_provider not in _ALLOWED_PROVIDERS:
            raise ValueError(f"Unsupported embedding cache provider: {provider}")
        return normalized_provider


embedding_cache_service = EmbeddingCacheService()

__all__ = [
    "EmbeddingCacheService",
    "EmbeddingDownloadConflictError",
    "InsufficientDiskSpaceError",
    "embedding_cache_service",
]
