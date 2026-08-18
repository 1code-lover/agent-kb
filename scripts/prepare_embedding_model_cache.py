"""准备 embedding 模型本地缓存，降低 API 冷启动等待。"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from threading import Event
from typing import Any, Callable

import config
from server.models.embedding import get_embedding_model_diagnostics
from server.utils.hf_mirror import use_hf_mirror

DOWNLOAD_PROVIDERS = {"huggingface", "modelscope"}
ProgressCallback = Callable[[dict[str, Any]], None]


class EmbeddingDownloadCancelled(RuntimeError):
    """表示 embedding 下载收到协作式取消请求。"""


MODELSCOPE_MODEL_PATH = {
    "bge-small-zh-v1.5": "AI-ModelScope/bge-small-zh-v1.5",
    "bge-large-zh-v1.5": "AI-ModelScope/bge-large-zh-v1.5",
}


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
    provider: str = "huggingface",
    progress_callback: ProgressCallback | None = None,
    cancel_event: Event | None = None,
    temp_dir: str | None = None,
) -> dict[str, Any]:
    """诊断或下载指定 embedding 模型到 localmodels。"""
    will_import_local = bool(source_dir)
    normalized_provider = provider.strip().lower()
    diagnostics = get_embedding_model_diagnostics(model_name, allow_remote_download=download)
    result: dict[str, Any] = {
        "model_name": model_name,
        "download_requested": download,
        "download_provider": normalized_provider,
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
    if normalized_provider not in DOWNLOAD_PROVIDERS:
        result["error"] = f"Unsupported download provider: {provider}"
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

    local_path.parent.mkdir(parents=True, exist_ok=True)
    download_path = Path(temp_dir).expanduser().resolve() if temp_dir else local_path

    def check_cancel() -> None:
        """在不会破坏完整缓存的安全点响应取消。"""
        if cancel_event is not None and cancel_event.is_set():
            raise EmbeddingDownloadCancelled("Embedding download was cancelled.")

    def report(phase: str, current_file: str | None = None) -> None:
        """向上层报告脚本可感知的阶段。"""
        if progress_callback is not None:
            progress_callback({"phase": phase, "current_file": current_file})

    def cleanup_incomplete_download() -> None:
        """清理本次创建的临时目录或不完整目标，不触碰既有完整缓存。"""
        shutil.rmtree(download_path, ignore_errors=True)

    if normalized_provider == "modelscope":
        try:
            from modelscope.hub.snapshot_download import snapshot_download as modelscope_snapshot_download
        except Exception as exc:
            result["error"] = f"modelscope is unavailable: {type(exc).__name__}: {exc}"
            return result
        modelscope_model_id = MODELSCOPE_MODEL_PATH.get(model_name)
        if not modelscope_model_id:
            result["error"] = f"ModelScope mapping is unavailable for model: {model_name}"
            return result
    else:
        try:
            from huggingface_hub import snapshot_download
        except Exception as exc:
            result["error"] = f"huggingface_hub is unavailable: {type(exc).__name__}: {exc}"
            return result

    cleanup_incomplete_download()
    download_path.mkdir(parents=True, exist_ok=True)
    try:
        check_cancel()
        report("downloading")
        if normalized_provider == "modelscope":
            modelscope_snapshot_download(model_id=modelscope_model_id, local_dir=str(download_path))
        else:
            use_hf_mirror()
            snapshot_download(
                repo_id=str(diagnostics["hf_model_path"]),
                local_dir=str(download_path),
                local_dir_use_symlinks=False,
                resume_download=True,
            )
        check_cancel()
        if not any(item.is_file() for item in download_path.rglob("*")):
            raise RuntimeError("Downloaded embedding cache is empty.")
        report("verifying")
        if download_path != local_path:
            if local_path.exists():
                raise FileExistsError(f"Embedding cache target already exists: {local_path}")
            os.replace(download_path, local_path)
        check_cancel()
    except EmbeddingDownloadCancelled:
        cleanup_incomplete_download()
        raise
    except Exception as exc:
        cleanup_incomplete_download()
        result["error"] = f"Download failed via {normalized_provider}: {type(exc).__name__}: {exc}"
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
    parser.add_argument(
        "--provider",
        choices=sorted(DOWNLOAD_PROVIDERS),
        default="huggingface",
        help="下载来源；默认 huggingface，可显式指定 modelscope",
    )
    parser.add_argument("--source-dir", help="从已有本地模型目录复制到项目 localmodels")
    args = parser.parse_args()

    result = prepare_embedding_model_cache(
        args.model,
        download=args.download,
        source_dir=args.source_dir,
        provider=args.provider,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("error"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
