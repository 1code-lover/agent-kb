# 20260820 RAG Interview Eval Test Report

> 说明：本文件已在 2026-08-21 依据当前仓库状态重写，用来替换原先含大量损坏内容的版本。若要看当前最新项目审计结论，请优先参考 `docs/20260821-project-audit-remediation/` 下的文档。

## 1. 这份报告回答什么

这份报告不是为了证明“所有东西都已经完工”，而是给面试或汇报场景准备一套**可解释、可落地、不过度包装**的测试口径。重点回答：

1. 项目到底测了哪些维度；
2. 为什么现在 layered suite 可以是 `150 / 150`，但工程仍不能说完全 finished；
3. grounding / evidence / preview / scope 这些指标应该怎么解释；
4. 面试时应该如何区分“能力完成度”和“工程完成度”。

## 2. 当前推荐统一口径

以 2026-08-21 最新 layered eval 产物为准，当前建议统一讲：

- Layered suite：`150 / 150`
- Smoke：`24 / 24`
- Main：`90 / 90`
- Hard：`36 / 36`
- 当前剩余重点：**工程治理与长期维护问题，而不是当前 semireal suite 的答题正确率**

这组数字适合面试表达，但必须配上一个前提：

> 当前 `1.0` 指的是这套 semireal layered suite 全绿，不代表项目在所有真实数据和所有工程维度上都没有问题。

## 3. 为什么现在会出现“全 1.0”

更合理的解释是：

1. **主能力闭环已经被打通**：scope、evidence、preview、cross-source fact assembly 这些核心路径都进入了当前评测；
2. **这轮修复是针对剩余硬问题做的**：targeted fact、preview excerpt hygiene、negative contract 和 forbidden-term 误判都在本轮被修掉；
3. **评测边界是明确的 semireal suite**：它足以说明当前主路径已经稳定，但不是对“所有未来场景”的无限外推。

所以在面试时，正确表达不是“我们完美了”，而是：

> 当前 suite 全绿说明主能力和评测闭环已成型；真正还在继续收口的是工程治理、文档统一、legacy 入口和代码可维护性。

## 4. 当前最重要的指标怎么讲

### 4.1 grounding

回答是不是建立在实际命中的知识片段上，而不是模型脑补。

### 4.2 evidence

回答里的关键结论能不能在返回的 source / excerpt 中找到支撑。

### 4.3 preview

用户点击来源时，是否能在前端预览中落到正确证据片段、页码或 OCR 位置。

### 4.4 scope

请求声明的知识库范围与系统实际生效范围是否一致，是否发生串库或越权。

## 5. 当前结果该怎么解读

### 5.1 能力层：可以明确说已经成型

当前可以比较有把握地讲：

- 多知识库 `single_kb` 约束已经打通；
- evidence / preview 返回链路已经打通；
- QueryRequest 请求级参数已经进入主链路；
- query / history 已经解耦；
- layered suite 当前全绿。

### 5.2 工程层：不能因为 1.0 就说没有问题

当前仍然成立的工程问题包括：

- legacy 入口 `app.py` / `frontend/` / `.streamlit/` 仍在仓库中；
- `docs/project.md` 等历史文档仍有旧叙事与默认端口描述；
- `chat_service.py` 中 `_maybe_*` 规则链较多，说明 heuristic 仍偏重；
- 根目录临时文件和日志明显过多。

## 6. 面试时怎么回答“为什么你敢讲这个结果？”

推荐回答：

> 因为我不会把这组 1.0 讲成“系统在所有意义上都完美”，而是把它讲成“当前 semireal 主能力闭环已经完整跑通”。我同时会主动补充工程尾巴还在，包括主入口和文档统一、legacy 入口治理、根目录临时产物治理，以及 prompt 和 heuristic 的边界继续优化。这样既不回避成绩，也不掩盖问题。

## 7. 最值得继续讲的优化过程

建议按三层讲：

1. **契约层**：修 basic / single_kb、QueryRequest 参数透传、query/history 解耦；
2. **答案层**：改进 source / evidence 返回、preview excerpt hygiene、negative contract；
3. **评测层**：把 Smoke / Main / Hard 分层，最终把当前 semireal suite 拉到 `150 / 150`。

## 8. 最后一句推荐收口

> 我会把这个项目讲成：主能力闭环和评测闭环都已经成型，但工程完成度还在继续追上能力完成度。这种表达比单纯说“都是 1.0”更真实，也更像一个真正做过系统的人。
