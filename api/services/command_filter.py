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
        检查命令是否被硬拒绝

        返回 None 表示命令可执行，返回字符串表示拒绝原因
        """
        normalized = (command or "").strip().lower()
        for pattern, reason in HARD_DENY_PATTERNS:
            if re.search(pattern, normalized):
                return reason
        return None
