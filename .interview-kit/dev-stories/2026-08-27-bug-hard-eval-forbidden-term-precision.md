# hard eval forbidden-term 误判收敛

## 基本信息
- 类型：bug
- 日期：2026-08-27
- 相关模块：RAG eval harness、chat QA metrics、layered eval 报告口径同步
- 相关文件：`tests/api/chat_qa_metrics.py`、`tests/api/test_chat_qa_metrics.py`、`docs/20260820-layered-rag-eval-refresh/20260820-layered-rag-eval-refresh-test-report.md`、`docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-rounds-rollup.md`、`docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-complete-guide.md`、`docs/interview/ThinkRAG_面试问答.md`

## 问题现象
上一版 hard semireal 报告里，`local_multi_kb_eval_v8_layered_hard` 只有 `31 / 36` 通过，而且失败画像里混着几类并不都是真实产品缺陷的问题：
1. forbidden-term 判定会把答案里“明确说明某旧值已废弃、不可用于 live answer”的情况也当成污染；
2. 对外材料里仍残留 `150 / 150`、`31 / 36` 这类旧口径，和当前 builder / fixture / eval 快照已经不一致。

这会带来两个问题：一是 hard 报告会高估真实缺陷数量，二是面试/汇报材料会继续沿用旧数字。

## 根因分析
根因不在 retrieval 本身，而在 eval harness 的 forbidden-term 规则过于字面：`tests/api/chat_qa_metrics.py` 只要命中 blocked term 就直接算失败，没有区分“错误引用旧值”和“明确声明该旧值不可用”这两种语义。

像 `Legacy rehearsal 18:20 is retired and must not be used for the live answer.` 这种回答，实际上是在做正确的防御性说明，但旧判定仍把 `18:20` 记成污染。另外，hard 报告改进后没有同步覆盖到 `docs/20260820-layered-rag-eval-refresh/` 与部分 `docs/20260825-p0-p2-status-closure/` / `docs/interview/` 文档，导致对外口径漂移继续存在。

## 解决方案
1. 在 `tests/api/chat_qa_metrics.py` 中保留大小写无关的 boundary 匹配，同时新增 blocked term 的上下文判定：当命中词出现在 `is retired`、`must not be used`、`should not be used`、`instead of` 等明显否定/废弃语境里时，不再算作 forbidden-term violation。
2. 在 `tests/api/test_chat_qa_metrics.py` 新增两类回归：
   - contextual negation 应通过；
   - 正向引用 blocked term 仍应失败。
3. 重新执行 hard semireal：`python -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v8_hard/cases.json --schema tests/fixtures/rag_quality/eval_v8_hard/schema.json --output-dir temp/eval-v8-hard-20260827-r9`，并把最新快照同步到 test report / interview 口径文档。

## 为什么选这个方案
我没有直接删掉 hard case，也没有简单放宽 forbidden-term gate，而是先把“错误引用”和“显式排除旧值”这两种语义分开。这样做的好处是：
- 不会为了提升指标去稀释 hard 集；
- 仍然保留对真正错误输出的约束；
- 改动只落在 eval harness 和测试，风险最小，能先验证当前 hard 失败里哪些是真问题、哪些是误判。

## 其他方案与为什么没选
1. 直接把相关 hard case 的 forbidden term 删掉：没选，因为这会把评测集变弱，属于用降门槛掩盖问题。
2. 直接把 hard 结果继续当作“系统还不稳定”：没选，因为这会把 eval harness 本身的误判和产品缺陷混在一起，诊断价值不高。
3. 顺手修剩余 2 条 PDF refusal wording：这轮没先做，因为先把评测误判清掉，才能更准确看到真正残留的产品瓶颈。

## 验证与结果
实际执行并通过了以下验证：
- `python -m pytest tests/api/test_chat_qa_metrics.py tests/api/test_chat_eval_runner.py -q`，结果 `31 passed`
- `python -m scripts.run_chat_eval --cases tests/fixtures/rag_quality/eval_v8_hard/cases.json --schema tests/fixtures/rag_quality/eval_v8_hard/schema.json --output-dir temp/eval-v8-hard-20260827-r9`
  - 最新结果：`34 / 36`
  - `pass_rate = 0.9444`
  - `evidence_hit_rate = 1.0`
  - `preview_resolvable_rate = 1.0`
  - `source_count_match_rate = 1.0`
  - `forbidden_term_clean_rate = 1.0`
- 残余失败收敛到 2 条：`eval-v8-hard-pdf-009`、`eval-v8-hard-pdf-010`
  - 当前共同瓶颈：refusal wording 仍返回通用 `active knowledge base only`，没有显式收口到 `active PDF knowledge base`

## 面试表达版本
我这轮没有去“刷题提分”，而是先修评测系统自己的误判。之前 hard eval 里有些 case 明明是在正确地说明“旧值已经废弃、不能用于 live answer”，结果 harness 还是把它当成 forbidden-term 污染。我把 blocked term 判定改成了带上下文的语义判断，并补了专门回归测试。这样重新跑 hard 以后，结果从 `31 / 36` 提升到 `34 / 36`，而且剩下的 2 条失败也更清楚地收敛成真实产品问题：PDF refusal 文案还不够 modality-aware。
