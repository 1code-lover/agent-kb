# 回执持久化存储详细设计文档

## 1. 概述

### 1.1 目标
将工具回执从内存存储升级为持久化存储，支持服务重启后数据恢复，提供高效的查询能力。

### 1.2 设计原则
- **数据持久化**：服务重启后数据不丢失
- **查询高效**：支持按会话、时间范围查询
- **向后兼容**：保持现有 API 接口不变

## 2. 架构设计

### 2.1 存储架构

```
┌─────────────────────────────────────────────────────────────┐
│                    ToolReceiptStore                          │
├─────────────────────────────────────────────────────────────┤
│  现有接口保持不变                                           │
│  + append_receipt()                                         │
│  + list_receipts()                                          │
│  + get_receipt()                                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ uses
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  ReceiptStorage (接口)                       │
├─────────────────────────────────────────────────────────────┤
│  + save(receipt: dict) -> dict                              │
│  + find_by_id(receipt_id: str) -> Optional[dict]            │
│  + find_by_session(session_id: str, limit: int) -> list     │
│  + find_by_time_range(start, end) -> list                   │
│  + delete(receipt_id: str) -> bool                          │
│  + count(session_id: str) -> int                            │
└─────────────────────────────────────────────────────────────┘
                              △
                              │ implements
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ MemoryStorage│  │ FileStorage  │  │SQLiteStorage │
│  (现有)      │  │   (新增)     │  │   (新增)     │
└──────────────┘  └──────────────┘  └──────────────┘
```

### 2.2 数据流

```
工具执行完成
    │
    ▼
┌─────────────────┐
│ append_receipt() │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ReceiptStorage  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  持久化存储     │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌────────┐
│ SQLite │ │  File  │
└────────┘ └────────┘
```

## 3. 详细设计

### 3.1 存储接口定义

```python
from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime


class ReceiptStorage(ABC):
    """回执存储接口"""
    
    @abstractmethod
    def save(self, receipt: dict) -> dict:
        """
        保存回执
        
        Args:
            receipt: 回执数据
            
        Returns:
            dict: 保存后的回执（包含生成的ID和时间戳）
        """
        ...
    
    @abstractmethod
    def find_by_id(self, receipt_id: str) -> Optional[dict]:
        """
        根据ID查找回执
        
        Args:
            receipt_id: 回执ID
            
        Returns:
            Optional[dict]: 回执数据，不存在返回 None
        """
        ...
    
    @abstractmethod
    def find_by_session(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> list[dict]:
        """
        根据会话ID查找回执
        
        Args:
            session_id: 会话ID
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            list[dict]: 回执列表
        """
        ...
    
    @abstractmethod
    def find_by_time_range(
        self,
        start: datetime,
        end: datetime,
        session_id: Optional[str] = None
    ) -> list[dict]:
        """
        根据时间范围查找回执
        
        Args:
            start: 开始时间
            end: 结束时间
            session_id: 可选的会话ID过滤
            
        Returns:
            list[dict]: 回执列表
        """
        ...
    
    @abstractmethod
    def delete(self, receipt_id: str) -> bool:
        """
        删除回执
        
        Args:
            receipt_id: 回执ID
            
        Returns:
            bool: 是否删除成功
        """
        ...
    
    @abstractmethod
    def count(self, session_id: Optional[str] = None) -> int:
        """
        统计回执数量
        
        Args:
            session_id: 可选的会话ID过滤
            
        Returns:
            int: 回执数量
        """
        ...
```

### 3.2 SQLite 存储实现

```python
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from utils.logger import logger


class SQLiteReceiptStorage:
    """SQLite 回执存储"""
    
    def __init__(self, db_path: str = "data/receipts.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tool_receipts (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    input_data TEXT,
                    output_data TEXT,
                    status TEXT NOT NULL,
                    risk_level TEXT,
                    action_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # 创建索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id 
                ON tool_receipts(session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON tool_receipts(created_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tool_name 
                ON tool_receipts(tool_name)
            """)
            
            conn.commit()
    
    def _row_to_dict(self, row: tuple) -> dict:
        """将数据库行转换为字典"""
        return {
            "id": row[0],
            "session_id": row[1],
            "tool_name": row[2],
            "input_data": json.loads(row[3]) if row[3] else {},
            "output_data": json.loads(row[4]) if row[4] else {},
            "status": row[5],
            "risk_level": row[6],
            "action_id": row[7],
            "created_at": row[8],
            "updated_at": row[9],
        }
    
    def save(self, receipt: dict) -> dict:
        """保存回执"""
        receipt_id = receipt.get("id") or str(uuid4())
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tool_receipts 
                (id, session_id, tool_name, input_data, output_data, 
                 status, risk_level, action_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt_id,
                    receipt.get("session_id", "default"),
                    receipt.get("tool_name", ""),
                    json.dumps(receipt.get("input_data", {})),
                    json.dumps(receipt.get("output_data", {})),
                    receipt.get("status", "ok"),
                    receipt.get("risk_level"),
                    receipt.get("action_id"),
                    receipt.get("created_at", now),
                    now,
                )
            )
            conn.commit()
        
        result = receipt.copy()
        result["id"] = receipt_id
        result["created_at"] = receipt.get("created_at", now)
        result["updated_at"] = now
        return result
    
    def find_by_id(self, receipt_id: str) -> Optional[dict]:
        """根据ID查找回执"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM tool_receipts WHERE id = ?",
                (receipt_id,)
            )
            row = cursor.fetchone()
            return self._row_to_dict(row) if row else None
    
    def find_by_session(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> list[dict]:
        """根据会话ID查找回执"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT * FROM tool_receipts 
                WHERE session_id = ? 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
                """,
                (session_id, limit, offset)
            )
            return [self._row_to_dict(row) for row in cursor.fetchall()]
    
    def find_by_time_range(
        self,
        start: datetime,
        end: datetime,
        session_id: Optional[str] = None
    ) -> list[dict]:
        """根据时间范围查找回执"""
        start_str = start.isoformat()
        end_str = end.isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            if session_id:
                cursor = conn.execute(
                    """
                    SELECT * FROM tool_receipts 
                    WHERE session_id = ? AND created_at BETWEEN ? AND ?
                    ORDER BY created_at DESC
                    """,
                    (session_id, start_str, end_str)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM tool_receipts 
                    WHERE created_at BETWEEN ? AND ?
                    ORDER BY created_at DESC
                    """,
                    (start_str, end_str)
                )
            return [self._row_to_dict(row) for row in cursor.fetchall()]
    
    def delete(self, receipt_id: str) -> bool:
        """删除回执"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM tool_receipts WHERE id = ?",
                (receipt_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def count(self, session_id: Optional[str] = None) -> int:
        """统计回执数量"""
        with sqlite3.connect(self.db_path) as conn:
            if session_id:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM tool_receipts WHERE session_id = ?",
                    (session_id,)
                )
            else:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM tool_receipts"
                )
            return cursor.fetchone()[0]
```

### 3.3 文件存储实现

```python
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from utils.logger import logger


class FileReceiptStorage:
    """文件回执存储"""
    
    def __init__(self, storage_dir: str = "data/receipts"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.storage_dir / "index.json"
        self._load_index()
    
    def _load_index(self):
        """加载索引"""
        if self.index_file.exists():
            with open(self.index_file, "r", encoding="utf-8") as f:
                self.index = json.load(f)
        else:
            self.index = {
                "by_id": {},
                "by_session": {},
            }
    
    def _save_index(self):
        """保存索引"""
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)
    
    def _get_receipt_path(self, receipt_id: str) -> Path:
        """获取回执文件路径"""
        return self.storage_dir / f"{receipt_id}.json"
    
    def save(self, receipt: dict) -> dict:
        """保存回执"""
        receipt_id = receipt.get("id") or str(uuid4())
        now = datetime.now().isoformat()
        
        result = receipt.copy()
        result["id"] = receipt_id
        result["created_at"] = receipt.get("created_at", now)
        result["updated_at"] = now
        
        # 保存回执文件
        receipt_path = self._get_receipt_path(receipt_id)
        with open(receipt_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        # 更新索引
        session_id = receipt.get("session_id", "default")
        self.index["by_id"][receipt_id] = {
            "session_id": session_id,
            "created_at": now,
        }
        if session_id not in self.index["by_session"]:
            self.index["by_session"][session_id] = []
        self.index["by_session"][session_id].append(receipt_id)
        self._save_index()
        
        return result
    
    def find_by_id(self, receipt_id: str) -> Optional[dict]:
        """根据ID查找回执"""
        receipt_path = self._get_receipt_path(receipt_id)
        if not receipt_path.exists():
            return None
        
        with open(receipt_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def find_by_session(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> list[dict]:
        """根据会话ID查找回执"""
        receipt_ids = self.index.get("by_session", {}).get(session_id, [])
        
        # 按时间倒序
        receipt_ids = receipt_ids[::-1]
        
        # 分页
        receipt_ids = receipt_ids[offset:offset + limit]
        
        # 加载回执
        receipts = []
        for receipt_id in receipt_ids:
            receipt = self.find_by_id(receipt_id)
            if receipt:
                receipts.append(receipt)
        
        return receipts
    
    def find_by_time_range(
        self,
        start: datetime,
        end: datetime,
        session_id: Optional[str] = None
    ) -> list[dict]:
        """根据时间范围查找回执"""
        start_str = start.isoformat()
        end_str = end.isoformat()
        
        receipts = []
        for receipt_id, info in self.index.get("by_id", {}).items():
            created_at = info.get("created_at", "")
            if start_str <= created_at <= end_str:
                if session_id is None or info.get("session_id") == session_id:
                    receipt = self.find_by_id(receipt_id)
                    if receipt:
                        receipts.append(receipt)
        
        # 按时间倒序
        receipts.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return receipts
    
    def delete(self, receipt_id: str) -> bool:
        """删除回执"""
        receipt_path = self._get_receipt_path(receipt_id)
        if not receipt_path.exists():
            return False
        
        # 删除文件
        receipt_path.unlink()
        
        # 更新索引
        info = self.index.get("by_id", {}).pop(receipt_id, None)
        if info:
            session_id = info.get("session_id")
            if session_id in self.index.get("by_session", {}):
                self.index["by_session"][session_id] = [
                    rid for rid in self.index["by_session"][session_id]
                    if rid != receipt_id
                ]
            self._save_index()
        
        return True
    
    def count(self, session_id: Optional[str] = None) -> int:
        """统计回执数量"""
        if session_id:
            return len(self.index.get("by_session", {}).get(session_id, []))
        return len(self.index.get("by_id", {}))
```

### 3.4 存储工厂

```python
from typing import Optional
from api.services.storage.receipt_storage import ReceiptStorage
from api.services.storage.sqlite_receipt_storage import SQLiteReceiptStorage
from api.services.storage.file_receipt_storage import FileReceiptStorage
from config import config
from utils.logger import logger


class ReceiptStorageFactory:
    """回执存储工厂"""
    
    _instance: Optional[ReceiptStorage] = None
    
    @classmethod
    def create(cls) -> ReceiptStorage:
        """创建存储实例"""
        if cls._instance is not None:
            return cls._instance
        
        storage_type = config.get("receipt_storage_type", "sqlite")
        
        if storage_type == "sqlite":
            db_path = config.get("receipt_sqlite_path", "data/receipts.db")
            cls._instance = SQLiteReceiptStorage(db_path)
            logger.info(f"使用 SQLite 回执存储: {db_path}")
        elif storage_type == "file":
            storage_dir = config.get("receipt_file_dir", "data/receipts")
            cls._instance = FileReceiptStorage(storage_dir)
            logger.info(f"使用文件回执存储: {storage_dir}")
        else:
            raise ValueError(f"不支持的存储类型: {storage_type}")
        
        return cls._instance
    
    @classmethod
    def reset(cls):
        """重置实例（用于测试）"""
        cls._instance = None
```

### 3.5 更新 ToolReceiptStore

```python
from api.services.storage.receipt_storage_factory import ReceiptStorageFactory
from utils.logger import logger


class ToolReceiptStore:
    """工具回执存储"""
    
    def __init__(self):
        self.storage = ReceiptStorageFactory.create()
    
    def append_receipt(
        self,
        session_id: str,
        tool_name: str,
        input_data: dict,
        output_data: dict,
        status: str = "ok",
        risk_level: str = None,
        action_id: str = None,
    ) -> dict:
        """添加回执"""
        receipt = {
            "session_id": session_id,
            "tool_name": tool_name,
            "input_data": input_data,
            "output_data": output_data,
            "status": status,
            "risk_level": risk_level,
            "action_id": action_id,
        }
        return self.storage.save(receipt)
    
    def list_receipts(
        self,
        session_id: str,
        limit: int = 50
    ) -> list[dict]:
        """列出回执"""
        return self.storage.find_by_session(session_id, limit)
    
    def get_receipt(self, receipt_id: str) -> dict:
        """获取回执"""
        return self.storage.find_by_id(receipt_id)
    
    def count(self, session_id: str = None) -> int:
        """统计回执数量"""
        return self.storage.count(session_id)
```

## 4. 配置设计

### 4.1 配置文件

```yaml
# config.yaml
receipt_storage:
  type: sqlite  # sqlite 或 file
  sqlite:
    path: data/receipts.db
  file:
    dir: data/receipts
```

### 4.2 环境变量

```bash
# 回执存储类型
RECEIPT_STORAGE_TYPE=sqlite

# SQLite 路径
RECEIPT_SQLITE_PATH=data/receipts.db

# 文件存储目录
RECEIPT_FILE_DIR=data/receipts
```

## 5. 测试设计

### 5.1 单元测试

```python
import pytest
import tempfile
from datetime import datetime, timedelta
from api.services.storage.sqlite_receipt_storage import SQLiteReceiptStorage


@pytest.fixture
def storage():
    """创建临时存储"""
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        yield SQLiteReceiptStorage(f.name)


def test_save_receipt(storage):
    """测试保存回执"""
    receipt = {
        "session_id": "test",
        "tool_name": "kb_search",
        "input_data": {"question": "test"},
        "output_data": {"answer": "ok"},
        "status": "ok",
    }
    result = storage.save(receipt)
    assert "id" in result
    assert result["session_id"] == "test"


def test_find_by_id(storage):
    """测试根据ID查找"""
    receipt = {
        "session_id": "test",
        "tool_name": "kb_search",
        "input_data": {"question": "test"},
        "output_data": {"answer": "ok"},
        "status": "ok",
    }
    saved = storage.save(receipt)
    found = storage.find_by_id(saved["id"])
    assert found is not None
    assert found["id"] == saved["id"]


def test_find_by_session(storage):
    """测试根据会话查找"""
    for i in range(5):
        storage.save({
            "session_id": "test",
            "tool_name": "kb_search",
            "input_data": {"question": f"test {i}"},
            "output_data": {"answer": "ok"},
            "status": "ok",
        })
    
    receipts = storage.find_by_session("test")
    assert len(receipts) == 5


def test_find_by_time_range(storage):
    """测试根据时间范围查找"""
    now = datetime.now()
    
    storage.save({
        "session_id": "test",
        "tool_name": "kb_search",
        "input_data": {"question": "test"},
        "output_data": {"answer": "ok"},
        "status": "ok",
        "created_at": (now - timedelta(hours=2)).isoformat(),
    })
    
    storage.save({
        "session_id": "test",
        "tool_name": "kb_search",
        "input_data": {"question": "test"},
        "output_data": {"answer": "ok"},
        "status": "ok",
        "created_at": now.isoformat(),
    })
    
    receipts = storage.find_by_time_range(
        now - timedelta(hours=1),
        now + timedelta(hours=1)
    )
    assert len(receipts) == 1


def test_delete_receipt(storage):
    """测试删除回执"""
    receipt = storage.save({
        "session_id": "test",
        "tool_name": "kb_search",
        "input_data": {"question": "test"},
        "output_data": {"answer": "ok"},
        "status": "ok",
    })
    
    assert storage.delete(receipt["id"]) is True
    assert storage.find_by_id(receipt["id"]) is None
```

### 5.2 集成测试

```python
import pytest
from api.services.tool_receipt_store import ToolReceiptStore


def test_tool_receipt_store():
    """测试工具回执存储集成"""
    store = ToolReceiptStore()
    
    # 保存回执
    receipt = store.append_receipt(
        session_id="test",
        tool_name="kb_search",
        input_data={"question": "test"},
        output_data={"answer": "ok"},
        status="ok",
    )
    assert "id" in receipt
    
    # 查询回执
    receipts = store.list_receipts("test")
    assert len(receipts) > 0
    
    # 获取单个回执
    found = store.get_receipt(receipt["id"])
    assert found is not None
```

## 6. 迁移计划

### 6.1 数据迁移

```python
def migrate_memory_to_persistent():
    """迁移内存数据到持久化存储"""
    from api.services.tool_receipt_store import _receipts, ToolReceiptStore
    
    store = ToolReceiptStore()
    
    for session_id, receipts in _receipts.items():
        for receipt in receipts:
            store.storage.save(receipt)
    
    logger.info(f"迁移完成: {sum(len(r) for r in _receipts.values())} 条回执")
```

### 6.2 迁移步骤

1. 实现新的存储后端
2. 添加数据迁移脚本
3. 更新配置文件
4. 运行测试验证
5. 切换到新存储
6. 清理旧代码
