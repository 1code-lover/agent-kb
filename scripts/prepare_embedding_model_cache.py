"""准备 embedding 模型本地缓存，降低 API 冷启动等待。"""

from __future__ import annotations

import argparse
import json
import shutil
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


def _copy_local_model_cache(source_dir: Path, local_path: Path) -> None:
    """把用户提供的本地模型目录复制到项目 localmodels。"""
    if not source_dir.exists() or not source_dir.is_dir():
        raise FileNotFoundError(f"Source directory does not exist: {source_dir}")
    local_path.parent.mkdir(parents=True, exist_ok=True)
    if local_path.exists():
        shutil.rmtree(local_path)
    shutil.copytree(source_dir, local_path, symlinks=True)


def prepare_embedding_model_cache(
    model_name: str,
    *,
    download: bool = False,
    source_dir: str | None = None,
) -> dict[str, Any]:
    """诊断或下载指定 embedding 模型到 localmodels。"""
    will_import_local = bool(source_dir)
    diagnostics = get_embedding_model_diagnostics(model_name, allow_remote_download=download)
    result: dict[str, Any] = {
        "model_name": model_name,
        "download_requested": download,
        "source_dir": source_dir,
        "imported_from_source": False,
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

    local_path = _normalize_local_path(diagnostics.get("local_path"))
    if local_path is None:
        result["error"] = "Local model path is unavailable."
        return result

    if will_import_local:
        try:
            _copy_local_model_cache(Path(str(source_dir)).expanduser(), local_path)
        except Exception as exc:
            result["error"] = f"Source import failed: {type(exc).__name__}: {exc}"
            return result
        result["imported_from_source"] = True
        result["after"] = get_embedding_model_diagnostics(model_name, allow_remote_download=download)
        return result

    if not download:
        result["skipped"] = True
        return result

    try:
        from huggingface_hub import snapshot_download
    except Exception as exc:
        result["error"] = f"huggingface_hub is unavailable: {type(exc).__name__}: {exc}"
        return result

    use_hf_mirror()
    local_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        snapshot_download(
            repo_id=str(diagnostics["hf_model_path"]),
            local_dir=str(local_path),
            local_dir_use_symlinks=False,
            resume_download=True,
        )
    except Exception as exc:
        result["error"] = f"Download failed: {type(exc).__name__}: {exc}"
        result["after"] = get_embedding_model_diagnostics(model_name, allow_remote_download=download)
        return result
    result["downloaded"] = True
    result["after"] = get_embedding_model_diagnostics(model_name, allow_remote_download=download)
    return result


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="准备 embedding 模型本地缓存")
    parser.add_argument("--model", default=config.DEFAULT_EMBEDDING_MODEL, help="embedding 模型名称")
    parser.add_argument("--download", action="store_true", help="实际下载模型；未传时只输出诊断")
    parser.add_argument("--source-dir", help="从已有本地模型目录复制到项目 localmodels")
    args = parser.parse_args()

    result = prepare_embedding_model_cache(args.model, download=args.download, source_dir=args.source_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("error"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
