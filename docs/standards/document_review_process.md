# ThinkRAG 文档评审流程规范（V1）

## 1. 目的
本规范定义开发专题文档的评审流程，确保每份文档（PRD、design、plan）在进入下一阶段前经过独立评审，评审意见集中存放、可追溯、可覆盖更新。

## 2. 适用范围
- `docs/development/YYYY-MM-DD_topic/` 下的所有开发专题文档
- 每个专题内的 prd、design、plan 文档必须逐份评审
- test 和 summary 文档是否需要评审由专题负责人决定

## 3. 评审角色

| 角色 | 职责 | 约束 |
|------|------|------|
| Writer | 编写文档内容 | 不得评审自己写的文档 |
| Reviewer | 独立评审文档 | 必须是独立 Agent / 新会话 / 不同人员 |

同一份文档的 writer 和 reviewer 不能是同一个 Agent 实例或同一次会话。

## 4. 评审状态

```
draft → in_review → changes_requested → in_review → ... → approved
```

| 状态 | 说明 |
|------|------|
| `draft` | 文档正在编写，尚未提交评审 |
| `in_review` | 文档已提交，等待 reviewer 评审 |
| `changes_requested` | Reviewer 要求修改，Writer 需修订后重新提交 |
| `approved` | 评审通过，可进入下一阶段 |

## 5. 评审顺序

每个专题按以下顺序逐文档评审，前一文档 approved 后才能开始写下一文档：

1. **prd**（需求文档）→ 评审通过
2. **design**（设计文档）→ 评审通过
3. **plan**（开发计划）→ 评审通过
4. 开始编码

## 6. 评审文件

每个专题目录下维护一个 `review.md`，存放当前最新评审意见。

### 文件位置

```text
docs/development/YYYY-MM-DD_topic/review.md
```

### 覆盖规则

- 每轮评审直接覆盖 `review.md` 的全部内容
- `review.md` 始终只保留最新一轮评审的完整结论
- 评审前 Reviewer 应先读取 `review.md` 了解上一轮意见（如有），在新一轮评审中确认历史问题是否已解决
- 如需保留评审历史，后续可引入 `review_history.md`，不作为首版强制要求

### 模板

```markdown
# 评审记录

## 基本信息
- **专题名称**：{topic_name}
- **评审对象**：{prd | design | plan}
- **当前阶段**：{draft | in_review | changes_requested | approved}
- **评审人**：{reviewer}
- **评审日期**：{YYYY-MM-DD}

## 评审结论
- **结论**：{approved | conditional | rejected}
- **是否允许进入下一阶段**：{是 | 否}

## 必改项
1. {问题描述} — 涉及章节：{章节名}
2. ...

## 建议项
1. {建议描述} — 涉及章节：{章节名}
2. ...

## 下一步动作
- {Writer 下一步需要做什么}
- {Reviewer 下一步需要做什么（如有）}
```

## 7. 评审结论说明

| 结论 | 含义 | 后续动作 |
|------|------|----------|
| `approved` | 文档完全通过 | 进入下一文档或编码阶段 |
| `conditional` | 有条件通过，仅有建议项无必改项 | Writer 处理建议项后可直接进入下一阶段 |
| `rejected` | 存在必改项，必须修订 | Writer 修订后重新提交评审，状态回退到 `in_review` |

## 8. 评审通过标准

### PRD 评审要点
- 背景、目标、范围是否清晰
- 用户场景和验收标准是否明确
- 功能边界是否合理，无过度设计

### Design 评审要点
- 架构和模块职责是否清晰
- 接口和数据流是否合理
- 是否与现有系统兼容
- 技术选型是否有依据

### Plan 评审要点
- 任务拆分粒度是否合理
- 依赖关系是否清晰
- 实施顺序是否可行
- 测试策略是否覆盖关键路径

## 9. 大模型执行约束

当大模型或 Agent 参与文档编写和评审时，必须遵守：

1. **Writer 和 Reviewer 必须分离**：同一 Agent 实例不得既写文档又审同一份文档。
2. **逐文档推进**：写完 prd 后必须先评审通过，再写 design；写完 design 后必须先评审通过，再写 plan。
3. **评审结果必须写入文件**：Reviewer 完成评审后，必须将结论写入专题目录的 `review.md`。
4. **读取上一轮评审**：Writer 修订文档前必须先读取 `review.md`，逐条处理必改项和建议项。
5. **覆盖式更新**：新一轮评审直接覆盖 `review.md`，不追加、不合并。
6. **禁止跳过评审**：未经评审通过的文档，不得作为后续文档或编码的依据。

## 10. 禁止事项

- 禁止 Writer 自我评审并标记为 approved
- 禁止跳过 prd 直接写 design，或跳过 design 直接写 plan
- 禁止将评审意见写在文档正文中替代 `review.md`
- 禁止在 `review.md` 中追加历史评审而不覆盖
- 禁止对同一份文档的必改项不做处理就进入下一阶段

## 11. 与既有规范的关系

- 本规范是 `docs/standards/development_document_requirement.md` 的补充，定义文档完成后的评审流程。
- 开发专题的目录和文件命名仍遵循 `docs/standards/development_document_requirement.md`。
- `AGENTS.md` 中的开发工作流应与本规范保持一致。

## 12. 生效规则

本规范自加入仓库后生效。所有 `docs/development/` 下的新开发专题必须遵循本评审流程。历史专题不强制回溯评审。