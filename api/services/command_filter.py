"""
文件功能：命令硬拒绝过滤器
文件描述：定义高危命令模式列表，检查命令是否应被硬拒绝执行
核心逻辑：使用正则表达式匹配命令字符串，命中硬拒绝模式则返回拒绝原因
"""
from __future__ import annotations

import re


# 硬拒绝模式列表：(正则模式, 拒绝原因)
HARD_DENY_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+-rf\s+/", "rm -rf / 会删除根目录"),
    (r"\bcurl\b.*\|\s*(bash|sh|powershell)", "curl | bash 可能执行恶意脚本"),
    (r"\bwget\b.*\|\s*(bash|sh|powershell)", "wget | bash 可能执行恶意脚本"),
    (r"\bformat\b", "format 会格式化磁盘"),
    (r"\bshutdown\b", "shutdown 会关机"),
    (r"\breboot\b", "reboot 会重启"),
]


class CommandFilter:
    """命令过滤器，检查命令是否被硬拒绝"""

    @staticmethod
    def check_hard_deny(command: str) -> str | None:
        """
        函数名：check_hard_deny
        入参：
            - command (str): 待检查的命令字符串
        功能：检查命令是否命中硬拒绝模式
        运行逻辑：
            1. 将命令转为小写并去除首尾空格
            2. 遍历硬拒绝模式列表
            3. 使用正则表达式匹配命令
            4. 命中则返回拒绝原因，否则返回 None
        出参：str | None - None 表示命令可执行，字符串表示拒绝原因
        """
        normalized = (command or "").strip().lower()
        for pattern, reason in HARD_DENY_PATTERNS:
            if re.search(pattern, normalized):
                return reason
        return None
