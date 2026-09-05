# refusal / negative-contract marker 共享化与上游拒答判定收口

## 基本信息
- 类型：refactor
- 日期：2026-08-28
- 相关模块：chat refusal 主链路、negative-contract 片段识别、source pruning
- 相关文件：`api/services/chat_contract_markers.py`、`api/services/chat_negative_contract_answers.py`、`api/services/chat_service.py`、`tests/api/test_chat_service.py`

## 重构背景
前一轮已经把中文 refusal / negative-contract 能力补进 `chat_negative_contract_answers.py` 和 targeted-fact 组装链路，但 `api/services/chat_service.py` 更上游的 `_answer_is_refusal_like(...)` 仍然要求“首行就带 refusal marker”。这会导致一种真实风险：如果回答是“先给 scope，再给 refusal，再给 no-fabrication”这种多行 negative-contract 结构，尤其是中文 `当前知识库 / 外部记忆` 写法，主链路会把它误判成普通回答，于是 source pruning 根本不会触发。另一个问题是 refusal / scope / memory marker 同时散落在多个模块里维护，后面继续补语言覆盖时很容易再次漂移。

## 重构方案
1. 新增 `api/services/chat_contract_markers.py`，把 refusal / scope / memory / refusal-source marker 以及 `extract_negative_contract_labels(...)` 收敛到一个共享模块。
2. `api/services/chat_negative_contract_answers.py` 改为直接复用共享 marker 与标签提取函数，不再自己复制一套判别规则。
3. `api/services/chat_service.py` 改造 `_answer_is_refusal_like(...)`：
   - 不再只看首行是否含 refusal marker；
   - 先按行做 negative-contract 标签识别；
   - 只要整体存在 refusal 锚点，且没有 grounded fact 行，就判为 refusal-like；
   - 这样 scope-first / memory-last 的多行拒答也能进入主链路裁剪逻辑。
4. 在 `tests/api/test_chat_service.py` 补两个回归：
   - 纯函数级：中文 `scope -> refusal -> memory` 多行答案应判成 refusal-like；
   - query 级：这种答案格式下应真正触发 source pruning，只保留 refusal-backed source。

## 为什么这样重构
我没有直接继续堆 prompt 或 targeted-fact case，而是先收口 `chat_service.py` 上游拒答判定，因为它决定了后面的 source pruning、postprocessor 和 evidence 输出是否走对分支。先把 marker 共享化，再修主链路判定，可以同时解决“语言覆盖漂移”和“scope-first 中文拒答漏判”两个问题，而且改动范围仍然可控，不会把整个 chat pipeline 一次性打散。

## 其他方案与为什么没选
1. 只在 `chat_service.py` 局部加几个中文字符串判断：没选，因为这样能临时修 bug，但 refusal / scope / memory 词表会继续多处分叉，下次补 mixed-language case 还会重复出问题。
2. 直接把 `_answer_is_refusal_like(...)` 改成“只要任一行出现 refusal marker 就算拒答”：没选，因为这会把“事实答案里顺带引用 refusal guideline”的场景误判成拒答，破坏已有 source 最小化与 answer repair 分支。
3. 进一步把 `chat_question_intents.py` 的问句 marker 也一起全部共享化：这轮没做，因为先优先修主链路误判；问句分类的统一是下一轮更合适的收口点。

## 风险控制与兼容性
这次重构的主要风险是扩大 refusal 判定后，误把正常事实回答打成拒答。为避免这种回归，我保留了 grounded fact 否决逻辑：如果任一行看起来像真实事实行（例如 `file:` 前缀、列表事实、冒号字段），仍然不会判成 refusal-like。同时保留了原有“事实答案里引用 refusal guideline 不应误判”的回归测试，确保这轮不是用更激进的启发式硬换通过率。共享 marker 也只先落在 `chat_service.py` 与 `chat_negative_contract_answers.py` 两处，范围可控，便于后续逐步扩展到 question intent 层。

## 验证与结果
实际执行并通过了以下验证：
- `python -m py_compile api/services/chat_contract_markers.py api/services/chat_negative_contract_answers.py api/services/chat_service.py tests/api/test_chat_service.py`
- `python -m pytest tests/api/test_chat_service.py -q -k "refusal or negative_contract or refusal_anchor or scope_first_chinese"`，结果 `17 passed, 67 deselected`
- `python -m pytest tests/api/test_chat_negative_contract_answers.py tests/api/test_chat_targeted_fact.py -q`，结果 `22 passed`
- `python -m pytest tests/api/test_chat_source_selection.py -q`，结果 `5 passed`

这轮之后，中文 `scope-first` negative-contract 不再卡在 `chat_service.py` 的首行 refusal 假设里，query 级 source pruning 也能在这种回答格式下正常触发。

## 面试表达版本
我发现前一轮虽然把中文 refusal/negative-contract 补到了 targeted-fact 辅助链路，但 chat 主链路仍然默认“首行必须是 refusal”，所以一些真实的中文多行拒答会漏判。我这轮做了两个动作：先把 refusal、scope、memory marker 抽成共享模块，再把 `chat_service.py` 的拒答判定改成按行识别 negative-contract，而不是盯着首行。这样既修掉了中文 `当前知识库 -> 无可确认信息 -> 不得编造` 这种真实格式的漏判，也降低了后面继续补 mixed-language case 时的维护成本。最关键的是我补了 query 级回归，证明这不是纯函数层面的“看起来更合理”，而是确实让 source pruning 主链路走对了。
