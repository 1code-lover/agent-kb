"""日志工具回归测试。"""

from __future__ import annotations

import shutil
from pathlib import Path

from utils import logging_utils


def test_append_json_log_writes_jsonl_and_releases_handle(tmp_path, monkeypatch) -> None:
    """写入日志后应立即释放句柄，便于清理临时目录。"""
    log_dir = tmp_path / "storage" / "logs"
    log_file = log_dir / "session.log"
    monkeypatch.setattr(logging_utils, "LOG_DIR", log_dir)

    logging_utils.append_json_log("session_logger", log_file, {"event": "hello", "count": 1})

    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert lines == ['{"event": "hello", "count": 1}']

    shutil.rmtree(tmp_path)
    assert not tmp_path.exists()
