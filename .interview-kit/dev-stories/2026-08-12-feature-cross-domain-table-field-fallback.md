# 跨领域表格字段问答兜底

## 基本信息
- 类型：feature
- 日期：2026-08-12
- 相关模块：知识库问答、跨领域评测、系统性故障诊断
- 相关文件：`api/services/chat_service.py`、`scripts/diag_cross_domain_kb_eval.py`、`tests/api/test_chat_service.py`、`tests/scripts/test_diag_cross_domain_kb_eval.py`、`docs/project.md`、`docs/20260810-model-fallback-desktop-e2e/20260810-model-fallback-desktop-e2e-test-report.md`

## 需求背景
v6 跨领域扩展样本把 README 的 Markdown 表格纳入了真实问答。临时模型 `qwen-math-turbo` 在该样本中能命中 README 来源和证据文本，但把“主要格式”答成了 `text(markdown)`，更像是把文件 metadata 当成正文表格内容。这个失败不是 KB 隔离问题，也不是检索缺失，而是表格字段类问答在生成阶段需要更强的 source grounding。

## 设计与实现方案
在 `api/services/chat_service.py` 增加 source-backed Markdown 表格字段兜底。流程是：先判断问题是否明确询问“表/字段”的值，再从 source 的 `text/excerpt` 中解析 Markdown 表格行，按字段名抽取对应单元格；如果模型答案没有包含这些表格原值，就用来源表格值生成最小答案。字段匹配优先精确和包含关系，弱匹配必须有多个 token 重叠，避免把“主要格式”错配到相邻的“主要语言”。

同时在 `scripts/diag_cross_domain_kb_eval.py` 中把 `Broken pipe` 与 timeout 一类断流归到 `network_error`。这样真实 v6 复跑如果在 preflight 阶段被模型链路卡住，报告会明确标记为模型/网络层问题，而不是混在业务断言失败里。

## 为什么选这个方案
这次没有把 README 的具体答案硬编码进评测，也没有强迫模型重写 prompt。表格字段问答本身是可结构化抽取的问题，服务端从已返回 source 中做轻量兜底，既能提升 README、配置表、参数表这类真实材料的稳定性，又不会扩大到普通叙述型问答。诊断分类则复用已有 `systemic_failure_summary`，只补充错误归因，不改变评测主流程。

## 其他方案与为什么没选
推断：可以把 v6 用例的期望改宽，只接受 `text(markdown)`，但本地 README 原文明确写的是 `.pdf` 和 `.docx`，改宽会掩盖真实表格抽取问题。也可以要求模型总是逐字引用表格，但这会影响所有问答风格，并且对当前临时模型的稳定性没有保障。

## 风险与权衡
表格兜底只在问题出现“表/字段/table/field”且询问具体值时触发，降低误改普通答案的风险。它依赖 source 中存在 Markdown 表格文本；如果 OCR 或 PDF 表格没有转成 Markdown 行，本轮不会强行猜测。真实 v6 复跑仍受当前模型和 runtime warmup 影响，本轮报告记录为 `network_error`，不把模型链路失败包装成业务通过。

## 验证与结果
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_chat_service.py tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`50 passed, 7 warnings`。
- 真实 v6 extra 复跑写出 `docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v6-after-table-fallback.json`；最终 preflight 首个 case 在 60 秒内 timeout，`dominant_error_kind=network_error`，记录为模型/运行时链路限制。
- 中途一次完整 v6 extra 复跑曾达到 `3/4 passed`，mixed batch 三轮用例通过；最终提交保留的是最新 preflight timeout 报告。

## 面试表达版本
我在跨知识库评测里遇到一个很具体的生成问题：检索已经命中 README 表格，但模型把文件 metadata 当成了表格里的“主要格式”。我没有硬编码这个 README，而是在聊天服务里做了一个 source-backed 表格字段兜底，只在问题明确问表格字段时，从返回来源的 Markdown 表格行里抽值补答案。同时我把 Broken pipe 和 timeout 归为 network_error，让评测报告能把模型链路问题和业务泛化问题分开。最后用 chat_service 和评测脚本单测覆盖了字段抽取、相邻字段误匹配和断流归因。
