"""
路径安全校验器

提供文件路径安全性校验，包括目录白名单、符号链接防护等功能。
"""

import os
from typing import Tuple


class PathValidator:
    """路径安全校验器"""
    
    def __init__(self, config: dict):
        """
        初始化路径校验器。
        
        Args:
            config: 安全配置字典
        """
        self.allowed_dirs = [os.path.abspath(d) for d in config.get("allowed_read_dirs", [])]
        self.max_size = config.get("max_file_size_mb", 10) * 1024 * 1024
        self.allowed_ext = set(config.get("allowed_extensions", []))
        self.follow_symlinks = config.get("follow_symlinks", False)
    
    def validate_read(self, path: str) -> Tuple[bool, str, str]:
        """
        校验文件读取是否安全。
        
        Args:
            path: 文件路径
            
        Returns:
            (allowed, resolved_path, reason): 是否允许，解析后的路径，原因说明
        """
        # 1. 解析真实路径（防止符号链接绕过）
        if not self.follow_symlinks:
            real_path = os.path.realpath(path)
        else:
            real_path = os.path.abspath(path)
        
        # 2. 检查是否在允许目录内
        in_allowed = False
        for allowed_dir in self.allowed_dirs:
            if real_path.startswith(allowed_dir + os.sep) or real_path == allowed_dir:
                in_allowed = True
                break
        
        if not in_allowed:
            return False, "", f"Path not in allowed directories: {real_path}"
        
        # 3. 检查文件是否存在
        if not os.path.exists(real_path):
            return False, "", f"File not found: {real_path}"
        
        # 4. 检查文件大小
        file_size = os.path.getsize(real_path)
        if file_size > self.max_size:
            return False, "", f"File too large: {file_size} bytes (max: {self.max_size})"
        
        # 5. 检查文件扩展名
        _, ext = os.path.splitext(real_path)
        if ext.lower() not in self.allowed_ext:
            return False, "", f"File extension not allowed: {ext}"
        
        return True, real_path, "OK"
