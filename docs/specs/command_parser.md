# 命令管道解析功能文档

## 1. 需求文档（PRD）

### 1.1 功能概述
支持解析复杂命令链，对每个子命令独立风险评估。

### 1.2 功能需求
- FR-01: 支持 `|`、`&&`、`;` 等管道符号
- FR-02: 对每个子命令独立风险评估
- FR-03: 取最高风险等级作为整体风险

### 1.3 非功能需求
- NFR-01: 支持引号内的管道符号不作为分隔符

### 1.4 验收标准
- 管道命令正确解析
- 每个子命令独立风险评估
- 取最高风险等级作为整体风险

## 2. 功能设计（FRD）

### 2.1 解析结果结构
```python
@dataclass
class ParsedCommand:
    original: str           # 原始命令
    sub_commands: list[str] # 子命令列表
    operators: list[str]    # 操作符列表
```

### 2.2 解析逻辑
1. 逐字符扫描命令字符串
2. 跟踪引号状态，引号内的操作符不作为分隔符
3. 遇到操作符时将当前累积字符作为子命令保存
4. 最后将剩余字符作为最后一个子命令

## 3. 实现文件
- `api/services/command_parser.py`
- `tests/api/test_command_parser.py`

## 4. 测试用例
- test_pipe_chain_is_split
- test_and_chain_is_split
- test_escaped_quotes
- test_semicolon_chain
- test_mixed_operators
