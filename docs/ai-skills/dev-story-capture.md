# 开发故事沉淀指南

## 说明

这是一份平台无关但不降级的镜像规范，适用于会扫描仓库说明文件的各类 AI 助手，例如 Codex、Claude、Gemini、Cursor 或其他类似工具。

完整规则以 `.codex/skills/dev-story-capture/SKILL.md` 作为唯一完整规范源；本文必须与其保持同等语义，不得退化成口号式摘要。

## 目标

把真实工程工作沉淀成可复用的面试材料，而不是 changelog。
默认规则不是“一次 commit 生成一篇文档”，而是“一个能讲清楚的完整功能、任务或问题窗口生成一篇文档”。

## 输出位置

默认按下面顺序选择输出目录：

1. 用户明确指定的路径
2. `.interview-kit/dev-stories/`
3. `docs/interview/dev-stories/`

显式输入永远覆盖默认目录，不得被回退路径覆盖。

如果目标目录不存在，先创建目录。如果这是第一次创建该目录，同时创建：

- `README.md`
- `.capture-state.json`

## 推荐状态文件

在故事目录下维护一个隐藏状态文件，例如：

- `.interview-kit/dev-stories/.capture-state.json`
- `docs/interview/dev-stories/.capture-state.json`

建议至少包含：

```json
{
  "last_generated_hash": "abc123def456",
  "last_generated_push_hash": "abc123def456",
  "last_prompted_hash": "def456abc123",
  "last_prompt_decision": "generated",
  "last_capture_time": "2026-07-06T10:15:30+08:00",
  "last_story_file": "2026-07-06-feature-add-dev-story-capture.md"
}
```

字段语义：

- `last_generated_hash`：上一次真正写入文档后的提交边界
- `last_generated_push_hash`：如果该次沉淀围绕一次 `git push` 完成，可额外记录当时 push 的 head
- `last_prompted_hash`：上一次已经询问过用户时的 head
- `last_prompt_decision`：最近一次询问结果，必须写成 `generated` 或 `skipped`
- `last_capture_time`：最近一次生成或跳过确认时间
- `last_story_file`：最近一次写入的故事文件

## 首次运行与修复策略

- 目标目录不存在：创建目录、`README.md`、`.capture-state.json`
- 状态文件不存在：视为首次运行，`last_generated_hash=null`
- 状态文件缺字段：按最小安全默认值补齐，不得静默跳过关键字段
- 状态文件损坏：先备份损坏文件，再重建最小状态文件
- `last_generated_hash` 在当前仓库不可解析：标记为失效锚点，提示用户确认是否以当前 `HEAD` 作为新边界，或从可识别最早提交重新聚合
- 空仓库或无提交：允许只基于当前未提交改动走直写模式

首次运行时，`last_generated_hash=null` 不是 `null..HEAD` 的隐式提交范围，而是一个明确状态：

- 如果当前存在 working tree / index 未提交改动，先只处理这批未提交改动，不默认回扫全部历史提交
- 如果当前没有未提交改动，不得直接把 `null` 当作“扫描全部历史”的边界
- 此时应先询问用户：是以当前 `HEAD` 作为首次生成后的新边界、从现在开始记；还是按一个明确、受控的历史窗口做首次补录
- 只有用户明确同意历史补录范围后，才能扫描对应提交窗口；否则默认不回扫整个仓库历史

## 两种模式

### 直写模式

适用于当前回合刚完成工作、上下文仍然完整时。

优先使用：

- 用户原始需求
- 当前改动文件
- 刚执行过的测试或验证命令
- 当前任务里真实讨论过的方案权衡

### git 补录模式

适用于 `git commit` 或 `git push` 前的补漏。

执行顺序：

1. 定位输出目录
2. 读取并修复状态文件
3. 判断当前是否有未提交改动
4. 若场景是 `git commit` 前且有未提交改动，优先采集本次未提交改动
5. 只有当未提交改动不足以构成完整故事，或需要补录历史遗漏时，才回退到 `last_generated_hash..HEAD` 的提交窗口做聚合
6. 若当前无未提交改动，再直接按提交窗口补录
7. 合并“未提交改动 + 历史遗漏提交”是否属于同一任务窗口
8. 生成后写入完整成功态；跳过则只写跳过态

硬规则：

- `git commit` 前必须先检查 working tree / index；提交窗口补录是第二优先级，不得替代本次未提交改动的采集
- 当 `last_generated_hash=null` 时，不得直接套用 `last_generated_hash..HEAD`；必须先按“首次运行与修复策略”确定边界语义

## 询问与跳过规则

在 `git commit` 或 `git push` 前，如果发现需要补录，应先询问用户是否现在生成。

允许两种结果：

1. 同意生成
2. 暂时跳过

如果用户选择跳过：

- 本次不生成文档
- 只更新 `last_prompted_hash`
- 设置 `last_prompt_decision=skipped`
- 绝不能更新 `last_generated_hash`

如果用户后续同意生成：

- 应把从 `last_generated_hash` 之后到当前 `HEAD` 的全部相关提交纳入总结范围
- 中间曾经跳过过的提交不能丢
- 先尝试把这整段提交理解为一个功能、任务或问题窗口，再决定是否拆分成多篇

## 成功生成后的状态推进

成功写入故事文档后，状态文件必须一次性写入完整成功态，至少同步更新：

- `last_generated_hash`
- `last_prompted_hash`
- `last_prompt_decision=generated`
- `last_capture_time`
- `last_story_file`

`last_generated_push_hash` 仅在 `git push` 场景更新。

不能只推进 `last_generated_hash` 而保留旧的 `skipped` 状态。

## 故事类型判定

- 当主要价值是修复错误行为、回归问题、异常处理、稳定性、兼容性或安全问题时，归为 `bug`
- 当主要价值是新增能力、流程、接口、界面、交互或明显增强时，归为 `feature`
- 当主要价值是重构结构、降低复杂度、改善可维护性、拆分职责或优化性能路径时，归为 `refactor`
- 如果两者都有，选择主要产出作为文档类型，并在正文里补充次要产出

## 证据规则

- 每个故事都必须建立在真实任务之上，不要写成泛泛的“最佳实践总结”
- 优先写真实文件路径、模块名、命令名、错误表现、验证结果
- 能从真实任务上下文里拿到的信息，不要退化成问答
- 不要编造不存在的方案取舍
- 如果某项权衡只能合理推断，必须明确标注“推断”

## 模板选择规则

- `bug` 类型：使用 `docs/ai-skills/templates/bug-template.md`
- `feature` 类型：使用 `docs/ai-skills/templates/feature-template.md`
- `refactor` 类型：使用 `docs/ai-skills/templates/refactor-template.md`
- 首次创建目录时：使用 `docs/ai-skills/templates/dev-stories-readme-template.md`

## 追问策略

只在证据不足时追问，而且只问结论性问题。

- `bug`：根因、解决方案、为什么选这个方案
- `feature`：需求核心、实现方案、为什么选、为什么不选其他方案
- `refactor`：重构背景、主要改动、收益和风险控制

## 最终检查

完成前确认：

1. 类型判断正确
2. 文档写明了真实改动文件或模块
3. 验证状态明确
4. 首次创建目录时已生成 `README.md` 和 `.capture-state.json`
5. 如果是补录模式，状态文件已写入完整成功态或合法跳过态
6. 没有编造不存在的权衡
7. 面试版本足够短，可以自然说出口
