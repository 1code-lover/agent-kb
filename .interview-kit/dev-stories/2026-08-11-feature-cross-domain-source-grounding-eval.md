# 跨领域评测补充来源文件级校验

## 基本信息
- 类型：feature
- 日期：2026-08-11
- 相关模块：跨知识库真实评测、来源 grounding、QA 诊断报告
- 相关文件：`scripts/diag_cross_domain_kb_eval.py`、`tests/scripts/test_diag_cross_domain_kb_eval.py`、`docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v4.json`、`docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v9.json`、`docs/project.md`

## 需求背景

跨领域评测已经能校验答案关键词、禁止泄漏词和来源 `kb_id`，也支持了多轮追问。但这还留着一个质量盲点：回答可能来自正确 KB，却没有引用到最期望的文件，尤其在粮仓这种大知识库里，一个问题可能召回多个同库文档。

这次工作的目标是把“来源文件是否落在目标文档上”纳入正式门禁，让评测不只证明没有跨库，还能证明引用 grounding 更精确。

## 设计与实现方案

在 `scripts/diag_cross_domain_kb_eval.py` 中新增来源文件抽取逻辑，从 `sources` 和 `evidence` 记录里按 `file`、`source`、`title`、`doc_id` 的顺序提取可读来源名。case 格式新增两个可选字段：

- `required_source_files`：每个片段都必须命中至少一个来源文件名。
- `forbidden_source_files`：任何来源文件名都不能包含这些片段。

评测结果新增 `source_files`，checks 中新增 `required_source_file_hit` 和 `forbidden_source_file_clean`。这些字段只在 case 显式配置时产生约束，所以旧样本保持兼容。

外部样本新增 `cross-domain-extra-cases-v4.json`，覆盖粮仓守则、桌面 workflow、扫描 PDF、图片 OCR 和 mixed batch cutover 的来源文件落点。真实评测输出到 `cross-domain-kb-eval-report-v9.json`。

## 为什么选这个方案

文件名片段比完整文件名更稳，因为粮仓导入后的文件名会带 hash 后缀，例如 `AAA粮油安全储存守则_0119014f.docx`。用片段断言可以保留真实导入产物的稳定性，同时避免把评测绑定到每次导入生成的完整 hash。

把 source file 断言放在现有跨领域脚本里，而不是另开脚本，是为了继续复用 case source、tag summary、多轮 turns、KB 隔离和 forbidden terms 这些已有能力，减少后续扩样本的维护成本。

## 其他方案与为什么没选

一种方案是只检查 `doc_id`。它更精确，但真实导入重建后 `doc_id` 可能变化，不适合做长期可复跑门禁。

另一种方案是只靠答案关键词判断。它对用户可见答案友好，但无法发现同 KB 内引用偏到错误文件的问题，所以不足以支撑 grounding 质量优化。

## 风险与权衡

文件级断言提高了评测强度，也会让评测对来源排序和 top-k 更敏感。为降低误报，这次样本选择的是来源文件名非常明确、真实 API 返回稳定的场景，并使用 `top_k=8` 保留必要召回空间。

这仍然不是物理隔离证明，也不是完整引用精确率评估；它是跨领域诊断里一层更硬的 grounding gate。

## 验证与结果

- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`16 passed, 1 warning`
- `/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v1.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v2.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v3.json --extra-cases docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v4.json --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v9.json`：`41/41 passed`，逐轮 `44/44 passed`，`source-grounding` 为 `5/5`
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"`：`727 passed, 1 deselected, 35 warnings`
- `git diff --check`：通过

## 面试表达版本

我在跨知识库评测里补了一层来源文件级 grounding 校验。之前评测能证明答案命中、没有跨 KB，但还不能证明同一个 KB 里是否引用到了目标文件。我给 case 增加了 `required_source_files` 和 `forbidden_source_files`，从 API 返回的 sources/evidence 里提取 `file/source/title/doc_id`，再做文件名片段断言。这样粮仓、桌面、OCR、扫描 PDF 和 mixed batch 的样本都可以确认引用落点。最后 v9 真实评测跑到 `41/41`，逐轮 `44/44`，其中 source-grounding 切片 `5/5` 通过。
