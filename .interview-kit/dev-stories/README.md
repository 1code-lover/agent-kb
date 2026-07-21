# 开发故事目录说明

## 目录用途

这个目录用于沉淀每次 bug 修复、功能开发、重要重构后的开发故事文档，供后续面试、自我复盘、项目表达使用。

## 文档分类

- `bug`：记录问题现象、根因、解决方案、验证结果和面试表达
- `feature`：记录需求背景、设计实现、方案权衡、验证结果和面试表达
- `refactor`：记录重构背景、重构方案、风险控制、验证结果和面试表达

## 文件命名规则

- `YYYY-MM-DD-bug-xxx.md`
- `YYYY-MM-DD-feature-xxx.md`
- `YYYY-MM-DD-refactor-xxx.md`

## 常见触发场景

- 完成一个 bugfix 后
- 完成一个 feature 后
- 完成一次值得复盘的重构后
- `git commit` 前
- `git push` 前补漏

## 状态文件

目录下可能会有一个隐藏文件 `.capture-state.json`，用于记录：

- `last_generated_hash`：上一次真正写入文档后的提交边界
- `last_generated_push_hash`：上一次围绕 push 完成沉淀时的 head
- `last_prompted_hash`：上一次已经询问过用户时的 head
- `last_prompt_decision`：最近一次询问结果，建议为 `generated` / `skipped`
- `last_capture_time`：最近一次生成或跳过确认时间
- `last_story_file`：最近一次更新的故事文档

跳过时只能更新 `last_prompted_hash`，不能推进 `last_generated_hash`。
后续如果用户同意生成，应从 `last_generated_hash` 之后到当前 `HEAD` 的整段提交重新汇总。

## 写作要求

- 基于真实改动、真实验证、真实权衡
- 默认使用中文
- 面试表达版本使用第一人称
- 不要粘贴大段 diff 或日志
- 默认按“一个完整任务窗口”组织故事，而不是“一条 commit 一篇”
