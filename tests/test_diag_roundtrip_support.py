"""diag_roundtrip_support ?????????"""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.diag_roundtrip_support as support_module
from scripts.diag_roundtrip_support import (
    find_file_result,
    resolve_saved_file_path,
    summarize_runtime_readiness,
    wait_for_runtime_ready,
)


class _FakeResponse:
    """????????? json ? raise_for_status?"""

    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class _FakeSession:
    """???????????????? Session?"""

    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = list(payloads)
        self.calls = 0
        self.closed = False

    def get(self, url: str, timeout: float) -> _FakeResponse:
        assert url.endswith('/api/health')
        self.calls += 1
        index = min(self.calls - 1, len(self._payloads) - 1)
        return _FakeResponse(self._payloads[index])

    def close(self) -> None:
        self.closed = True


def test_find_file_result_prefers_matching_relative_path() -> None:
    """??? relative_path ?????????? file_result?"""
    import_resp = {
        "data": {
            "file_results": [
                {"relative_path": "docs/a.md", "path": "C:/tmp/docs/a.md"},
                {"relative_path": "pdf/report.pdf", "path": "C:/tmp/pdf/report.pdf"},
            ]
        }
    }

    result = find_file_result(import_resp, relative_path="pdf/report.pdf")

    assert result == {"relative_path": "pdf/report.pdf", "path": "C:/tmp/pdf/report.pdf"}


def test_resolve_saved_file_path_uses_existing_runtime_path(tmp_path: Path, monkeypatch) -> None:
    """? file_result.path ????????????????????"""
    saved_path = tmp_path / "existing" / "note.md"
    saved_path.parent.mkdir(parents=True)
    saved_path.write_text("alpha", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    import_resp = {
        "data": {
            "file_results": [
                {"relative_path": "docs/note.md", "path": str(saved_path)}
            ]
        }
    }

    resolved = resolve_saved_file_path(import_resp, kb_id="kb-a", relative_path="docs/note.md")

    assert resolved == saved_path.resolve()


def test_resolve_saved_file_path_falls_back_to_kb_relative_path(tmp_path: Path, monkeypatch) -> None:
    """????????????? data/{kb_id}/{relative_path} ???????"""
    saved_path = tmp_path / "data" / "kb-a" / "docs" / "note.md"
    saved_path.parent.mkdir(parents=True)
    saved_path.write_text("alpha", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    import_resp = {"data": {"file_results": [{"relative_path": "docs/note.md", "path": None}]}}

    resolved = resolve_saved_file_path(import_resp, kb_id="kb-a", relative_path="docs/note.md")

    assert resolved == saved_path.resolve()


def test_resolve_saved_file_path_returns_none_when_failed_file_was_cleaned(tmp_path: Path, monkeypatch) -> None:
    """????????????????? None ????????"""
    monkeypatch.chdir(tmp_path)
    import_resp = {
        "data": {
            "file_results": [
                {
                    "relative_path": "pdf/manual.pdf",
                    "path": None,
                    "status": "failed",
                    "diagnostics": {"file_retained_on_disk": False},
                }
            ]
        }
    }

    resolved = resolve_saved_file_path(import_resp, kb_id="kb-a", relative_path="pdf/manual.pdf")

    assert resolved is None


def test_summarize_runtime_readiness_reports_embedding_and_ocr_blockers() -> None:
    """? embedding/OCR ? ready ??????? blockers?"""
    health = {
        "data": {
            "embedding_warmup": {"is_ready": False},
            "ocr_warmup": {"is_ready": False},
            "import_capabilities": {
                "image_ocr": {"ready": True},
            },
        }
    }

    summary = summarize_runtime_readiness(health, require_ocr=True)

    assert summary["is_ready"] is False
    assert summary["blockers"] == ["embedding_warmup", "ocr_warmup"]
    assert summary["blocker_details"] == ["(embedding_warmup, ready=False)", "(ocr_warmup, ready=False)"]
    assert summary["embedding_ready"] is False
    assert summary["ocr_dependencies_ready"] is True


def test_summarize_runtime_readiness_includes_embedding_cache_diagnostics() -> None:
    """embedding 未就绪时，应保留本地缓存和远程下载诊断。"""

    health = {
        "data": {
            "embedding_warmup": {
                "state": "failed",
                "is_ready": False,
                "last_error": "Embedding model is unavailable.",
            },
            "embedding_diagnostics": {
                "local_path_exists": False,
                "allow_remote_download": False,
                "local_path": "./localmodels/BAAI/bge-small-zh-v1.5",
                "hf_endpoint": "https://hf-mirror.com",
            },
            "ocr_warmup": {"state": "ready", "is_ready": True},
            "import_capabilities": {
                "image_ocr": {"ready": True},
            },
        }
    }

    summary = summarize_runtime_readiness(health, require_ocr=True)

    assert summary["is_ready"] is False
    assert summary["blockers"] == ["embedding_warmup"]
    assert summary["embedding_diagnostics"]["allow_remote_download"] is False
    assert summary["blocker_details"] == [
        "("
        "embedding_warmup, state=failed, ready=False, error=Embedding model is unavailable., "
        "local_path_exists=False, allow_remote_download=False, "
        "local_path=./localmodels/BAAI/bge-small-zh-v1.5, hf_endpoint=https://hf-mirror.com"
        ")"
    ]




def test_summarize_runtime_readiness_requires_ready_state_when_present() -> None:
    """???????? warming ???????? is_ready ?????"""
    health = {
        "data": {
            "embedding_warmup": {"is_ready": True, "state": "warming"},
            "ocr_warmup": {"is_ready": True, "state": "ready"},
            "import_capabilities": {
                "image_ocr": {"ready": True},
            },
        }
    }

    summary = summarize_runtime_readiness(health, require_ocr=True)

    assert summary["is_ready"] is False
    assert summary["blockers"] == ["embedding_warmup"]
    assert summary["embedding_ready"] is False
    assert summary["ocr_ready"] is True

def test_wait_for_runtime_ready_retries_until_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    """?? helper ?????????????????????"""
    session = _FakeSession(
        [
            {
                "data": {
                    "embedding_warmup": {"is_ready": False},
                    "ocr_warmup": {"is_ready": False},
                    "import_capabilities": {"image_ocr": {"ready": True}},
                }
            },
            {
                "data": {
                    "embedding_warmup": {"is_ready": True},
                    "ocr_warmup": {"is_ready": True},
                    "import_capabilities": {"image_ocr": {"ready": True}},
                }
            },
        ]
    )
    perf_values = iter([0.0, 0.2, 0.4, 0.6])
    monkeypatch.setattr(support_module.time, "perf_counter", lambda: next(perf_values))
    monkeypatch.setattr(support_module.time, "sleep", lambda _: None)

    payload = wait_for_runtime_ready(
        "http://127.0.0.1:18080",
        timeout=5.0,
        poll_interval=0.1,
        require_ocr=True,
        session=session,
    )

    assert session.calls == 2
    assert payload["data"]["embedding_warmup"]["is_ready"] is True
    assert payload["data"]["ocr_warmup"]["is_ready"] is True
    assert session.closed is False




def test_wait_for_runtime_ready_retries_after_request_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """?????????????????????????"""

    class _FlakySession:
        def __init__(self) -> None:
            self.calls = 0

        def get(self, url: str, timeout: float):
            assert url.endswith('/api/health')
            self.calls += 1
            if self.calls == 1:
                raise support_module.requests.ReadTimeout('warmup still blocking')
            return _FakeResponse(
                {
                    "data": {
                        "embedding_warmup": {"is_ready": True},
                        "ocr_warmup": {"is_ready": True},
                        "import_capabilities": {"image_ocr": {"ready": True}},
                    }
                }
            )

        def close(self) -> None:
            return None

    session = _FlakySession()
    perf_values = iter([0.0, 0.1, 0.2, 0.3])
    monkeypatch.setattr(support_module.time, "perf_counter", lambda: next(perf_values))
    monkeypatch.setattr(support_module.time, "sleep", lambda _: None)

    payload = wait_for_runtime_ready(
        "http://127.0.0.1:18080",
        timeout=5.0,
        poll_interval=0.1,
        require_ocr=True,
        session=session,
    )

    assert session.calls == 2
    assert payload["data"]["embedding_warmup"]["is_ready"] is True

def test_wait_for_runtime_ready_raises_timeout_with_blockers(monkeypatch: pytest.MonkeyPatch) -> None:
    """??????? blockers ??? TimeoutError???????????"""
    session = _FakeSession(
        [
            {
                "data": {
                    "embedding_warmup": {"is_ready": False},
                    "ocr_warmup": {"is_ready": False},
                    "import_capabilities": {"image_ocr": {"ready": True}},
                }
            }
        ]
    )
    perf_values = iter([0.0, 0.1, 0.2, 1.2, 1.3])
    monkeypatch.setattr(support_module.time, "perf_counter", lambda: next(perf_values))
    monkeypatch.setattr(support_module.time, "sleep", lambda _: None)

    with pytest.raises(TimeoutError, match="embedding_warmup, ocr_warmup"):
        wait_for_runtime_ready(
            "http://127.0.0.1:18080",
            timeout=1.0,
            poll_interval=0.1,
            require_ocr=True,
            session=session,
        )


def test_wait_for_runtime_ready_timeout_reports_embedding_cache_details(monkeypatch: pytest.MonkeyPatch) -> None:
    """等待 runtime ready 超时时，应把 embedding 缓存缺失原因带进错误消息。"""

    session = _FakeSession(
        [
            {
                "data": {
                    "embedding_warmup": {
                        "state": "failed",
                        "is_ready": False,
                        "last_error": "Embedding model is unavailable.",
                    },
                    "embedding_diagnostics": {
                        "local_path_exists": False,
                        "allow_remote_download": False,
                        "local_path": "./localmodels/BAAI/bge-small-zh-v1.5",
                        "hf_endpoint": "https://hf-mirror.com",
                    },
                    "ocr_warmup": {"state": "ready", "is_ready": True},
                    "import_capabilities": {"image_ocr": {"ready": True}},
                }
            }
        ]
    )
    perf_values = iter([0.0, 0.1, 0.2, 1.2, 1.3])
    monkeypatch.setattr(support_module.time, "perf_counter", lambda: next(perf_values))
    monkeypatch.setattr(support_module.time, "sleep", lambda _: None)

    with pytest.raises(TimeoutError) as exc_info:
        wait_for_runtime_ready(
            "http://127.0.0.1:18080",
            timeout=1.0,
            poll_interval=0.1,
            require_ocr=True,
            session=session,
        )

    message = str(exc_info.value)
    assert "local_path_exists=False" in message
    assert "allow_remote_download=False" in message
    assert "./localmodels/BAAI/bge-small-zh-v1.5" in message
