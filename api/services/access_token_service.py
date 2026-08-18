"""本地只读知识库授权令牌服务。"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.kb_registry import KBRegistry
from server.utils.file import get_storage_root, validate_kb_id


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: str | None) -> datetime | None:
    """解析 ISO 8601 时间，并将格式错误转换为稳定的输入异常。"""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid expires_at timestamp; use ISO 8601 format") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _chmod_private(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError:
        pass


class AccessTokenService:
    """创建、验证、列出和撤销只读令牌。"""

    def __init__(
        self,
        *,
        store_path: str | Path | None = None,
        pepper_path: str | Path | None = None,
        admin_key_path: str | Path | None = None,
        registry: Any | None = None,
    ) -> None:
        root = get_storage_root()
        self.store_path = Path(store_path or root / "access_tokens.json").resolve()
        self.pepper_path = Path(pepper_path or root / "token-pepper").resolve()
        self.admin_key_path = Path(admin_key_path or root / "access-admin-key").resolve()
        self.registry = registry or KBRegistry(root / "kb_registry.json")
        self._lock = threading.RLock()

    def _load_or_create_secret(self, path: Path, env_name: str) -> str:
        env_value = os.getenv(env_name, "").strip()
        if env_value:
            return env_value
        with self._lock:
            if path.exists():
                _chmod_private(path)
                return path.read_text(encoding="utf-8").strip()
            path.parent.mkdir(parents=True, exist_ok=True)
            value = secrets.token_urlsafe(48)
            tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}-{threading.get_ident()}")
            try:
                tmp.write_text(value, encoding="utf-8")
                _chmod_private(tmp)
                os.replace(tmp, path)
                _chmod_private(path)
            finally:
                tmp.unlink(missing_ok=True)
            return value

    def _pepper(self) -> bytes:
        return self._load_or_create_secret(self.pepper_path, "THINKRAG_TOKEN_PEPPER").encode("utf-8")

    def get_admin_key(self) -> str:
        """返回本机管理密钥；环境变量优先。"""
        return self._load_or_create_secret(self.admin_key_path, "THINKRAG_ADMIN_KEY")

    def _read_unlocked(self) -> list[dict[str, Any]]:
        if not self.store_path.exists():
            return []
        try:
            value = json.loads(self.store_path.read_text(encoding="utf-8") or "[]")
        except json.JSONDecodeError as exc:
            raise RuntimeError("Access token store is corrupted") from exc
        if not isinstance(value, list):
            raise RuntimeError("Access token store must contain a list")
        return value

    def _write_unlocked(self, records: list[dict[str, Any]]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.store_path.with_name(f"{self.store_path.name}.tmp-{os.getpid()}-{threading.get_ident()}")
        try:
            with tmp.open("w", encoding="utf-8") as handle:
                json.dump(records, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            _chmod_private(tmp)
            os.replace(tmp, self.store_path)
            _chmod_private(self.store_path)
        finally:
            tmp.unlink(missing_ok=True)

    def _hash_token(self, token: str) -> str:
        return hmac.new(self._pepper(), token.encode("utf-8"), hashlib.sha256).hexdigest()

    def _validate_kbs(self, kb_ids: list[str]) -> list[str]:
        if not kb_ids:
            raise ValueError("at least one knowledge base is required")
        result = []
        for raw in kb_ids:
            kb_id = validate_kb_id(raw)
            record = self.registry.get_kb(kb_id)
            if not record or record.get("status", "active") != "active":
                raise ValueError(f"Knowledge base is not active: {kb_id}")
            if kb_id not in result:
                result.append(kb_id)
        return sorted(result)

    def create_token(self, *, name: str, kb_ids: list[str], expires_at: str | None = None) -> dict[str, Any]:
        """创建令牌，明文只在本次返回。"""
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Token name is required")
        allowed_kbs = self._validate_kbs(kb_ids)
        expiry = _parse_time(expires_at)
        token_id = secrets.token_hex(8)
        token = f"nak_ro_{token_id}_{secrets.token_urlsafe(32)}"
        now = _utc_now()
        record = {
            "token_id": token_id,
            "name": normalized_name[:128],
            "secret_hash": self._hash_token(token),
            "prefix": token[:24],
            "kb_ids": allowed_kbs,
            "status": "active",
            "created_at": now,
            "expires_at": expiry.isoformat() if expiry else None,
            "revoked_at": None,
            "last_used_at": None,
        }
        with self._lock:
            records = self._read_unlocked()
            records.append(record)
            self._write_unlocked(records)
        return {**self._public_record(record), "token": token}

    @staticmethod
    def _public_record(record: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in record.items() if key != "secret_hash"}

    def list_tokens(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._public_record(item) for item in self._read_unlocked()]

    def verify_token(self, token: str) -> dict[str, Any]:
        """验证令牌并返回不含摘要的授权上下文。"""
        parts = token.split("_", 3)
        if len(parts) != 4 or parts[0:2] != ["nak", "ro"]:
            raise PermissionError("Invalid access token")
        token_id = parts[2]
        with self._lock:
            record = next((item for item in self._read_unlocked() if item.get("token_id") == token_id), None)
        if not record or not hmac.compare_digest(str(record.get("secret_hash", "")), self._hash_token(token)):
            raise PermissionError("Invalid access token")
        if record.get("status") == "revoked" or record.get("revoked_at"):
            raise PermissionError("Access token has been revoked")
        expiry = _parse_time(record.get("expires_at"))
        if expiry is not None and expiry <= datetime.now(timezone.utc):
            raise PermissionError("Access token has expired")
        return self._public_record(record)

    def authorize_kb(self, record: dict[str, Any], kb_id: str) -> dict[str, Any]:
        safe_kb_id = validate_kb_id(kb_id)
        if safe_kb_id not in set(record.get("kb_ids") or []):
            raise PermissionError("Knowledge base is not authorized for this token")
        kb = self.registry.get_kb(safe_kb_id)
        if not kb or kb.get("status", "active") != "active":
            raise PermissionError("Knowledge base is not active")
        return kb

    def touch_last_used(self, token_id: str) -> None:
        with self._lock:
            records = self._read_unlocked()
            for record in records:
                if record.get("token_id") == token_id:
                    record["last_used_at"] = _utc_now()
                    self._write_unlocked(records)
                    return

    def revoke_token(self, token_id: str) -> dict[str, Any]:
        with self._lock:
            records = self._read_unlocked()
            for record in records:
                if record.get("token_id") == token_id:
                    record["status"] = "revoked"
                    record["revoked_at"] = record.get("revoked_at") or _utc_now()
                    self._write_unlocked(records)
                    return self._public_record(record)
        raise ValueError(f"Access token not found: {token_id}")


access_token_service = AccessTokenService()

__all__ = ["AccessTokenService", "access_token_service"]
