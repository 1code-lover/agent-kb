---
name: dev-story-capture
description: 将已完成的 bug 修复、功能开发、重要重构沉淀成面试可复用的开发故事。适用于 Codex 已完成实现、需要基于真实改动和验证结果立即写故事文档，或在 git commit、git push 前按增量提交窗口补录遗漏开发故事的场景。
---

# 开发故事沉淀

## 目标

把真实工程工作沉淀成可复用的面试材料，而不是 changelog。
默认规则不是“一次 commit 生成一篇文档”，而是“一个能讲清楚的完整功能、任务或问题窗口生成一篇文档”。

## 输出位置

默认按下面顺序选择输出目录：

1. 用户明确指定的路径
2. `.interview-kit/dev-stories/`
3. `docs/interview/dev-stories/`

显式输入永远覆盖默认目录，不得被回退路径覆盖。

如果目标目录不存在，先创建目录。
如果这是第一次创建该目录，同时创建：

- `README.md`
- `.capture-state.json`

其中 `README.md` 说明：

- 目录用途
- `bug` / `feature` / `refactor` 文档如何组织
- 文件命名规则
- 常见触发场景

`.capture-state.json` 至少包含：

- `last_generated_hash`
- `last_generated_push_hash`
- `last_prompted_hash`
- `last_prompt_decision`
- `last_capture_time`
- `last_story_file`

说明文档内容参考 [dev-stories-readme-template.md](references/dev-stories-readme-template.md)。

## 首次运行与修复策略

- 目标目录不存在：创建目录、`README.md`、`.capture-state.json`
- 状态文件不存在：视为首次运行，`last_generated_hash=null`
- `last_generated_hash` 在当前仓库不可解析：标记为失效锚点，提示用户确认是否以当前 `HEAD` 作为新边界，或从可识别最早提交重新聚合
- 状态文件缺字段：按最小安全默认值补齐，不得静默跳过关键字段
- 状态文件损坏：先备份损坏文件，再重建最小状态文件
- 空仓库或无提交：允许只基于当前未提交改动走直写模式

## 两种模式

### 模式一：直写模式

适用于当前回合刚完成工作、上下文仍然完整时。

优先使用：

- 用户原始需求
- 当前任务真实改动文件
- 刚执行过的测试或验证命令
- 当前任务里真实出现过的方案权衡

这是默认模式，也是首选模式。

### 模式二：git 补录模式

适用于准备执行 `git commit` 或 `git push` 时，怀疑本次工作尚未完整沉淀。

执行顺序：

1. 先定位输出目录
2. 读取并修复状态文件
3. 判断当前是否存在 working tree 或 index 的未提交改动
4. 若场景是 `git commit` 前且存在未提交改动，先基于“本轮未提交改动 + 当前任务上下文”判断是否需要沉淀
5. 只有当未提交改动不足以构成完整故事，或需要补录历史遗漏时，才回退到 `last_generated_hash..HEAD` 的提交窗口做聚合
6. 若当前无未提交改动，再直接按提交窗口补录
7. 合并“未提交改动 + 历史遗漏提交”是否属于同一任务窗口
8. 根据用户选择生成或跳过，写入对应状态

硬规则：

- `git commit` 前必须先检查 working tree / index；提交窗口补录是第二优先级，不得替代本次未提交改动的采集。

## 判断故事类型

- 当主要价值是修复错误行为、回归问题、异常处理、稳定性、兼容性或安全问题时，归为 `bug`。
- 当主要价值是新增能力、流程、界面、集成、交互或明显增强时，归为 `feature`。
- 当主要价值是重构结构、降低复杂度、改善可维护性、拆分职责或优化性能路径时，归为 `refactor`。
- 如果两者都有，选择主要产出作为故事类型，并在正文里补充次要产出。

## 证据规则

- 每个故事都必须建立在真实任务之上，不要写成泛泛的“最佳实践总结”。
- 优先写真实文件路径、模块名、命令名、错误现象、验证结果，不要只写抽象概括。
- 不要编造权衡。如果备选方案没有被明确讨论，只能补充最邻近、最明显的方案，并标注“推断”。
- 能从当前任务上下文里直接获得的信息，不要退化成问答。
- 这份记录是给面试复盘用的，不是 changelog。

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

## 状态推进规则

只允许以下规则：

1. 用户同意生成，且故事文档成功写入后，状态文件必须一次性写入完整成功态
2. 完整成功态至少同步更新：`last_generated_hash`、`last_prompted_hash`、`last_prompt_decision=generated`、`last_capture_time`、`last_story_file`
3. `last_generated_push_hash` 仅在 `git push` 场景更新
4. 用户选择跳过时，只更新 `last_prompted_hash`、`last_prompt_decision=skipped`、`last_capture_time`
5. 跳过时绝不能推进 `last_generated_hash`
6. 不能只推进 `last_generated_hash` 而保留旧的 `skipped` 状态
7. 用户后续一旦同意生成，应从 `last_generated_hash` 之后到当前 `HEAD` 的全部相关提交重新汇总，不能丢掉中间曾经跳过的提交

## 写作规则

- 默认使用中文，除非用户明确要求英文。
- 正文保持具体、简洁，不要空泛铺陈。
- 结尾必须有一段第一人称、能直接说出口的面试版本。
- 不要把大段 diff 或日志原样贴进文档。
- 验证情况必须如实写；如果没跑测试，就明确写未执行。
- git 补录模式下，优先按“一个完整工作”聚合，而不是“一条 commit 一篇文档”。

## 模板选择规则

- 写 `bug` 时，读取 [bug-template.md](references/bug-template.md)。
- 写 `feature` 时，读取 [feature-template.md](references/feature-template.md)。
- 写 `refactor` 时，读取 [refactor-template.md](references/refactor-template.md)。
- 首次创建故事目录时，读取 [dev-stories-readme-template.md](references/dev-stories-readme-template.md) 生成目录说明文档。

## 触发时机

当实现已经完成，或在当前回合里已经可以认定为“完成”时，使用这个 skill。典型触发场景包括：

- 一个 bug 被修好了
- 一个 feature 被做完了
- 一次重构已经足够影响行为或架构，值得在面试里讲
- 准备执行一次 `git commit`
- 一次 `git push` 之前做最终补漏
- 用户明确说“记录”“沉淀”“总结”“写成面试材料”之类的话

触发优先级建议如下：

1. 实现完成后立即触发
2. `git commit` 前再次触发，确保本次开发闭环有记录
3. `git push` 前做最后兜底

如果工作还在探索阶段、还没有真正落地实现，就不要写最终故事，等有真实结果后再写。

## 追问策略

仅在证据不足时追问，而且只问结论性问题。

### `bug`

最多追问：

1. 根因是什么
2. 最终怎么修
3. 为什么选这个修法

### `feature`

最多追问：

1. 需求核心是什么
2. 设计 / 实现方案是什么
3. 为什么选当前方案
4. 有没有备选方案，为什么不选

### `refactor`

最多追问：

1. 为什么要重构
2. 主要改了什么
3. 收益和风险控制是什么

## git 聚合规则

- 优先把多个明显属于同一工作的 commit 合并成一条故事。
- 如果 commit message 同属 `fix:`，但目标问题不同，不要强行合并。
- 判断是否属于同一故事时，优先看改动文件重合度、commit subject 目标是否一致、以及当前任务上下文。
- 如果用户此前对某一段提交窗口选择了“跳过”，后续再次生成时应继续从 `last_generated_hash` 开始累计，而不是从跳过时的 head 重新开始。
- 如果无法可靠判断，再向用户确认是否合并。

## 最终检查

完成前检查：

1. 故事类型是否和主要产出一致。
2. 文档是否写明了真实改动文件或模块。
3. 验证状态是否写清楚了。
4. 如果目录是首次创建，是否已经生成 `README.md` 和 `.capture-state.json`。
5. 如果是补录模式，状态文件是否按规则推进。
6. 面试版本是否足够短、足够自然，可以直接说。
