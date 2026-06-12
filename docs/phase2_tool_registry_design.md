# 工具注册表详细设计文档

## 1. 概述

### 1.1 目标
建立可扩展的工具注册和调用机制，使新工具可通过注册表快速接入，无需修改核心运行时代码。

### 1.2 设计原则
- **开闭原则**：对扩展开放，对修改关闭
- **单一职责**：每个工具只负责一个功能
- **依赖倒置**：运行时依赖抽象接口，不依赖具体工具

## 2. 架构设计

### 2.1 类图

```
┌─────────────────────────────────────────────────────────────┐
│                      ToolRegistry                           │
├─────────────────────────────────────────────────────────────┤
│ - _tools: dict[str, ToolBase]                               │
│ - _initialized: bool                                        │
├─────────────────────────────────────────────────────────────┤
│ + register(tool: ToolBase) -> None                          │
│ + unregister(name: str) -> None                             │
│ + get(name: str) -> ToolBase                                │
│ + list_tools() -> list[dict]                                │
│ + execute(name: str, input_data: dict) -> dict              │
│ + initialize() -> None                                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ uses
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       ToolBase (ABC)                         │
├─────────────────────────────────────────────────────────────┤
│ + name: str                                                 │
│ + description: str                                          │
│ + input_schema: type[BaseModel]                             │
│ + output_schema: type[BaseModel]                            │
│ + risk_level: str                                           │
├─────────────────────────────────────────────────────────────┤
│ + validate_input(data: dict) -> BaseModel                   │
│ + validate_output(data: dict) -> BaseModel                  │
│ + execute(input_data: dict) -> dict (abstract)              │
└─────────────────────────────────────────────────────────────┘
                              △
                              │ implements
                              │
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  KbSearchTool │  │ ReadFileTool │  │   RunCmdTool │
└──────────────┘  └──────────────┘  └──────────────┘
```

### 2.2 流程图

```
用户请求
    │
    ▼
┌─────────────────┐
│  Agent Runtime  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Agent Router   │
└────────┬────────┘
         │ tool_name
         ▼
┌─────────────────┐
│  Tool Registry  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Tool.execute() │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Schema 验证   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   实际执行      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   返回结果      │
└─────────────────┘
```

## 3. 详细设计

### 3.1 ToolBase 基类

```python
from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel, ValidationError


class ToolBase(ABC):
    """工具基类"""
    
    name: str  # 工具名称
    description: str  # 工具描述
    input_schema: type[BaseModel]  # 输入 Schema
    output_schema: type[BaseModel]  # 输出 Schema
    risk_level: str = "L0"  # 风险等级
    
    def validate_input(self, data: dict) -> BaseModel:
        """验证输入数据"""
        try:
            return self.input_schema(**data)
        except ValidationError as e:
            raise ValueError(f"输入验证失败: {e}")
    
    def validate_output(self, data: dict) -> BaseModel:
        """验证输出数据"""
        try:
            return self.output_schema(**data)
        except ValidationError as e:
            raise ValueError(f"输出验证失败: {e}")
    
    @abstractmethod
    def execute(self, input_data: dict) -> dict:
        """执行工具逻辑"""
        ...
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "risk_level": self.risk_level,
            "input_schema": self.input_schema.model_json_schema(),
            "output_schema": self.output_schema.model_json_schema(),
        }
```

### 3.2 ToolRegistry 注册表

```python
from typing import Any
from utils.logger import logger


class ToolRegistry:
    """工具注册表"""
    
    _instance = None
    _tools: dict[str, ToolBase] = {}
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register(self, tool: ToolBase) -> None:
        """注册工具"""
        if tool.name in self._tools:
            logger.warning(f"工具 {tool.name} 已存在，将被覆盖")
        self._tools[tool.name] = tool
        logger.info(f"工具 {tool.name} 注册成功")
    
    def unregister(self, name: str) -> None:
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
            logger.info(f"工具 {name} 注销成功")
        else:
            logger.warning(f"工具 {name} 不存在")
    
    def get(self, name: str) -> ToolBase:
        """获取工具"""
        if name not in self._tools:
            raise ValueError(f"工具 {name} 不存在")
        return self._tools[name]
    
    def list_tools(self) -> list[dict]:
        """列出所有工具"""
        return [tool.to_dict() for tool in self._tools.values()]
    
    def execute(self, name: str, input_data: dict) -> dict:
        """执行工具"""
        tool = self.get(name)
        
        # 验证输入
        validated_input = tool.validate_input(input_data)
        
        # 执行工具
        result = tool.execute(validated_input.model_dump())
        
        # 验证输出
        validated_output = tool.validate_output(result)
        
        return validated_output.model_dump()
    
    def initialize(self) -> None:
        """初始化注册表，注册内置工具"""
        if self._initialized:
            return
        
        from api.services.agent_tools import KbSearchTool, ReadFileTool, RunCmdTool
        
        self.register(KbSearchTool())
        self.register(ReadFileTool())
        self.register(RunCmdTool())
        
        self._initialized = True
        logger.info("工具注册表初始化完成")
```

### 3.3 内置工具实现示例

```python
from pydantic import BaseModel, Field
from api.services.tool_registry import ToolBase


class KbSearchInput(BaseModel):
    """知识库搜索输入"""
    question: str = Field(..., min_length=1, description="搜索问题")
    session_id: str = Field(default="default", description="会话ID")
    top_k: int = Field(default=5, ge=1, le=20, description="返回数量")


class KbSearchOutput(BaseModel):
    """知识库搜索输出"""
    answer: str = Field(..., description="回答")
    sources: list[dict] = Field(default_factory=list, description="来源")
    evidence_count: int = Field(..., description="证据数量")


class KbSearchTool(ToolBase):
    """知识库搜索工具"""
    
    name = "kb_search"
    description = "从知识库中搜索相关信息"
    input_schema = KbSearchInput
    output_schema = KbSearchOutput
    risk_level = "L0"
    
    def execute(self, input_data: dict) -> dict:
        from api.services import chat_service
        from api.schemas import QueryRequest
        
        result = chat_service.query(
            QueryRequest(
                question=input_data["question"],
                session_id=input_data["session_id"]
            )
        )
        
        sources = result.get("sources", [])
        return {
            "answer": result.get("answer", ""),
            "sources": sources,
            "evidence_count": len(sources),
        }
```

## 4. 接口设计

### 4.1 工具列表接口

```
GET /api/agent/tools
```

**响应**：
```json
{
    "code": 0,
    "data": {
        "tools": [
            {
                "name": "kb_search",
                "description": "从知识库中搜索相关信息",
                "risk_level": "L0"
            },
            {
                "name": "read_file",
                "description": "读取本地文件",
                "risk_level": "L1"
            },
            {
                "name": "run_cmd",
                "description": "执行命令",
                "risk_level": "L2"
            }
        ]
    }
}
```

### 4.2 工具 Schema 接口

```
GET /api/agent/tools/{tool_name}/schema
```

**响应**：
```json
{
    "code": 0,
    "data": {
        "name": "kb_search",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "minLength": 1},
                "session_id": {"type": "string", "default": "default"},
                "top_k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20}
            },
            "required": ["question"]
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "sources": {"type": "array"},
                "evidence_count": {"type": "integer"}
            }
        }
    }
}
```

## 5. 测试设计

### 5.1 单元测试

```python
import pytest
from api.services.tool_registry import ToolRegistry, ToolBase
from pydantic import BaseModel


class TestInput(BaseModel):
    value: str


class TestOutput(BaseModel):
    result: str


class TestTool(ToolBase):
    name = "test_tool"
    description = "测试工具"
    input_schema = TestInput
    output_schema = TestOutput
    risk_level = "L0"
    
    def execute(self, input_data: dict) -> dict:
        return {"result": input_data["value"]}


def test_tool_register():
    registry = ToolRegistry()
    tool = TestTool()
    registry.register(tool)
    assert "test_tool" in [t["name"] for t in registry.list_tools()]


def test_tool_execute():
    registry = ToolRegistry()
    tool = TestTool()
    registry.register(tool)
    result = registry.execute("test_tool", {"value": "hello"})
    assert result["result"] == "hello"


def test_tool_validation_error():
    registry = ToolRegistry()
    tool = TestTool()
    registry.register(tool)
    with pytest.raises(ValueError):
        registry.execute("test_tool", {})
```

### 5.2 集成测试

```python
from fastapi.testclient import TestClient
from api.app import app


def test_list_tools():
    client = TestClient(app)
    response = client.get("/api/agent/tools")
    assert response.status_code == 200
    tools = response.json()["data"]["tools"]
    assert len(tools) > 0
```

## 6. 迁移计划

### 6.1 现有工具迁移

1. 将 `agent_tools.py` 中的函数迁移为 Tool 类
2. 更新 `agent_runtime.py` 使用注册表调用工具
3. 保持向后兼容

### 6.2 迁移步骤

1. 创建新的 Tool 类
2. 在注册表中注册
3. 更新运行时调用方式
4. 运行测试验证
5. 清理旧代码
