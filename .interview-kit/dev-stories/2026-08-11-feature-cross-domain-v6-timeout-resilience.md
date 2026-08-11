# 跨领域 v6 扩面与超时韧性

## 基本信息
- 类型：feature
- 日期：2026-08-11
- 相关模块：跨知识库真实问答诊断、模型配置复核、项目进度文档
- 相关文件：`scripts/diag_cross_domain_kb_eval.py`、`tests/scripts/test_diag_cross_domain_kb_eval.py`、`docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v6.json`、`docs/project.md`

## 需求背景
跨领域评测在 v10 已经达到 `45/45 passed`，但还缺少 README 表格、长多轮追问和更多负向隔离样本。继续扩到 v6 时，当前通用模型 `qwen-plus-2025-07-28` 返回免费额度耗尽，临时切到 `qwen-math-turbo` 后又暴露出评测脚本遇到底层超时时会整轮崩掉的问题，无法稳定留下失败归因。

## 设计与实现方案
新增 `cross-domain-extra-cases-v6.json`，覆盖 grain README 表格、mixed batch 三轮追问、桌面 KB 对 grain README 的负向隔离，以及图片 OCR KB 对 mixed rollback approval 的负向隔离。对评测脚本的 `_post_json` 增加 `TimeoutError` 捕获，将底层超时转成 `_http_status=-1` 的普通失败响应，让报告继续生成。同步补充单测，验证超时不会中断整轮评测，并把 v6 试跑结果写入项目总览和专题测试报告。

## 为什么选这个方案
评测脚本本来已经支持 `http_status_ok`、失败检查项汇总和耗时诊断，因此把超时归一到现有响应结构里成本最低，也能复用已有 summary。v6 样本先作为独立 `--cases` 试验集运行，而不是马上并入稳定门禁，可以区分“当前临时模型不稳”和“系统真实回归”。

## 其他方案与为什么没选
推断：也可以直接把超时时间调大并重跑全量，但这会把单个慢请求放大成整轮阻塞，定位效率低。还可以先放宽表格和长多轮断言让 v6 全绿，但这会削弱扩面样本本来要验证的表格抽取和长链路稳定性。

## 风险与权衡
`TimeoutError` 归一会把网络、模型慢响应和服务端长耗时都表现为 `_http_status=-1`，需要结合 `duration_summary` 和具体 `error` 文本判断根因。v6 当前在 `qwen-math-turbo` 下只有 `2/4 passed`，不能作为正式质量门禁；它的价值是暴露下一步要恢复通用模型额度、再复跑 v1-v6 全量。

## 验证与结果
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`21 passed, 1 warning`。
- `/opt/miniconda3/envs/agent-kb/bin/python -m json.tool docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-extra-cases-v6.json >/dev/null`：通过。
- `/opt/miniconda3/envs/agent-kb/bin/python -m json.tool docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v6-only-v2.json >/dev/null`：通过。
- v6 定向评估：`2/4 passed`；两个 cross-KB negative case 通过，README 表格抽取和 mixed batch approval turn 超时仍待在稳定通用模型上复核。

## 面试表达版本
我在跨知识库评测已经稳定到 v10 全绿之后，又设计了一组 v6 真实样本，专门补表格、长多轮和跨库拒答隔离。试跑时遇到模型额度耗尽，只能临时切到数学模型，这暴露了评测脚本遇到底层超时时会直接崩掉的问题。我把超时收敛成结构化失败响应，让整轮报告可以继续生成，并补了单测防止回退。最后我把 v6 作为试验集记录到项目文档里，没有把它伪装成已完成门禁，因为当前失败更多是在提示下一步需要恢复稳定通用模型并复跑全量。
