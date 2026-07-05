"""
文件功能：命令管道解析器
文件描述：将命令字符串解析为子命令和操作符列表，支持引号转义
核心逻辑：逐字符扫描命令字符串，在非引号状态下识别操作符（|, &&, ||, ;），拆分为子命令
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParsedCommand:
    """解析后的命令结构"""
    original: str
    sub_commands: list[str] = field(default_factory=list)
    operators: list[str] = field(default_factory=list)


class CommandParser:
    """命令管道解析器，支持 |, &&, ||, ; 操作符"""

    OPERATORS = ("&&", "||", "|", ";")

    @staticmethod
    def parse(command: str) -> ParsedCommand:
        """
        函数名：parse
        入参：
            - command (str): 待解析的命令字符串
        功能：解析命令管道，返回子命令列表和操作符列表
        运行逻辑：
            1. 逐字符扫描命令字符串
            2. 跟踪引号状态，引号内的操作符不作为分隔符
            3. 遇到操作符时将当前累积字符作为子命令保存
            4. 最后将剩余字符作为最后一个子命令
        出参：ParsedCommand - 包含原始命令、子命令列表和操作符列表
        """
        sub_commands: list[str] = []
        operators: list[str] = []
        current: list[str] = []
        in_quote = False
        quote_char = ""
        i = 0

        while i < len(command):
            char = command[i]
            if char in {'"', "'"}:
                if not in_quote:
                    in_quote = True
                    quote_char = char
                elif quote_char == char:
                    in_quote = False
                current.append(char)
                i += 1
                continue

            if not in_quote:
                matched = next((op for op in CommandParser.OPERATORS if command.startswith(op, i)), None)
                if matched:
                    sub_commands.append("".join(current).strip())
                    operators.append(matched)
                    current = []
                    i += len(matched)
                    continue

            current.append(char)
            i += 1

        tail = "".join(current).strip()
        if tail:
            sub_commands.append(tail)

        return ParsedCommand(original=command, sub_commands=sub_commands, operators=operators)
