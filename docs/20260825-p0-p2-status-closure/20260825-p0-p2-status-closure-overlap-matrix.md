# 20260825 P0/P2 Status Closure Overlap Matrix

## 1. 文档目的

这份文档用于持续收口 **P1-7「Prompt 契约偏弱、后处理 heuristic 太重」** 里的 classifier / postprocessor overlap 问题。

本轮以当前 worktree 的下列文件为事实来源：

- `C:/Users/ethan1.zhao/Desktop/xiangmu/agent-kb/api/services/chat_question_intents.py`
- `C:/Users/ethan1.zhao/Desktop/xiangmu/agent-kb/api/services/chat_postprocessors.py`
- `C:/Users/ethan1.zhao/Desktop/xiangmu/agent-kb/api/services/chat_targeted_fact.py`

扫描数据集仍然限定为当前 layered eval 主评测三组题库：

- `C:/Users/ethan1.zhao/Desktop/xiangmu/agent-kb/tests/fixtures/rag_quality/eval_v7/cases.json`
- `C:/Users/ethan1.zhao/Desktop/xiangmu/agent-kb/tests/fixtures/rag_quality/eval_v8_main/cases.json`
- `C:/Users/ethan1.zhao/Desktop/xiangmu/agent-kb/tests/fixtures/rag_quality/eval_v8_hard/cases.json`

目的不是刷分，而是回答两个更关键的问题：

1. 当前主评测题里，哪些 classifier 还在稳定重叠；
2. 哪些 overlap 是合理协同，哪些其实是 heuristic 误判，应该继续收紧。

---

## 2. 本轮扫描边界

| 数据集 | 用例数 |
| --- | ---: |
| `eval_v7` | 24 |
| `eval_v8_main` | 93 |
| `eval_v8_hard` | 36 |
| **合计** | **153** |

扫描 classifier：`preview / boundary / scope / merge / summary / targeted / exact / negative / cross_source`。

---

## 3. 本轮新增整改结论

### 3.1 第 29 轮遗留问题已闭环

上一轮扫描发现：

- `question_requests_negative_contract(...)` 之前把 `active knowledge base` / `active PDF knowledge base` 当作 negative-contract 信号；
- 这会把普通 scope-contract 问句 `eval-v8-main-pdf-004` 误打成 `targeted + negative`。

本轮已经确认这个误判被消掉：

- `eval-v8-main-pdf-004`
  - question：`In the PDF scope contract, which response field should echo the active PDF knowledge base, and what scope type must remain in force?`
  - **现在不再命中 `negative`**；
  - 保留为普通 scope-contract / targeted 处理。

### 3.2 第 30 轮新收口：targeted 不再误吃“单一 cross-source boundary 问句”

本轮又发现一个真实 overlap：

- `question_requests_targeted_fact_answer(...)` 之前只要问句里出现裸 `and/or`，就会把它视为 multi-clause；
- 这会把下面这类**只有一个问题、只是 source 名里出现 and 的 cross-source boundary 问句**误判成 targeted：
  - `eval-v5-md-003`
  - `eval-v5-pdf-003`
  - `eval-v5-img-003`

典型样例：

```text
Across the scope manual and the folder boundary note, what remains the authorization boundary rule?
```

这类题本质上是：

- `boundary + cross_source`
- 不是 `targeted-fact multi-subquestion`

因此本轮已把 `targeted-fact` 的“多子问题信号”从**裸 `and/or`** 收紧为：

- 必须出现真正的子问题切分信号；
- 也就是 `and/or` 后面要跟 `who / what / which / does / may / must ...` 这类第二个问句子句；
- 不能仅因为 source 名或前置描述里有 `X and Y` 就命中 targeted。

---

## 4. 一眼结论

### 4.1 最重要的正面变化

1. **`merge` 仍只剩 4 条真 merge**，说明第 28 轮对 `and what` 的收紧已经稳定，没有回滚。
2. **`negative` 从 4 降到 3**，说明第 29 轮修掉 `active PDF knowledge base` 误判后，普通 scope-contract 已不再被错误归到 refusal/negative 题型。
3. **`targeted` 从 39 降到 35**，说明第 30 轮又成功清掉了 3 条“单一 cross-source boundary 问句”误判。
4. 现在这 153 条主评测题里已经**没有任何三重 overlap 留在 `boundary + targeted + cross_source`**，这比上一版矩阵更干净。

### 4.2 当前主矛盾是什么

经过两轮收口后，当前最值得继续盯的 overlap 已经变成：

1. `targeted + cross_source`：**11 条**
2. `boundary + targeted`：**6 条**
3. `boundary + cross_source`：**3 条**
4. `targeted + exact`：**3 条**，再加上 **1 条** `preview + targeted + exact`
5. `targeted + negative`：**1 条**
6. `preview + targeted`：**1 条**

这说明：

- `merge vs targeted` 已不是主矛盾；
- `negative` 的明显误判也收住了；
- 下一阶段真正要治理的，是 **targeted 与 cross-source / exact / preview 的协同边界**，以及 **boundary 与 cross-source 的单问句路由**。

---

## 5. classifier 命中分布

| classifier | 命中用例数 | 备注 |
| --- | ---: | --- |
| `preview` | 9 | preview / evidence preview 问法 |
| `boundary` | 16 | authorization boundary / access-control / permission wall |
| `scope` | 0 | 范围定义类问句；本轮扫描中未命中 |
| `merge` | 4 | 只剩显式 merge 意图（如 “分别” / `one answer`） |
| `summary` | 8 | 一句话总结 / summarize |
| `targeted` | 35 | 多子问题精确事实拼装；较上一版减少 4 |
| `exact` | 7 | `what must` / `what should` / exact phrase 等精确短语倾向 |
| `negative` | 3 | refusal / no confirmable information / outside memory |
| `cross_source` | 15 | `compare` / `across` 等跨 source 组装 |

---

## 6. exact overlap 组合矩阵

这里统计的是**精确组合**，不是 pair co-occurrence；因此不会把三重 overlap 重复记入二重组合。

| overlap 组合 | 用例数 |
| --- | ---: |
| `targeted + cross_source` | 11 |
| `boundary + targeted` | 6 |
| `boundary + cross_source` | 3 |
| `targeted + exact` | 3 |
| `boundary + summary` | 1 |
| `boundary + summary + negative` | 1 |
| `preview + targeted` | 1 |
| `preview + targeted + exact` | 1 |
| `targeted + negative` | 1 |

补充说明：

- co-occurrence 口径下，`targeted + exact = 4`，因为 `preview + targeted + exact` 会再贡献 1 次 pair；
- 同理，`preview + targeted = 2`，其中 1 条来自三重 overlap；
- 但从治理角度看，**exact combination** 更能说明还剩哪些“真重叠题型”。

---

## 7. 高风险词形扫描

| 高风险词形 | 命中用例数 | 例子 |
| --- | ---: | --- |
| `and what` | 15 | `eval-v7-md-005`<br>`eval-v7-pdf-005`<br>`eval-v7-pdf-008`<br>`eval-v7-img-005` |
| `and does` | 0 | — |
| `which field` | 4 | `eval-v8-main-md-002`<br>`eval-v8-main-pdf-002`<br>`eval-v8-hard-pdf-007`<br>`eval-v8-hard-img-011` |
| `authorization boundary` | 13 | `eval-v7-md-005`<br>`eval-v7-pdf-005`<br>`eval-v7-img-005`<br>`eval-v8-hard-pdf-011` |
| `preview excerpt` | 1 | `eval-v8-hard-pdf-005` |

补充说明：

- `and what` 仍然很多，但 `merge` 没有回升，说明第 28 轮收紧是稳定生效的；
- `authorization boundary` 仍是 boundary 题簇最稳定的信号源；
- `preview excerpt` 目前仍只出现 1 条，但它正好是 `preview + targeted + exact` 的代表样例，价值很高。

---

## 8. 典型风险题型样本

### `eval-v7-md-005`
- classifier：`boundary + targeted`
- question：`In the workflow boundary note, what is not an authorization boundary, and what remains the access-control boundary?`
- 含义：单 source 的双子问题 boundary 题，仍然需要 targeted 组装。

### `eval-v5-pdf-003`
- classifier：`boundary + cross_source`
- question：`Across the scope manual and the folder boundary note, what remains the authorization boundary rule?`
- 含义：这是第 30 轮修掉的典型误判；现在它不再被错误打成 targeted。

### `eval-v8-hard-md-005`
- classifier：`preview + targeted`
- question：`According to the workflow boundary note, which two fields must an evidence preview include, and what remains the access-control boundary?`
- 含义：preview 与 targeted 协同仍然真实存在，不能简单二选一。

### `eval-v8-hard-pdf-005`
- classifier：`preview + targeted + exact`
- question：`From the PDF preview guide, which two fields must every answer carry, and what must the preview excerpt resolve back to?`
- 含义：这是当前最典型的三类协同题，后续所有修复都应把它当金标。

### `eval-v8-hard-img-012`
- classifier：`targeted + negative`
- question：`When OCR evidence is sparse on the noisy policy board, may the assistant rely on fabricated memory, or must it stay inside the active knowledge base?`
- 含义：负向契约 + 多子问题对齐仍然是高风险边界题。

---

## 9. 当前 `merge` 还剩哪些“真 merge”题

下面 4 条仍是本轮扫描里命中 `merge` 的全部题目：

- `eval-v4-md-003`：最终审批人和 rollback owner 分别是谁？
- `eval-v4-pdf-003`：在 Payroll release checklist 里，final sign-off owner 和 rollback owner 分别是谁？
- `eval-v4-img-003`：在这块 whiteboard 上，final approver 和 rollback owner 分别是谁？
- `eval-v4-md-015`：最终审批人和 business confirmer 分别是谁？

这 4 条都带明确的“分别”语义，属于 `merge` 收紧后仍然应该保留的真阳性。

---

## 10. 已完成的本轮真实验证

### 10.1 新增/更新的关键测试

- `C:/Users/ethan1.zhao/Desktop/xiangmu/agent-kb/tests/api/test_chat_question_intents.py`
  - 新增：`test_question_requests_targeted_fact_answer_rejects_single_question_cross_source_boundary_prompt`
- `C:/Users/ethan1.zhao/Desktop/xiangmu/agent-kb/tests/api/test_chat_service.py`
  - 新增：`test_apply_source_answer_postprocessors_keeps_single_question_cross_source_boundary_out_of_targeted_handler`

### 10.2 定向回归结果

- `python -m pytest tests/api/test_chat_question_intents.py -q` -> **14 passed**
- `python -m pytest tests/api/test_chat_service.py -q` -> **80 passed**
- `python -m pytest tests/api/test_chat_targeted_fact.py -q` -> **8 passed**

---

## 11. 对下一轮整改的直接建议

1. **优先盯 `targeted + exact`**：`what must ... remain / what should ... echo` 这类题现在还有 3 条精确组合 + 1 条三重 co-occurrence，值得继续判断 exact 是否还能再收窄。
2. **把 `boundary + cross_source` 的非 targeted 路由显式写成规则**：虽然第 30 轮已经靠 classifier 收紧清掉了误判，但最好在调度文档里明确这类题默认先走 boundary，再决定是否补 exact repair。
3. **继续把 `eval-v8-hard-pdf-005` 当作金标**：这题是 preview / targeted / exact 的真实协同代表，后续任何优化都要先确认它不回退。
4. **保留对 `targeted + negative` 的高优先级关注**：虽然只剩 1 条，但 refusal / active-KB / no-fabrication 这类题的解释价值很高，面试时也最能体现边界意识。

---

## 12. 本轮结论

如果把这轮扫描压成一句话，最准确的说法是：

> 经过第 29 轮 negative-contract 收紧和第 30 轮 targeted-fact 收紧后，当前 layered eval 主题库里最明显的 heuristic 误判已经继续下降；下一阶段真正要治理的，是 targeted 与 cross-source / exact / preview 的协同边界，而不是再回头处理 merge 抢跑。
