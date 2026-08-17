"""Embedding 缓存后台恢复状态机测试。"""

from __future__ import annotations

from threading import Event, Thread
from types import SimpleNamespace

from api.services.embedding_cache_service import EmbeddingCacheService


def test_prepare_success_marks_cache_ready_and_starts_warmup(monkeypatch) -> None:
    """ModelScope 准备成功后应重置旧模型状态并重新触发 embedding 预热。"""
    runtime = SimpleNamespace(
        _get_configured_embedding_model_name=lambda: "bge-small-zh-v1.5",
        reset_embedding_runtime=lambda: calls.append("reset"),
        start_embedding_warmup_in_background=lambda: calls.append("warmup") or True,
    )
    calls: list[str] = []
    service = EmbeddingCacheService(runtime=runtime)
    monkeypatch.setattr(
        "api.services.embedding_cache_service.prepare_embedding_model_cache",
        lambda model_name, download, provider: {
            "model_name": model_name,
            "downloaded": True,
            "error": None,
            "after": {"local_path_exists": True, "local_path": "/tmp/model"},
        },
    )

    service._run_prepare("modelscope", "bge-small-zh-v1.5")

    status = service.get_status()
    assert status["state"] == "ready"
    assert status["result"]["downloaded"] is True
    assert status["warmup_started"] is True
    assert calls == ["reset", "warmup"]


def test_prepare_failure_is_retryable_and_does_not_start_warmup(monkeypatch) -> None:
    """下载失败应保留可展示错误，且不污染 embedding 运行时。"""
    runtime = SimpleNamespace(
        _get_configured_embedding_model_name=lambda: "bge-small-zh-v1.5",
        reset_embedding_runtime=lambda: calls.append("reset"),
        start_embedding_warmup_in_background=lambda: calls.append("warmup") or True,
    )
    calls: list[str] = []
    service = EmbeddingCacheService(runtime=runtime)
    monkeypatch.setattr(
        "api.services.embedding_cache_service.prepare_embedding_model_cache",
        lambda model_name, download, provider: {
            "model_name": model_name,
            "downloaded": False,
            "error": "modelscope unavailable",
            "after": {"local_path_exists": False},
        },
    )

    service._run_prepare("modelscope", "bge-small-zh-v1.5")

    status = service.get_status()
    assert status["state"] == "failed"
    assert status["last_error"] == "modelscope unavailable"
    assert calls == []


def test_start_prepare_does_not_spawn_duplicate_download(monkeypatch) -> None:
    """连续点击恢复按钮时，同一时刻只能存在一个下载线程。"""
    runtime = SimpleNamespace(_get_configured_embedding_model_name=lambda: "bge-small-zh-v1.5")
    service = EmbeddingCacheService(runtime=runtime)

    class AliveThread:
        def is_alive(self) -> bool:
            return True

    service._thread = AliveThread()
    service._status["state"] = "downloading"

    status, started = service.start_prepare(provider="modelscope")

    assert started is False
    assert status["state"] == "downloading"


def test_start_prepare_closes_pre_start_duplicate_thread_race(monkeypatch) -> None:
    """线程登记到真正 start 之间也必须保持幂等，避免并发请求各自创建下载线程。"""
    runtime = SimpleNamespace(_get_configured_embedding_model_name=lambda: "bge-small-zh-v1.5")
    service = EmbeddingCacheService(runtime=runtime)
    start_entered = Event()
    release_start = Event()
    second_finished = Event()
    created_threads: list[object] = []
    results: list[tuple[dict, bool]] = []

    class ControlledThread:
        def __init__(self, **kwargs) -> None:
            self.alive = False
            created_threads.append(self)

        def start(self) -> None:
            start_entered.set()
            assert release_start.wait(timeout=1)
            self.alive = True

        def is_alive(self) -> bool:
            return self.alive

    monkeypatch.setattr("api.services.embedding_cache_service.Thread", ControlledThread)

    first = Thread(target=lambda: results.append(service.start_prepare(provider="modelscope")))

    def run_second() -> None:
        results.append(service.start_prepare(provider="modelscope"))
        second_finished.set()

    second = Thread(target=run_second)
    first.start()
    assert start_entered.wait(timeout=1)
    second.start()

    assert second_finished.wait(timeout=0.05) is False
    release_start.set()
    first.join(timeout=1)
    second.join(timeout=1)

    assert len(created_threads) == 1
    assert sorted(started for _, started in results) == [False, True]
