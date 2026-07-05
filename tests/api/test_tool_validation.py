"""工具 Schema 验证测试"""
import pytest


def test_kb_search_schema_rejects_empty_question():
    from api.schemas.tool_schemas import KbSearchInput
    with pytest.raises(Exception):
        KbSearchInput(question="")


def test_run_cmd_schema_requires_command():
    from api.schemas.tool_schemas import RunCmdInput
    with pytest.raises(Exception):
        RunCmdInput(command="")
