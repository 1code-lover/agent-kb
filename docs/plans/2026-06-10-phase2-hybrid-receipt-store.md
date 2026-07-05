# Phase 2 Hybrid Receipt Store Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the agent runtime with a tool registry, tool-level schema validation, L0-L3 risk classification, hard-deny command checks, pipeline-aware command risk parsing, and a hybrid persistence model using session snapshots plus a SQLite receipt store.

**Architecture:** Keep `api/services/session_store.py` as the workspace-state snapshot source for `workspace`, `task_state`, `timeline`, `plan`, `evidence`, and `pending_actions`. Introduce a dedicated SQLite-backed receipt store for durable event records, and route all receipt writes through `api/services/tool_receipt_store.py` so runtime code remains storage-agnostic.

**Tech Stack:** Python, FastAPI, Pydantic, SQLite, pytest

---

## File Structure And Responsibilities

- `api/services/tool_registry.py`
  - Tool base class, tool registration, input/output validation, execution entrypoint.
- `api/schemas/tool_schemas.py`
  - Pydantic schemas for tool input/output contracts.
- `api/services/risk_assessor.py`
  - L0-L3 command risk mapping and pipeline risk aggregation.
- `api/services/command_filter.py`
  - Hard-deny command pattern matching and audit event capture.
- `api/services/command_parser.py`
  - Pipeline parsing for `|`, `&&`, `||`, `;` with quote-aware token splitting.
- `api/services/storage/receipt_storage.py`
  - Receipt storage interface.
- `api/services/storage/sqlite_receipt_storage.py`
  - SQLite receipt storage implementation.
- `api/services/storage/receipt_storage_factory.py`
  - Receipt store factory with singleton lifecycle.
- `api/services/tool_receipt_store.py`
  - Stable facade used by runtime and tools for receipt persistence and listing.
- `api/services/agent_tools.py`
  - Register built-in tools through registry-compatible classes or adapters.
- `api/services/approval_service.py`
  - Replace `low/medium/high` classification with L0-L3-aware behavior.
- `api/services/agent_runtime.py`
  - Consume new risk model and new receipt store without changing high-level run flow.
- `api/schemas.py`
  - Align `risk_level` fields and receipt/pending-action response contracts.
- `tests/api/test_tool_registry.py`
  - Registry tests.
- `tests/api/test_tool_validation.py`
  - Tool schema validation tests.
- `tests/api/test_risk_levels.py`
  - L0-L3 risk classification tests.
- `tests/api/test_command_filter.py`
  - Hard-deny pattern tests.
- `tests/api/test_command_parser.py`
  - Command pipeline parsing tests.
- `tests/api/test_receipt_persistence.py`
  - SQLite receipt store persistence tests.
- `tests/integration/test_phase2_integration.py`
  - End-to-end integration checks for runtime-level behavior.

---

### Task 1: Add Tool Registry Core

**Files:**
- Create: `api/services/tool_registry.py`
- Test: `tests/api/test_tool_registry.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from pydantic import BaseModel


class DummyInput(BaseModel):
    value: str


class DummyOutput(BaseModel):
    result: str


class DummyTool:
    name = "dummy"
    description = "dummy test tool"
    input_schema = DummyInput
    output_schema = DummyOutput
    risk_level = "L0"

    def validate_input(self, data: dict):
        return self.input_schema(**data)

    def validate_output(self, data: dict):
        return self.output_schema(**data)

    def execute(self, input_data: dict) -> dict:
        return {"result": input_data["value"]}

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "risk_level": self.risk_level,
        }


@pytest.fixture
def registry():
    from api.services.tool_registry import ToolRegistry
    reg = ToolRegistry()
    reg.clear()
    return reg


def test_tool_registration_and_listing(registry):
    registry.register(DummyTool())
    assert registry.list_tools() == [
        {"name": "dummy", "description": "dummy test tool", "risk_level": "L0"}
    ]


def test_tool_execution(registry):
    registry.register(DummyTool())
    result = registry.execute("dummy", {"value": "hello"})
    assert result == {"result": "hello"}


def test_missing_tool_raises_clear_error(registry):
    with pytest.raises(ValueError, match="Tool not found: missing"):
        registry.get("missing")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/api/test_tool_registry.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'api.services.tool_registry'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ValidationError


class ToolBase(ABC):
    name: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    risk_level: str = "L0"

    def validate_input(self, data: dict[str, Any]) -> BaseModel:
        try:
            return self.input_schema(**data)
        except ValidationError as exc:
            raise ValueError(f"Tool input validation failed: {exc}") from exc

    def validate_output(self, data: dict[str, Any]) -> BaseModel:
        try:
            return self.output_schema(**data)
        except ValidationError as exc:
            raise ValueError(f"Tool output validation failed: {exc}") from exc

    @abstractmethod
    def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "description": self.description,
            "risk_level": self.risk_level,
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolBase] = {}

    def clear(self) -> None:
        self._tools.clear()

    def register(self, tool: ToolBase) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolBase:
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"Tool not found: {name}")
        return tool

    def list_tools(self) -> list[dict[str, str]]:
        return [tool.to_dict() for tool in self._tools.values()]

    def execute(self, name: str, input_data: dict[str, Any]) -> dict[str, Any]:
        tool = self.get(name)
        validated_input = tool.validate_input(input_data)
        result = tool.execute(validated_input.model_dump())
        validated_output = tool.validate_output(result)
        return validated_output.model_dump()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/api/test_tool_registry.py -v`

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add api/services/tool_registry.py tests/api/test_tool_registry.py
git commit -m "feat: add tool registry core"
```

---

### Task 2: Add Tool Schemas And Register Built-In Tools

**Files:**
- Create: `api/schemas/tool_schemas.py`
- Modify: `api/services/agent_tools.py:1-203`
- Test: `tests/api/test_tool_validation.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest


def test_kb_search_schema_rejects_empty_question():
    from api.schemas.tool_schemas import KbSearchInput

    with pytest.raises(Exception):
        KbSearchInput(question="")


def test_run_cmd_schema_requires_command():
    from api.schemas.tool_schemas import RunCmdInput

    with pytest.raises(Exception):
        RunCmdInput(command="")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/api/test_tool_validation.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'api.schemas.tool_schemas'`

- [ ] **Step 3: Write minimal schema implementation**

```python
from pydantic import BaseModel, Field


class KbSearchInput(BaseModel):
    question: str = Field(..., min_length=1)
    session_id: str = Field(default="default")


class KbSearchOutput(BaseModel):
    answer: str = ""
    sources: list[dict] = Field(default_factory=list)
    evidence_count: int = 0


class ReadFileInput(BaseModel):
    path: str = Field(..., min_length=1)
    session_id: str = Field(default="default")


class ReadFileOutput(BaseModel):
    path: str
    excerpt: str


class RunCmdInput(BaseModel):
    command: str = Field(..., min_length=1)
    session_id: str = Field(default="default")


class RunCmdOutput(BaseModel):
    exit_code: int
    output: str
```

- [ ] **Step 4: Adapt built-in tools to registry-compatible classes**

```python
from api.schemas.tool_schemas import (
    KbSearchInput,
    KbSearchOutput,
    ReadFileInput,
    ReadFileOutput,
    RunCmdInput,
    RunCmdOutput,
)
from api.services.tool_registry import ToolBase


class KbSearchTool(ToolBase):
    name = "kb_search"
    description = "Search knowledge base"
    input_schema = KbSearchInput
    output_schema = KbSearchOutput
    risk_level = "L0"

    def execute(self, input_data: dict) -> dict:
        result = run_kb_search(input_data["session_id"], input_data["question"])
        return {
            "answer": result["result"].get("answer", ""),
            "sources": result["result"].get("sources", []),
            "evidence_count": len(result.get("evidence", [])),
        }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/api/test_tool_validation.py -v`

Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add api/schemas/tool_schemas.py api/services/agent_tools.py tests/api/test_tool_validation.py
git commit -m "feat: add tool schemas and built-in tool adapters"
```

---

### Task 3: Add L0-L3 Risk Model

**Files:**
- Create: `api/services/risk_assessor.py`
- Modify: `api/schemas.py:160-197`
- Modify: `api/services/approval_service.py:1-103`
- Test: `tests/api/test_risk_levels.py`

- [ ] **Step 1: Write the failing test**

```python
from api.services.risk_assessor import RiskAssessor, RiskLevel


def test_l0_readonly_commands():
    assert RiskAssessor.assess("pwd") == RiskLevel.L0
    assert RiskAssessor.assess("ls -la") == RiskLevel.L0


def test_l1_safe_local_commands():
    assert RiskAssessor.assess("python --version") == RiskLevel.L1


def test_l2_mutating_commands():
    assert RiskAssessor.assess("rm temp.txt") == RiskLevel.L2


def test_l3_system_commands():
    assert RiskAssessor.assess("shutdown /r /t 0") == RiskLevel.L3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/api/test_risk_levels.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'api.services.risk_assessor'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

import re
from enum import Enum


class RiskLevel(str, Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"

    @property
    def needs_approval(self) -> bool:
        return self in {RiskLevel.L2, RiskLevel.L3}


class RiskAssessor:
    @staticmethod
    def _assess_single(command: str) -> RiskLevel:
        normalized = (command or "").strip().lower()
        if re.match(r'\b(pwd|ls|dir|whoami|cat|type|echo|head|tail|grep|find|wc)\b', normalized):
            return RiskLevel.L0
        if re.match(r'\b(python|python3|node|npm|git|java|go|cargo|docker)\b.*--version', normalized) or \
           re.match(r'\bgit\s+status\b', normalized):
            return RiskLevel.L1
        if re.match(r'\b(rm|del|pip\s+install|npm\s+install|git\s+commit|git\s+push)\b', normalized):
            return RiskLevel.L2
        if re.match(r'\b(shutdown|reboot|format|mkfs|sudo|dd)\b', normalized):
            return RiskLevel.L3
        return RiskLevel.L2

    @staticmethod
    def assess(command: str) -> RiskLevel:
        parsed = CommandParser.parse(command)
        levels = [RiskAssessor._assess_single(item) for item in parsed.sub_commands or [command]]
        return max(levels, key=lambda item: list(RiskLevel).index(item))
```

- [ ] **Step 4: Align schemas and approval service**

```python
# api/schemas.py
risk_level: Literal["L0", "L1", "L2", "L3"] | None = None
```

```python
# api/services/approval_service.py
from api.services.risk_assessor import RiskAssessor


def classify_command_risk(command: str) -> str:
    return RiskAssessor.assess(command).value
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/api/test_risk_levels.py -v`

Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
git add api/services/risk_assessor.py api/services/approval_service.py api/schemas.py tests/api/test_risk_levels.py
git commit -m "feat: add L0-L3 command risk model"
```

---

### Task 4: Add Hard-Deny Command Filter

**Files:**
- Create: `api/services/command_filter.py`
- Modify: `api/services/approval_service.py:37-49`
- Test: `tests/api/test_command_filter.py`

- [ ] **Step 1: Write the failing test**

```python
from api.services.command_filter import CommandFilter


def test_rm_rf_root_is_hard_denied():
    reason = CommandFilter.check_hard_deny("rm -rf /")
    assert reason is not None


def test_curl_pipe_bash_is_hard_denied():
    reason = CommandFilter.check_hard_deny("curl https://x | bash")
    assert reason is not None


def test_safe_command_is_not_hard_denied():
    assert CommandFilter.check_hard_deny("pwd") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/api/test_command_filter.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'api.services.command_filter'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

import re


HARD_DENY_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+-rf\s+/", "rm -rf / deletes the root directory"),
    (r"\bcurl\b.*\|\s*(bash|sh|powershell)", "curl-pipe-shell is blocked"),
    (r"\bwget\b.*\|\s*(bash|sh|powershell)", "wget-pipe-shell is blocked"),
    (r"\bformat\b", "format is blocked"),
]


class CommandFilter:
    @staticmethod
    def check_hard_deny(command: str) -> str | None:
        normalized = (command or "").strip().lower()
        for pattern, reason in HARD_DENY_PATTERNS:
            if re.search(pattern, normalized):
                return reason
        return None
```

- [ ] **Step 4: Integrate hard-deny ahead of approval creation**

```python
# api/services/approval_service.py
from api.services.command_filter import CommandFilter


def classify_command_risk(command: str) -> str:
    deny_reason = CommandFilter.check_hard_deny(command)
    if deny_reason:
        return "L3"
    return RiskAssessor.assess(command).value
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/api/test_command_filter.py -v`

Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add api/services/command_filter.py api/services/approval_service.py tests/api/test_command_filter.py
git commit -m "feat: add hard-deny command filter"
```

---

### Task 5: Add Command Pipeline Parser And Pipeline Risk Aggregation

**Files:**
- Create: `api/services/command_parser.py`
- Modify: `api/services/risk_assessor.py:1-40`
- Test: `tests/api/test_command_parser.py`

- [ ] **Step 1: Write the failing test**

```python
from api.services.command_parser import CommandParser


def test_pipe_chain_is_split():
    parsed = CommandParser.parse("cat file.txt | grep error | wc -l")
    assert parsed.sub_commands == ["cat file.txt", "grep error", "wc -l"]
    assert parsed.operators == ["|", "|"]


def test_and_chain_is_split():
    parsed = CommandParser.parse("make && make install")
    assert parsed.sub_commands == ["make", "make install"]
    assert parsed.operators == ["&&"]


def test_escaped_quotes():
    parsed = CommandParser.parse('echo "hello \\"world\\"" | grep hello')
    assert len(parsed.sub_commands) == 2


def test_semicolon_chain():
    parsed = CommandParser.parse("echo hello; echo world")
    assert parsed.sub_commands == ["echo hello", "echo world"]
    assert parsed.operators == [";"]


def test_mixed_operators():
    parsed = CommandParser.parse("cat file.txt | grep error && echo done")
    assert len(parsed.sub_commands) == 3
    assert parsed.operators == ["|", "&&"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/api/test_command_parser.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'api.services.command_parser'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParsedCommand:
    original: str
    sub_commands: list[str]
    operators: list[str]


class CommandParser:
    OPERATORS = ("&&", "||", "|", ";")

    @staticmethod
    def parse(command: str) -> ParsedCommand:
        sub_commands: list[str] = []
        operators: list[str] = []
        current = []
        in_quote = False
        quote_char = ""
        i = 0

        while i < len(command):
            char = command[i]
            if char in {'\"', "'"}:
                if not in_quote:
                    in_quote = True
                    quote_char = char
                elif quote_char == char:
                    in_quote = False
                current.append(char)
                i += 1
                continue

            if not in_quote:
                matched = next((op for op in CommandParser.OPERATORS if command.startswith(op, i)), None)
                if matched:
                    sub_commands.append("".join(current).strip())
                    operators.append(matched)
                    current = []
                    i += len(matched)
                    continue

            current.append(char)
            i += 1

        tail = "".join(current).strip()
        if tail:
            sub_commands.append(tail)

        return ParsedCommand(original=command, sub_commands=sub_commands, operators=operators)
```

- [ ] **Step 4: Update risk assessor to use max risk across pipeline**

```python
from api.services.command_parser import CommandParser


class RiskAssessor:
    @staticmethod
    def assess(command: str) -> RiskLevel:
        parsed = CommandParser.parse(command)
        levels = [RiskAssessor._assess_single(item) for item in parsed.sub_commands or [command]]
        return max(levels, key=lambda item: list(RiskLevel).index(item))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/api/test_command_parser.py tests/api/test_risk_levels.py -v`

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add api/services/command_parser.py api/services/risk_assessor.py tests/api/test_command_parser.py tests/api/test_risk_levels.py
git commit -m "feat: add pipeline-aware command parsing"
```

---

### Task 6: Add SQLite Receipt Store And Hybrid Persistence

**Files:**
- Create: `api/services/storage/__init__.py`
- Create: `api/services/storage/receipt_storage.py`
- Create: `api/services/storage/sqlite_receipt_storage.py`
- Create: `api/services/storage/receipt_storage_factory.py`
- Modify: `api/services/tool_receipt_store.py:1-29`
- Test: `tests/api/test_receipt_persistence.py`

- [ ] **Step 1: Write the failing test**

```python
import tempfile


def test_sqlite_receipt_store_persists_between_instances():
    from api.services.storage.sqlite_receipt_storage import SQLiteReceiptStorage

    with tempfile.NamedTemporaryFile(suffix=".db") as handle:
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
    from api.services.tool_receipt_store import append_receipt, list_receipts

    append_receipt("sess-a", "run_cmd", {"command": "pwd"}, {"output": "x"}, "ok")
    receipts = list_receipts("sess-a", limit=10)
    assert receipts[-1]["tool_name"] == "run_cmd"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/api/test_receipt_persistence.py -v`

Expected: FAIL with missing storage modules

- [ ] **Step 3: Add receipt storage interface and SQLite implementation**

```python
# api/services/storage/receipt_storage.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ReceiptStorage(ABC):
    @abstractmethod
    def save(self, receipt: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def find_by_id(self, receipt_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def list_by_session(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        raise NotImplementedError
```

```python
# api/services/storage/sqlite_receipt_storage.py
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from api.services.storage.receipt_storage import ReceiptStorage


class SQLiteReceiptStorage(ReceiptStorage):
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
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
```

- [ ] **Step 4: Repoint `tool_receipt_store.py` to SQLite store and keep session snapshot only as workspace state**

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import config
from api.services.storage.receipt_storage_factory import get_receipt_storage


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
    return get_receipt_storage().save(receipt)


def list_receipts(session_id: str, limit: int = 50) -> list[dict[str, Any]]:
    return get_receipt_storage().list_by_session(session_id, limit)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/api/test_receipt_persistence.py -v`

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add api/services/storage api/services/tool_receipt_store.py tests/api/test_receipt_persistence.py
git commit -m "feat: add hybrid SQLite receipt persistence"
```

---

### Task 7: Integrate Runtime And Verify End-To-End Behavior

**Files:**
- Modify: `api/services/agent_runtime.py:1-388`
- Modify: `api/routers/agent.py:16-35`
- Test: `tests/integration/test_phase2_integration.py`
- Test: `tests/api/test_agent_runtime.py`

- [ ] **Step 1: Write the failing integration test**

```python
from types import SimpleNamespace


def test_run_cmd_high_risk_creates_pending_action_and_receipt(monkeypatch):
    from api.services.agent_runtime import run_agent

    monkeypatch.setattr("api.services.agent_runtime.validate_command_policy", lambda command: (True, ""))
    monkeypatch.setattr("api.services.agent_runtime.classify_command_risk", lambda command: "L2")
    monkeypatch.setattr("api.services.agent_runtime.get_pending_actions", lambda session_id: [
        {
            "action_id": "a1",
            "session_id": session_id,
            "command": "rm temp.txt",
            "risk_level": "L2",
            "status": "pending",
            "created_at": "2026-06-10T00:00:00Z",
            "review_reason": "",
            "reviewed_by": "",
        }
    ])

    request = SimpleNamespace(
        question="rm temp.txt",
        session_id="s1",
        mode="run_cmd",
        knowledge_scope=SimpleNamespace(model_dump=lambda: {"kb_id": "default", "kb_name": "Default"}),
    )

    result = run_agent(request)
    assert result["task_state"]["status"] == "waiting_approval"
    assert result["pending_actions"][0]["risk_level"] == "L2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_phase2_integration.py -v`

Expected: FAIL because runtime still uses `low/medium/high`

- [ ] **Step 3: Update runtime to use L0/L1 direct-execute and L2/L3 approval path**

```python
# api/services/agent_runtime.py
if risk_level in {"L0", "L1"}:
    output = run_cmd(session_id, command)
    ...
else:
    pending_action = create_pending_action(session_id, command, risk_level)
    ...
```

- [ ] **Step 4: Update runtime step metadata and API route responses**

```python
# api/services/agent_runtime.py
steps.append(
    {
        "step": "run_cmd",
        "title": "Run direct command",
        "status": "completed",
        "risk_level": risk_level,
        "receipt_id": output["receipt"]["id"],
        "summary": command,
    }
)
```

- [ ] **Step 5: Run targeted tests**

Run: `pytest tests/api/test_agent_runtime.py tests/integration/test_phase2_integration.py -v`

Expected: all tests PASS

- [ ] **Step 6: Run full Phase 2 test suite**

Run: `pytest tests/api/test_tool_registry.py tests/api/test_tool_validation.py tests/api/test_risk_levels.py tests/api/test_command_filter.py tests/api/test_command_parser.py tests/api/test_receipt_persistence.py tests/api/test_agent_runtime.py tests/integration/test_phase2_integration.py -v`

Expected: all tests PASS

- [ ] **Step 7: Run coverage check**

Run: `pytest --cov=api.services --cov-report=term-missing tests/api tests/integration`

Expected: total coverage `>= 80%`

- [ ] **Step 8: Commit**

```bash
git add api/services/agent_runtime.py api/routers/agent.py tests/integration/test_phase2_integration.py tests/api/test_agent_runtime.py
git commit -m "feat: integrate hybrid receipt store and risk model into runtime"
```

---

## Spec Coverage Self-Review

- P2-FR-01 Tool registry: covered by Task 1 and Task 2.
- P2-FR-02 Tool schema validation: covered by Task 2.
- P2-FR-03 L0-L3 risk classification: covered by Task 3.
- P2-FR-04 Hard-deny command patterns: covered by Task 4.
- P2-FR-05 Pipeline parsing and aggregated risk: covered by Task 5.
- P2-FR-06 Receipt persistence with session-based workspace state retained: covered by Task 6 and Task 7.
- P2-NFR-01 Extendability: addressed by registry-based tool structure in Task 1 and Task 2.
- P2-NFR-02 Security coverage: addressed by Task 3, Task 4, Task 5, and integration assertions in Task 7.
- P2-NFR-03 Performance: verified by acceptance checklist (1000 receipts < 100ms, tool call < 10ms, risk assess < 5ms). Use `pytest --durations=10` to detect regressions.
- P2-NFR-04 Maintainability and test coverage: addressed by focused modules and Task 7 coverage gate.

## 时间估算

| 任务 | 估算时间 | 依赖 |
|------|----------|------|
| Task 1 | 2小时 | 无 |
| Task 2 | 3小时 | Task 1 |
| Task 3 | 2小时 | Task 2 |
| Task 4 | 1小时 | Task 3 |
| Task 5 | 2小时 | Task 3 |
| Task 6 | 3小时 | Task 1 |
| Task 7 | 2小时 | 全部 |
| **总计** | **15小时** | |

## 风险和缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 现有工具迁移破坏兼容性 | 高 | 保持向后兼容，充分测试 |
| 命令解析遗漏边界情况 | 中 | 丰富的测试用例，参考现有实现 |
| SQLite 并发写入性能 | 低 | 使用连接池，批量写入 |
| 测试间状态污染 | 中 | 使用 fixture 隔离实例 |

## 验收清单

### 功能验收
- [ ] 工具注册表可正常注册和调用工具
- [ ] 工具 Schema 验证正确
- [ ] L0-L3 风险分级映射正确
- [ ] 硬拒绝命令不可执行
- [ ] 管道命令正确解析和评估
- [ ] 回执数据持久化存储可用

### 测试验收
- [ ] 所有单元测试通过
- [ ] 集成测试通过
- [ ] 测试覆盖率 >= 80%

### 性能验收
- [ ] 1000 条回执查询时间 < 100ms
- [ ] 工具调用延迟增加 < 10ms
- [ ] 命令风险评估延迟 < 5ms

## Notes

- Do not move `pending_actions` out of `session_store` in Phase 2.
- Do not add UI pages for tool management or risk rule editing in Phase 2.
- Do not replace `session_store` as the workspace snapshot mechanism.
- Keep existing route shapes stable where possible so the frontend does not require broad changes.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-10-phase2-hybrid-receipt-store.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
