"""Embedding 模型下载适配器。

模块职责：
- 解析模型缓存目标并执行磁盘空间预检；
- 统一下载进度采样、取消检查与临时目录清理；
- 在服务层与具体 ModelScope/HuggingFace 下载脚本之间建立可测试边界。
"""

from __future__ import annotations

import inspect
import os
import shutil
import time
from pathlib import Path
from threading import Event, Thread
from typing import Any, Callable
from uuid import uuid4

from scripts.prepare_embedding_model_cache import (
    MODELSCOPE_MODEL_PATH,
    EmbeddingDownloadCancelled,
    prepare_embedding_model_cache,
)
from server.models.embedding import get_embedding_model_diagnostics

_DEFAULT_REQUIRED_BYTES = 2 * 1024**3
_MIN_RESERVE_BYTES = 512 * 1024**2

ProgressCallback = Callable[[dict[str, Any]], None]


def _directory_size(path: Path) -> tuple[int, str | None]:
    """统计目录实际落盘字节，并返回最近修改的相对文件名。"""
    if not path.exists():
        return 0, None
    total = 0
    newest_name: str | None = None
    newest_mtime = -1.0
    for item in path.rglob("*"):
        try:
            if not item.is_file():
                continue
            stat = item.stat()
        except OSError:
            continue
        total += stat.st_size
        if stat.st_mtime >= newest_mtime:
            newest_mtime = stat.st_mtime
            try:
                newest_name = str(item.relative_to(path))
            except ValueError:
                newest_name = item.name
    return total, newest_name


def _nearest_existing_parent(path: Path) -> Path:
    """返回可用于磁盘容量查询的最近已存在父目录。"""
    current = path
    while not current.exists() and current.parent != current:
        current = current.parent
    return current


class EmbeddingDownloadAdapter:
    """为 embedding 缓存下载提供预检、进度、取消与清理能力。"""

    def __init__(
        self,
        *,
        diagnostics_getter: Callable[..., dict[str, Any]] = get_embedding_model_diagnostics,
        prepare_func: Callable[..., dict[str, Any]] = prepare_embedding_model_cache,
        remote_size_resolver: Callable[[str, str], int | None] | None = None,
        disk_usage_getter: Callable[[str | os.PathLike[str]], Any] = shutil.disk_usage,
        default_required_bytes: int | None = None,
        sample_interval_seconds: float = 0.1,
        modelscope_files_getter: Callable[[str], list[dict[str, Any]]] | None = None,
        metadata_timeout_seconds: float = 3.0,
    ) -> None:
        self._diagnostics_getter = diagnostics_getter
        self._prepare_func = prepare_func
        self._remote_size_resolver = remote_size_resolver or self._resolve_remote_size
        self._disk_usage_getter = disk_usage_getter
        self._modelscope_files_getter = modelscope_files_getter
        self._metadata_timeout_seconds = max(0.05, float(metadata_timeout_seconds))
        env_required = os.getenv("THINKRAG_EMBED_REQUIRED_BYTES", "").strip()
        if default_required_bytes is not None:
            self._default_required_bytes = max(1, int(default_required_bytes))
        elif env_required:
            try:
                self._default_required_bytes = max(1, int(env_required))
            except ValueError:
                self._default_required_bytes = _DEFAULT_REQUIRED_BYTES
        else:
            self._default_required_bytes = _DEFAULT_REQUIRED_BYTES
        self._sample_interval_seconds = max(0.01, float(sample_interval_seconds))

    def resolve_target(self, model_name: str) -> dict[str, Any]:
        """解析模型缓存目录和现有缓存状态。"""
        diagnostics = self._diagnostics_getter(model_name, allow_remote_download=False)
        target_value = diagnostics.get("local_path")
        if not target_value:
            raise ValueError(f"Embedding cache target is unavailable for model: {model_name}")
        if diagnostics.get("hf_model_path") is None:
            raise ValueError(f"Unknown embedding model: {model_name}")
        target = Path(str(target_value)).expanduser().resolve()
        return {
            "target_dir": str(target),
            "cache_exists": bool(diagnostics.get("local_path_exists")),
            "diagnostics": diagnostics,
        }

    def preflight(self, model_name: str, *, provider: str) -> dict[str, Any]:
        """计算目标目录、下载所需空间、预留空间和当前可用空间。"""
        resolved = self.resolve_target(model_name)
        target = Path(resolved["target_dir"])
        cache_exists = bool(resolved["cache_exists"])
        remote_size: int | None = None
        if not cache_exists:
            try:
                remote_size = self._remote_size_resolver(model_name, provider)
            except Exception:
                remote_size = None
        required_bytes = 0 if cache_exists else int(remote_size or self._default_required_bytes)
        progress_mode = "exact" if cache_exists or remote_size else "estimated"
        reserve_bytes = 0 if required_bytes == 0 else max(int(required_bytes * 0.2), _MIN_RESERVE_BYTES)
        usage = self._disk_usage_getter(_nearest_existing_parent(target))
        free_bytes = int(getattr(usage, "free", usage[2]))
        total_required = required_bytes + reserve_bytes
        shortfall = max(0, total_required - free_bytes)
        return {
            "model_name": model_name,
            "provider": provider,
            "target_dir": str(target),
            "cache_exists": cache_exists,
            "required_bytes": required_bytes,
            "reserve_bytes": reserve_bytes,
            "free_bytes": free_bytes,
            "shortfall_bytes": shortfall,
            "bytes_total": required_bytes,
            "progress_mode": progress_mode,
            "enough_space": shortfall == 0,
        }

    def prepare(
        self,
        model_name: str,
        *,
        provider: str,
        preflight: dict[str, Any],
        progress_callback: ProgressCallback,
        cancel_event: Event,
    ) -> dict[str, Any]:
        """在受控临时目录下载，周期采样落盘字节并校验最终缓存。"""
        if cancel_event.is_set():
            raise EmbeddingDownloadCancelled("Embedding download was cancelled before start.")

        target = Path(str(preflight["target_dir"]))
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_dir = target.parent / f".thinkrag-embedding-{uuid4().hex}.partial"
        stop_sampling = Event()
        callback_error: list[BaseException] = []

        def emit(event: dict[str, Any] | None = None) -> None:
            """合并脚本阶段事件与目录采样值。"""
            try:
                downloaded, current_file = _directory_size(temp_dir)
                payload = dict(event or {})
                payload.setdefault("phase", "downloading")
                payload["bytes_downloaded"] = max(int(payload.get("bytes_downloaded") or 0), downloaded)
                payload.setdefault("bytes_total", int(preflight.get("bytes_total") or 0))
                payload.setdefault("progress_mode", preflight.get("progress_mode") or "estimated")
                payload.setdefault("current_file", current_file)
                progress_callback(payload)
            except BaseException as exc:  # pragma: no cover - 防止监控线程吞掉异常
                callback_error.append(exc)

        def sample_loop() -> None:
            """第三方下载阻塞期间周期采样临时目录。"""
            while not stop_sampling.wait(self._sample_interval_seconds):
                emit({"phase": "downloading"})

        sampler = Thread(target=sample_loop, name="thinkrag-embedding-progress", daemon=True)
        sampler.start()
        try:
            emit({"phase": "downloading"})
            result = self._call_prepare(
                model_name,
                provider=provider,
                temp_dir=temp_dir,
                progress_callback=emit,
                cancel_event=cancel_event,
            )
            emit({"phase": "downloading"})
            if cancel_event.is_set():
                raise EmbeddingDownloadCancelled("Embedding download was cancelled.")
            error = result.get("error")
            if error:
                raise RuntimeError(str(error))
            progress_callback(
                {
                    "phase": "verifying",
                    "bytes_downloaded": max(
                        int(preflight.get("bytes_total") or 0),
                        _directory_size(target)[0],
                    ),
                    "bytes_total": int(preflight.get("bytes_total") or 0),
                    "progress_mode": preflight.get("progress_mode") or "estimated",
                    "current_file": None,
                }
            )
            cache_ready = bool((result.get("after") or {}).get("local_path_exists"))
            if not cache_ready:
                raise RuntimeError("Embedding cache is still unavailable after preparation.")
            if callback_error:
                raise RuntimeError(f"Embedding progress callback failed: {callback_error[0]}")
            return result
        finally:
            stop_sampling.set()
            sampler.join(timeout=max(0.2, self._sample_interval_seconds * 3))
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _call_prepare(
        self,
        model_name: str,
        *,
        provider: str,
        temp_dir: Path,
        progress_callback: ProgressCallback,
        cancel_event: Event,
    ) -> dict[str, Any]:
        """兼容旧三参数下载函数，同时为新版脚本传递控制参数。"""
        kwargs: dict[str, Any] = {"download": True, "provider": provider}
        try:
            signature = inspect.signature(self._prepare_func)
            accepts_kwargs = any(
                parameter.kind is inspect.Parameter.VAR_KEYWORD
                for parameter in signature.parameters.values()
            )
            if accepts_kwargs or "temp_dir" in signature.parameters:
                kwargs.update(
                    temp_dir=str(temp_dir),
                    progress_callback=progress_callback,
                    cancel_event=cancel_event,
                )
        except (TypeError, ValueError):
            pass
        try:
            return self._prepare_func(model_name, **kwargs)
        except TypeError as exc:
            if "unexpected keyword argument" not in str(exc) or not any(
                key in kwargs for key in ("temp_dir", "progress_callback", "cancel_event")
            ):
                raise
            return self._prepare_func(model_name, download=True, provider=provider)

    def _get_modelscope_files(self, model_id: str) -> list[dict[str, Any]]:
        """调用 ModelScope 官方 Hub API 获取模型文件元数据。"""
        if self._modelscope_files_getter is not None:
            return self._modelscope_files_getter(model_id)
        from modelscope.hub.api import HubApi

        return HubApi().get_model_files(model_id, recursive=True)

    def _resolve_remote_size(self, model_name: str, provider: str) -> int | None:
        """限时读取 ModelScope 文件元数据总量；失败或超时返回空值。"""
        if provider.strip().lower() != "modelscope":
            return None
        model_id = MODELSCOPE_MODEL_PATH.get(model_name)
        if not model_id:
            return None

        outcome: dict[str, Any] = {}

        def load_metadata() -> None:
            """在线程内执行可能阻塞的远端元数据请求。"""
            try:
                outcome["files"] = self._get_modelscope_files(model_id)
            except Exception as exc:  # 网络和 SDK 错误统一触发保守回退
                outcome["error"] = exc

        worker = Thread(target=load_metadata, name="thinkrag-modelscope-metadata", daemon=True)
        worker.start()
        worker.join(self._metadata_timeout_seconds)
        if worker.is_alive() or outcome.get("error") is not None:
            return None

        total = 0
        for item in outcome.get("files") or []:
            if not isinstance(item, dict):
                continue
            raw_size = item.get("Size", item.get("size"))
            try:
                size = int(raw_size)
            except (TypeError, ValueError):
                continue
            if size > 0:
                total += size
        return total or None


__all__ = [
    "EmbeddingDownloadAdapter",
    "EmbeddingDownloadCancelled",
]
