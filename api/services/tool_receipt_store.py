"""Tool receipt persistence helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from api.services.session_store import append_receipt as persist_receipt
from api.services.session_store import list_receipts as load_receipts


def append_receipt(session_id: str, tool_name: str, input_data: Any, output_data: Any, status: str) -> dict[str, Any]:
    receipt = {
        "id": str(uuid4()),
        "session_id": session_id,
        "tool_name": tool_name,
        "input": input_data,
        "output": output_data,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    persist_receipt(session_id, receipt)
    return receipt


def list_receipts(session_id: str, limit: int = 50) -> list[dict[str, Any]]:
    return load_receipts(session_id, limit)

