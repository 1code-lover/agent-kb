"""embedding 本地缓存准备脚本测试。"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from threading import Event

import pytest

import scripts.prepare_embedding_model_cache as prepare_cache


def _localmodels_target() -> str:
    """返回断言用的规范化本地模型路径。"""

    return (Path("localmodels") / "BAAI" / "bge-small-zh-v1.5").as_posix()


def test_prepare_embedding_model_cache_dry_run_reports_missing_cache(monkeypatch, tmp_path: Path) -> None:
    """未传 --download 时只输出诊断，不创建本地缓存目录。"""

    monkeypatch.chdir(tmp_path)

    result = prepare_cache.prepare_embedding_model_cache("bge-small-zh-v1.5", download=False)

    assert result["download_requested"] is False
    assert result["download_provider"] == "huggingface"
    assert result["source_dir"] is None
    assert result["imported_from_source"] is False
    assert result["downloaded"] is False
    assert result["skipped"] is True
    assert result["before"]["local_path_exists"] is False
    assert result["before"]["load_source"] == "remote"
    assert not (tmp_path / "localmodels").exists()


def test_prepare_embedding_model_cache_rejects_unknown_model() -> None:
    """未知 embedding 名称应返回 error，避免下载错误 repo。"""

    result = prepare_cache.prepare_embedding_model_cache("missing-model", download=True)

    assert result["downloaded"] is False
    assert result["error"] == "Unknown embedding model: missing-model"


def test_prepare_embedding_model_cache_rejects_unknown_provider() -> None:
    """未知下载来源应返回 error。"""

    result = prepare_cache.prepare_embedding_model_cache(
        "bge-small-zh-v1.5",
        download=True,
        provider="unknown",
    )

    assert result["downloaded"] is False
    assert result["error"] == "Unsupported download provider: unknown"


def test_prepare_embedding_model_cache_skips_existing_local_cache(monkeypatch, tmp_path: Path) -> None:
    """本地缓存已存在时应跳过下载。"""

    local_model = tmp_path / "localmodels" / "BAAI" / "bge-small-zh-v1.5"
    local_model.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    result = prepare_cache.prepare_embedding_model_cache("bge-small-zh-v1.5", download=True)

    assert result["skipped"] is True
    assert result["downloaded"] is False
    assert result["before"]["local_path_exists"] is True
    assert result["error"] is None


def test_prepare_embedding_model_cache_downloads_to_project_localmodels(monkeypatch, tmp_path: Path) -> None:
    """显式 download 时应调用 huggingface_hub.snapshot_download 到 localmodels。"""

    calls: list[dict[str, object]] = []

    def fake_snapshot_download(**kwargs):
        calls.append(kwargs)
        target = Path(str(kwargs["local_dir"]))
        target.mkdir(parents=True, exist_ok=True)
        (target / "config.json").write_text("{}", encoding="utf-8")
        return str(target)

    fake_hf = types.SimpleNamespace(snapshot_download=fake_snapshot_download)
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hf)
    monkeypatch.chdir(tmp_path)

    result = prepare_cache.prepare_embedding_model_cache("bge-small-zh-v1.5", download=True)

    assert result["downloaded"] is True
    assert result["after"]["local_path_exists"] is True
    assert len(calls) == 1
    assert calls[0] == {
        "repo_id": "BAAI/bge-small-zh-v1.5",
        "local_dir": str(Path("localmodels") / "BAAI" / "bge-small-zh-v1.5"),
        "local_dir_use_symlinks": False,
        "resume_download": True,
    }
    assert Path(str(calls[0]["local_dir"])).as_posix() == _localmodels_target()


def test_prepare_embedding_model_cache_downloads_from_modelscope(monkeypatch, tmp_path: Path) -> None:
    """显式 provider=modelscope 时应调用 ModelScope 下载到 localmodels。"""

    calls: list[dict[str, object]] = []

    def fake_modelscope_snapshot_download(**kwargs):
        calls.append(kwargs)
        target = Path(str(kwargs["local_dir"]))
        target.mkdir(parents=True, exist_ok=True)
        (target / "config.json").write_text("{}", encoding="utf-8")
        return str(target)

    fake_snapshot_module = types.SimpleNamespace(snapshot_download=fake_modelscope_snapshot_download)
    monkeypatch.setitem(sys.modules, "modelscope.hub.snapshot_download", fake_snapshot_module)
    monkeypatch.chdir(tmp_path)

    result = prepare_cache.prepare_embedding_model_cache(
        "bge-small-zh-v1.5",
        download=True,
        provider="modelscope",
    )

    assert result["downloaded"] is True
    assert result["download_provider"] == "modelscope"
    assert result["after"]["local_path_exists"] is True
    assert len(calls) == 1
    assert calls[0] == {
        "model_id": "AI-ModelScope/bge-small-zh-v1.5",
        "local_dir": str(Path("localmodels") / "BAAI" / "bge-small-zh-v1.5"),
    }
    assert Path(str(calls[0]["local_dir"])).as_posix() == _localmodels_target()


def test_prepare_embedding_model_cache_imports_from_source_dir(monkeypatch, tmp_path: Path) -> None:
    """传入 source_dir 时应从本地目录复制模型缓存。"""

    source_dir = tmp_path / "snapshot"
    source_dir.mkdir()
    (source_dir / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = prepare_cache.prepare_embedding_model_cache(
        "bge-small-zh-v1.5",
        source_dir=str(source_dir),
    )

    local_model = tmp_path / "localmodels" / "BAAI" / "bge-small-zh-v1.5"
    assert result["imported_from_source"] is True
    assert result["downloaded"] is False
    assert result["after"]["local_path_exists"] is True
    assert (local_model / "config.json").read_text(encoding="utf-8") == "{}"


def test_prepare_embedding_model_cache_reports_missing_source_dir(monkeypatch, tmp_path: Path) -> None:
    """source_dir 不存在时应返回结构化 error。"""

    monkeypatch.chdir(tmp_path)

    result = prepare_cache.prepare_embedding_model_cache(
        "bge-small-zh-v1.5",
        source_dir=str(tmp_path / "missing"),
    )

    assert result["imported_from_source"] is False
    assert result["error"].startswith("Source import failed: FileNotFoundError")


def test_prepare_embedding_model_cache_reports_download_failure(monkeypatch, tmp_path: Path) -> None:
    """下载异常应进入 JSON error，而不是抛出 traceback。"""

    def fake_snapshot_download(**kwargs):
        raise TimeoutError("mirror timeout")

    fake_hf = types.SimpleNamespace(snapshot_download=fake_snapshot_download)
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hf)
    monkeypatch.chdir(tmp_path)

    result = prepare_cache.prepare_embedding_model_cache("bge-small-zh-v1.5", download=True)

    assert result["downloaded"] is False
    assert result["after"]["local_path_exists"] is False
    assert result["error"] == "Download failed via huggingface: TimeoutError: mirror timeout"



def test_prepare_embedding_model_cache_uses_atomic_temp_dir_and_reports_progress(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """显式临时目录应在校验后原子移动，并报告下载与校验阶段。"""

    phases: list[str] = []
    partial = tmp_path / ".embedding.partial"

    def fake_snapshot_download(**kwargs):
        target = Path(str(kwargs["local_dir"]))
        target.mkdir(parents=True, exist_ok=True)
        (target / "config.json").write_text("{}", encoding="utf-8")
        return str(target)

    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        types.SimpleNamespace(snapshot_download=fake_snapshot_download),
    )
    monkeypatch.chdir(tmp_path)

    result = prepare_cache.prepare_embedding_model_cache(
        "bge-small-zh-v1.5",
        download=True,
        temp_dir=str(partial),
        progress_callback=lambda event: phases.append(str(event["phase"])),
    )

    target = tmp_path / "localmodels" / "BAAI" / "bge-small-zh-v1.5"
    assert result["downloaded"] is True
    assert phases == ["downloading", "verifying"]
    assert (target / "config.json").is_file()
    assert not partial.exists()


def test_prepare_embedding_model_cache_cancellation_cleans_direct_target(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """下载开始前收到取消时应抛出取消异常并清理本次创建的目标目录。"""

    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        types.SimpleNamespace(snapshot_download=lambda **kwargs: None),
    )
    monkeypatch.chdir(tmp_path)
    cancel_event = Event()
    cancel_event.set()

    with pytest.raises(prepare_cache.EmbeddingDownloadCancelled):
        prepare_cache.prepare_embedding_model_cache(
            "bge-small-zh-v1.5",
            download=True,
            cancel_event=cancel_event,
        )

    assert not (tmp_path / "localmodels" / "BAAI" / "bge-small-zh-v1.5").exists()


def test_prepare_embedding_model_cache_rejects_empty_download_and_cleans_target(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """下载器未写入任何文件时不得把空目录标记为完整缓存。"""

    def fake_snapshot_download(**kwargs):
        Path(str(kwargs["local_dir"])).mkdir(parents=True, exist_ok=True)

    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        types.SimpleNamespace(snapshot_download=fake_snapshot_download),
    )
    monkeypatch.chdir(tmp_path)

    result = prepare_cache.prepare_embedding_model_cache("bge-small-zh-v1.5", download=True)

    assert result["downloaded"] is False
    assert result["error"] == "Download failed via huggingface: RuntimeError: Downloaded embedding cache is empty."
    assert result["after"]["local_path_exists"] is False
