"""
文件功能：回执持久化存储测试
文件描述：验证 SQLite 回执存储的持久化能力和 tool_receipt_store 集成
核心逻辑：使用临时数据库文件测试跨实例持久化、会话查询等功能
"""

import tempfile


def test_sqlite_receipt_store_persists_between_instances():
    """验证 SQLite 存储跨实例持久化"""
    from api.services.storage.sqlite_receipt_storage import SQLiteReceiptStorage

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
        store_a = SQLiteReceiptStorage(handle.name)
        saved = store_a.save(
            {
                "session_id": "s1",
                "tool_name": "kb_search",
                "input": {"question": "hello"},
                "output": {"answer": "ok"},
                "status": "ok",
            }
        )

        store_b = SQLiteReceiptStorage(handle.name)
        loaded = store_b.find_by_id(saved["id"])

        assert loaded is not None
        assert loaded["tool_name"] == "kb_search"


def test_tool_receipt_store_lists_latest_records():
    """验证 tool_receipt_store 集成 SQLite 后能正常读写"""
    from api.services.tool_receipt_store import append_receipt, list_receipts

    append_receipt("sess-a", "run_cmd", {"command": "pwd"}, {"output": "x"}, "ok")
    receipts = list_receipts("sess-a", limit=10)
    assert receipts[-1]["tool_name"] == "run_cmd"


def test_find_by_session():
    """验证按会话 ID 查询回执列表"""
    from api.services.storage.sqlite_receipt_storage import SQLiteReceiptStorage

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
        store = SQLiteReceiptStorage(handle.name)
        store.save({"session_id": "s1", "tool_name": "t1", "input": {}, "output": {}, "status": "ok"})
        store.save({"session_id": "s1", "tool_name": "t2", "input": {}, "output": {}, "status": "ok"})
        store.save({"session_id": "s2", "tool_name": "t3", "input": {}, "output": {}, "status": "ok"})

        results = store.list_by_session("s1", limit=10)
        assert len(results) == 2
