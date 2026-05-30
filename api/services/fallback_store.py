"""Persistent fallback config store for lightweight runtime mode."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import config


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_STORE_FILE = _PROJECT_ROOT / config.STORAGE_DIR / config.CONFIG_STORE_FILE
def _ensure_parent_dir() -> None:
    _STORE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_from_disk() -> dict[str, Any]:
    _ensure_parent_dir()
    if not _STORE_FILE.exists():
      return {}

    try:
      return json.loads(_STORE_FILE.read_text(encoding="utf-8"))
    except Exception:
      return {}


def _save_to_disk(data: dict[str, Any]) -> None:
    _ensure_parent_dir()
    _STORE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class FallbackConfigStore:
    def get(self, key: str):
        return _load_from_disk().get(key)

    def put(self, key: str, value):
        store = _load_from_disk()
        store[key] = value
        _save_to_disk(store)


FALLBACK_CONFIG_STORE = FallbackConfigStore()
