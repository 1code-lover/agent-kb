# 20260810 Grain Retrieval Quality Tuning Test Plan

## 自动化测试

- 检索实验脚本单元测试：验证文件名归一化、hit rank、MRR 和 source_noise 统计。
- 检索排序/boost 单元测试：验证精确文件名/标题命中能提升排序，且不破坏 kb_id 过滤。
- QA eval 脚本回归：确保拒答、KB 隔离、source 去重指标不回退。

## 实验验证

- 运行检索-only 实验矩阵，输出 JSON 和 Markdown 报告。
- 重点比较：
  - `top_k=5/8/10`
  - fusion mode：`dist_based_score`、`relative_score`、`reciprocal_rerank`
  - reranker：关闭 / 开启
- 记录每个方案的：
  - answerable Recall@5
  - MRR@5
  - retrieval_miss
  - rank_miss
  - source_noise
  - 0034/0078 hit rank

## 真实 QA 验证

- 使用已启动 API 复跑 80 条 QA。
- 验收：
  - `error_count=0`
  - `Recall@5 >= 0.974`
  - `MRR@5 > 0.8961`
  - `refusal_accuracy=1.0`
  - `kb_isolation_rate=1.0`
  - `retrieval_miss=0`
  - `source_noise <= 4`

## 回归风险

- 不得降低已有 80 条 QA 的 Recall。
- 不得引入跨 KB 来源泄漏。
- 不得让不可回答用例重新出现误召回或拒答失败。
