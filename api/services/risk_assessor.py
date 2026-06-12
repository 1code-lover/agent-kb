"""
文件功能：命令风险评估器
文件描述：实现 L0-L3 风险分级模型，用于评估命令执行的风险等级
核心逻辑：通过正则匹配将命令分类到不同风险等级，使用 CommandParser 解析管道命令取最高风险
"""
from __future__ import annotations

import re
from enum import Enum

from api.services.command_parser import CommandParser


class RiskLevel(str, Enum):
    """风险等级枚举"""
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"

    @property
    def needs_approval(self) -> bool:
        """
        函数名：needs_approval
        入参：无
        功能：判断该风险等级是否需要审批
        运行逻辑：L2 和 L3 需要审批，L0 和 L1 不需要
        出参：bool - True 表示需要审批
        """
        return self in {RiskLevel.L2, RiskLevel.L3}


class RiskAssessor:
    """命令风险评估器"""

    @staticmethod
    def _assess_single(command: str) -> RiskLevel:
        """
        函数名：_assess_single
        入参：
            - command (str): 单个命令字符串
        功能：评估单个命令的风险等级
        运行逻辑：
            1. 将命令转为小写并去除首尾空格
            2. 使用正则匹配判断命令类型：
               - L0：只读命令（pwd, ls, cat 等）
               - L1：安全本地命令（python --version, git status 等）
               - L2：修改性命令（rm, pip install, git commit 等）
               - L3：系统级命令（shutdown, reboot, sudo 等）
            3. 未匹配到则默认返回 L2
        出参：RiskLevel - 风险等级枚举值
        """
        normalized = (command or "").strip().lower()
        if re.match(r'\b(pwd|ls|dir|whoami|cat|type|echo|head|tail|grep|find|wc)\b', normalized):
            return RiskLevel.L0
        if re.match(r'\b(python|python3|node|npm|git|java|go|cargo|docker)\b.*--version', normalized) or \
           re.match(r'\bgit\s+status\b', normalized):
            return RiskLevel.L1
        if re.match(r'\b(rm|del|pip\s+install|npm\s+install|git\s+commit|git\s+push)\b', normalized):
            return RiskLevel.L2
        if re.match(r'\b(shutdown|reboot|format|mkfs|sudo|dd)\b', normalized):
            return RiskLevel.L3
        return RiskLevel.L2

    @staticmethod
    def assess(command: str) -> RiskLevel:
        """
        函数名：assess
        入参：
            - command (str): 命令字符串（支持管道命令）
        功能：评估命令的整体风险等级
        运行逻辑：
            1. 使用 CommandParser 解析命令管道
            2. 对每个子命令调用 _assess_single 评估风险
            3. 取最高风险等级作为整体风险
        出参：RiskLevel - 命令的整体风险等级
        """
        parsed = CommandParser.parse(command)
        levels = [RiskAssessor._assess_single(item) for item in parsed.sub_commands or [command]]
        if not levels:
            return RiskLevel.L0
        return max(levels, key=lambda item: list(RiskLevel).index(item))
