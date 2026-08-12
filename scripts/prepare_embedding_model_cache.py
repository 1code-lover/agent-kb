"""准备 embedding 模型本地缓存，降低 API 冷启动等待。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import config
from server.models.embedding import get_embedding_model_diagnostics
from server.utils.hf_mirror import use_hf_mirror


def _normalize_local_path(local_path: str | None) -> Path | None:
    """把诊断里的本地路径转换为 Path。"""
    if not local_path:
        return None
    return Path(local_path)


def prepare_embedding_model_cache(model_name: str, *, download: bool = False) -> dict[str, Any]:
    """诊断或下载指定 embedding 模型到 localmodels。"""
    diagnostics = get_embedding_model_diagnostics(model_name)
    result: dict[str, Any] = {
        "model_name": model_name,
        "download_requested": download,
        "before": diagnostics,
        "after": diagnostics,
        "downloaded": False,
        "skipped": False,
        "error": None,
    }
    if diagnostics.get("hf_model_path") is None:
        result["error"] = f"Unknown embedding model: {model_name}"
        return result
    if diagnostics.get("local_path_exists"):
        result["skipped"] = True
        return result
    if not download:
        result["skipped"] = True
        return result

    local_path = _normalize_local_path(diagnostics.get("local_path"))
    if local_path is None:
        result["error"] = "Local model path is unavailable."
        return result

    try:
        from huggingface_hub import snapshot_download
    except Exception as exc:
        result["error"] = f"huggingface_hub is unavailable: {type(exc).__name__}: {exc}"
        return result

    use_hf_mirror()
    local_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=str(diagnostics["hf_model_path"]),
        local_dir=str(local_path),
        local_dir_use_symlinks=False,
        resume_download=True,
    )
    result["downloaded"] = True
    result["after"] = get_embedding_model_diagnostics(model_name)
    return result


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="准备 embedding 模型本地缓存")
    parser.add_argument("--model", default=config.DEFAULT_EMBEDDING_MODEL, help="embedding 模型名称")
    parser.add_argument("--download", action="store_true", help="实际下载模型；未传时只输出诊断")
    args = parser.parse_args()

    result = prepare_embedding_model_cache(args.model, download=args.download)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("error"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
