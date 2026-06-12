"""工具注册表测试"""
import pytest
from pydantic import BaseModel


class DummyInput(BaseModel):
    value: str


class DummyOutput(BaseModel):
    result: str


class DummyTool:
    """测试用工具类"""
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
    """测试工具注册和列表功能"""
    registry.register(DummyTool())
    assert registry.list_tools() == [
        {"name": "dummy", "description": "dummy test tool", "risk_level": "L0"}
    ]


def test_tool_execution(registry):
    """测试工具执行功能"""
    registry.register(DummyTool())
    result = registry.execute("dummy", {"value": "hello"})
    assert result == {"result": "hello"}


def test_missing_tool_raises_clear_error(registry):
    """测试获取不存在的工具时抛出清晰错误"""
    with pytest.raises(ValueError, match="Tool not found: missing"):
        registry.get("missing")
