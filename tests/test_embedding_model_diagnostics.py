"""embedding 模型路径诊断测试。"""

from __future__ import annotations

from pathlib import Path

from llama_index.core import Settings
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
    assert Path(diagnostics["local_path"]).as_posix() == "localmodels/BAAI/bge-small-zh-v1.5"
    assert diagnostics["recommendations"] == []


def test_embedding_diagnostics_blocks_runtime_remote_download_when_cache_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """本地缓存缺失时，运行时默认不应直接走远程下载。"""

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
    assert diagnostics["allow_remote_download"] is False
    assert diagnostics["hf_model_path"] == "BAAI/bge-small-zh-v1.5"
    assert any("Local embedding model cache is missing" in item for item in diagnostics["recommendations"])
    assert any("Pre-download" in item for item in diagnostics["recommendations"])
    assert any("EMBEDDING_ALLOW_REMOTE_DOWNLOAD=1" in item for item in diagnostics["recommendations"])


def test_embedding_diagnostics_can_allow_explicit_remote_download(monkeypatch, tmp_path: Path) -> None:
    """显式允许远程时，应在诊断中暴露下载风险。"""

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(embedding_module, "MODEL_DIR", "localmodels")
    monkeypatch.setattr(
        embedding_module,
        "EMBEDDING_MODEL_PATH",
        {"bge-small-zh-v1.5": "BAAI/bge-small-zh-v1.5"},
    )

    diagnostics = embedding_module.get_embedding_model_diagnostics(
        "bge-small-zh-v1.5",
        allow_remote_download=True,
    )

    assert diagnostics["load_source"] == "remote"
    assert diagnostics["local_path_exists"] is False
    assert diagnostics["allow_remote_download"] is True
    assert any("Remote download is explicitly enabled" in item for item in diagnostics["recommendations"])


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


def test_create_embedding_model_fails_fast_when_cache_missing_and_remote_disabled(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """缓存缺失且未允许远程下载时，不应调用 HuggingFaceEmbedding 卡住启动。"""

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Settings, "_embed_model", None, raising=False)
    monkeypatch.setattr(embedding_module, "MODEL_DIR", "localmodels")
    monkeypatch.setattr(
        embedding_module,
        "EMBEDDING_MODEL_PATH",
        {"bge-small-zh-v1.5": "BAAI/bge-small-zh-v1.5"},
    )

    class ForbiddenEmbedding:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError("HuggingFaceEmbedding should not be initialized without local cache")

    fake_module = type("FakeEmbeddingModule", (), {"HuggingFaceEmbedding": ForbiddenEmbedding})
    monkeypatch.setitem(__import__("sys").modules, "llama_index.embeddings.huggingface", fake_module)

    assert embedding_module.create_embedding_model("bge-small-zh-v1.5") is None
    assert Settings._embed_model is None



def test_create_embedding_model_reports_runtime_agnostic_cache_guidance(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    """缓存缺失报错应提示通用 python 命令，而不是机器绝对路径。"""

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Settings, "_embed_model", None, raising=False)
    monkeypatch.setattr(embedding_module, "MODEL_DIR", "localmodels")
    monkeypatch.setattr(
        embedding_module,
        "EMBEDDING_MODEL_PATH",
        {"bge-small-zh-v1.5": "BAAI/bge-small-zh-v1.5"},
    )

    class ForbiddenEmbedding:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError("HuggingFaceEmbedding should not be initialized without local cache")

    fake_module = type("FakeEmbeddingModule", (), {"HuggingFaceEmbedding": ForbiddenEmbedding})
    monkeypatch.setitem(__import__("sys").modules, "llama_index.embeddings.huggingface", fake_module)

    assert embedding_module.create_embedding_model("bge-small-zh-v1.5") is None

    captured = capsys.readouterr()
    output = f"{captured.out}\n{captured.err}"
    assert "python -m scripts.prepare_embedding_model_cache --download" in output
    assert "KB_PYTHON" in output
    assert "/opt/miniconda3/envs/agent-kb/bin/python" not in output
