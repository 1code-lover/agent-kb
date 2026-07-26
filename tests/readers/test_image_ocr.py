"""图片 OCR 读取器测试：验证细粒度诊断字段稳定输出。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image

from server.readers import image_ocr


_OCR_TIMING_FIELDS = (
    "ocr_init_ms",
    "ocr_load_image_ms",
    "ocr_predict_ms",
    "ocr_postprocess_ms",
    "ocr_total_ms",
)


def _create_png(path: Path) -> None:
    """创建最小 PNG 测试图片。"""
    image = Image.new("RGB", (2, 2), color=(255, 255, 255))
    image.save(path)



def _assert_runtime_metrics(payload: dict[str, Any], *, expected: dict[str, Any] | None = None) -> None:
    expected_values = dict(expected or {})
    for key in _OCR_TIMING_FIELDS:
        assert key in payload
        assert isinstance(payload[key], float)
        if key in expected_values:
            assert payload[key] == pytest.approx(float(expected_values[key]))
        else:
            assert payload[key] >= 0.0
    assert payload["ocr_instance_reused"] is bool(expected_values.get("ocr_instance_reused", payload["ocr_instance_reused"]))



def test_unsupported_image_type_returns_skipped_with_zero_runtime_metrics(tmp_path: Path) -> None:
    """不受支持的文件类型应直接 skipped，且返回稳定的 timing 字段。"""
    file_path = tmp_path / "note.txt"
    file_path.write_text("plain text", encoding="utf-8")

    result = image_ocr.extract_image_ocr_result(file_path, content_type="text/plain")

    assert result["status"] == "skipped"
    assert result["attempted"] is False
    assert result["text"] == ""
    assert result["error"] is None
    assert result["engine"] is None
    _assert_runtime_metrics(
        result,
        expected={
            "ocr_init_ms": 0.0,
            "ocr_load_image_ms": 0.0,
            "ocr_predict_ms": 0.0,
            "ocr_postprocess_ms": 0.0,
            "ocr_instance_reused": False,
        },
    )



def test_extract_image_ocr_result_returns_success_with_fine_grained_metrics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """OCR 成功时，应返回识别文本与可观察的细粒度 timing。"""
    image_path = tmp_path / "flow.png"
    _create_png(image_path)

    class FakeOCR:
        def predict(self, img_array):
            assert img_array.shape == (2, 2, 3)
            return [
                SimpleNamespace(json={"res": {"rec_texts": ["系统架构图", "订单服务"]}})
            ]

    def _fake_get_ocr(timing_metrics: dict[str, Any] | None = None):
        if timing_metrics is not None:
            timing_metrics["ocr_init_ms"] = 10.5
            timing_metrics["ocr_instance_reused"] = True
        return FakeOCR()

    monkeypatch.setattr(image_ocr, "_get_ocr", _fake_get_ocr)

    result = image_ocr.extract_image_ocr_result(image_path, content_type="image/png")

    assert result["status"] == "success"
    assert result["attempted"] is True
    assert result["error"] is None
    assert result["engine"] == "paddleocr"
    assert result["text"] == "\u7cfb\u7edf\u67b6\u6784\u56fe\n\u8ba2\u5355\u670d\u52a1"
    _assert_runtime_metrics(
        result,
        expected={
            "ocr_init_ms": 10.5,
            "ocr_instance_reused": True,
        },
    )



def test_extract_image_ocr_result_separates_init_and_predict_runtime_metrics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """OCR init timing should be separated from predict timing."""
    image_path = tmp_path / "timing.png"
    _create_png(image_path)

    class FakeOCR:
        def predict(self, img_array):
            assert img_array.shape == (2, 2, 3)
            return [SimpleNamespace(json={"res": {"rec_texts": ["system diagram"]}})]

    perf_values = iter([0.0, 1.0, 1.2, 2.0, 2.7, 3.0, 3.4, 4.0, 4.05, 5.0])

    def _fake_perf_counter() -> float:
        return next(perf_values)

    def _fake_get_ocr(timing_metrics: dict[str, Any] | None = None):
        init_started_at = image_ocr.time.perf_counter()
        init_finished_at = image_ocr.time.perf_counter()
        if timing_metrics is not None:
            timing_metrics["ocr_init_ms"] += round((init_finished_at - init_started_at) * 1000, 3)
            timing_metrics["ocr_instance_reused"] = False
        return FakeOCR()

    monkeypatch.setattr(image_ocr.time, "perf_counter", _fake_perf_counter)
    monkeypatch.setattr(image_ocr, "_get_ocr", _fake_get_ocr)

    result = image_ocr.extract_image_ocr_result(image_path, content_type="image/png")

    assert result["status"] == "success"
    assert result["ocr_load_image_ms"] == pytest.approx(200.0)
    assert result["ocr_init_ms"] == pytest.approx(700.0)
    assert result["ocr_predict_ms"] == pytest.approx(400.0)
    assert result["ocr_postprocess_ms"] == pytest.approx(50.0)
    assert result["ocr_total_ms"] == pytest.approx(5000.0)
    assert result["ocr_instance_reused"] is False


def test_extract_image_ocr_result_returns_failed_with_runtime_metrics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """OCR predict 异常时，也应返回稳定的诊断字段。"""
    image_path = tmp_path / "broken.png"
    _create_png(image_path)

    class FakeOCR:
        def predict(self, img_array):
            assert img_array.shape == (2, 2, 3)
            raise RuntimeError("mock predict failed")

    def _fake_get_ocr(timing_metrics: dict[str, Any] | None = None):
        if timing_metrics is not None:
            timing_metrics["ocr_init_ms"] = 7.0
            timing_metrics["ocr_instance_reused"] = False
        return FakeOCR()

    monkeypatch.setattr(image_ocr, "_get_ocr", _fake_get_ocr)

    result = image_ocr.extract_image_ocr_result(image_path, content_type="image/png")

    assert result["status"] == "failed"
    assert result["attempted"] is True
    assert result["text"] == ""
    assert result["error"] == "mock predict failed"
    assert result["engine"] == "paddleocr"
    _assert_runtime_metrics(
        result,
        expected={
            "ocr_init_ms": 7.0,
            "ocr_instance_reused": False,
        },
    )


class _ImmediateThread:
    """??????????? target????????????????"""

    def __init__(self, *, target, name: str | None = None, daemon: bool | None = None):
        self._target = target
        self.name = name
        self.daemon = daemon
        self._alive = False

    def start(self) -> None:
        self._alive = True
        try:
            self._target()
        finally:
            self._alive = False

    def is_alive(self) -> bool:
        return self._alive


def test_start_ocr_warmup_in_background_marks_runtime_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    """?????????? OCR ???????? ready?"""
    image_ocr._reset_ocr_runtime_state_for_tests()
    sentinel = object()

    def _fake_get_ocr(timing_metrics: dict[str, Any] | None = None):
        image_ocr._OCR_INSTANCE = sentinel
        return sentinel

    monkeypatch.setattr(image_ocr, '_get_ocr', _fake_get_ocr)
    monkeypatch.setattr(image_ocr.threading, 'Thread', _ImmediateThread)

    scheduled = image_ocr.start_ocr_warmup_in_background()

    assert scheduled is True
    status = image_ocr.get_ocr_warmup_status()
    assert status['state'] == 'ready'
    assert status['is_ready'] is True
    assert status['attempt_count'] == 1
    assert status['last_error'] is None
    assert isinstance(status['last_duration_ms'], float)
    assert status['last_duration_ms'] >= 0.0


def test_start_ocr_warmup_in_background_marks_runtime_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """??????????? failed ????????"""
    image_ocr._reset_ocr_runtime_state_for_tests()

    def _fake_get_ocr(timing_metrics: dict[str, Any] | None = None):
        raise RuntimeError('mock warmup failed')

    monkeypatch.setattr(image_ocr, '_get_ocr', _fake_get_ocr)
    monkeypatch.setattr(image_ocr.threading, 'Thread', _ImmediateThread)

    scheduled = image_ocr.start_ocr_warmup_in_background()

    assert scheduled is True
    status = image_ocr.get_ocr_warmup_status()
    assert status['state'] == 'failed'
    assert status['is_ready'] is False
    assert status['attempt_count'] == 1
    assert status['last_error'] == 'mock warmup failed'
    assert isinstance(status['last_duration_ms'], float)
    assert status['last_duration_ms'] >= 0.0
