"""Shared fallback config store for lightweight runtime mode."""

from __future__ import annotations

from typing import Any

_MEMORY_STORE: dict[str, Any] = {}


class FallbackConfigStore:
    def get(self, key: str):
        return _MEMORY_STORE.get(key)

    def put(self, key: str, value):
        _MEMORY_STORE[key] = value


FALLBACK_CONFIG_STORE = FallbackConfigStore()
