"""embedding 模型路径诊断测试。"""

from __future__ import annotations

from pathlib import Path

from server.models import embedding as embedding_module


def test_embedding_diagnostics_prefers_existing_local_cache(monkeypatch, tmp_path: Path) -> None:
    """本地模型缓存存在时，应诊断为 local 加载。"""

    model_dir = tmp_path / "localmodels"
    local_model = model_dir / "BAAI" / "bge-small-zh-v1.5"
    local_model.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(embedding_module, "MODEL_DIR", "localmodels")
    monkeypatch.setattr(
        embedding_module,
        "EMBEDDING_MODEL_PATH",
        {"bge-small-zh-v1.5": "BAAI/bge-small-zh-v1.5"},
    )

    diagnostics = embedding_module.get_embedding_model_diagnostics("bge-small-zh-v1.5")

    assert diagnostics["load_source"] == "local"
    assert diagnostics["local_path_exists"] is True
    assert diagnostics["allow_remote_download"] is False
    assert diagnostics["local_path"] == "./localmodels/BAAI/bge-small-zh-v1.5"
    assert diagnostics["recommendations"] == []


def test_embedding_diagnostics_reports_remote_fallback_when_cache_missing(monkeypatch, tmp_path: Path) -> None:
    """本地缓存缺失时，应明确提示远程回退和预下载建议。"""

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(embedding_module, "MODEL_DIR", "localmodels")
    monkeypatch.setattr(
        embedding_module,
        "EMBEDDING_MODEL_PATH",
        {"bge-small-zh-v1.5": "BAAI/bge-small-zh-v1.5"},
    )

    diagnostics = embedding_module.get_embedding_model_diagnostics("bge-small-zh-v1.5")

    assert diagnostics["load_source"] == "remote"
    assert diagnostics["local_path_exists"] is False
    assert diagnostics["allow_remote_download"] is True
    assert diagnostics["hf_model_path"] == "BAAI/bge-small-zh-v1.5"
    assert any("Local embedding model cache is missing" in item for item in diagnostics["recommendations"])
    assert any("Pre-download" in item for item in diagnostics["recommendations"])


def test_embedding_diagnostics_reports_unknown_model(monkeypatch) -> None:
    """未知 embedding 名称应返回支持列表，避免 KeyError 样式错误。"""

    monkeypatch.setattr(
        embedding_module,
        "EMBEDDING_MODEL_PATH",
        {"bge-small-zh-v1.5": "BAAI/bge-small-zh-v1.5"},
    )

    diagnostics = embedding_module.get_embedding_model_diagnostics("missing-model")

    assert diagnostics["model_name"] == "missing-model"
    assert diagnostics["hf_model_path"] is None
    assert diagnostics["load_source"] == "remote"
    assert diagnostics["known_models"] == ["bge-small-zh-v1.5"]
    assert "Select one of supported embedding models" in diagnostics["recommendations"][0]
