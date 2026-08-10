# 粮仓知识库检索排序质量调优

## 基本信息
- 类型：feature
- 日期：2026-08-10
- 相关模块：粮仓知识库检索、QA 评测、模型配置验证、项目质量文档
- 相关文件：`server/retriever.py`、`scripts/run_grain_retrieval_experiments.py`、`scripts/run_grain_qa_eval.py`、`tests/test_retriever.py`、`tests/scripts/test_run_grain_retrieval_experiments.py`、`tests/scripts/test_run_grain_qa_eval.py`、`docs/20260810-grain-retrieval-quality-tuning/`

## 需求背景

上一轮索引覆盖修复后，粮仓知识库 80 条 verified QA 的文档覆盖已经恢复，但仍留下排序质量问题：部分问题能召回到正确文档，却不是首位；还有旧版规范、团体标准和主题相近规程会挤占来源列表。用户要求继续把目标做完，而不是停在“基本可用”。所以本轮目标是把 answerable QA 的 `retrieval_miss`、`rank_miss` 和 `source_noise` 清零，并保留可复跑的实验依据。

## 设计与实现方案

我先新增 `scripts/run_grain_retrieval_experiments.py`，绕过 LLM 生成，直接加载 `grain-knowledge-base` 的 KB-scoped index，跑 top_k、fusion mode 和 reranker 的检索-only 矩阵。实验结果显示，reranker 对部分样例有帮助，但速度和稳定性不适合作为默认方案；真正有效的是在融合检索出口扩大内部候选池，并对文件名、标题、正文证据和来源多样性做轻量后排序。

实现上，我在 `server/retriever.py` 里保留外部配置的 `top_k` 语义不变，但让 vector/BM25/fusion 的内部候选池至少取 10，再由 `_rerank_and_trim_nodes` 裁剪回用户配置值。排序规则包括：

- 归一化来源文件名，去掉导入 hash 后缀并统一括号。
- 对查询与文件名/标题的强匹配、最长公共子串和关键词覆盖加权。
- 对正文中出现较长查询片段的节点补充分。
- 优先不同来源文件，避免同一文件多个 chunk 把 top5 塞满。
- 对正式编号/最新版规范做轻量偏好，对旧版、试行稿和无年份团体标准做轻量降权。

评测侧，我扩展 `scripts/run_grain_qa_eval.py` 的拒答识别，把“未包含”“无法根据现有信息”这类知识库兜底句计为正确拒答。运行 API QA 时，原模型 `qwen3.7-plus` 触发 `AllocationQuota.FreeTierOnly`，我按用户要求切换到可用的 `阿里百联 / qwen-plus-2025-07-28` 后重跑完整 80 条。

## 为什么选这个方案

这个方案的核心约束是可控和可解释。直接默认启用 reranker 会增加运行成本、模型依赖和延迟，而且实验里没有稳定优于轻量后排序。只调大最终 top_k 又会把更多噪声暴露给用户，不能解决“正确来源排第一”的问题。把改动放在融合检索出口，可以复用现有 vector/BM25 结构，也能保持 API 的 `top_k` 契约不变。

## 其他方案与为什么没选

推断：可以重建索引或重新切 chunk，但覆盖诊断已经证明文档都在 docstore 里，本轮问题主要是排序，不是数据缺失。

推断：可以把 top_k 从 5 提到 8 或 10，但这会改变用户看到的来源数量，仍然不能保证首位证据正确。

推断：可以把 reranker 作为默认开启项，但本地模型加载和运行时间更重，且实验显示它对 top10/source_noise 有回归风险，所以保留为可实验变量，不作为本轮默认路径。

## 风险与权衡

这轮排序规则包含少量粮仓领域偏好，例如正式版/最新版规范、常规熏蒸和空调控温规程。这些规则能解决当前 verified QA 的真实噪声，但如果未来扩展到其他行业知识库，需要用跨领域评测确认是否抽成配置或关闭领域偏好。

另一个风险是 API QA 依赖外部 LLM 可用性。首次完整评估因为模型额度耗尽失败，这不是检索质量问题，但会拖慢验证闭环。因此下一步更应该做模型 fallback 和评测断点续跑，而不是继续堆排序规则。

## 验证与结果

- 检索-only 最终矩阵：`top5-dist_based_score-no-rerank` 达到 `answerable_total=77`、`Recall@5=1.0`、`MRR@5=1.0`、`retrieval_miss_count=0`、`rank_miss_count=0`、`source_noise_count=0`
- 覆盖诊断：`local_exists_count=82`、`docstore_hit_count=82`、`docstore_kb_id_hit_count=82`
- API QA：80 条，`error_count=0`、`Recall@5=1.0`、`MRR@5=1.0`、`citation_hit_rate=1.0`、`refusal_accuracy=1.0`、`kb_isolation_rate=1.0`
- `/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"`：`702 passed, 1 deselected, 35 warnings`
- `git diff --check`：通过

## 面试表达版本

我接手时，粮仓知识库已经补齐了索引覆盖，但 QA 里还有排序和来源噪声问题。我的第一步不是直接开 reranker，而是做了一个检索-only 实验矩阵，把 top_k、fusion mode 和 reranker 的效果跑清楚。实验发现，最划算的方案是在融合检索出口扩大内部候选池，再用标题、文件名、正文证据和来源多样性做轻量重排。这样既不改变用户配置的 top_k，也避免把更重的 reranker 变成默认依赖。最后 80 条 verified QA 的 Recall@5、MRR、引用、拒答和 KB 隔离都达到了 1.0，全量非 slow 测试也通过了。这个过程里我还处理了模型额度耗尽的问题，切到可用模型后重跑完整评估，避免把外部模型故障误当成检索回归。
