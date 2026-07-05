"""
文件功能：L0-L3 风险分级模型测试
文件描述：测试命令风险评估器的风险等级分类功能
核心逻辑：验证不同命令被正确分类到对应的风险等级
"""
from api.services.risk_assessor import RiskAssessor, RiskLevel


def test_l0_readonly_commands():
    """测试只读命令被分类为 L0 风险等级"""
    assert RiskAssessor.assess("pwd") == RiskLevel.L0
    assert RiskAssessor.assess("ls -la") == RiskLevel.L0


def test_l1_safe_local_commands():
    """测试安全本地命令被分类为 L1 风险等级"""
    assert RiskAssessor.assess("python --version") == RiskLevel.L1


def test_l2_mutating_commands():
    """测试变更性命令被分类为 L2 风险等级"""
    assert RiskAssessor.assess("rm temp.txt") == RiskLevel.L2


def test_l3_system_commands():
    """测试系统级命令被分类为 L3 风险等级"""
    assert RiskAssessor.assess("shutdown /r /t 0") == RiskLevel.L3


def test_risk_level_properties():
    """测试风险等级的属性方法"""
    assert RiskLevel.L0.needs_approval is False
    assert RiskLevel.L1.needs_approval is False
    assert RiskLevel.L2.needs_approval is True
    assert RiskLevel.L3.needs_approval is True
