# Cross Domain V1-V6 Suite Baseline

## 基本信息
- 类型：feature
- 日期：2026-08-12
- 相关模块：跨领域评测脚本、真实样本门禁、项目进度文档
- 相关文件：`scripts/diag_cross_domain_kb_eval.py`、`tests/scripts/test_diag_cross_domain_kb_eval.py`、`docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v1-v6-suite.json`

## 需求背景
跨领域评测已经积累了默认 23 条基线和 v1-v6 多批外部真实样本，但每次全量复跑都要手工拼多个 `--extra-cases` 参数。这样既容易漏样本，也不利于把“更大的验证面”变成稳定门禁。

## 设计与实现方案
在 `scripts/diag_cross_domain_kb_eval.py` 增加 `CROSS_DOMAIN_SUITES`，提供 `--suite v1-v6` 入口，一次性加载默认基线和 v1 到 v6 的外部真实样本。CLI 同时增加逐 case 进度输出，评测 49 条 case、54 个 turn 时能看到当前跑到哪里、哪条慢、哪条失败。

测试覆盖命名 suite 加载、未知 suite 报错和进度回调。随后用当前运行中的 API 执行全量 suite，输出 `cross-domain-kb-eval-report-v1-v6-suite.json`，把真实失败分布固化为后续优化基线。

## 为什么选这个方案
把 suite 做进原有评测脚本，复用了已有 case schema、summary、preflight、duration 和 systemic failure 逻辑，不需要另写一个包装脚本。逐 case 进度输出是必要补充，因为当前临时模型下全量评测会跑数分钟，没有进度时很难判断是正常慢、单条 timeout 还是脚本卡住。

## 其他方案与为什么没选
继续在文档里维护一长串 `--extra-cases` 命令没有采用，因为人工复制容易漏文件。把 v1-v6 全部并入默认用例也暂时没有采用，因为当前全量 suite 还不是绿门禁，直接改变默认命令会让已有稳定诊断口径变得太重。

## 风险与权衡
这次全量 suite 在当前 `qwen-math-turbo` 下只有 `26/49 passed`，所以不能把它宣称为已完成门禁。它的价值是把失败面量化：负向隔离 `15/15` 和 contract `1/1` 稳定，失败主要集中在正向 expected terms、长多轮和 source/evidence grounding。

## 验证与结果
`/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/scripts/test_diag_cross_domain_kb_eval.py -q`：`29 passed, 1 warning`。

`/opt/miniconda3/envs/agent-kb/bin/python -m scripts.diag_cross_domain_kb_eval --api-base http://127.0.0.1:18080 --timeout 60 --preflight --suite v1-v6 --output docs/20260810-model-fallback-desktop-e2e/artifacts/cross-domain-kb-eval-report-v1-v6-suite.json`：`26/49 passed`、逐轮 `30/54 passed`，`negative_pass_rate=1.0`、`contract_pass_rate=1.0`、`positive_pass_rate=0.303`，`systemic_failure_summary.suspected=false`。

## 面试表达版本
我把一个逐步扩出来的 RAG 跨领域评测集收口成了可复用 suite。以前要手工拼六个外部样本文件，很容易漏跑；我给脚本加了 `--suite v1-v6`，并补了逐 case 进度输出，因为全量评测在慢模型上会跑好几分钟。跑完以后结果并不全绿，但这反而是有价值的基线：负向隔离和 contract 全部通过，正向泛化和 grounding 明显不足。这个结果让后续优化能有明确地图，而不是靠印象判断系统好不好。
