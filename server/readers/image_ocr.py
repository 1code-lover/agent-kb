"""图片 OCR 能力与运行时预热状态管理。"""

from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
_SUPPORTED_IMAGE_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/bmp",
}
_SIGNATURE_SNIFF_FALLBACK_IMAGE_MIME_TYPES = {"", "application/octet-stream", "binary/octet-stream"}
_OCR_TIMING_FLOAT_FIELDS = (
    "ocr_init_ms",
    "ocr_load_image_ms",
    "ocr_predict_ms",
    "ocr_postprocess_ms",
    "ocr_total_ms",
)
_OCR_RUNTIME_CONFIG = {
    "lang": "ch",
    "use_doc_orientation_classify": False,
    "use_doc_unwarping": False,
    "use_textline_orientation": False,
}
_OCR_INSTANCE = None
_OCR_LOCK = threading.RLock()
_OCR_PREDICT_LOCK = threading.RLock()
_OCR_WARMUP_THREAD: threading.Thread | None = None
_OCR_WARMUP_STATUS: dict[str, Any] = {
    "state": "idle",
    "attempt_count": 0,
    "last_error": None,
    "last_duration_ms": None,
    "started_at": None,
    "finished_at": None,
}
_OCR_WARMUP_LOCK = threading.RLock()


def _utc_now_iso() -> str:
    """返回当前 UTC 时间的 ISO 8601 字符串。"""
    return datetime.now(timezone.utc).isoformat()


def _elapsed_ms(started_at: float) -> float:
    """根据 monotonic 起点计算已耗时毫秒数。"""
    return round(max(time.perf_counter() - started_at, 0.0) * 1000, 3)


def _new_ocr_timing_metrics() -> dict[str, Any]:
    """创建 OCR 细粒度耗时指标的默认结构。"""
    metrics = {field: 0.0 for field in _OCR_TIMING_FLOAT_FIELDS}
    metrics["ocr_instance_reused"] = False
    return metrics


def _finalize_ocr_timing_metrics(metrics: dict[str, Any], request_started_at: float) -> dict[str, Any]:
    """补齐请求级总耗时并返回新的 OCR 指标。"""
    finalized = dict(metrics)
    finalized["ocr_total_ms"] = _elapsed_ms(request_started_at)
    return finalized


def _build_ocr_result(
    *,
    status: str,
    attempted: bool,
    text: str,
    error: str | None,
    engine: str | None,
    timing_metrics: dict[str, Any],
    failure_category: str | None = None,
    missing_dependency: str | None = None,
    dependency_status: str | None = None,
) -> dict[str, Any]:
    """构造统一的 OCR 结果结构，便于上层诊断。"""
    payload = {
        "status": status,
        "attempted": attempted,
        "text": text,
        "error": error,
        "engine": engine,
    }
    if missing_dependency:
        payload["missing_dependency"] = missing_dependency
        payload["failure_category"] = "dependency_missing"
        payload["dependency_status"] = "missing"
    else:
        if failure_category is not None:
            payload["failure_category"] = failure_category
        if dependency_status is not None:
            payload["dependency_status"] = dependency_status
    payload.update(timing_metrics)
    return payload



def _infer_missing_dependency(exc: Exception) -> str | None:
    """从 OCR 异常中推断缺失的依赖名。"""
    name = getattr(exc, "name", None)
    if isinstance(name, str) and name.strip():
        lowered = name.strip().lower()
    else:
        lowered = ""
    if lowered in {"paddleocr"}:
        return lowered

    message = str(exc or "")
    lowered_message = message.lower()
    if "paddleocr" in lowered_message:
        return "paddleocr"

    match = re.search(r'no module named [\'"]([^\'"]+)[\'"]', message, re.IGNORECASE)
    if match:
        dependency = match.group(1).strip().lower()
        if dependency == "paddleocr":
            return dependency
        return dependency
    return None



def get_ocr_warmup_status() -> dict[str, Any]:
    """返回 OCR 预热线程的当前状态快照。"""
    with _OCR_WARMUP_LOCK:
        status = dict(_OCR_WARMUP_STATUS)
    status["is_ready"] = _OCR_INSTANCE is not None
    return status


def _set_ocr_warmup_status(**kwargs: Any) -> None:
    """原子更新 OCR 预热状态字段。"""
    with _OCR_WARMUP_LOCK:
        _OCR_WARMUP_STATUS.update(kwargs)



def _run_ocr_dummy_inference() -> None:
    """执行一次轻量 OCR 预热推理，提前加载检测与识别模型。"""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    ocr = get_shared_ocr()
    canvas = Image.new("RGB", (1280, 720), color="white")
    draw = ImageDraw.Draw(canvas)
    font = None
    for candidate in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        try:
            if candidate.exists():
                font = ImageFont.truetype(str(candidate), size=36)
                break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    warmup_lines = [
        "ThinkRAG OCR warmup sample",
        "PDF fallback should hit detect and recognize",
        "Local knowledge base OCR warmup",
        "Shared OCR runtime for image and PDF",
    ]
    y = 72
    for line in warmup_lines:
        draw.text((72, y), line, fill="black", font=font)
        y += 140
    warmup_image = np.asarray(canvas, dtype="uint8")
    run_ocr_predict(ocr, warmup_image)


def _run_ocr_warmup() -> None:
    """执行后台 OCR 预热任务。"""
    global _OCR_WARMUP_THREAD
    started_at = time.perf_counter()
    try:
        _run_ocr_dummy_inference()
    except Exception as exc:
        _set_ocr_warmup_status(
            state="failed",
            last_error=str(exc),
            last_duration_ms=_elapsed_ms(started_at),
            finished_at=_utc_now_iso(),
        )
    else:
        _set_ocr_warmup_status(
            state="ready",
            last_error=None,
            last_duration_ms=_elapsed_ms(started_at),
            finished_at=_utc_now_iso(),
        )
    finally:
        with _OCR_WARMUP_LOCK:
            _OCR_WARMUP_THREAD = None


def start_ocr_warmup_in_background(force: bool = False) -> bool:
    """按需启动后台 OCR 预热线程。"""
    global _OCR_WARMUP_THREAD
    with _OCR_WARMUP_LOCK:
        if _OCR_INSTANCE is not None and not force:
            _OCR_WARMUP_STATUS.update(
                state="ready",
                last_error=None,
                last_duration_ms=0.0,
                started_at=_OCR_WARMUP_STATUS.get("started_at") or _utc_now_iso(),
                finished_at=_utc_now_iso(),
            )
            return False
        if _OCR_WARMUP_THREAD is not None and _OCR_WARMUP_THREAD.is_alive() and not force:
            return False
        _OCR_WARMUP_STATUS.update(
            state="warming",
            attempt_count=int(_OCR_WARMUP_STATUS.get("attempt_count") or 0) + 1,
            last_error=None,
            last_duration_ms=None,
            started_at=_utc_now_iso(),
            finished_at=None,
        )
        thread = threading.Thread(target=_run_ocr_warmup, name="thinkrag-ocr-warmup", daemon=True)
        _OCR_WARMUP_THREAD = thread
    thread.start()
    return True


def _reset_ocr_runtime_state_for_tests() -> None:
    """重置 OCR 运行时状态，便于测试隔离。"""
    global _OCR_INSTANCE, _OCR_WARMUP_THREAD
    with _OCR_LOCK:
        _OCR_INSTANCE = None
    with _OCR_WARMUP_LOCK:
        _OCR_WARMUP_THREAD = None
        _OCR_WARMUP_STATUS.clear()
        _OCR_WARMUP_STATUS.update(
            {
                "state": "idle",
                "attempt_count": 0,
                "last_error": None,
                "last_duration_ms": None,
                "started_at": None,
                "finished_at": None,
            }
        )


def _get_ocr(timing_metrics: dict[str, Any] | None = None):
    """获取或初始化 PaddleOCR 实例，并记录初始化耗时。"""
    global _OCR_INSTANCE
    with _OCR_LOCK:
        reused = _OCR_INSTANCE is not None
        if timing_metrics is not None:
            timing_metrics["ocr_instance_reused"] = reused
        if reused:
            return _OCR_INSTANCE

        init_started_at = time.perf_counter()
        try:
            from paddleocr import PaddleOCR

            _OCR_INSTANCE = PaddleOCR(**_OCR_RUNTIME_CONFIG)
            return _OCR_INSTANCE
        finally:
            if timing_metrics is not None:
                timing_metrics["ocr_init_ms"] += _elapsed_ms(init_started_at)



def get_shared_ocr(timing_metrics: dict[str, Any] | None = None):
    """获取共享 PaddleOCR 实例，供图片 OCR 与 PDF OCR 共同复用。"""
    return _get_ocr(timing_metrics)


def run_ocr_predict(ocr: Any, image: Any):
    """串行执行 OCR predict，避免共享运行时并发调用不稳定。"""
    with _OCR_PREDICT_LOCK:
        return ocr.predict(image)


def _normalize_ocr_text(text: str) -> str:
    """规范化 OCR 输出文本，清理多余空白与噪声。"""
    normalized_lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    normalized = "\n".join(normalized_lines).strip()
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized


def _has_meaningful_text(text: str) -> bool:
    """判断 OCR 文本是否包含可用于入库的有效内容。"""
    if not text:
        return False
    visible_chars = [char for char in text if not char.isspace()]
    if len(visible_chars) < 2:
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z0-9]", text))


def _collect_rec_texts(result: Any) -> list[str]:
    """从 PaddleOCR 返回结果中提取识别文本列表。"""
    texts: list[str] = []
    for ocr_item in result or []:
        payload = getattr(ocr_item, "json", None)
        if not isinstance(payload, dict):
            continue
        res_payload = payload.get("res") or {}
        if isinstance(res_payload, dict):
            rec_texts = res_payload.get("rec_texts") or []
        else:
            rec_texts = []
        for raw_text in rec_texts:
            value = str(raw_text or "").strip()
            if value:
                texts.append(value)
    return texts


def _has_supported_image_signature(path: Path) -> bool:
    """基于文件头识别当前 OCR 能处理的图片格式。"""
    try:
        with path.open("rb") as handle:
            sample = handle.read(32)
    except OSError:
        return False

    if sample.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if sample.startswith(b"\xff\xd8\xff"):
        return True
    if sample.startswith(b"BM"):
        return True
    if len(sample) >= 12 and sample[:4] == b"RIFF" and sample[8:12] == b"WEBP":
        return True
    return False


def _is_supported_image_input(path: Path, content_type: str) -> bool:
    """判断当前输入是否属于可进入 OCR 流程的图片。"""
    suffix = path.suffix.lower()
    mime_type = str(content_type or "").strip().lower()
    if suffix in _SUPPORTED_IMAGE_SUFFIXES or mime_type in _SUPPORTED_IMAGE_MIME_TYPES:
        return True
    if suffix:
        return False
    if mime_type not in _SIGNATURE_SNIFF_FALLBACK_IMAGE_MIME_TYPES:
        return False
    return _has_supported_image_signature(path)


def extract_image_ocr_result(file_path: str | Path, *, content_type: str = "") -> dict[str, Any]:
    """对图片执行 OCR，并返回稳定的诊断结果。"""
    request_started_at = time.perf_counter()
    timing_metrics = _new_ocr_timing_metrics()
    path = Path(file_path).resolve()
    if not _is_supported_image_input(path, content_type):
        return _build_ocr_result(
            status="skipped",
            attempted=False,
            text="",
            error=None,
            engine=None,
            timing_metrics=_finalize_ocr_timing_metrics(timing_metrics, request_started_at),
        )

    try:
        load_started_at = time.perf_counter()
        import numpy as np
        from PIL import Image

        with Image.open(path) as image:
            rgb_image = image.convert("RGB")
            img_array = np.asarray(rgb_image)
        timing_metrics["ocr_load_image_ms"] += _elapsed_ms(load_started_at)

        ocr = _get_ocr(timing_metrics)
        predict_started_at = time.perf_counter()
        result = run_ocr_predict(ocr, img_array)
        timing_metrics["ocr_predict_ms"] += _elapsed_ms(predict_started_at)
    except Exception as exc:
        missing_dependency = _infer_missing_dependency(exc)
        return _build_ocr_result(
            status="failed",
            attempted=True,
            text="",
            error=str(exc),
            engine="paddleocr",
            timing_metrics=_finalize_ocr_timing_metrics(timing_metrics, request_started_at),
            failure_category="ocr_runtime_error",
            missing_dependency=missing_dependency,
            dependency_status="missing" if missing_dependency else "unknown",
        )

    postprocess_started_at = time.perf_counter()
    normalized_text = _normalize_ocr_text("\n".join(_collect_rec_texts(result)))
    timing_metrics["ocr_postprocess_ms"] += _elapsed_ms(postprocess_started_at)
    finalized_metrics = _finalize_ocr_timing_metrics(timing_metrics, request_started_at)
    if not _has_meaningful_text(normalized_text):
        return _build_ocr_result(
            status="no_text",
            attempted=True,
            text="",
            error=None,
            engine="paddleocr",
            timing_metrics=finalized_metrics,
        )

    return _build_ocr_result(
        status="success",
        attempted=True,
        text=normalized_text,
        error=None,
        engine="paddleocr",
        timing_metrics=finalized_metrics,
    )
