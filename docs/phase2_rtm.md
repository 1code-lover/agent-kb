# Phase 2 需求追踪矩阵（RTM）- 工具注册表和安全执行增强

## 1. 说明
- 目的：确保需求、实现、测试、验收一一对应，避免遗漏。
- 规则：每条需求至少对应 1 条测试用例和 1 条验收检查项。

## 2. 需求追踪矩阵

| 需求ID | 需求描述 | 对应功能模块 | 测试类型 | 验收标准 |
| --- | --- | --- | --- | --- |
| P2-FR-01 | 工具注册表框架 | M1 工具注册表 | 单元测试、集成测试 | 工具可注册、可发现、可调用 |
| P2-FR-02 | 工具 Schema 验证 | M2 Schema 验证 | 单元测试 | 输入输出验证正确 |
| P2-FR-03 | L0-L3 风险分级 | M3 风险分级 | 单元测试、安全测试 | 四级风险映射正确 |
| P2-FR-04 | 硬拒绝命令模式 | M4 硬拒绝模块 | 单元测试、安全测试 | 高危命令不可执行 |
| P2-FR-05 | 命令管道解析 | M5 管道解析 | 单元测试 | 管道命令正确解析 |
| P2-FR-06 | 回执持久化存储 | M6 回执持久化 | 单元测试、集成测试 | 数据重启后可恢复 |
| P2-NFR-01 | 可扩展性 | M1 工具注册表 | 代码评审 | 新工具注册简单 |
| P2-NFR-02 | 安全性 | M3/M4 | 安全测试 | 硬拒绝覆盖率 100% |
| P2-NFR-03 | 性能 | 全模块 | 性能测试 | 延迟增加 < 10ms |
| P2-NFR-04 | 可维护性 | 全模块 | 代码评审 | 测试覆盖率 >= 80% |

## 3. 场景测试映射

| 场景ID | 场景描述 | 覆盖需求 |
| --- | --- | --- |
| P2-SC-01 | 注册新工具并成功调用 | P2-FR-01, P2-FR-02 |
| P2-SC-02 | 工具输入 Schema 验证失败 | P2-FR-02 |
| P2-SC-03 | L0 命令直接执行 | P2-FR-03 |
| P2-SC-04 | L2 命令触发审批 | P2-FR-03 |
| P2-SC-05 | 硬拒绝命令被阻断 | P2-FR-04, P2-NFR-02 |
| P2-SC-06 | 管道命令风险评估 | P2-FR-05 |
| P2-SC-07 | 回执数据持久化存储 | P2-FR-06 |
| P2-SC-08 | 重启后回执数据恢复 | P2-FR-06 |

## 4. 测试用例映射

| 测试ID | 测试描述 | 对应需求 | 测试类型 |
| --- | --- | --- | --- |
| P2-T-01 | 测试工具注册 | P2-FR-01 | 单元测试 |
| P2-T-02 | 测试工具发现 | P2-FR-01 | 单元测试 |
| P2-T-03 | 测试工具调用 | P2-FR-01 | 单元测试 |
| P2-T-04 | 测试输入验证成功 | P2-FR-02 | 单元测试 |
| P2-T-05 | 测试输入验证失败 | P2-FR-02 | 单元测试 |
| P2-T-06 | 测试输出验证 | P2-FR-02 | 单元测试 |
| P2-T-07 | 测试 L0 风险分级 | P2-FR-03 | 单元测试 |
| P2-T-08 | 测试 L1 风险分级 | P2-FR-03 | 单元测试 |
| P2-T-09 | 测试 L2 风险分级 | P2-FR-03 | 单元测试 |
| P2-T-10 | 测试 L3 风险分级 | P2-FR-03 | 单元测试 |
| P2-T-11 | 测试硬拒绝模式匹配 | P2-FR-04 | 单元测试 |
| P2-T-12 | 测试硬拒绝执行阻断 | P2-FR-04 | 安全测试 |
| P2-T-13 | 测试管道命令解析 | P2-FR-05 | 单元测试 |
| P2-T-14 | 测试管道风险评估 | P2-FR-05 | 单元测试 |
| P2-T-15 | 测试回执存储 | P2-FR-06 | 单元测试 |
| P2-T-16 | 测试回执查询 | P2-FR-06 | 单元测试 |
| P2-T-17 | 测试回执持久化 | P2-FR-06 | 集成测试 |
| P2-T-18 | 测试端到端工具调用 | 全需求 | 集成测试 |

## 5. 代码文件映射

| 功能模块 | 新建文件 | 修改文件 |
| --- | --- | --- |
| M1 工具注册表 | `api/services/tool_registry.py` | `api/services/agent_tools.py` |
| M2 Schema 验证 | `api/schemas/tool_schemas.py` | `api/services/tool_registry.py` |
| M3 风险分级 | - | `api/services/approval_service.py` |
| M4 硬拒绝模块 | `api/services/command_filter.py` | `api/services/approval_service.py` |
| M5 管道解析 | `api/services/command_parser.py` | `api/services/approval_service.py` |
| M6 回执持久化 | `api/services/storage/receipt_storage.py` | `api/services/tool_receipt_store.py` |
| 测试 | `tests/api/test_tool_registry.py`<br>`tests/api/test_risk_levels.py`<br>`tests/api/test_command_filter.py`<br>`tests/api/test_command_parser.py`<br>`tests/api/test_receipt_persistence.py`<br>`tests/integration/test_phase2_integration.py` | - |

## 6. 发布门禁（由 RTM 驱动）

1. P2-FR-01 ~ P2-FR-06 覆盖率 100%
2. 场景测试 P2-SC-01 ~ P2-SC-08 通过率 100%
3. 单元测试覆盖率 >= 80%
4. 阻断问题（安全、崩溃、数据错乱）为 0
5. 文档更新完成
