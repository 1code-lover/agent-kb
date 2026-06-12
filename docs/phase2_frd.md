# Phase 2 功能设计文档（FRD）- 工具注册表和安全执行增强

## 1. 文档目的
将 Phase 2 PRD 转换为可执行的功能清单，为研发排期、联调和测试设计提供统一依据。

## 2. 功能模块总览
1. 工具注册表模块
2. 工具 Schema 验证模块
3. 风险分级增强模块
4. 硬拒绝命令模块
5. 命令管道解析模块
6. 回执持久化模块
7. 集成测试模块

## 3. 功能清单（按优先级）

## 3.1 P0（必须）

### M1 工具注册表框架

**目标**：建立可扩展的工具注册和调用机制

**包含**：
- ToolBase 基类定义
- ToolRegistry 注册表实现
- 工具自动发现和路由
- 工具元数据管理

**验收要点**：
- 新工具可通过装饰器或显式注册
- 工具可通过名称自动调用
- 注册表支持工具列表查询

**详细设计**：

```python
# 工具基类
class ToolBase(ABC):
    name: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    risk_level: str  # L0/L1/L2/L3
    
    @abstractmethod
    def execute(self, input_data: dict) -> dict: ...

# 注册表
class ToolRegistry:
    _tools: dict[str, ToolBase] = {}
    
    def register(self, tool: ToolBase): ...
    def get(self, name: str) -> ToolBase: ...
    def list_tools(self) -> list[dict]: ...
    def execute(self, name: str, input_data: dict) -> dict: ...
```

### M2 工具 Schema 验证

**目标**：确保工具输入输出符合定义的 Schema

**包含**：
- 输入验证（调用前）
- 输出验证（返回后）
- 验证错误处理

**验收要点**：
- 输入不符合 Schema 时返回 400 错误
- 输出不符合 Schema 时记录异常
- 验证错误信息清晰可理解

**详细设计**：

```python
# 输入 Schema 示例
class KbSearchInput(BaseModel):
    question: str = Field(..., min_length=1)
    session_id: str = Field(default="default")
    top_k: int = Field(default=5, ge=1, le=20)

# 输出 Schema 示例
class KbSearchOutput(BaseModel):
    answer: str
    sources: list[dict]
    evidence_count: int
```

### M3 L0-L3 风险分级

**目标**：提供更细粒度的风险控制

**包含**：
- 风险等级常量定义
- 风险映射规则
- 风险评估函数

**验收要点**：
- L0：无风险命令直接执行
- L1：低风险命令直接执行
- L2：中风险命令需审批
- L3：高风险命令需审批或硬拒绝

**风险等级映射表**：

| 等级 | 描述 | 示例命令 | 处理方式 |
|------|------|----------|----------|
| L0 | 无风险 | `pwd`, `whoami`, `echo` | 直接执行 |
| L1 | 低风险 | `ls`, `cat`, `python --version` | 直接执行 |
| L2 | 中风险 | `pip install`, `git commit`, `rm file.txt` | 需审批 |
| L3 | 高风险 | `rm -rf`, `format`, `shutdown` | 硬拒绝或需审批 |

## 3.2 P1（重要）

### M4 硬拒绝命令模块

**目标**：对极高危命令实现硬阻断

**包含**：
- 硬拒绝模式列表
- 命令过滤器
- 审计日志

**验收要点**：
- 硬拒绝命令不可执行，无论是否审批
- 硬拒绝事件记录到审计日志
- 用户收到清晰的拒绝提示

**硬拒绝模式列表**：

```python
HARD_DENY_PATTERNS = [
    r"\brm\s+-rf\s+/",           # rm -rf /
    r"\bformat\b",               # format
    r"\bshutdown\b",             # shutdown
    r"\breboot\b",               # reboot
    r"\bmkfs\b",                 # mkfs
    r"\bdd\s+.*of=/dev/",        # dd to device
    r"\bcurl\b.*\|\s*(bash|sh)", # curl | bash
    r"\bwget\b.*\|\s*(bash|sh)", # wget | bash
]
```

### M5 命令管道解析

**目标**：支持解析复杂命令链

**包含**：
- 命令分割和解析
- 子命令风险评估
- 整体风险计算

**验收要点**：
- 支持 `|`、`&&`、`;` 管道符号
- 每个子命令独立风险评估
- 取最高风险等级作为整体风险

**解析逻辑**：

```python
def parse_command_pipeline(command: str) -> list[str]:
    """解析命令管道，返回子命令列表"""
    # 处理引号内的管道符号
    # 分割命令
    # 返回子命令列表

def assess_pipeline_risk(sub_commands: list[str]) -> str:
    """评估命令管道的整体风险"""
    # 对每个子命令评估风险
    # 返回最高风险等级
```

### M6 回执持久化存储

**目标**：将回执从内存存储升级为持久化存储

**包含**：
- 存储接口定义
- SQLite 存储实现
- 查询接口

**验收要点**：
- 回执数据在服务重启后可恢复
- 支持按会话查询回执
- 支持按时间范围查询回执

**数据库设计**：

```sql
CREATE TABLE tool_receipts (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    input_data TEXT,  -- JSON
    output_data TEXT, -- JSON
    status TEXT NOT NULL,
    risk_level TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session_id (session_id),
    INDEX idx_created_at (created_at)
);
```

## 3.3 P2（增强）

### M7 工具热注册

**目标**：支持运行时动态注册新工具

**包含**：
- 动态注册 API
- 工具卸载机制

**验收要点**：
- 可通过 API 注册新工具
- 可卸载已注册工具

### M8 风险规则配置化

**目标**：支持通过配置文件自定义风险规则

**包含**：
- 风险规则配置文件
- 规则热加载

**验收要点**：
- 风险规则可通过配置文件修改
- 配置变更后自动生效

## 4. 页面级设计（高层）

### 4.1 工具管理页面（新增）
- 工具列表展示
- 工具 Schema 查看
- 工具测试调用

### 4.2 风险配置页面（新增）
- 风险等级说明
- 硬拒绝规则列表
- 风险规则测试

## 5. 交互规则

1. 工具调用失败时显示清晰的错误信息
2. 风险等级变化时通知用户
3. 硬拒绝命令给出替代建议
4. 回执查询支持分页和筛选

## 6. 异常处理设计

1. 工具不存在：返回 404 错误
2. Schema 验证失败：返回 400 错误和详细信息
3. 硬拒绝命令：返回 403 错误和拒绝原因
4. 存储异常：返回 500 错误并记录日志

## 7. 开发拆分建议

### 后端
- 工具注册表框架（Task 1）
- Schema 验证（Task 2）
- 风险分级增强（Task 3）
- 硬拒绝命令（Task 4）
- 命令管道解析（Task 5）
- 回执持久化（Task 6）

### 测试
- 单元测试（各 Task）
- 集成测试（Task 7）

## 8. DoD（功能完成定义）

1. 所有 P0 功能通过测试用例
2. 所有 P1 功能通过测试用例
3. 单元测试覆盖率 >= 80%
4. 集成测试通过
5. 文档更新完成
