# development 开发专题文档目录

本目录用于集中存放每个功能开发、大 Bug 修复和系统级优化的全过程文档。

## 目录规则
每个开发专题必须单独建立文件夹：

```text
docs/development/YYYY-MM-DD_topic/
```

示例：

```text
docs/development/2026-07-07_agent_execution_control/
```

## 文件规则
专题目录内文档统一使用以下格式：

```text
YYYY-MM-DD_topic_type.md
```

常用类型：
- `prd`：需求文档
- `design`：设计文档
- `plan`：开发计划
- `test`：测试方案或测试记录
- `summary`：开发总结

推荐结构：

```text
docs/development/2026-07-07_agent_execution_control/
├── 2026-07-07_agent_execution_control_prd.md
├── 2026-07-07_agent_execution_control_design.md
├── 2026-07-07_agent_execution_control_plan.md
├── review.md          # 当前最新评审结论（覆盖式更新）
├── 2026-07-07_agent_execution_control_test.md
└── 2026-07-07_agent_execution_control_summary.md
```

## 评审规则

每个专题目录内必须维护 `review.md`，存放当前最新评审结论。

- **覆盖式更新**：新一轮评审直接覆盖 `review.md` 全部内容，不追加、不合并
- **逐文档评审**：按 prd → design → plan 顺序逐份评审，前一份 approved 后才能写下一份
- **Writer/Reviewer 分离**：同一 Agent 不得既写文档又审同一份文档
- 评审模板和完整流程见 `docs/standards/document_review_process.md`

完整规范见：`docs/standards/development_document_requirement.md`。
