"""Embedding 下载适配器测试。"""

from __future__ import annotations

from pathlib import Path
from threading import Event

import pytest

from api.services.embedding_download_adapter import (
    EmbeddingDownloadAdapter,
    EmbeddingDownloadCancelled,
)


def _diagnostics(target: Path, *, exists: bool = False) -> dict:
    return {
        "hf_model_path": "BAAI/bge-small-zh-v1.5",
        "local_path": str(target),
        "local_path_exists": exists,
    }


def test_preflight_uses_exact_remote_size_and_reserve(tmp_path, monkeypatch) -> None:
    """远端元数据可用时应给出 exact 总量并计算 20%/512MiB 预留。"""
    target = tmp_path / "models" / "bge"
    adapter = EmbeddingDownloadAdapter(
        diagnostics_getter=lambda model, allow_remote_download: _diagnostics(target),
        remote_size_resolver=lambda model, provider: 3 * 1024**3,
        disk_usage_getter=lambda path: (10 * 1024**3, 0, 5 * 1024**3),
    )

    result = adapter.preflight("bge-small-zh-v1.5", provider="modelscope")

    assert result["progress_mode"] == "exact"
    assert result["required_bytes"] == 3 * 1024**3
    assert result["reserve_bytes"] == int(3 * 1024**3 * 0.2)
    assert result["enough_space"] is True
    assert result["target_dir"] == str(target)


def test_preflight_falls_back_to_estimated_size_and_detects_shortage(tmp_path) -> None:
    """元数据不可用时应使用保守估值，且空间不足给出结构化结果。"""
    target = tmp_path / "models" / "bge"
    adapter = EmbeddingDownloadAdapter(
        diagnostics_getter=lambda model, allow_remote_download: _diagnostics(target),
        remote_size_resolver=lambda model, provider: None,
        disk_usage_getter=lambda path: (3 * 1024**3, 0, 2 * 1024**3),
        default_required_bytes=2 * 1024**3,
    )

    result = adapter.preflight("bge-small-zh-v1.5", provider="modelscope")

    assert result["progress_mode"] == "estimated"
    assert result["required_bytes"] == 2 * 1024**3
    assert result["reserve_bytes"] == 512 * 1024**2
    assert result["enough_space"] is False
    assert result["shortfall_bytes"] == 512 * 1024**2


def test_prepare_samples_temp_directory_and_cleans_it(tmp_path) -> None:
    """下载期间应按实际落盘字节报告进度，成功或结束后清理本次临时目录。"""
    target = tmp_path / "models" / "bge"
    events: list[dict] = []

    def prepare_func(model_name, *, download, provider, temp_dir, progress_callback, cancel_event):
        temp = Path(temp_dir)
        temp.mkdir(parents=True, exist_ok=True)
        (temp / "weights.bin").write_bytes(b"x" * 64)
        progress_callback({"phase": "downloading", "current_file": "weights.bin"})
        target.parent.mkdir(parents=True, exist_ok=True)
        temp.replace(target)
        return {"error": None, "downloaded": True, "after": _diagnostics(target, exists=True)}

    adapter = EmbeddingDownloadAdapter(
        diagnostics_getter=lambda model, allow_remote_download: _diagnostics(target, exists=target.exists()),
        prepare_func=prepare_func,
        remote_size_resolver=lambda model, provider: 128,
        disk_usage_getter=lambda path: (10_000, 0, 10_000),
    )

    result = adapter.prepare(
        "bge-small-zh-v1.5",
        provider="modelscope",
        preflight=adapter.preflight("bge-small-zh-v1.5", provider="modelscope"),
        progress_callback=events.append,
        cancel_event=Event(),
    )

    assert result["after"]["local_path_exists"] is True
    assert any(event.get("bytes_downloaded", 0) >= 64 for event in events)
    assert events[-1]["phase"] == "verifying"
    assert not any(path.name.startswith(".thinkrag-embedding-") for path in target.parent.iterdir())


def test_prepare_checks_cancel_and_removes_partial_temp_dir(tmp_path) -> None:
    """取消检查点必须终止任务并删除 partial，不得删除已有完整缓存。"""
    target = tmp_path / "models" / "bge"
    old_cache = tmp_path / "models" / "old-complete"
    old_cache.mkdir(parents=True)
    (old_cache / "keep.bin").write_bytes(b"ok")
    cancel_event = Event()

    def prepare_func(model_name, *, download, provider, temp_dir, progress_callback, cancel_event):
        temp = Path(temp_dir)
        temp.mkdir(parents=True, exist_ok=True)
        (temp / "partial.bin").write_bytes(b"partial")
        cancel_event.set()
        progress_callback({"phase": "downloading", "current_file": "partial.bin"})
        raise EmbeddingDownloadCancelled("cancelled")

    adapter = EmbeddingDownloadAdapter(
        diagnostics_getter=lambda model, allow_remote_download: _diagnostics(target),
        prepare_func=prepare_func,
        remote_size_resolver=lambda model, provider: 100,
        disk_usage_getter=lambda path: (10_000, 0, 10_000),
    )

    with pytest.raises(EmbeddingDownloadCancelled):
        adapter.prepare(
            "bge-small-zh-v1.5",
            provider="modelscope",
            preflight=adapter.preflight("bge-small-zh-v1.5", provider="modelscope"),
            progress_callback=lambda event: None,
            cancel_event=cancel_event,
        )

    assert (old_cache / "keep.bin").read_bytes() == b"ok"
    assert not any(path.name.startswith(".thinkrag-embedding-") for path in target.parent.iterdir())


def test_default_modelscope_metadata_resolver_sums_file_sizes(tmp_path) -> None:
    """默认 ModelScope resolver 应汇总官方文件元数据并进入 exact 模式。"""
    target = tmp_path / "models" / "bge"
    calls: list[str] = []

    def get_files(model_id):
        calls.append(model_id)
        return [
            {"Path": "config.json", "Size": 10},
            {"Path": "model.safetensors", "Size": "90"},
            {"Path": "README.md", "Size": None},
        ]

    adapter = EmbeddingDownloadAdapter(
        diagnostics_getter=lambda model, allow_remote_download: _diagnostics(target),
        modelscope_files_getter=get_files,
        disk_usage_getter=lambda path: (10_000, 0, 10_000),
    )

    result = adapter.preflight("bge-small-zh-v1.5", provider="modelscope")

    assert calls == ["AI-ModelScope/bge-small-zh-v1.5"]
    assert result["required_bytes"] == 100
    assert result["bytes_total"] == 100
    assert result["progress_mode"] == "exact"


def test_modelscope_metadata_timeout_falls_back_without_blocking_preflight(tmp_path) -> None:
    """远端元数据超时后应快速回退保守估值。"""
    import time

    target = tmp_path / "models" / "bge"

    def slow_get_files(model_id):
        time.sleep(0.2)
        return [{"Path": "model.bin", "Size": 100}]

    adapter = EmbeddingDownloadAdapter(
        diagnostics_getter=lambda model, allow_remote_download: _diagnostics(target),
        modelscope_files_getter=slow_get_files,
        metadata_timeout_seconds=0.05,
        default_required_bytes=2048,
        disk_usage_getter=lambda path: (10_000, 0, 10_000),
    )

    started = time.perf_counter()
    result = adapter.preflight("bge-small-zh-v1.5", provider="modelscope")

    assert time.perf_counter() - started < 0.15
    assert result["required_bytes"] == 2048
    assert result["progress_mode"] == "estimated"
