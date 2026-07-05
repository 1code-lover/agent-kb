# 工具注册表功能文档

## 1. 需求文档（PRD）

### 1.1 功能概述
建立可扩展的工具注册和调用机制，使新工具可通过注册表快速接入。

### 1.2 功能需求
- FR-01: 提供统一的工具注册和发现机制
- FR-02: 支持工具 Schema 定义（输入/输出）
- FR-03: 支持工具自动调用和路由

### 1.3 非功能需求
- NFR-01: 新工具注册不超过 10 行代码
- NFR-02: 工具列表可动态扩展

### 1.4 验收标准
- 工具可通过注册表注册
- 工具可通过名称调用
- 工具列表可查询

## 2. 功能设计（FRD）

### 2.1 模块结构
- `ToolBase`: 工具抽象基类
- `ToolRegistry`: 工具注册表

### 2.2 接口设计
```python
class ToolBase(ABC):
    name: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    risk_level: str
    
    def validate_input(data: dict) -> BaseModel
    def validate_output(data: dict) -> BaseModel
    def execute(input_data: dict) -> dict
    def to_dict() -> dict

class ToolRegistry:
    def register(tool: ToolBase) -> None
    def get(name: str) -> ToolBase
    def list_tools() -> list[dict]
    def execute(name: str, input_data: dict) -> dict
```

## 3. 实现文件
- `api/services/tool_registry.py`
- `tests/api/test_tool_registry.py`

## 4. 测试用例
- test_tool_registration_and_listing
- test_tool_execution
- test_missing_tool_raises_clear_error
