"""?? OCR ??????????????????????"""

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
_OCR_TIMING_FLOAT_FIELDS = (
    "ocr_init_ms",
    "ocr_load_image_ms",
    "ocr_predict_ms",
    "ocr_postprocess_ms",
    "ocr_total_ms",
)
_OCR_INSTANCE = None
_OCR_LOCK = threading.RLock()
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
    """?? UTC ISO ????????????????"""
    return datetime.now(timezone.utc).isoformat()


def _elapsed_ms(started_at: float) -> float:
    """?? monotonic ???????????????"""
    return round(max(time.perf_counter() - started_at, 0.0) * 1000, 3)


def _new_ocr_timing_metrics() -> dict[str, Any]:
    """?? OCR ??????????????????????"""
    metrics = {field: 0.0 for field in _OCR_TIMING_FLOAT_FIELDS}
    metrics["ocr_instance_reused"] = False
    return metrics


def _finalize_ocr_timing_metrics(metrics: dict[str, Any], request_started_at: float) -> dict[str, Any]:
    """?????????????????? OCR ?????"""
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
) -> dict[str, Any]:
    """???? OCR ????????????????????"""
    payload = {
        "status": status,
        "attempted": attempted,
        "text": text,
        "error": error,
        "engine": engine,
    }
    payload.update(timing_metrics)
    return payload


def get_ocr_warmup_status() -> dict[str, Any]:
    """?? OCR ??????????????????"""
    with _OCR_WARMUP_LOCK:
        status = dict(_OCR_WARMUP_STATUS)
    status["is_ready"] = _OCR_INSTANCE is not None
    return status


def _set_ocr_warmup_status(**kwargs: Any) -> None:
    """???? OCR ?????????????????"""
    with _OCR_WARMUP_LOCK:
        _OCR_WARMUP_STATUS.update(kwargs)


def _run_ocr_warmup() -> None:
    """?????? OCR ?????????????"""
    global _OCR_WARMUP_THREAD
    started_at = time.perf_counter()
    try:
        _get_ocr()
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
    """??????? OCR ?????????????????"""
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
    """?? OCR ?????????????????"""
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
    """??? PaddleOCR ??????????????????"""
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

            _OCR_INSTANCE = PaddleOCR(lang="ch", use_textline_orientation=True)
            return _OCR_INSTANCE
        finally:
            if timing_metrics is not None:
                timing_metrics["ocr_init_ms"] += _elapsed_ms(init_started_at)


def _normalize_ocr_text(text: str) -> str:
    """? OCR ?????????????????"""
    normalized_lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    normalized = "\n".join(normalized_lines).strip()
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized


def _has_meaningful_text(text: str) -> bool:
    """?????????????????????????"""
    if not text:
        return False
    visible_chars = [char for char in text if not char.isspace()]
    if len(visible_chars) < 2:
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z0-9]", text))


def _collect_rec_texts(result: Any) -> list[str]:
    """?? PaddleOCR ?????? result ??????????"""
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


def extract_image_ocr_result(file_path: str | Path, *, content_type: str = "") -> dict[str, Any]:
    """????????? OCR???????????"""
    request_started_at = time.perf_counter()
    timing_metrics = _new_ocr_timing_metrics()
    path = Path(file_path).resolve()
    suffix = path.suffix.lower()
    mime_type = str(content_type or "").lower()
    if suffix not in _SUPPORTED_IMAGE_SUFFIXES and mime_type not in _SUPPORTED_IMAGE_MIME_TYPES:
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
        result = ocr.predict(img_array)
        timing_metrics["ocr_predict_ms"] += _elapsed_ms(predict_started_at)
    except Exception as exc:
        return _build_ocr_result(
            status="failed",
            attempted=True,
            text="",
            error=str(exc),
            engine="paddleocr",
            timing_metrics=_finalize_ocr_timing_metrics(timing_metrics, request_started_at),
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
