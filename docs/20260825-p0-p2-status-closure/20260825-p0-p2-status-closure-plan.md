# 20260825 P0/P2 Status Closure Plan

## 1. 文档定位

这份 `plan` 不是重复写一遍状态报告，而是把当前已经整理出来的 **12 个问题状态、两条推进路线、下一阶段真实优先级** 收成一页，方便在“继续改代码”和“准备面试表达”之间快速切换。

适用场景：

1. 继续按 P0 / P1 / P2 往下做时，先确认 **现在最该动什么、不该再重复动什么**；
2. 面试或汇报前，快速判断应该讲“已经收口的主能力”还是“仍在继续的工程 backlog”；
3. 避免把原始问题清单、当前状态和下一步计划散落在多个文档里。

---

## 2. 当前总判断：Route A 继续做工程收口，Route B 负责稳定表达

结合 `status-report`、`rounds-rollup`、`evidence-cheat-sheet` 和本轮新增的 cleanup backlog 可见性，可以把当前 12 个问题先压成三组：

### 2.1 已经进入“回归守护”阶段的项

这些问题已经不再适合作为当前第一优先级主攻方向，更适合作为 **持续防回归** 的守护项：

- **#1** basic 模式和后端 `single_kb` 约束冲突
- **#4** QueryRequest 请求级参数没有完整打进 chat 主链路
- **#5** 前端把 query 成功和 history 成功绑死
- **#12** 面试表述需要区分“能力完成度”和“工程完成度”

意思不是“永远不用看”，而是：

> 这些点现在应该靠测试和文档守住，不该再消耗下一轮最宝贵的开发预算去重复证明。

### 2.2 当前最值得继续做“实改”的项

这些是当前还会真实影响工程完成度的 backlog：

- **#2 / #3 / #8** 启动入口、legacy 兼容层、Docker / requirements / 端口 / 启动脚本的最终统一
- **#6** refusal / negative contract 继续往 semireal hard negatives 加深
- **#7** Prompt 契约偏弱、后处理 heuristic 太重
- **#9 / #11** root 临时产物、日志、scratch inventory 的真实减法
- **#10** 文档闭环继续去重、减少代际并存

### 2.3 当前更适合“维护而不是继续扩写”的项

- `interview-complete-guide`
- `interview-script`
- `interview-pack`
- `ThinkRAG_面试问答.md`

这些材料现在已经足够支撑面试和汇报，后续应该以 **少量增量同步** 为主，而不是继续无限拆新文档。

---

## 3. 两条路线里，当前默认建议怎么选

### 3.1 Route A：继续整改 —— **当前默认主路线**

原因很简单：

1. 面试材料已经能讲；
2. 主能力闭环已经能证；
3. 现在最稀缺的是 **把工程完成度继续追上来**，而不是再做一层包装。

所以如果没有新的外部汇报 deadline，默认建议继续走 **Route A**。

### 3.2 Route B：准备面试表达 —— **当前作为配套路线**

什么时候切到 Route B：

1. 临近面试或汇报，需要快速复习；
2. 某一轮刚做完真实整改，需要把新变化同步进现有讲稿；
3. 需要准备“为什么 1.0 不代表一切都完美”这类回答。

但当前不建议继续把 Route B 发展成新的大文档工程。更好的做法是：

> 保持现有材料链顺、口径一致、数字和结论可追溯，然后把主要精力放回真实整改。

---

## 4. 当前 Route A 的真实优先级（按现在证据重新排序）

> 注意：这份排序不是照搬最早的问题清单，而是根据当前真实状态重新排序后的“现在该先做什么”。

### A1. 先继续压 Prompt / heuristic 复杂度（#7）

**为什么排第一：**

- 这是当前最接近“主链路内部复杂度”的问题；
- 它直接影响 targeted fact、postprocessor、answer repair 的可解释性；
- 也是“能力完成度高、工程完成度还在追”的最典型来源。

**优先看这些文件：**

- `api/services/chat_service.py`
- `api/services/chat_query_flow.py`
- `api/services/chat_targeted_fact.py`
- `api/services/chat_postprocessors.py`
- `api/services/chat_answer_repair.py`

**至少要继续守住的验证：**

- `python -m pytest tests/api/test_chat_service.py -q`
- `python -m pytest tests/api/test_chat_targeted_fact.py tests/api/test_chat_postprocessors.py tests/api/test_chat_answer_repair.py -q`
- `python -m pytest tests/api/test_chat_eval_runner.py tests/api/test_chat_eval_contracts.py -q`

**这一包真正做完的标志：**

- 不是“把文件拆得更多”，而是 **减少主链路隐式 heuristic 分支**；
- 遇到追问时，可以更清楚地区分“prompt 契约”“source selection”“answer repair”各自负责什么。

### A2. 再继续增强 refusal / semireal hard negatives（#6）

**为什么排第二：**

- 当前 refusal / negative contract 已经不是空白，但仍偏 contract / fixture 驱动；
- 这是最容易被面试官追问“是不是题太少、是不是只会正向题”的部分；
- 它和 A1 一起，决定系统是不是只在“理想题集”里稳定。

**优先看这些文件：**

- `tests/api/test_chat_eval_contracts.py`
- `tests/api/test_chat_eval_runner.py`
- `tests/test_rag_quality_eval_dataset_v8.py`
- `tests/fixtures/rag_quality/eval_v8_*`

**至少要继续守住的验证：**

- `python -m pytest tests/api/test_chat_eval_contracts.py -q`
- `python -m pytest tests/api/test_chat_eval_runner.py -q`
- `python -m pytest tests/test_rag_quality_eval_dataset_v8.py -q`

**这一包真正做完的标志：**

- 不只是 refusal marker 还在；
- 而是 hard negative、scope trap、跨源误拼接等场景都有更像真实追问的 case。

### A3. 然后继续收启动入口 / Docker / 配置漂移（#2 / #3 / #8）

**为什么排第三：**

- 这组问题已经从“高风险硬伤”降到“还有兼容层残留”；
- 但它仍然影响新同学第一印象、环境复现和桌面链路可信度；
- 适合做成一组“统一入口、减少 wrapper、统一端口口径”的收尾工程。

**优先看这些文件：**

- `start_all.ps1`
- `start_dev.ps1`
- `start_frontend.ps1`
- `scripts/dev-all.ps1`
- `scripts/docker_smoke.py`
- `requirements-runtime.txt`
- `requirements-smoke.txt`
- `docs/project.md`

**至少要继续守住的验证：**

- `python -m pytest tests/scripts/test_dev_startup_contracts.py -q`
- `python -m pytest tests/scripts/test_docker_smoke.py tests/test_requirements_profiles.py -q`
- `python -m pytest tests/test_legacy_streamlit_entry.py tests/scripts/test_docs_entry_contracts.py -q`

**这一包真正做完的标志：**

- 新主入口更清楚；
- legacy 兼容层继续缩薄；
- 端口 / API base / requirements profile 的口径在脚本、文档、测试里进一步统一。

### A4. 最后持续做 root backlog 减法（#9 / #11）

**为什么排第四：**

- 它不会立刻改变主能力，但会持续影响仓库卫生和维护体验；
- 现在已经从“看起来乱”推进到“有脚本、有 summary、有测试”；
- 下一步应该从“看见库存”进入“减少库存”。

**当前已知库存（2026-08-26 dry-run）：**

- `managed_count = 0`
- 其中 `tmp_eval` 家族约 **12 条 / 1.13 MB**
- 当前最显著的 backlog 已收敛到 `tmp_eval_out`、`tmp_eval_out5`、`tmp_eval_debug_codex3`、`tmp_eval_debug_codex5`、`tmp_eval_out8` 这些评测 scratch 目录

**优先看这些文件：**

- `scripts/cleanup_local_artifacts.py`
- `tests/scripts/test_cleanup_local_artifacts.py`
- `tests/scripts/test_repo_hygiene_contracts.py`
- `docs/project.md`

**至少要继续守住的验证：**

- `python -m pytest tests/scripts/test_cleanup_local_artifacts.py -q`
- `python -m pytest tests/scripts/test_cleanup_local_artifacts.py tests/scripts/test_repo_hygiene_contracts.py -q`

**这一包真正做完的标志：**

- 不只是 summary 更漂亮；
- 而是真正减少一批 root scratch / temp 资产，且不误伤 tracked 历史目录。

---

## 5. 哪些项现在不该再放到前两位

### 5.1 `basic / single_kb`（#1）

这条现在应该作为 **回归守护项** 存在。除非出现新的绕过入口，否则不建议再把它放回第一优先级。

### 5.2 QueryRequest override（#4）

这条已经有比较明确的 runtime 和 chat 主链路测试兜底，也不适合继续占用当前第一开发优先级。

### 5.3 query / history 解耦（#5）

这条现在已经足够作为“真实优化案例”用于面试表达，继续投入应以回归守护为主，而不是重新大改前端状态机。

---

## 6. 当前 Route B 最简使用法

如果下一次不是继续改代码，而是要快速准备面试 / 汇报，建议固定按这条链路：

1. `20260825-p0-p2-status-closure-master-guide.md`
2. `20260825-p0-p2-status-closure-interview-complete-guide.md`
3. `20260825-p0-p2-status-closure-interview-script.md`
4. `20260825-p0-p2-status-closure-status-report.md`
5. `20260825-p0-p2-status-closure-evidence-cheat-sheet.md`
6. `docs/interview/ThinkRAG_面试问答.md`

最关键的表达边界只有一句：

> **主能力闭环已经比较扎实，工程完成度还在继续追赶。**

---

## 7. 一句话收口

> 现在最适合做的，不是继续重复证明已经收口的点，也不是继续无限扩写面试材料，而是按 **A1 heuristic 降复杂度 → A2 refusal hard negatives → A3 startup/docker/配置统一 → A4 root backlog 减法** 这条线继续把工程完成度往前推。

