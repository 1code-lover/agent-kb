"""
文件功能：Phase 2 集成测试
文件描述：验证各组件协同工作的端到端流程
核心逻辑：测试风险评估管道、工具注册执行、回执持久化等集成场景
"""
from types import SimpleNamespace


def test_full_risk_assessment_pipeline():
    """测试完整的风险评估流程：正常命令 -> 硬拒绝 -> 风险分级"""
    from api.services.risk_assessor import RiskAssessor, RiskLevel
    from api.services.command_filter import CommandFilter

    # 正常命令 - 低风险
    risk = RiskAssessor.assess("ls -la")
    assert risk == RiskLevel.L0
    assert CommandFilter.check_hard_deny("ls -la") is None

    # 中风险命令
    risk = RiskAssessor.assess("rm file.txt")
    assert risk == RiskLevel.L2
    assert risk.needs_approval is True

    # 硬拒绝命令
    deny_reason = CommandFilter.check_hard_deny("rm -rf /")
    assert deny_reason is not None


def test_pipeline_risk_aggregation():
    """测试管道命令风险聚合：取最高风险等级"""
    from api.services.risk_assessor import RiskAssessor, RiskLevel
    from api.services.command_parser import CommandParser

    parsed = CommandParser.parse("cat safe.txt | rm dangerous.txt")
    assert len(parsed.sub_commands) == 2

    # 管道中包含 rm，整体风险应为 L2
    risk = RiskAssessor.assess("cat safe.txt | rm dangerous.txt")
    assert risk == RiskLevel.L2


def test_tool_registry_execution():
    """测试工具注册和执行流程"""
    from api.services.tool_registry import ToolRegistry
    from pydantic import BaseModel

    class TestInput(BaseModel):
        value: str

    class TestOutput(BaseModel):
        result: str

    class TestTool:
        name = "test"
        description = "test tool"
        input_schema = TestInput
        output_schema = TestOutput
        risk_level = "L0"

        def validate_input(self, data: dict):
            return self.input_schema(**data)

        def validate_output(self, data: dict):
            return self.output_schema(**data)

        def execute(self, input_data: dict) -> dict:
            return {"result": input_data["value"]}

        def to_dict(self) -> dict:
            return {"name": self.name, "description": self.description, "risk_level": self.risk_level}

    registry = ToolRegistry()
    registry.clear()
    registry.register(TestTool())

    result = registry.execute("test", {"value": "hello"})
    assert result == {"result": "hello"}


def test_receipt_persistence_flow():
    """测试回执持久化流程：写入 -> 查询"""
    from api.services.storage.sqlite_receipt_storage import SQLiteReceiptStorage
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
        store = SQLiteReceiptStorage(handle.name)

        # 写入多条回执
        store.save({"session_id": "s1", "tool_name": "kb_search", "input": {"q": "test"}, "output": {"a": "ok"}, "status": "ok"})
        store.save({"session_id": "s1", "tool_name": "run_cmd", "input": {"cmd": "pwd"}, "output": {"out": "/"}, "status": "ok"})
        store.save({"session_id": "s2", "tool_name": "read_file", "input": {"p": "/tmp"}, "output": {"c": "data"}, "status": "ok"})

        # 按会话查询
        s1_receipts = store.list_by_session("s1", limit=10)
        assert len(s1_receipts) == 2

        s2_receipts = store.list_by_session("s2", limit=10)
        assert len(s2_receipts) == 1

        # 按 ID 查询
        by_id = store.find_by_id(s1_receipts[0]["id"])
        assert by_id is not None
        assert by_id["session_id"] == "s1"


def test_approval_service_risk_classification():
    """测试审批服务的风险分级集成"""
    from api.services.approval_service import classify_command_risk

    # L0 命令
    assert classify_command_risk("pwd") == "L0"

    # L2 命令
    assert classify_command_risk("rm temp.txt") == "L2"

    # 硬拒绝命令应返回 L3
    assert classify_command_risk("rm -rf /") == "L3"
