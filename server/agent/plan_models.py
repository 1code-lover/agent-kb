"""
模块功能：
- 定义任务计划的数据模型
- 包括 Plan、StepPlan、StepType、RiskLevel 等核心结构

执行逻辑：
1. 使用 Pydantic v2 定义数据模型
2. 提供字段验证器确保数据合法性
3. 支持 JSON 序列化和反序列化

关键依赖：
- pydantic: 数据验证和序列化
- enum: 枚举类型定义
"""

from enum import Enum
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# 合法工具名称白名单
VALID_TOOLS = {"kb_search", "read_file", "run_cmd", "analyze", "summarize"}


class StepType(str, Enum):
    """
    功能：
    定义步骤类型枚举

    枚举值：
    - READ_FILE: 读取文件内容
    - WRITE_FILE: 写入文件内容
    - RUN_CMD: 执行命令
    - KB_SEARCH: 检索知识库
    - ANALYZE: 分析/思考（不调用工具）
    - SUMMARIZE: 汇总结果
    """
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    RUN_CMD = "run_cmd"
    KB_SEARCH = "kb_search"
    ANALYZE = "analyze"
    SUMMARIZE = "summarize"


class RiskLevel(str, Enum):
    """
    功能：
    定义风险等级枚举

    枚举值：
    - LOW: 低风险，可直接执行
    - MEDIUM: 中风险，需要记录
    - HIGH: 高风险，需要审批
    """
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StepPlan(BaseModel):
    """
    功能：
    定义单个步骤的计划结构

    字段说明：
    - id(str): 步骤唯一标识
    - type(StepType): 步骤类型
    - title(str): 步骤标题
    - description(str): 步骤详细描述（可选）
    - tool(str): 使用的工具名称（必须在 VALID_TOOLS 中）
    - input(dict): 工具输入参数
    - depends_on(list[str]): 依赖的步骤 ID 列表
    - risk_level(RiskLevel): 风险等级
    - expected_output(str): 预期输出描述

    验证规则：
    - tool 字段必须在 VALID_TOOLS 白名单中
    - model_config 设置 frozen=False 允许修改字段
    """
    id: str
    type: StepType
    title: str
    description: str = ""  # 可选字段，LLM 可能不输出
    tool: str
    input: dict = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    expected_output: str = ""

    @field_validator("tool")
    @classmethod
    def validate_tool(cls, v: str) -> str:
        """
        功能：
        校验工具名称是否合法

        输入：
        - v(str): 工具名称

        输出：
        - str: 验证通过的工具名称

        异常：
        - ValueError: 工具名称不在白名单中
        """
        if v not in VALID_TOOLS:
            raise ValueError(f"Invalid tool: {v}. Valid tools: {VALID_TOOLS}")
        return v

    # 允许修改字段（validate_plan 需要修改 id 和 depends_on）
    model_config = {"frozen": False}


class Plan(BaseModel):
    """
    功能：
    定义完整的任务计划结构

    字段说明：
    - task(str): 原始任务描述
    - steps(list[StepPlan]): 步骤列表
    - created_at(datetime): 创建时间（UTC）
    - estimated_seconds(int): 预估耗时（秒）
    - notes(str): 备注信息

    设计决策：
    - created_at 默认使用 UTC 时区，避免跨时区部署问题
    - estimated_seconds 使用整型而非字符串，便于程序处理
    """
    task: str
    steps: list[StepPlan]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    estimated_seconds: int = 0
    notes: str = ""
