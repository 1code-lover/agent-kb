# targeted-fact orchestration 模块化下沉

## 基本信息
- 类型：refactor
- 日期：2026-08-24
- 相关模块：chat source-backed 后处理、targeted-fact 组装、chat 主链路测试拆分
- 相关文件：`api/services/chat_targeted_fact.py`、`api/services/chat_service.py`、`tests/api/test_chat_targeted_fact.py`

## 重构背景
上一轮已经把 `source projection`、`answer repair`、`composite answers` 从 `api/services/chat_service.py` 里拆成独立模块，但 targeted-fact 这条链路仍然保留了最重的 orchestration 主流程：包括子问题拆分后的候选选择、cross-source 组装、alignment field 补齐、negative-contract 拼接、以及按 source 压缩证据段落。这样的问题是，`chat_targeted_fact.py` 虽然已经承载了候选抽取和评分 helper，但真正复杂、最容易继续演化的部分仍然耦合在 `chat_service.py` 里，导致 chat 主 service 继续维持巨石状态。

## 设计与实现方案
1. 在 `api/services/chat_targeted_fact.py` 里扩展 `TargetedFactHooks`，把 split / cross-source / dedupe 这些 orchestration 需要的依赖也纳入 hook 契约，而不是让模块重新反向依赖 `chat_service.py`。
2. 把下列逻辑整体下沉到 `chat_targeted_fact.py`：
   - `collect_alignment_field_segments(...)`
   - `source_reference_question_overlap(...)`
   - `maybe_answer_targeted_fact_question_from_sources(...)`
3. `api/services/chat_service.py` 仍保留 `_maybe_answer_targeted_fact_question_from_sources(...)` 这个稳定 wrapper，但它只负责：
   - 无 source / refusal-like answer 的 guard
   - summary question 的 guard
   - 然后把真正逻辑委托给 `chat_targeted_fact.maybe_answer_targeted_fact_question_from_sources(...)`
4. 在 `tests/api/test_chat_targeted_fact.py` 新增 orchestration 级测试，直接覆盖：
   - scope-contract 的“双 id 字段 + boundary”组合回答
   - cross-source deadline / interval 组合与噪声裁剪
   - PDF preview resolve-back 子问的最小化命中

## 为什么选这个方案
这次没有直接继续改 prompt，也没有先整理 builder registry，而是优先把 targeted-fact orchestration 下沉，原因是它是 `chat_service.py` 里剩余最重、最适合独立测的一块逻辑。先把主流程模块化，收益最直接：`chat_service.py` 体量能继续下降，targeted-fact 规则也终于能在独立测试文件里演化，而不是每次都把所有行为都压到一个超大的 service 测试里。

## 其他方案与为什么没选
1. 只保留当前 helper 拆分，不继续动 orchestration：没选，因为真正复杂的变化点仍在 `chat_service.py`，维护收益有限。
2. 先做 hook builder / dependency registry 统一：没选，因为那属于下一层结构收口；如果 targeted-fact 主流程还没先下沉，registry 只会把现有复杂度重新包装一层。
3. 直接把 `tests/api/test_chat_service.py` 大幅删改并迁测试：这轮没先做，因为先稳住模块边界更重要；等 orchestration 真正下沉后，再迁测试更安全。

## 风险与权衡
最大的风险是 hook 依赖继续增多，模块虽然拆开了，但 builder 可能变成新的复杂点。所以这轮刻意保持外层 API 不动，只在 `TargetedFactHooks` 里补充 orchestration 必需依赖，避免一次性改动 postprocessor 调度契约。另一个权衡是没有顺手去统一所有 builder，因为那会把本轮改动范围放大；我把这件事留给下一轮，先确保 targeted-fact 模块化闭环完整成立。

## 验证与结果
实际执行并通过了以下验证：
- `python -m pytest tests/api/test_chat_targeted_fact.py tests/api/test_chat_postprocessors.py -q`，结果 `10 passed`
- `python -m pytest tests/api/test_chat_service.py -q`，结果 `75 passed`
- `python -m pytest tests/api/test_chat_question_intents.py tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py -q`，结果 `34 passed, 2 warnings`

本轮之后，`api/services/chat_service.py` 从上一轮的 `1425` 行进一步降到 `1264` 行，说明这次不是“函数搬家但主流程没动”，而是 targeted-fact 的重逻辑确实已经离开 chat 主 service。

## 面试表达版本
我在 source projection、answer repair、composite answers 之后，又把 targeted-fact 的 orchestration 主流程从 `chat_service.py` 拆到了独立模块。这样 chat 主 service 更像调度层，而 targeted-fact 的 cross-source 组装、alignment field 补齐、negative-contract 拼接这些复杂逻辑可以独立测试。这个重构直接把 `chat_service.py` 又压缩了 161 行，并补了模块级回归，所以能比较扎实地说明我不是只靠补题刷分，而是在同步降低系统维护成本。
