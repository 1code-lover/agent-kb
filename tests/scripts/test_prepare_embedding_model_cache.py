"""embedding 本地缓存准备脚本测试。"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import scripts.prepare_embedding_model_cache as prepare_cache


def test_prepare_embedding_model_cache_dry_run_reports_missing_cache(monkeypatch, tmp_path: Path) -> None:
    """未传 --download 时只输出诊断，不创建本地缓存目录。"""

    monkeypatch.chdir(tmp_path)

    result = prepare_cache.prepare_embedding_model_cache("bge-small-zh-v1.5", download=False)

    assert result["download_requested"] is False
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
        Path(str(kwargs["local_dir"])).mkdir(parents=True, exist_ok=True)
        return str(kwargs["local_dir"])

    fake_hf = types.SimpleNamespace(snapshot_download=fake_snapshot_download)
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hf)
    monkeypatch.chdir(tmp_path)

    result = prepare_cache.prepare_embedding_model_cache("bge-small-zh-v1.5", download=True)

    assert result["downloaded"] is True
    assert result["after"]["local_path_exists"] is True
    assert calls == [
        {
            "repo_id": "BAAI/bge-small-zh-v1.5",
            "local_dir": "localmodels/BAAI/bge-small-zh-v1.5",
            "local_dir_use_symlinks": False,
            "resume_download": True,
        }
    ]


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
    assert result["error"] == "Download failed: TimeoutError: mirror timeout"
