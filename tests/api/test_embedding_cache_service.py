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


def test_preflight_reports_space_and_start_rejects_shortage() -> None:
    """空间不足时不得创建线程，并保留可展示的预检字段。"""
    from api.services.embedding_cache_service import InsufficientDiskSpaceError

    class Adapter:
        def preflight(self, model_name, *, provider):
            return {
                "target_dir": "/tmp/model",
                "required_bytes": 200,
                "reserve_bytes": 50,
                "free_bytes": 249,
                "shortfall_bytes": 1,
                "bytes_total": 200,
                "progress_mode": "estimated",
                "enough_space": False,
            }

    runtime = SimpleNamespace(_get_configured_embedding_model_name=lambda: "bge-small-zh-v1.5")
    service = EmbeddingCacheService(runtime=runtime, adapter=Adapter())

    status = service.preflight(provider="modelscope")
    assert status["state"] == "idle"
    assert status["phase"] == "checking_space"
    assert status["required_bytes"] == 200

    try:
        service.start_prepare(provider="modelscope")
    except InsufficientDiskSpaceError as exc:
        assert exc.preflight["shortfall_bytes"] == 1
    else:
        raise AssertionError("空间不足必须拒绝启动")
    assert service._thread is None


def test_progress_is_monotonic_and_never_reaches_100_before_verification() -> None:
    """第三方回调乱序时，服务公开进度仍需单调，校验前最多 99%。"""
    class Adapter:
        def preflight(self, model_name, *, provider):
            return {
                "target_dir": "/tmp/model",
                "required_bytes": 100,
                "reserve_bytes": 50,
                "free_bytes": 1000,
                "shortfall_bytes": 0,
                "bytes_total": 100,
                "progress_mode": "exact",
                "enough_space": True,
            }

        def prepare(self, model_name, *, provider, preflight, progress_callback, cancel_event):
            progress_callback({"phase": "downloading", "bytes_downloaded": 80, "bytes_total": 100})
            progress_callback({"phase": "downloading", "bytes_downloaded": 20, "bytes_total": 100})
            progress_callback({"phase": "downloading", "bytes_downloaded": 150, "bytes_total": 100})
            assert service.get_status()["progress_percent"] == 99.0
            progress_callback({"phase": "verifying", "bytes_downloaded": 100, "bytes_total": 100})
            return {"error": None, "after": {"local_path_exists": True}}

    runtime = SimpleNamespace(
        _get_configured_embedding_model_name=lambda: "bge-small-zh-v1.5",
        reset_embedding_runtime=lambda: None,
        start_embedding_warmup_in_background=lambda: True,
    )
    service = EmbeddingCacheService(runtime=runtime, adapter=Adapter())
    service._run_prepare("modelscope", "bge-small-zh-v1.5", service.preflight(provider="modelscope"))

    status = service.get_status()
    assert status["state"] == "ready"
    assert status["progress_percent"] == 100.0
    assert status["progress_mode"] == "exact"


def test_cancelled_download_does_not_warmup_and_can_retry() -> None:
    """协作取消后进入 cancelled、不预热，并允许下一次重新启动。"""
    from api.services.embedding_download_adapter import EmbeddingDownloadCancelled

    calls: list[str] = []

    class Adapter:
        attempt = 0

        def preflight(self, model_name, *, provider):
            return {
                "target_dir": "/tmp/model",
                "required_bytes": 100,
                "reserve_bytes": 50,
                "free_bytes": 1000,
                "shortfall_bytes": 0,
                "bytes_total": 100,
                "progress_mode": "estimated",
                "enough_space": True,
            }

        def prepare(self, model_name, *, provider, preflight, progress_callback, cancel_event):
            self.attempt += 1
            if self.attempt == 1:
                cancel_event.set()
                raise EmbeddingDownloadCancelled("用户已取消")
            return {"error": None, "after": {"local_path_exists": True}}

    runtime = SimpleNamespace(
        _get_configured_embedding_model_name=lambda: "bge-small-zh-v1.5",
        reset_embedding_runtime=lambda: calls.append("reset"),
        start_embedding_warmup_in_background=lambda: calls.append("warmup") or True,
    )
    adapter = Adapter()
    service = EmbeddingCacheService(runtime=runtime, adapter=adapter)
    preflight = service.preflight(provider="modelscope")

    service._run_prepare("modelscope", "bge-small-zh-v1.5", preflight)
    assert service.get_status()["state"] == "cancelled"
    assert calls == []

    service._run_prepare("modelscope", "bge-small-zh-v1.5", preflight)
    assert service.get_status()["state"] == "ready"
    assert calls == ["reset", "warmup"]


def test_request_cancel_is_idempotent() -> None:
    """仅运行中任务设置取消事件，非运行状态应返回 cancel_requested=false。"""
    runtime = SimpleNamespace(_get_configured_embedding_model_name=lambda: "bge-small-zh-v1.5")
    service = EmbeddingCacheService(runtime=runtime)

    idle = service.request_cancel()
    assert idle["cancel_requested"] is False

    class AliveThread:
        def is_alive(self):
            return True

    service._thread = AliveThread()
    service._status["state"] = "downloading"
    first = service.request_cancel()
    second = service.request_cancel()
    assert first["state"] == "cancelling"
    assert second["state"] == "cancelling"
    assert service._cancel_event.is_set()
