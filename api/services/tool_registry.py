"""
文件功能：工具注册表
文件描述：提供工具注册、查找和执行的统一框架，支持工具的生命周期管理
核心逻辑：使用字典存储工具实例，通过工具名称进行索引，支持注册、查询、列表和执行操作
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ValidationError


class ToolBase(ABC):
    """工具基类，定义工具的标准接口"""
    name: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    risk_level: str = "L0"

    def validate_input(self, data: dict[str, Any]) -> BaseModel:
        """
        函数名：validate_input
        入参：
            - data (dict[str, Any]): 待验证的输入数据
        功能：验证输入数据是否符合工具的输入模式
        运行逻辑：
            1. 使用 input_schema 对数据进行验证
            2. 验证失败时抛出 ValueError 异常
        出参：BaseModel - 验证后的输入数据模型
        """
        try:
            return self.input_schema(**data)
        except ValidationError as exc:
            raise ValueError(f"Tool input validation failed: {exc}") from exc

    def validate_output(self, data: dict[str, Any]) -> BaseModel:
        """
        函数名：validate_output
        入参：
            - data (dict[str, Any]): 待验证的输出数据
        功能：验证输出数据是否符合工具的输出模式
        运行逻辑：
            1. 使用 output_schema 对数据进行验证
            2. 验证失败时抛出 ValueError 异常
        出参：BaseModel - 验证后的输出数据模型
        """
        try:
            return self.output_schema(**data)
        except ValidationError as exc:
            raise ValueError(f"Tool output validation failed: {exc}") from exc

    @abstractmethod
    def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """
        函数名：execute
        入参：
            - input_data (dict[str, Any]): 经过验证的输入数据
        功能：执行工具的核心逻辑
        运行逻辑：由子类实现具体的执行逻辑
        出参：dict[str, Any] - 执行结果
        """
        raise NotImplementedError

    def to_dict(self) -> dict[str, str]:
        """
        函数名：to_dict
        入参：无
        功能：将工具信息转换为字典格式
        运行逻辑：提取工具的名称、描述和风险等级
        出参：dict[str, str] - 工具信息字典
        """
        return {
            "name": self.name,
            "description": self.description,
            "risk_level": self.risk_level,
        }


class ToolRegistry:
    """工具注册表，管理工具的注册、查找和执行"""

    def __init__(self) -> None:
        """
        函数名：__init__
        入参：无
        功能：初始化工具注册表
        运行逻辑：创建空的工具存储字典
        出参：无
        """
        self._tools: dict[str, ToolBase] = {}

    def clear(self) -> None:
        """
        函数名：clear
        入参：无
        功能：清空注册表中的所有工具
        运行逻辑：清除工具存储字典
        出参：无
        """
        self._tools.clear()

    def register(self, tool: ToolBase) -> None:
        """
        函数名：register
        入参：
            - tool (ToolBase): 待注册的工具实例
        功能：注册一个工具到注册表
        运行逻辑：以工具名称为键存储工具实例
        出参：无
        """
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolBase:
        """
        函数名：get
        入参：
            - name (str): 工具名称
        功能：根据名称获取工具实例
        运行逻辑：
            1. 从存储字典中查找工具
            2. 如果未找到则抛出 ValueError 异常
        出参：ToolBase - 工具实例
        """
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"Tool not found: {name}")
        return tool

    def list_tools(self) -> list[dict[str, str]]:
        """
        函数名：list_tools
        入参：无
        功能：列出所有已注册的工具
        运行逻辑：遍历所有工具，调用每个工具的 to_dict 方法
        出参：list[dict[str, str]] - 工具信息列表
        """
        return [tool.to_dict() for tool in self._tools.values()]

    def execute(self, name: str, input_data: dict[str, Any]) -> dict[str, Any]:
        """
        函数名：execute
        入参：
            - name (str): 工具名称
            - input_data (dict[str, Any]): 输入数据
        功能：执行指定工具
        运行逻辑：
            1. 获取工具实例
            2. 验证输入数据
            3. 执行工具逻辑
            4. 验证输出数据
            5. 返回验证后的结果
        出参：dict[str, Any] - 执行结果
        """
        tool = self.get(name)
        validated_input = tool.validate_input(input_data)
        result = tool.execute(validated_input.model_dump())
        validated_output = tool.validate_output(result)
        return validated_output.model_dump()
