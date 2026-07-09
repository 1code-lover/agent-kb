# 开发故事沉淀 Skill 完整设计

## 1. 设计背景

当前仓库里已经有一版 `dev-story-capture`，它解决的是“实现完成后，立刻把真实改动沉淀成可复用面试材料”的问题。

你提供的 `record-work` 则强调另一类能力：

- 围绕 `git commit` / `git push` 做增量扫描
- 根据未记录 commit 反推需要补录的工作
- 在信息不足时，通过问答补齐原因、方案和取舍
- 维护“上次已记录到哪个 commit”的状态

这两版思路都对，但职责边界不同：

- `dev-story-capture` 更像“结果导向的沉淀 skill”
- `record-work` 更像“围绕 git 生命周期的补录工作流”

如果直接二选一，会有明显问题：

- 只保留 `dev-story-capture`：缺少增量补录能力，`commit` / `push` 前容易漏记
- 只保留 `record-work`：容易把输出降级成流水账式工作记录，弱化面试材料质量

所以最终设计不应该是二选一，而应该是“一个主 skill + 一套补录机制”。

## 2. 设计目标

完整方案需要同时满足以下目标：

1. 默认服务于面试复盘，而不是普通 changelog
2. 能在实现完成时立即沉淀，而不是只能等到 `push`
3. 能在 `commit` / `push` 前发现漏记内容并补录
4. 输出文档写在当前项目内，而不是全局目录
5. 对 Codex 友好，也能被其他会扫描仓库说明文件的 AI 理解
6. 首次创建故事目录时自动补 `README.md`
7. 记录必须基于真实改动、真实验证、真实权衡，不允许编造

## 3. 核心结论

最终采用“双层设计”：

### 3.1 第一层：主 Skill

保留并强化 `dev-story-capture`，把它定义成唯一的“开发故事沉淀主 skill”。

它的职责是：

- 判断本次工作属于 `bug`、`feature` 还是“值得复盘的重构”
- 从当前任务上下文和真实改动里提炼故事
- 生成结构化 Markdown 文档
- 写入项目内的故事目录
- 首次创建目录时补 `README.md`

### 3.2 第二层：补录机制

吸收 `record-work` 的优点，但不把它当成独立主输出系统，而是定义为 `dev-story-capture` 的“增量补录模式”。

它的职责是：

- 在 `git commit` / `git push` 前扫描“自上次沉淀后尚未记录的 commit”
- 判断这些 commit 是否已经被故事文档覆盖
- 如果没有覆盖，则触发补录
- 在信息不足时，向用户追问最少量的关键信息

也就是说：

- `dev-story-capture` 是主技能名
- “增量补录”只是它的一种执行模式，不再单独裂变成另一套记录体系

## 4. 当前版本存在的问题

### 4.1 现有 `dev-story-capture` 的问题

- 已经定义了“实现完成后记录”和“`commit` / `push` 前补漏”，但没有状态机制
- 无法系统判断“哪些 commit 已经被沉淀过”
- 更适合处理单次、上下文仍然完整的任务，不擅长补历史漏记

### 4.2 `record-work` 思路的问题

- 输出目标偏“工作记录”，不够聚焦面试表达
- 默认追加到单一汇总文档，容易越写越像流水账
- 状态目录放在 `.claude/work-records/`，工具绑定太重
- 触发点过度依赖 `git push hook`，不适合没有 hook 能力的代理环境

## 5. 合并后的统一设计

## 5.1 Skill 定位

技能名称仍建议保留：

`dev-story-capture`

原因：

- 语义更稳定，直接表达“沉淀开发故事”
- 不被某个工具品牌绑定
- 可以同时覆盖即时沉淀和增量补录

`record-work` 不再作为平级 skill，而作为设计参考，被吸收到本 skill 的“补录模式”和“状态管理”部分。

## 5.2 触发模型

统一定义 3 类触发：

### A. 即时沉淀触发

适用于上下文仍然新鲜、信息最完整的时候：

- 一个 bug 已修复完成
- 一个 feature 已实现完成
- 一次重构已经形成稳定结果，值得复盘
- 用户明确说“记录”“沉淀”“写成面试材料”

这是最高优先级触发。

### B. 提交前补录触发

适用于准备 `git commit` 时：

- 若本次工作尚未沉淀，先调用 skill
- 若已沉淀，但新增了关键实现、测试结果或方案权衡，则更新已有文档

### C. 推送前兜底触发

适用于准备 `git push` 时：

- 扫描上次沉淀后新增的 commit
- 如果发现这些 commit 对应的关键变更尚未进入故事文档，则触发补录

结论：

- `push` 不是主触发点，而是最终兜底点
- 最佳时机仍然是“实现完成后立即沉淀”

## 5.3 执行模式

统一定义两种执行模式：

### 模式一：上下文直写模式

适用于当前回合刚完成工作时。

输入来源：

- 用户需求
- 当前任务里的改动文件
- 刚跑过的测试 / 验证命令
- 任务中真实出现过的方案权衡

行为：

- 不依赖 git 增量扫描
- 直接生成故事文档

这是默认模式。

### 模式二：git 补录模式

适用于 `commit` / `push` 前发现可能漏记时。

输入来源：

- 上次沉淀后新增的 commit 列表
- commit message
- commit 涉及文件
- 必要时的用户补充问答

行为：

- 先扫描
- 再判断是否需要补录
- 需要时生成新故事或补充已有故事

这是兜底模式。

### 模式二补充：允许询问后跳过

`git` 补录模式不是强制生成模式。

在识别到自上次已生成锚点之后存在新增 commit 时，先向用户确认是否现在生成。

允许的行为：

1. 同意生成
2. 暂时跳过

如果用户选择跳过：

- 本次不生成故事文档
- 只记录“已经询问到哪个 head”
- 不能把“已生成锚点”推进到当前 head

如果用户之后又同意生成：

- 仍然应从上一次“真正已生成”的锚点之后开始统计
- 把中间曾经跳过的 commit 一并纳入当前总结窗口
- 再尝试将这一整段提交归并成一个功能或任务

## 5.4 证据优先级

统一约束证据来源优先级：

1. 当前任务里的真实上下文
2. 当前工作区改动和测试结果
3. git commit 历史
4. 用户补充问答
5. 明确标注为“推断”的最小补充说明

原则：

- 能从真实任务里拿到的信息，不要退化成问答
- 只有当前证据不足时，才进入问答补齐
- 任何未被真实改动支持的技术取舍，都不能伪造

## 5.5 文档输出模型

合并后采用“两类输出，主次分明”：

### 主输出：故事文档

这是面试复盘真正要用的文档，必须保留为独立文件。

默认输出目录优先级：

1. `.interview-kit/dev-stories/`
2. `docs/interview/dev-stories/`
3. 用户明确指定路径

输出规则：

- 一条完整故事对应一个 Markdown 文件
- 文件名按日期 + 类型 + 主题生成
- 首次创建目录时，同时创建 `README.md`

示例：

- `2026-07-01-bug-fix-cos-timeout-handling.md`
- `2026-07-01-feature-add-dev-story-capture-mode.md`

### 辅助输出：状态文件

吸收 `record-work` 的增量追踪思路，但不再使用 `.claude/work-records/`。

建议改成项目内、工具无关的状态文件，例如：

- `.interview-kit/dev-stories/.capture-state.json`

或在 fallback 目录下：

- `docs/interview/dev-stories/.capture-state.json`

状态文件只负责记录：

- 上一次真正完成故事沉淀的提交边界
- 上一次已经询问过但允许用户跳过的提交边界
- 上一次询问的决策结果
- 最近一次更新的故事文件
- 最近一次扫描时间

它不承担面试表达内容，只承担“增量去重”和“补录追踪”。

## 5.6 不再推荐的输出形式

以下形式不作为主设计：

- 单一 `工作记录.md` 持续追加
- 强绑定 `.claude/work-records/`
- 只记录 commit message，不生成结构化故事文件

原因很直接：

- 面试时不好复用
- 容易堆成流水账
- 迁移到其他 AI 工具时兼容性差

## 5.7 故事类型体系

统一支持 3 类故事：

### bug

关注：

- 现象
- 根因
- 解决方案
- 为什么这样选
- 如何验证

### feature

关注：

- 需求背景
- 目标能力
- 设计实现方案
- 为什么选这个方案
- 备选方案和不选原因
- 如何验证

### refactor

关注：

- 为什么需要重构
- 重构前的问题
- 重构策略
- 风险控制
- 结果收益
- 是否有行为变化

注意：

- `refactor` 应单独成为正式类型，而不是简单塞到“其他”
- 这更符合你前面说的“值得复盘的重构也要记录”

## 5.8 用户问答策略

从 `record-work` 吸收一个关键优点：在信息不足时主动追问，但要收敛。

建议问答规则：

### 对 bug

最多追问 3 个核心问题：

1. 问题根因是什么
2. 最终解决方案是什么
3. 为什么选这个方案

### 对 feature

最多追问 4 个核心问题：

1. 需求核心是什么
2. 设计 / 实现方案是什么
3. 为什么选当前方案
4. 是否有备选方案，为什么不选

### 对 refactor

最多追问 3 个核心问题：

1. 为什么要重构
2. 主要怎么改
3. 收益和风险控制是什么

原则：

- 能不问就不问
- 一旦进入问答，只问结论性问题，不问已经能从代码看出来的问题

## 5.9 commit 聚合策略

这是 `record-work` 的强项，应该保留。

对于补录模式，建议采用以下聚合规则：

1. 先读取上次沉淀后的 commit 列表
2. 按主题而不是只按 commit type 聚合
3. 如果多个 commit 明显属于同一任务，合并成一个故事
4. 如果多个 commit 虽同为 `fix:` 但实际是不同问题，拆成多条故事

判断依据优先级：

1. 改动文件是否高度重合
2. commit subject 是否围绕同一目标
3. 当前任务上下文是否能证明它们是同一工作
4. 如果仍不确定，再向用户确认

结论：

- 不以“一个 commit 一条记录”为默认规则
- 以“一个可讲清楚的完整工作 = 一条故事”为默认规则
- 如果用户此前对某一段提交窗口选择了“跳过”，后续再次生成时应继续从 `last_generated_hash` 开始累计，而不是从跳过时的 head 重新开始

## 5.10 与 git 生命周期的关系

这里必须明确边界：

### Skill 层

`dev-story-capture` 本质是 AI 工作流规范，不是 git hook 程序。

它负责告诉代理：

- 什么时候该沉淀
- 怎么收集证据
- 输出到哪里
- 如何避免重复和编造

### 自动化层

如果某个平台支持 hook 或 automation，可以额外接入：

- `git commit` 前检查是否已沉淀
- `git push` 前扫描是否有未补录变更

但这属于“调度方式”，不是 skill 本体。

结论：

- skill 设计里要兼容 hook
- 但不能把 hook 当作 skill 唯一前提

## 5.11 跨工具兼容设计

完整方案保留两层载体：

### Codex 专用层

路径：

- `.codex/skills/dev-story-capture/`
- `AGENTS.md`
- 全局 `~/.codex/skills/dev-story-capture/`

用途：

- 给 Codex 直接触发和执行

### 平台无关层

路径：

- `docs/ai-skills/dev-story-capture.md`

用途：

- 给 Claude、Cursor、Gemini 等会扫描仓库说明文件的 AI 使用

平台无关层应明确写清：

- 触发时机
- 主输出目录
- 状态文件规则
- 首次创建 README 的规则
- bug / feature / refactor 的写法

## 6. 推荐的最终目录结构

### 6.1 Skill 目录

```text
.codex/skills/dev-story-capture/
├── SKILL.md
├── agents/openai.yaml
└── references/
    ├── bug-template.md
    ├── feature-template.md
    ├── refactor-template.md
    └── dev-stories-readme-template.md
```

### 6.2 项目输出目录

```text
.interview-kit/dev-stories/
├── README.md
├── .capture-state.json
├── 2026-07-01-bug-fix-xxx.md
├── 2026-07-01-feature-add-xxx.md
└── 2026-07-01-refactor-xxx.md
```

fallback：

```text
docs/interview/dev-stories/
├── README.md
├── .capture-state.json
└── ...
```

## 7. 推荐的 SKILL 行为定义

最终建议把 `SKILL.md` 的行为定义为：

1. 先判断当前是“直写模式”还是“git 补录模式”
2. 优先使用当前任务上下文，不足时再扫描 commit
3. 需要时从状态文件读取“上次已沉淀位置”
4. 判断应输出新故事、更新已有故事，还是无需处理
5. 写入故事文档
6. 首次创建目录时写入 `README.md`
7. 成功沉淀后更新 `.capture-state.json`

## 8. 推荐的状态文件结构

建议使用简单 JSON：

```json
{
  "last_generated_hash": "abc123def456",
  "last_generated_push_hash": "abc123def456",
  "last_prompted_hash": "def456abc123",
  "last_prompt_decision": "generated",
  "last_capture_time": "2026-07-01T10:15:30+08:00",
  "last_story_file": "2026-07-01-feature-add-dev-story-capture-mode.md"
}
```

这个结构足够支撑：

- `commit` / `push` 前增量扫描
- 区分“已经生成”和“只是询问过但跳过”
- 避免对同一个 head 无限重复询问
- 在用户后续同意时，把从上一次已生成锚点到当前的整段提交重新纳入总结窗口
- 快速定位最近一次故事文件

不建议一开始做得太复杂。

### 8.1 字段语义

- `last_generated_hash`：上一次真正已沉淀进故事文档的提交边界；只有成功生成文档后才能更新
- `last_generated_push_hash`：如果这次沉淀是围绕一次 `git push` 完成，可以同步记录对应 push 时的 head；没有也可以为空
- `last_prompted_hash`：上一次已经询问过用户是否生成时的 head
- `last_prompt_decision`：最近一次询问结果，建议枚举为 `generated` / `skipped`
- `last_story_file`：最近一次写入或更新的故事文档文件名
- `last_capture_time`：最近一次生成或确认跳过时的时间

### 8.2 推进规则

只允许以下规则：

1. 用户同意生成，且故事文档成功写入后，更新 `last_generated_hash`，同时可更新 `last_prompted_hash`
2. 用户选择跳过时，只更新 `last_prompted_hash` 和 `last_prompt_decision=skipped`
3. 跳过时绝不能更新 `last_generated_hash`
4. 下一次如果新增提交仍落在同一任务窗口内，且用户同意生成，应从 `last_generated_hash` 之后的全部提交重新汇总，而不是只汇总“跳过后的新增提交”

## 9. 最终方案摘要

一句话总结：

`dev-story-capture` 负责把“真实工作”沉淀成“可讲的开发故事”，`record-work` 提供的 commit 扫描、状态追踪、补录问答能力，则被吸收到这个主 skill 的增量补录模式中。

所以最终不再是两套并行系统，而是：

- 一个主 skill：`dev-story-capture`
- 两种模式：直写模式 + git 补录模式
- 两类产物：故事文档 + 状态文件
- 两层载体：Codex skill + 平台无关说明

## 10. 下一步建议

如果按这份设计继续落地，推荐顺序是：

1. 重写 `.codex/skills/dev-story-capture/SKILL.md`
2. 新增 `references/refactor-template.md`
3. 更新 `docs/ai-skills/dev-story-capture.md`
4. 明确 `.capture-state.json` 的读写规则
5. 最后再决定是否接 git hook / automation

这样能先把 skill 语义做对，再决定要不要做自动化触发。
