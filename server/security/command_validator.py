"""
命令白名单校验器

提供命令安全性校验，包括白名单、黑名单、管道控制等功能。
"""

import os
import re
import shlex
from typing import Tuple, Optional

# 涉及文件参数的命令，需要对文件参数进行路径校验
FILE_ARG_CMDS = {"cat", "head", "tail", "grep", "less", "more"}


class CommandValidator:
    """命令白名单校验器"""
    
    def __init__(self, config: dict, path_validator=None):
        """
        初始化命令校验器。
        
        Args:
            config: 安全配置字典
            path_validator: 路径校验器实例，用于校验文件参数
        """
        self.path_validator = path_validator
        self.allow_pipes = config.get("allow_pipes", False)
        self.allow_chaining = config.get("allow_chaining", False)
        self.default_timeout = config.get("default_timeout", 30)
        self.tool_timeouts = config.get("tool_timeouts", {})
        
        # 预编译黑名单正则，启动时即发现配置错误
        try:
            self.blacklist = [re.compile(p) for p in config.get("blacklist_patterns", [])]
        except re.error as e:
            raise ValueError(f"Invalid blacklist pattern in config: {e}")
        
        # 预编译白名单参数正则
        self.whitelist = []
        for entry in config.get("whitelist", []):
            compiled = dict(entry)
            if "args_pattern" in entry:
                try:
                    compiled["args_pattern"] = re.compile(entry["args_pattern"])
                except re.error as e:
                    raise ValueError(f"Invalid args_pattern for '{entry['cmd']}': {e}")
            self.whitelist.append(compiled)
    
    def get_timeout(self, command: str) -> int:
        """
        获取命令的超时时间。
        
        Args:
            command: 命令字符串
            
        Returns:
            超时时间（秒）
        """
        # 使用 os.path.basename 处理绝对路径（如 /usr/bin/python → python）
        base_cmd = os.path.basename(command.split()[0]) if command.split() else ""
        return self.tool_timeouts.get(base_cmd, self.default_timeout)
    
    def validate(self, command: str) -> Tuple[bool, str]:
        """
        校验命令是否安全。
        
        Args:
            command: 命令字符串
            
        Returns:
            (allowed, reason): 是否允许执行，原因说明
        """
        # 1. 检查链接符
        if not self.allow_chaining and re.search(r'\s*(&&|\|\||;)\s*', command):
            return False, "Command chaining is not allowed"
        
        # 2. 拆分管道命令
        if self.allow_pipes:
            commands = [cmd.strip() for cmd in command.split("|")]
        else:
            if "|" in command:
                return False, "Pipes are not allowed"
            commands = [command]
        
        # 3. 校验每个命令
        for cmd in commands:
            try:
                # 使用 posix=False 提高 Windows 兼容性
                parts = shlex.split(cmd, posix=False)
            except ValueError:
                parts = cmd.split()
            
            if not parts:
                continue
            
            base_cmd = os.path.basename(parts[0])  # 提取基础命令名
            
            # 检查黑名单
            for pattern in self.blacklist:
                if pattern.search(cmd):
                    return False, f"Command matches blacklist pattern: {pattern.pattern}"
            
            # 检查白名单
            allowed = False
            for entry in self.whitelist:
                if entry["cmd"] == base_cmd:
                    # 检查参数模式
                    if "args_pattern" in entry:
                        args = " ".join(parts[1:])
                        if entry["args_pattern"].match(args):
                            allowed = True
                            break
                    else:
                        allowed = True
                        break
            
            if not allowed:
                return False, f"Command not in whitelist: {base_cmd}"
            
            # 4. 对文件操作命令，校验文件参数路径
            if self.path_validator and base_cmd in FILE_ARG_CMDS:
                file_args = [p for p in parts[1:] if not p.startswith("-")]
                for f in file_args:
                    # 清理引号
                    f = f.strip("'\"")
                    allowed_path, _, reason = self.path_validator.validate_read(f)
                    if not allowed_path:
                        return False, f"File argument not allowed for '{base_cmd}': {reason}"
        
        return True, "OK"
