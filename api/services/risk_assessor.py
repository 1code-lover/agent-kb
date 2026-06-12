"""
文件功能：命令风险评估器
文件描述：实现 L0-L3 风险分级模型，用于评估命令执行的风险等级
核心逻辑：通过正则匹配将命令分类到不同风险等级，支持管道命令取最高风险
"""
from __future__ import annotations

import re
from enum import Enum


class RiskLevel(str, Enum):
    """风险等级枚举"""
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"

    @property
    def needs_approval(self) -> bool:
        """是否需要审批"""
        return self in {RiskLevel.L2, RiskLevel.L3}


class RiskAssessor:
    """命令风险评估器"""

    @staticmethod
    def _assess_single(command: str) -> RiskLevel:
        """评估单个命令的风险等级"""
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
        """评估命令的整体风险等级（支持管道命令取最高风险）"""
        # 先按管道分割命令
        parts = re.split(r'\s*[|;&]{1,2}\s*', command)
        levels = [RiskAssessor._assess_single(item) for item in parts if item.strip()]
        if not levels:
            return RiskLevel.L0
        return max(levels, key=lambda item: list(RiskLevel).index(item))
