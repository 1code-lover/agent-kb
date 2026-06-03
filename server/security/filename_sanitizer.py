"""
文件名清理器

提供文件名安全性清理，防止路径穿越和 Unicode 攻击。
"""

import os
import uuid
import unicodedata


class FilenameSanitizer:
    """文件名清理器"""
    
    # 危险字符列表
    DANGEROUS_CHARS = ['/', '\\', '~', '|', '*', '?', '<', '>', '"', ':']
    
    @staticmethod
    def sanitize(filename: str) -> str:
        """
        清理文件名，防止路径穿越和 Unicode 攻击。
        
        Args:
            filename: 原始文件名
            
        Returns:
            安全的文件名
        """
        # 1. 移除 Unicode 控制字符（方向控制、零宽字符等）
        #    防止 file\u202e.pdf 这种反转攻击
        filename = ''.join(
            c for c in filename 
            if unicodedata.category(c) not in ('Cf', 'Cc', 'Cn')
        )
        
        # 2. 规范化 Unicode（全角 → 半角）
        filename = unicodedata.normalize('NFKC', filename)
        
        # 3. 提取基础文件名（去除路径）
        basename = os.path.basename(filename)
        
        # 4. 移除危险字符
        for char in FilenameSanitizer.DANGEROUS_CHARS:
            basename = basename.replace(char, '_')
        
        # 5. 移除前后空白和点号
        basename = basename.strip('. ')
        
        # 6. 处理空文件名
        if not basename:
            basename = "unnamed_file"
        
        # 7. 限制文件名长度
        name, ext = os.path.splitext(basename)
        if len(name) > 200:
            name = name[:200]
        
        return name + ext
    
    @staticmethod
    def generate_unique_filename(safe_filename: str) -> str:
        """
        生成唯一文件名，避免并发上传时的竞态条件。
        
        Args:
            safe_filename: 已清理的安全文件名
            
        Returns:
            带唯一后缀的文件名（如 "document_a1b2c3d4.pdf"）
        """
        base, ext = os.path.splitext(safe_filename)
        unique_id = uuid.uuid4().hex[:8]
        return f"{base}_{unique_id}{ext}"
