"""
文件功能：工具输入输出 Schema 定义
文件描述：定义内置工具的输入和输出数据模型，用于数据验证和序列化
核心逻辑：使用 Pydantic BaseModel 定义结构化 Schema，通过 Field 约束字段有效性
"""
from pydantic import BaseModel, Field


class KbSearchInput(BaseModel):
    """知识库搜索输入 Schema"""
    question: str = Field(..., min_length=1)
    session_id: str = Field(default="default")


class KbSearchOutput(BaseModel):
    """知识库搜索输出 Schema"""
    answer: str = ""
    sources: list[dict] = Field(default_factory=list)
    evidence_count: int = 0


class ReadFileInput(BaseModel):
    """文件读取输入 Schema"""
    path: str = Field(..., min_length=1)
    session_id: str = Field(default="default")


class ReadFileOutput(BaseModel):
    """文件读取输出 Schema"""
    path: str
    excerpt: str


class RunCmdInput(BaseModel):
    """命令执行输入 Schema"""
    command: str = Field(..., min_length=1)
    session_id: str = Field(default="default")


class RunCmdOutput(BaseModel):
    """命令执行输出 Schema"""
    exit_code: int
    output: str
