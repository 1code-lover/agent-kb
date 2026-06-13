# 硬拒绝命令模式功能文档

## 1. 需求文档（PRD）

### 1.1 功能概述
对极高危命令实现硬阻断，无论是否审批都不执行。

### 1.2 功能需求
- FR-01: 定义不可执行的命令模式列表
- FR-02: 硬拒绝命令无论是否审批都不执行
- FR-03: 硬拒绝事件记录到审计日志

### 1.3 非功能需求
- NFR-01: 硬拒绝命令覆盖率 100%

### 1.4 验收标准
- 硬拒绝命令不可执行
- 硬拒绝事件记录到日志
- 用户收到清晰的拒绝提示

## 2. 功能设计（FRD）

### 2.1 硬拒绝模式列表
```python
HARD_DENY_PATTERNS = [
    (r"\brm\s+-rf\s+/", "rm -rf / 会删除根目录"),
    (r"\bcurl\b.*\|\s*(bash|sh|powershell)", "curl | bash 可能执行恶意脚本"),
    (r"\bwget\b.*\|\s*(bash|sh|powershell)", "wget | bash 可能执行恶意脚本"),
    (r"\bformat\b", "format 会格式化磁盘"),
    (r"\bshutdown\b", "shutdown 会关机"),
    (r"\breboot\b", "reboot 会重启"),
]
```

### 2.2 过滤器接口
```python
class CommandFilter:
    @staticmethod
    def check_hard_deny(command: str) -> str | None:
        # 返回 None 表示可执行，返回字符串表示拒绝原因
```

## 3. 实现文件
- `api/services/command_filter.py`
- `tests/api/test_command_filter.py`

## 4. 测试用例
- test_rm_rf_root_is_hard_denied
- test_curl_pipe_bash_is_hard_denied
- test_safe_command_is_not_hard_denied
- test_format_is_hard_denied
