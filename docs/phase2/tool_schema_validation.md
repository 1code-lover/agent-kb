# 工具Schema验证功能文档

## 1. 需求文档（PRD）

### 1.1 功能概述
为工具输入输出添加 Schema 验证，确保数据格式正确。

### 1.2 功能需求
- FR-01: 工具输入必须符合定义的 Schema
- FR-02: 工具输出必须符合定义的 Schema
- FR-03: 验证失败时返回清晰的错误信息

### 1.3 非功能需求
- NFR-01: 验证错误信息清晰可理解

### 1.4 验收标准
- 输入不符合 Schema 时返回 400 错误
- 输出不符合 Schema 时记录异常

## 2. 功能设计（FRD）

### 2.1 Schema 定义
```python
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

## 3. 实现文件
- `api/schemas/tool_schemas.py`
- `tests/api/test_tool_validation.py`

## 4. 测试用例
- test_kb_search_schema_rejects_empty_question
- test_run_cmd_schema_requires_command
