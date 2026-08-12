# Source Backed Exact Phrase Repair

## 基本信息
- 类型：feature
- 日期：2026-08-12
- 相关模块：聊天服务、跨领域评测泛化优化
- 相关文件：`api/services/chat_service.py`、`tests/api/test_chat_service.py`、`docs/20260810-model-fallback-desktop-e2e/20260810-model-fallback-desktop-e2e-test-report.md`

## 需求背景
v1-v6 全量跨领域 suite 显示，负向隔离和 contract 已经稳定，但正向用例仍有大量 `expected_terms_hit` 失败。排查后发现其中一类不是检索失败：source 已经命中目标文件，但模型会把精确短语改坏，例如把 `northagent-desktop-e2e-1786353063` 改成带空格的版本，或把 `OCR fallback` 粘成 `OCRfallback`。

## 设计与实现方案
在 `api/services/chat_service.py` 增加 source-backed 精确短语修复逻辑。它只在问题明显索要 unique/exact/passcode 或 `what does/what should/what must` 类来源短语时启用，并只从 source 的 `text/excerpt` 抽取高置信 hyphen token 和固定短语，不从 file/title 抽词。

如果答案缺少 source 中的精确短语，会优先返回包含该短语的 source 原句；找不到短句时才追加“精确来源短语”。该逻辑在拒答分支不运行，避免把负向隔离题的来源泄漏回答案。

## 为什么选这个方案
这类失败的根因是模型改写破坏了已经召回的证据，而不是索引或检索参数。用 source-backed 修复能在不扩大检索范围、不降低负向隔离约束的前提下，先修复最确定的答案保真问题。

## 其他方案与为什么没选
直接放宽评测 expected terms 没有采用，因为 passcode 和 OCR fallback 本来就是需要精确保真的产品行为。全量切换模型也没有在本轮做，因为当前用户要求模型不可用时保留桌面/Web 手动配置，且这类问题可以先用来源证据修补。

## 风险与权衡
这个修复不能覆盖所有正向泛化失败，只覆盖 source 已命中但答案改写精确短语的情况。为了控制误补，逻辑限制了问题类型、来源字段和短语类型；因此它是保守修复，不会把 v1-v6 全量 suite 直接变成绿灯。

## 验证与结果
`/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/api/test_chat_service.py tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`55 passed, 7 warnings`。

临时启动 `KB_API_PORT=18084 /opt/miniconda3/envs/agent-kb/bin/python run_api.py` 验证新 health 字段仍可用，`embedding_diagnostics.local_path_exists=false`、`load_source=remote`，并提示预下载 `localmodels/`。该临时进程未等待 embedding 完整 ready，已手动停止；当前 18080 仍是旧进程，需重启后复跑全量 suite。

## 面试表达版本
我在做 RAG 泛化评测时发现一种很具体的失败：检索已经拿到了正确 source，但模型把精确短语改写坏了。比如 passcode 里的连字符被去掉，或者 `OCR fallback` 被粘成一个词。我没有放宽评测，而是在聊天服务里加了 source-backed 的精确短语修复，只从 source 正文抽取高置信短语，并且拒答时不启用。这个修复很保守，但它能先解决证据已经命中时的答案保真问题，为后续继续处理长多轮和 grounding 失败打基础。
