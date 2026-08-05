"""图片 OCR 读取测试：覆盖成功、失败、无文本与预热边界场景。"""

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



def _create_extensionless_png(path: Path) -> None:
    """创建无扩展名的 PNG 测试图片。"""
    image = Image.new("RGB", (2, 2), color=(255, 255, 255))
    image.save(path, format="PNG")



def _assert_runtime_metrics(payload: dict[str, Any], *, expected: dict[str, Any] | None = None) -> None:
    """断言 OCR 运行时指标字段稳定存在。"""
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
    """不支持的文件类型应直接 skipped，且返回稳定 timing 字段。"""
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



def test_extract_image_ocr_result_supports_extensionless_png_without_content_type(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """无扩展名且无 MIME 的 PNG 也应基于文件头进入 OCR。"""
    image_path = tmp_path / "diagram"
    _create_extensionless_png(image_path)

    class FakeOCR:
        def predict(self, img_array):
            assert img_array.shape == (2, 2, 3)
            return [SimpleNamespace(json={"res": {"rec_texts": ["extensionless diagram"]}})]

    def _fake_get_ocr(timing_metrics: dict[str, Any] | None = None):
        if timing_metrics is not None:
            timing_metrics["ocr_init_ms"] = 3.5
            timing_metrics["ocr_instance_reused"] = False
        return FakeOCR()

    monkeypatch.setattr(image_ocr, "_get_ocr", _fake_get_ocr)

    result = image_ocr.extract_image_ocr_result(image_path, content_type="")

    assert result["status"] == "success"
    assert result["attempted"] is True
    assert result["error"] is None
    assert result["engine"] == "paddleocr"
    assert result["text"] == "extensionless diagram"
    _assert_runtime_metrics(
        result,
        expected={
            "ocr_init_ms": 3.5,
            "ocr_instance_reused": False,
        },
    )


def test_extract_image_ocr_result_supports_extensionless_png_with_octet_stream_content_type(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """无后缀 PNG 在 MIME 为 octet-stream 时也应进入 OCR。"""
    image_path = tmp_path / "diagram-octet"
    _create_extensionless_png(image_path)

    class FakeOCR:
        def predict(self, img_array):
            assert img_array.shape == (2, 2, 3)
            return [SimpleNamespace(json={"res": {"rec_texts": ["octet stream diagram"]}})]

    def _fake_get_ocr(timing_metrics: dict[str, Any] | None = None):
        if timing_metrics is not None:
            timing_metrics["ocr_init_ms"] = 2.0
            timing_metrics["ocr_instance_reused"] = False
        return FakeOCR()

    monkeypatch.setattr(image_ocr, "_get_ocr", _fake_get_ocr)

    result = image_ocr.extract_image_ocr_result(image_path, content_type="application/octet-stream")

    assert result["status"] == "success"
    assert result["attempted"] is True
    assert result["error"] is None
    assert result["engine"] == "paddleocr"
    assert result["text"] == "octet stream diagram"
    _assert_runtime_metrics(
        result,
        expected={
            "ocr_init_ms": 2.0,
            "ocr_instance_reused": False,
        },
    )


def test_extract_image_ocr_result_returns_success_with_fine_grained_metrics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """OCR 成功时，应返回识别文本与可观测的细粒度 timing。"""
    image_path = tmp_path / "flow.png"
    _create_png(image_path)

    class FakeOCR:
        def predict(self, img_array):
            assert img_array.shape == (2, 2, 3)
            return [SimpleNamespace(json={"res": {"rec_texts": ["system diagram", "order service"]}})]

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
    assert result["text"] == "system diagram\norder service"
    _assert_runtime_metrics(
        result,
        expected={
            "ocr_init_ms": 10.5,
            "ocr_instance_reused": True,
        },
    )



def test_extract_image_ocr_result_returns_no_text_with_runtime_metrics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """OCR 无可用文本时，应返回 no_text 而不是伪造正文。"""
    image_path = tmp_path / "no-text.png"
    _create_png(image_path)

    class FakeOCR:
        def predict(self, img_array):
            assert img_array.shape == (2, 2, 3)
            return [SimpleNamespace(json={"res": {"rec_texts": ["-", "  "]}})]

    def _fake_get_ocr(timing_metrics: dict[str, Any] | None = None):
        if timing_metrics is not None:
            timing_metrics["ocr_init_ms"] = 4.0
            timing_metrics["ocr_instance_reused"] = False
        return FakeOCR()

    monkeypatch.setattr(image_ocr, "_get_ocr", _fake_get_ocr)

    result = image_ocr.extract_image_ocr_result(image_path, content_type="image/png")

    assert result["status"] == "no_text"
    assert result["attempted"] is True
    assert result["text"] == ""
    assert result["error"] is None
    assert result["engine"] == "paddleocr"
    _assert_runtime_metrics(
        result,
        expected={
            "ocr_init_ms": 4.0,
            "ocr_instance_reused": False,
        },
    )



def test_extract_image_ocr_result_separates_init_and_predict_runtime_metrics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """OCR 初始化耗时应与预测耗时拆开统计。"""
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



def test_extract_image_ocr_result_marks_missing_dependency_when_paddleocr_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """缺少 PaddleOCR 依赖时，应返回稳定的依赖缺失诊断字段。"""
    image_path = tmp_path / "dependency.png"
    _create_png(image_path)

    def _fake_get_ocr(timing_metrics: dict[str, Any] | None = None):
        if timing_metrics is not None:
            timing_metrics["ocr_init_ms"] = 2.5
            timing_metrics["ocr_instance_reused"] = False
        raise ModuleNotFoundError("No module named 'paddleocr'")

    monkeypatch.setattr(image_ocr, "_get_ocr", _fake_get_ocr)

    result = image_ocr.extract_image_ocr_result(image_path, content_type="image/png")

    assert result["status"] == "failed"
    assert result["attempted"] is True
    assert result["text"] == ""
    assert result["engine"] == "paddleocr"
    assert result["missing_dependency"] == "paddleocr"
    assert result["failure_category"] == "dependency_missing"
    assert result["dependency_status"] == "missing"
    _assert_runtime_metrics(
        result,
        expected={
            "ocr_init_ms": 2.5,
            "ocr_instance_reused": False,
        },
    )



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
    """用同步线程替身运行 target，便于验证 warmup 状态。"""

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
    """后台预热成功后，OCR 运行时状态应变为 ready。"""
    image_ocr._reset_ocr_runtime_state_for_tests()
    sentinel = object()
    called = {"warmup": 0}

    def _fake_warmup() -> None:
        called["warmup"] += 1
        image_ocr._OCR_INSTANCE = sentinel

    monkeypatch.setattr(image_ocr, "_run_ocr_dummy_inference", _fake_warmup)
    monkeypatch.setattr(image_ocr.threading, "Thread", _ImmediateThread)

    scheduled = image_ocr.start_ocr_warmup_in_background()

    assert scheduled is True
    assert called["warmup"] == 1
    status = image_ocr.get_ocr_warmup_status()
    assert status["state"] == "ready"
    assert status["is_ready"] is True
    assert status["attempt_count"] == 1
    assert status["last_error"] is None
    assert isinstance(status["last_duration_ms"], float)
    assert status["last_duration_ms"] >= 0.0



def test_start_ocr_warmup_in_background_marks_runtime_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """后台预热抛异常时，运行时状态应标记为 failed。"""
    image_ocr._reset_ocr_runtime_state_for_tests()

    def _fake_warmup() -> None:
        raise RuntimeError("mock warmup failed")

    monkeypatch.setattr(image_ocr, "_run_ocr_dummy_inference", _fake_warmup)
    monkeypatch.setattr(image_ocr.threading, "Thread", _ImmediateThread)

    scheduled = image_ocr.start_ocr_warmup_in_background()

    assert scheduled is True
    status = image_ocr.get_ocr_warmup_status()
    assert status["state"] == "failed"
    assert status["is_ready"] is False
    assert status["attempt_count"] == 1
    assert status["last_error"] == "mock warmup failed"
    assert isinstance(status["last_duration_ms"], float)
    assert status["last_duration_ms"] >= 0.0





def test_run_ocr_dummy_inference_reuses_instance_and_runs_predict(monkeypatch: pytest.MonkeyPatch) -> None:
    """预热假推理应复用 OCR 实例，并真正执行一次 predict。"""
    image_ocr._reset_ocr_runtime_state_for_tests()
    captured: dict[str, Any] = {}

    class _FakeOCR:
        def predict(self, image):
            captured["shape"] = tuple(image.shape)
            captured["dtype"] = str(image.dtype)
            return []

    monkeypatch.setattr(image_ocr, "get_shared_ocr", lambda timing_metrics=None: _FakeOCR(), raising=False)

    image_ocr._run_ocr_dummy_inference()

    assert captured["shape"] == (720, 1280, 3)
    assert captured["dtype"] == "uint8"

def test_start_ocr_warmup_in_background_skips_when_runtime_is_ready() -> None:
    """运行时已就绪时，重复预热应直接跳过而不是重复调度。"""
    image_ocr._reset_ocr_runtime_state_for_tests()
    image_ocr._OCR_INSTANCE = object()

    scheduled = image_ocr.start_ocr_warmup_in_background()

    assert scheduled is False
    status = image_ocr.get_ocr_warmup_status()
    assert status["state"] == "ready"
    assert status["is_ready"] is True
    assert status["last_error"] is None
    assert status["last_duration_ms"] == 0.0



def test_infer_missing_dependency_accepts_exception_name_and_message() -> None:
    """依赖推断应同时支持异常 name 字段与错误消息匹配。"""

    class NamedImportError(ImportError):
        def __init__(self, message: str, *, name: str | None = None) -> None:
            super().__init__(message)
            self.name = name

    assert image_ocr._infer_missing_dependency(NamedImportError("boom", name="paddleocr")) == "paddleocr"
    assert image_ocr._infer_missing_dependency(ModuleNotFoundError("No module named 'cv2'")) == "cv2"
    assert image_ocr._infer_missing_dependency(RuntimeError("other failure")) is None



def test_normalize_collect_and_meaningful_text_filters_noise() -> None:
    """OCR 后处理应能过滤无效 payload，并识别真正可入库的文本。"""
    result = [
        SimpleNamespace(json={"res": {"rec_texts": ["  第一行  ", "", "第二行"]}}),
        SimpleNamespace(json={"res": {"rec_texts": [None, "  ", "A1"]}}),
        SimpleNamespace(json=None),
        SimpleNamespace(json={"res": []}),
    ]

    texts = image_ocr._collect_rec_texts(result)
    normalized = image_ocr._normalize_ocr_text("\n\n".join(texts) + "\n\n")

    assert texts == ["第一行", "第二行", "A1"]
    assert normalized == "\u7b2c\u4e00\u884c\n\u7b2c\u4e8c\u884c\nA1"
    assert image_ocr._has_meaningful_text(normalized) is True
    assert image_ocr._has_meaningful_text("-\n ") is False
    assert image_ocr._has_meaningful_text("A") is False

def test_get_ocr_returns_cached_instance_and_marks_reused() -> None:
    """已有 OCR 实例时，应直接复用而不是重复初始化。"""
    image_ocr._reset_ocr_runtime_state_for_tests()
    sentinel = object()
    image_ocr._OCR_INSTANCE = sentinel
    timing_metrics = image_ocr._new_ocr_timing_metrics()

    result = image_ocr._get_ocr(timing_metrics)

    assert result is sentinel
    assert timing_metrics["ocr_instance_reused"] is True
    assert timing_metrics["ocr_init_ms"] == 0.0


class _AliveThread:
    """模拟仍在运行中的后台线程。"""

    def is_alive(self) -> bool:
        return True



def test_start_ocr_warmup_in_background_skips_when_thread_is_running() -> None:
    """已有 warmup 线程存活时，不应重复调度。"""
    image_ocr._reset_ocr_runtime_state_for_tests()
    image_ocr._OCR_WARMUP_THREAD = _AliveThread()

    scheduled = image_ocr.start_ocr_warmup_in_background()

    assert scheduled is False
    status = image_ocr.get_ocr_warmup_status()
    assert status["state"] == "idle"
    assert status["attempt_count"] == 0



def test_start_ocr_warmup_in_background_force_restarts_even_when_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """force=True 时即使 OCR 已 ready，也应重新触发一次预热。"""
    image_ocr._reset_ocr_runtime_state_for_tests()
    sentinel = object()
    image_ocr._OCR_INSTANCE = sentinel
    called = {"warmup": 0}

    def _fake_warmup() -> None:
        called["warmup"] += 1
        image_ocr._OCR_INSTANCE = sentinel

    monkeypatch.setattr(image_ocr, "_run_ocr_dummy_inference", _fake_warmup)
    monkeypatch.setattr(image_ocr.threading, "Thread", _ImmediateThread)

    scheduled = image_ocr.start_ocr_warmup_in_background(force=True)

    assert scheduled is True
    assert called["warmup"] == 1
    status = image_ocr.get_ocr_warmup_status()
    assert status["state"] == "ready"
    assert status["is_ready"] is True
    assert status["attempt_count"] == 1
