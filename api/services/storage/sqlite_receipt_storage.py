"""
文件功能：SQLite 回执存储实现
文件描述：基于 SQLite 数据库的回执持久化存储，支持保存、按 ID 查询、按会话查询
核心逻辑：使用 sqlite3 模块操作本地数据库文件，将 input/output 字段序列化为 JSON 字符串存储
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from api.services.storage.receipt_storage import ReceiptStorage


class SQLiteReceiptStorage(ReceiptStorage):
    """SQLite 回执存储实现"""

    def __init__(self, db_path: str) -> None:
        """
        函数名：__init__
        入参：
            - db_path (str): SQLite 数据库文件路径
        功能：初始化存储实例，创建数据库目录和表结构
        运行逻辑：
            1. 保存数据库路径
            2. 确保父目录存在
            3. 调用 _init_db 创建表和索引
        出参：None
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """
        函数名：_connect
        入参：无
        功能：创建数据库连接
        运行逻辑：使用 self.db_path 创建 sqlite3 连接并返回
        出参：sqlite3.Connection - 数据库连接对象
        """
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        """
        函数名：_init_db
        入参：无
        功能：初始化数据库表结构
        运行逻辑：
            1. 创建 tool_receipts 表（如不存在）
            2. 在 session_id 字段上创建索引
            3. 提交事务
        出参：None
        """
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_receipts (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    output_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_receipts_session_id ON tool_receipts(session_id)")
            conn.commit()

    def save(self, receipt: dict[str, Any]) -> dict[str, Any]:
        """
        函数名：save
        入参：
            - receipt (dict[str, Any]): 回执数据字典
        功能：保存一条回执到数据库
        运行逻辑：
            1. 补全 id 和 created_at 字段（如未提供）
            2. 将 input/output 序列化为 JSON 字符串
            3. INSERT 到 tool_receipts 表
            4. 提交事务并返回完整回执
        出参：dict[str, Any] - 保存后的完整回执数据
        """
        payload = {
            "id": receipt.get("id") or str(uuid4()),
            "session_id": receipt["session_id"],
            "tool_name": receipt["tool_name"],
            "input": receipt.get("input", {}),
            "output": receipt.get("output", {}),
            "status": receipt["status"],
            "created_at": receipt.get("created_at") or datetime.now(timezone.utc).isoformat(),
        }
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO tool_receipts (id, session_id, tool_name, input_json, output_json, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    payload["id"],
                    payload["session_id"],
                    payload["tool_name"],
                    json.dumps(payload["input"], ensure_ascii=False),
                    json.dumps(payload["output"], ensure_ascii=False),
                    payload["status"],
                    payload["created_at"],
                ),
            )
            conn.commit()
        return payload

    def find_by_id(self, receipt_id: str) -> dict[str, Any] | None:
        """
        函数名：find_by_id
        入参：
            - receipt_id (str): 回执唯一标识
        功能：根据 ID 查询单条回执
        运行逻辑：
            1. 执行 SELECT 查询
            2. 将 input_json/output_json 反序列化为字典
            3. 返回回执字典或 None
        出参：dict[str, Any] | None - 查询结果
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, session_id, tool_name, input_json, output_json, status, created_at FROM tool_receipts WHERE id = ?",
                (receipt_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "session_id": row[1],
            "tool_name": row[2],
            "input": json.loads(row[3]),
            "output": json.loads(row[4]),
            "status": row[5],
            "created_at": row[6],
        }

    def list_by_session(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        函数名：list_by_session
        入参：
            - session_id (str): 会话 ID
            - limit (int): 返回记录数量上限
        功能：按会话 ID 查询回执列表，按创建时间倒序
        运行逻辑：
            1. 执行 SELECT 查询，按 created_at DESC 排序
            2. 将每行数据反序列化为字典
            3. 返回回执列表
        出参：list[dict[str, Any]] - 回执列表
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, session_id, tool_name, input_json, output_json, status, created_at FROM tool_receipts WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [
            {
                "id": row[0],
                "session_id": row[1],
                "tool_name": row[2],
                "input": json.loads(row[3]),
                "output": json.loads(row[4]),
                "status": row[5],
                "created_at": row[6],
            }
            for row in rows
        ]
