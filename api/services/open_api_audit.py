"""只读开放 API 的最小化审计日志。"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.utils.file import get_storage_root


class OpenAPIAudit:
    """追加不含令牌明文和问题正文的 JSONL 审计。"""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or get_storage_root() / "logs" / "open-api-audit.jsonl").resolve()
        self._lock = threading.RLock()

    def append(self, **fields: Any) -> None:
        allowed = {"token_id", "route", "kb_id", "status_code", "duration_ms", "request_id"}
        payload = {key: fields.get(key) for key in allowed}
        payload["created_at"] = datetime.now(timezone.utc).isoformat()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())


open_api_audit = OpenAPIAudit()
