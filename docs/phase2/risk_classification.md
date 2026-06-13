# L0-L3风险分级功能文档

## 1. 需求文档（PRD）

### 1.1 功能概述
将现有三级风险扩展为四级，提供更细粒度的安全控制。

### 1.2 功能需求
- FR-01: L0：无风险（如查看类命令）
- FR-02: L1：低风险（如只读操作）
- FR-03: L2：中风险（如文件修改）
- FR-04: L3：高风险（如系统级操作）

### 1.3 非功能需求
- NFR-01: 硬拒绝命令覆盖率 100%
- NFR-02: L2/L3 命令审批覆盖率 100%

### 1.4 验收标准
- L0 命令直接执行
- L1 命令直接执行
- L2 命令需审批
- L3 命令需审批或硬拒绝

## 2. 功能设计（FRD）

### 2.1 风险等级定义
```python
class RiskLevel(str, Enum):
    L0 = "L0"  # 无风险
    L1 = "L1"  # 低风险
    L2 = "L2"  # 中风险
    L3 = "L3"  # 高风险
    
    @property
    def needs_approval(self) -> bool:
        return self in {RiskLevel.L2, RiskLevel.L3}
```

### 2.2 风险映射规则
- L0: pwd, ls, dir, whoami, cat, type, echo, head, tail, grep, find, wc
- L1: python --version, git status, node --version
- L2: rm, del, pip install, npm install, git commit, git push
- L3: shutdown, reboot, format, mkfs, sudo, dd

## 3. 实现文件
- `api/services/risk_assessor.py`
- `tests/api/test_risk_levels.py`

## 4. 测试用例
- test_l0_readonly_commands
- test_l1_safe_local_commands
- test_l2_mutating_commands
- test_l3_system_commands
- test_risk_level_properties
