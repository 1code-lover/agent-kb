# Source-backed 跨领域真实评测收口

## 基本信息
- 类型：feature
- 日期：2026-08-14
- 相关模块：知识库问答后处理、docstore 原文回看、多事实回答、跨领域评测
- 相关文件：`api/services/chat_service.py`、`tests/api/test_chat_service.py`、`scripts/diag_cross_domain_kb_eval.py`、`docs/20260810-model-fallback-desktop-e2e/20260810-model-fallback-desktop-e2e-test-report.md`、`docs/project.md`

## 需求背景
v1-v6 跨领域真实评测从 `37/49` 提升到 `44/49` 后，剩余失败并不都是检索缺失：部分 source chunk 截断了 UTF-16、OCR 或授权边界完整句；部分问题同时要求 boundary、approval 和 preview，但最终回答只保留一个事实；另有 exact/passcode 负向问题在没有相关证据时仍可能调用 LLM 产生跨库臆答。继续只调 prompt 或扩大 top-k 无法稳定解决这些 source 已命中但答案不完整的问题。

## 设计与实现方案
`api/services/chat_service.py` 增加了受问题语义约束的 source-backed 处理链：

1. 对知识库、文件夹、授权边界问题，从 source 的 `kb_id` / `doc_id` 回看 docstore 完整文档或 ref-doc nodes，补足截断 chunk；同时清理 UTF-16 NUL 夹字。
2. 对 scope/definition 问题从证据句中选择包含关系锚点的完整句，不把已经完整且由多个 source 支撑的答案压缩掉。
3. 对 `In one answer`、`and does` 等多事实问题，分别选择 approval、boundary、preview 的最佳证据句；只有至少找到两个请求事实时才合并，否则保留模型原答。
4. 对唯一值、原文、passcode 类问题先执行纯检索；如果限定知识库没有具备词面支撑的 source，直接返回稳定拒答，不再调用 LLM 猜测。
5. 跨领域评测的答案、来源文件和禁止词检查统一改为 `casefold()`，避免大小写差异制造假失败。

## 为什么选这个方案
真实报告已经证明目标文档经常出现在 sources 中，问题主要发生在 chunk 截断和最终答案选择阶段。回看同一 `doc_id` 的完整文本能继续遵守当前 KB 范围，不需要放宽 metadata filter；按问题类型做窄触发的 source-backed 合并，也比全局替换模型回答更可控。对于无相关证据的 exact 问题，在 LLM 之前拒答可以直接守住跨 KB 隔离边界。

## 风险与权衡
docstore 回看依赖 source 中存在正确的 `kb_id` 和 `doc_id`，因此实现保留异常回落，不会因为历史节点缺字段而中断问答。多事实合并可能误选相邻句，所以要求问题明确包含多个事实信号，并按 approval、boundary、preview 锚点评分；事实不足时不覆盖原答案。纯检索 preflight 只用于 exact/source phrase 类问题，避免给普通开放问答增加重复检索成本。

## 验证与结果
新增 12 个 Chat Service 测试，覆盖：

- 无 grounded source 时在调用 LLM 前拒答；
- OCR/中文/UTF-16 边界原句；
- chunk 截断后的 ref-doc 回看；
- 完整多 source 边界答案保留；
- scope definition；
- approval + preview、boundary + preview 多事实合并。

最终门禁结果：

- Python 非 slow 全量测试：`783 passed, 1 deselected, 35 warnings`。
- Web 测试：`89 passed`，Vite build 通过。
- Electron CSP/runtime/release 测试：`44 passed`。
- v1-v6 真实评测：`49/49 cases passed`、`54/54 turns passed`。
- 正向、负向和 contract 通过率：`100%`。
- 多轮：`4/4 passed`。
- `failure_check_summary={}`、`failure_case_summary=[]`、`systemic_failure_summary.suspected=false`。

正式 macOS 签名、公证和 stapling 不属于这次问答修复的通过条件；当前仍因 Apple 凭证和 Developer ID Application 证书缺失而等待外部环境。

## 面试表达版本
我在跨领域 RAG 评测里发现，最后几个失败不是简单的召回不足，而是 source chunk 截断和多事实答案被压缩。我的方案不是继续扩大 top-k，而是利用 source 的 `kb_id` 和 `doc_id` 回看同一知识库里的完整文档，对边界、scope 和 preview 做窄触发的证据句选择；多事实问题按 approval、boundary、preview 分别找证据，找不齐就保留原回答。同时对 passcode 这类 exact 问题增加 LLM 前检索拒答，防止跨库猜测。最终真实门禁从 44/49 收口到 49/49，54 个 turn 全部通过。
