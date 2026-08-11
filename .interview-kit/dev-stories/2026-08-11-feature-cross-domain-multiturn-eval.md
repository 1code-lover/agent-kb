# 跨领域评测支持多轮追问

## 基本信息
- 类型：feature
- 日期：2026-08-11
- 相关模块：跨知识库真实评测、QA 诊断脚本、项目测试报告
- 相关文件：`scripts/diag_cross_domain_kb_eval.py`、`tests/scripts/test_diag_cross_domain_kb_eval.py`、`docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v3.json`、`docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v8.json`、`docs/project.md`

## 需求背景

桌面发布预检、模型 fallback 和跨知识库单轮评测都已经收口后，下一块风险变成了真实用户不会只问单轮问题。项目后端已经有最小 follow-up/session grounding 能力，但之前跨领域门禁只能验证单轮 case，无法证明同一个 session 里的追问是否仍能保持目标 KB 范围、来源隔离和拒答边界。

这次工作的目标是把多轮追问纳入正式跨领域评测，而不是只靠单元测试或口头说明来判断能力。

## 设计与实现方案

在 `scripts/diag_cross_domain_kb_eval.py` 中保留原有单轮 case 格式，同时新增可选 `turns` 字段。单轮逻辑被抽成 `_evaluate_single_turn()`，多轮逻辑由 `_evaluate_multi_turn_case()` 顺序执行，每个多轮 case 生成一个本次评测专用 `session_id`，case 内所有 turns 共用这个 session，避免跨运行历史污染。

报告层增加了 `is_multi_turn`、`turn_count`、`passed_turn_count`、`failed_turn_ids` 和逐轮 `turns` 明细；总汇总里增加 `multi_turn_total`、`turn_total`、`turn_passed`、`turn_failed` 和 `turn_pass_rate`。这样既能看顶层 case 是否通过，也能定位具体哪一轮失败。

外部样本新增 `cross-domain-extra-cases-v3.json`，覆盖三类真实场景：粮仓知识库内的中文追问、桌面诊断知识库里的英文 evidence preview 追问，以及粮仓 KB 内追问桌面 passcode 的负向隔离。真实评测输出到 `cross-domain-kb-eval-report-v8.json`。

## 为什么选这个方案

这个方案没有引入新的评测 DSL，也没有破坏既有 JSON list / `{ "cases": [...] }` 外部样本格式。`turns` 是向后兼容的增量字段，旧 case 仍然按单轮执行，新 case 可以自然表达“先铺垫，再追问”的链路。

每个多轮 case 使用独立 session id，是为了让评测结果只受当前 turns 影响，不被上一次运行的聊天历史干扰；而同一 case 内共享 session，又能真实触发后端已有的 follow-up history grounding。

## 其他方案与为什么没选

一种方案是只在 `tests/api/test_chat_service.py` 里继续补 follow-up 单测。它能证明函数逻辑，但不能覆盖真实 API、检索、来源 KB 和跨库隔离，所以不适合作为泛化门禁。

另一种方案是把多轮样本直接写进 Python 默认列表。它执行方便，但扩真实业务样本时需要频繁改脚本代码；当前项目已经走向外部 case 文件，所以继续用 v3 JSON 更容易维护和复跑。

## 风险与权衡

多轮评测会比单轮更受模型措辞影响，因此每一轮仍沿用 `expected_terms`、`expected_any_term_groups`、`forbidden_terms` 和 source KB 检查的组合，不引入 LLM 裁判。这样可解释性更强，但对复杂语义等价表达的覆盖仍有限。

这次证明的是最小 follow-up/session grounding 能进入正式回归，不代表完整多轮推理已经完成。后续如果要验证更长链路、跨文档竞争或摘要记忆，还需要继续扩展 v3 之后的样本。

## 验证与结果

- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`14 passed, 1 warning`
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v1.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v2.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v3.json --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v8.json`：`36/36 passed`，逐轮 `39/39 passed`
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"`：`725 passed, 1 deselected, 35 warnings`
- `git diff --check`：通过

## 面试表达版本

我在项目里把跨知识库评测从单轮问答扩展到了多轮追问。做法是保持原来的 case 格式兼容，只新增一个 `turns` 字段，同一个 case 内共用 session，这样能真实触发后端的 follow-up 上下文注入。报告里不只看总通过率，还会记录每一轮的 checks、来源 KB 和失败 turn，方便定位问题。真实样本里我覆盖了粮仓中文追问、桌面诊断英文追问，以及粮仓 KB 里追问桌面 passcode 的隔离拒答。最后默认基线加三组外部样本跑到 `36/36`，逐轮 `39/39` 全通过。
