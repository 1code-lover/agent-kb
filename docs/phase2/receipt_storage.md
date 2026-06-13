# 回执持久化存储功能文档

## 1. 需求文档（PRD）

### 1.1 功能概述
将工具回执从内存存储升级为持久化存储，支持服务重启后数据恢复。

### 1.2 功能需求
- FR-01: 回执存储支持 SQLite 后端
- FR-02: 支持按会话查询回执
- FR-03: 支持按时间范围查询回执

### 1.3 非功能需求
- NFR-01: 回执数据在服务重启后可恢复
- NFR-02: 回执查询响应时间 < 100ms

### 1.4 验收标准
- 回执数据持久化存储
- 服务重启后数据可恢复
- 支持按会话查询
- 支持按时间范围查询

## 2. 功能设计（FRD）

### 2.1 存储接口
```python
class ReceiptStorage(ABC):
    def save(receipt: dict) -> dict
    def find_by_id(receipt_id: str) -> dict | None
    def list_by_session(session_id: str, limit: int) -> list[dict]
```

### 2.2 SQLite 表结构
```sql
CREATE TABLE tool_receipts (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    input_json TEXT NOT NULL,
    output_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
)
```

### 2.3 工厂模式
```python
def get_receipt_storage() -> ReceiptStorage:
    # 单例模式，返回 SQLiteReceiptStorage 实例
```

## 3. 实现文件
- `api/services/storage/receipt_storage.py` - 接口定义
- `api/services/storage/sqlite_receipt_storage.py` - SQLite 实现
- `api/services/storage/receipt_storage_factory.py` - 工厂
- `api/services/tool_receipt_store.py` - 对外接口
- `tests/api/test_receipt_persistence.py`

## 4. 测试用例
- test_sqlite_receipt_store_persists_between_instances
- test_tool_receipt_store_lists_latest_records
- test_find_by_session
