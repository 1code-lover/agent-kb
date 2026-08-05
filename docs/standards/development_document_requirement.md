# ThinkRAG 开发文档管理规范（V1）

## 1. 目的
本规范用于统一功能开发、大 Bug 修复和系统优化过程中的文档管理方式，确保需求、设计、计划和执行记录集中存放、命名一致、便于追溯。

## 2. 适用范围
- 新功能开发
- 大 Bug 修复
- 系统级优化或重构
- 影响多个模块、接口、数据结构或用户流程的变更

以下场景可不单独建立开发专题目录：
- 文案、注释、格式等小改动
- 单文件小修复且不改变业务行为
- 临时排查记录或一次性说明

## 3. 目录要求
所有开发专题文档必须放在 `docs/development/` 下，并按专题单独建立文件夹。

目录格式：

```text
docs/development/YYYY-MM-DD_topic/
```

命名要求：
- `YYYY-MM-DD` 为专题启动日期。
- `topic` 使用小写英文、数字和下划线，表达功能、Bug 或优化主题。
- 一个专题只对应一个文件夹，不允许将多个无关事项混放。

示例：

```text
docs/development/2026-07-07_agent_execution_control/
docs/development/2026-07-07_kb_import_bugfix/
docs/development/2026-07-07_runtime_performance_optimization/
```

## 4. 文件要求
专题文件夹内存放该专题的开发文档，文件名必须使用统一格式：

```text
YYYY-MM-DD_topic_type.md
```

常用文档类型：
- `prd`：需求文档，说明背景、目标、范围、用户场景和验收标准。
- `design`：设计文档，说明架构、模块职责、接口、数据结构和关键流程。
- `plan`：开发计划，说明任务拆分、实施顺序、测试方式和风险。
- `test`：测试方案或测试记录，说明测试用例、执行结果和问题结论。
- `summary`：开发总结，说明最终变更、遗留问题和后续建议。

推荐结构：

```text
docs/development/2026-07-07_agent_execution_control/
├── 2026-07-07_agent_execution_control_prd.md
├── 2026-07-07_agent_execution_control_design.md
├── 2026-07-07_agent_execution_control_plan.md
├── 2026-07-07_agent_execution_control_test.md
└── 2026-07-07_agent_execution_control_summary.md
```

## 5. 强制要求
1. 涉及新功能、大 Bug 修复或系统级优化时，编码前必须先建立对应的 `docs/development/YYYY-MM-DD_topic/` 专题目录。
2. 编码前至少需要具备 `prd`、`design`、`plan` 三类文档，除非用户明确说明该任务不需要完整文档流程。
3. 文档内容必须和实际开发范围一致，不允许只创建空文件或占位内容。
4. 专题进行中如果范围变化，必须同步更新对应专题文档。
5. 测试完成后，应在专题目录中补充 `test` 或 `summary` 文档，记录验证结果和遗留风险。

## 6. 大模型执行要求
当大模型或 Agent 接到功能开发、大 Bug 修复或系统优化任务时，应先判断是否触发本规范：

1. 若触发，应先创建或确认专题目录。
2. 若用户已有指定目录，应沿用用户指定目录。
3. 若缺少需求、设计或计划信息，应先向用户确认，或先起草文档草案供用户审核。
4. 未经用户确认，不应跳过文档阶段直接进行大范围编码。
5. 小修小补不强制建立专题目录，但应在最终回复中说明未建立的原因。

## 7. 禁止事项
- 禁止将新专题文档继续散落在 `docs/` 根目录。
- 禁止同一专题在 `specs/`、`plans/`、`implementation/` 中分散创建多份互相独立的文档。
- 禁止使用无意义主题名，例如 `fix`、`update`、`new_feature`。
- 禁止文档文件名缺少日期、主题或类型。
- 禁止文档内容与实际实现不一致。

## 8. 评审检查项
1. 是否已在 `docs/development/` 下建立独立专题目录。
2. 专题目录命名是否符合 `YYYY-MM-DD_topic` 格式。
3. 文件命名是否符合 `YYYY-MM-DD_topic_type.md` 格式。
4. 是否包含必要的需求、设计和计划文档。
5. 文档是否覆盖范围、验收标准、实施步骤和测试方式。
6. 开发完成后是否补充测试结果或总结。

## 9. 与既有目录的关系
- `docs/development/`：新开发专题的统一入口，承载单个功能、Bug 修复或优化的全过程文档。
- `docs/standards/`：存放项目级规范，本文件属于项目级规范。
- `docs/prd/`、`docs/specs/`、`docs/plans/`、`docs/implementation/`：保留历史文档和已有主线文档；新专题优先使用 `docs/development/` 聚合管理。
- `docs/operations/`：仍用于运行手册、回归清单、发布和运维资料。
- `docs/architecture/`：仍用于长期有效的系统架构文档；若专题设计沉淀为长期架构，可在评审后同步到该目录。

## 10. 生效规则
本规范自加入仓库后生效。后续所有由人工或大模型发起的新功能开发、大 Bug 修复和系统级优化，均应优先遵守本规范。历史文档不强制迁移，按“新专题使用新结构，历史文档逐步归档”的方式增量落地。
