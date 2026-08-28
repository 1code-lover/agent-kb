# 20260825 P0/P2 Status Closure Master Guide

## 1. 文档定位

这份 `master-guide` 是当前这批材料的**统一总入口**，目标只有一个：

> 把 **1~30 轮问题、12 项问题状态、最新主链路验证、面试表达口径、下一步迭代顺序** 收到一页里，避免继续在 `20260821` 审计材料、`20260825` 收口材料和 `docs/interview/` 导航页之间来回跳。

如果你只记一条原则，请记：

- **当前主讲口径优先看 `20260825-p0-p2-status-closure/`；**
- `20260821-project-audit-remediation/` 继续作为**深证据 / 历史审计归档**，不再作为第一跳入口。

---

## 2. 如果你只想“把这些整理完成”

如果你当前的目标不是继续翻历史细节，而是要把这批材料**一次性整理清楚、能直接拿去讲**，建议直接按下面 4 份看：

1. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-master-guide.md`
2. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-complete-guide.md`
3. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-status-report.md`
4. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-rounds-rollup.md`

这样分工最清楚：

- `master-guide`：告诉你**先看什么、后看什么、当前到底讲到哪**；
- `interview-complete-guide`：给你**完整讲稿主线**；
- `status-report`：给你**12 项问题当前状态**；
- `rounds-rollup`：给你**1~30 轮问题压缩后的 6 个主题**。

---

## 3. 当前统一阅读顺序

建议以后固定按下面顺序读：

1. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-master-guide.md`
2. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-plan.md`
3. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-complete-guide.md`
4. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md`
5. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-status-report.md`
6. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-rounds-rollup.md`
7. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-overlap-matrix.md`
8. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-evidence-cheat-sheet.md`
9. `docs/interview/ThinkRAG_面试问答.md`
10. `docs/20260821-project-audit-remediation/` 下的 audit / guide / report-script / status-matrix（只在需要深证据或追溯历史演进时再看）

---

## 4. 按原始 12 项问题怎么定位到当前材料

如果你想把目标里的原始问题逐条对上当前材料，最推荐按下表定位：

| 编号 | 原始问题 | 当前主看文档 | 当前判断 | 面试里怎么讲 |
| --- | --- | --- | --- | --- |
| 1 | basic 模式和后端 single_kb 约束冲突 | `20260825-p0-p2-status-closure-status-report.md` | 已收口 | 讲“产品语义和系统约束已经一致，basic / knowledge 都显式绑定 active KB”。 |
| 2 | 启动链路 / 桌面链路存在硬编码 | `20260825-p0-p2-status-closure-status-report.md`、`20260821-project-audit-remediation-status-matrix.md` | 部分完成 | 讲“主入口已统一，但 compatibility wrapper / legacy 兼容层仍在逐步收口”。 |
| 3 | 项目主入口不统一 | `20260825-p0-p2-status-closure-status-report.md`、`docs/project.md` | 大体收口 | 讲“当前统一主线是 FastAPI + React(Vite) + Electron；Streamlit 只保留 opt-in legacy 兼容语义”。 |
| 4 | QueryRequest 参数没有完整打进 chat 主链路 | `20260825-p0-p2-status-closure-status-report.md` | 已收口 | 讲“请求级参数已经从前端字段变成真正影响 runtime query engine 的输入”。 |
| 5 | 前端把 query 成功和 history 成功绑死 | `20260825-p0-p2-status-closure-status-report.md`、`ThinkRAG_面试问答.md` | 已收口 | 讲“query 成功优先，history 只负责后续同步，不再让慢一拍的回写覆盖结果”。 |
| 6 | 评测 harness 对 refusal / negative contract 覆盖不足 | `20260825-p0-p2-status-closure-status-report.md`、`20260820-layered-rag-eval-refresh-test-report.md` | 大体收口 | 讲“现在已经不是只看全局 marker，而是 refusal / negative-contract / follow-up 都有正式 gate，且模态内一旦存在该类 case，required marker 就不能缺”。 |
| 7 | Prompt 契约偏弱，后处理 heuristic 太重 | `20260825-p0-p2-status-closure-rounds-rollup.md`、`20260825-p0-p2-status-closure-overlap-matrix.md` | 部分完成 | 讲“已经从 classifier / orchestration / source minimization 开始减重，但复杂度治理仍在继续”。 |
| 8 | Docker / requirements / 端口 / 启动脚本存在配置漂移 | `20260825-p0-p2-status-closure-status-report.md` | 大体收口 | 讲“配置漂移已经进入自动化 gate，不再完全靠人工记忆，但历史脚本和文档还在继续统一”。 |
| 9 | 仓库根目录临时文件、日志、调试脚本较多 | `20260825-p0-p2-status-closure-status-report.md`、`20260825-p0-p2-status-closure-plan.md` | 部分完成 | 讲“治理规则已经建立，但 inventory 减法和 scratch backlog 仍未彻底清空”。 |
| 10 | 文档闭环不够满 | `20260825-p0-p2-status-closure-master-guide.md`、`20260825-p0-p2-status-closure-status-report.md` | 部分完成 | 讲“当前主入口、主讲稿、状态报告、rounds rollup 已经成套，但历史材料仍较多”。 |
| 11 | 日志与临时产物治理需要规范化 | `20260825-p0-p2-status-closure-plan.md`、`20260825-p0-p2-status-closure-evidence-cheat-sheet.md` | 部分完成 | 讲“cleanup / repo hygiene 已经形成规则，但 apply 与归档策略还要继续收口”。 |
| 12 | 面试表述需要主动区分“能力完成度”和“工程完成度” | `20260825-p0-p2-status-closure-interview-complete-guide.md`、`20260825-p0-p2-status-closure-interview-script.md` | 已整理 | 讲“主能力闭环已成型，但工程完成度仍在追赶，不把系统讲成所有问题都清零”。 |

如果现场只允许讲 1 分钟，不要逐条背这 12 项；应先讲**三条已经收口的能力项**、再讲**三条仍在继续的工程项**。

---

## 5. 当前最新真实基线（便于统一口径）

这一节只收当前最值得复述的真实结果，不替代详细测试报告。

### 5.1 截至 2026-08-28 最值得记住的验证结果

- `python -m pytest tests/scripts/test_docs_entry_contracts.py tests/test_rag_quality_fixtures.py tests/test_rag_quality_eval_dataset_v8.py tests/api/test_chat_eval_contracts.py tests/api/test_chat_eval_runner.py -q` → `94 passed`
- `python -m pytest tests/test_rag_quality_fixtures.py tests/test_rag_quality_eval_dataset_v8.py tests/api/test_chat_eval_contracts.py -q` → `44 passed`
- `python -m pytest tests/api/test_chat_eval_runner.py -q` → `23 passed`
- `python -m pytest tests/api/test_chat_service.py tests/api/test_chat_answer_repair.py tests/api/test_chat_source_selection.py tests/api/test_chat_source_reconciliation.py tests/api/test_chat_targeted_fact.py -q` → `121 passed`
- `python scripts/build_audit_metrics_snapshot.py --bundle full_non_slow --sync-docs` → 已把 audit / interview / project 主线材料里的 full non-slow 口径刷新到当前快照（`1296 passed, 4 deselected`）
- `python scripts/validate_rag_quality_fixtures.py --eval-cases tests/fixtures/rag_quality/eval_v8_main/cases.json --eval-schema tests/fixtures/rag_quality/eval_v8_main/schema.json --print-eval-summary` 已确认：
  - `total_cases = 93`
  - `refusal_case_count = 23`
  - `negative_contract_case_count = 22`
  - `history_grounded_case_count = 6`
- `python scripts/cleanup_local_artifacts.py --dry-run --include-directories` → `managed_count = 0`

### 5.2 这轮整理完成的两个关键补充

这轮不只是“把旧材料摆到一起”，而是把两类容易讲错的点真正收口了：

1. **文档指标口径漂移已被真实修正**
   - `docs/20260821-project-audit-remediation/` 这一组材料之前还残留旧的 full non-slow 口径；
   - 现在已经通过 `scripts/build_audit_metrics_snapshot.py --bundle full_non_slow --sync-docs` 做增量刷新；
   - 好处是以后再遇到 pytest collect 数变化，不必手工逐个改历史材料。
2. **refusal / negative-contract 的 per-modality gate 已有正式说明**
   - 现在不是只看“全局 marker 是否出现过”；
   - 而是某个模态里只要已经存在被 tracked 的 refusal / negative-contract category，该模态下 required marker 就不能缺；
   - 这层语义已经补进 `20260820-layered-rag-eval-refresh-test-report.md` 和 `docs/interview/ThinkRAG_面试问答.md`，面试时不再需要临场口头解释。

### 5.3 这轮真实新增的一点工程进展

这轮不是只补文档，还补了一个真实兼容性问题：

- `api/services/chat_service.py` 在 `_build_query_flow_hooks()` 里原本硬依赖 `runtime_state.invalidate_llm`；
- `tests/api/test_open_api_integration.py` 的 `_PhysicalRuntime` mock 没有这个方法，导致 open-api integration bundle 初始出现 `2 failed, 108 passed, 2 warnings`；
- 现在已经改成兼容缺省 no-op；
- 同一 bundle 已恢复到 `110 passed, 2 warnings`。

这类修复很适合面试时讲成：**不是只在堆文档，而是在持续把主链路里的真实兼容性尖点磨平。**

---

## 6. 按场景怎么用

### 6.1 面试前 30 秒 / 2 分钟快记

优先看：

- `20260825-p0-p2-status-closure-interview-complete-guide.md`
- `20260825-p0-p2-status-closure-interview-script.md`
- `20260825-p0-p2-status-closure-interview-pack.md`

目标：先用 complete-guide 一次性过完整讲稿，再用 interview-script / interview-pack 记住项目定位、4 句话骨架、能力完成度 vs 工程完成度的边界表达。

### 6.2 需要讲“1~30 轮到底做了什么”

优先看：

- `20260825-p0-p2-status-closure-rounds-rollup.md`

目标：把 30 轮问题压成 6 个主题，而不是按时间线背流水账。

### 6.3 需要讲“12 个问题现在各自到什么状态”

优先看：

- `20260825-p0-p2-status-closure-status-report.md`

目标：按“已收口 / 大体收口 / 部分完成”回答，不要一上来就讲代码细节。

### 6.3.1 需要决定“下一步先改什么、后改什么”

优先看：

- `20260825-p0-p2-status-closure-plan.md`

目标：把已经进入回归守护的项和仍需继续实改的项分开，避免下一轮又回头重复证明已经收口的点。

### 6.4 需要讲“最近真实修了什么 heuristic 问题”

优先看：

- `20260825-p0-p2-status-closure-overlap-matrix.md`

目标：讲清 recent negative-contract 与 targeted-fact overlap 的真实收紧案例，而不是泛泛说“我优化了一些 heuristics”。

### 6.5 需要讲“证据和验证从哪里来”

优先看：

- `20260825-p0-p2-status-closure-evidence-cheat-sheet.md`
- `20260821-project-audit-remediation/` 下对应 audit / report / matrix

目标：把验证讲成“可复跑、可复核、可追溯”，而不是只报一个 1.0。

---

## 7. 当前统一一句话总判断

如果一定要把这批材料压成一句话，建议统一这样讲：

> 这 30 轮的核心成果，不是把一个 demo 勉强跑通，而是把一个已经有能力雏形的本地知识库助手，逐步收口成 **主能力闭环更完整、系统契约更一致、验证证据更扎实，但工程完成度仍在继续追赶能力完成度** 的工程系统。

---

## 8. 当前最推荐的对外引用顺序

以后在面试、汇报、复盘里，建议优先引用下面这条链路：

1. `master-guide`：先定阅读边界和当前主线；
2. `interview-script`：给 30 秒 / 2 分钟 / 5 分钟稳定表达；
3. `status-report`：给 12 项问题当前状态；
4. `rounds-rollup`：给 1~30 轮问题压缩主题；
5. `overlap-matrix`：给最近真实 heuristic 收口案例；
6. `20260821-project-audit-remediation/`：给更深的历史证据、审计矩阵和详细测试记录。

这样讲的好处是：

- 不会把最新收口材料埋在历史 audit 文档后面；
- 不会把导航页、问答页、证据页混成一层；
- 更容易在现场快速切换“讲结论 / 讲状态 / 讲证据 / 讲边界”。

---

## 9. 路线 A / 路线 B 现在怎么接

### 9.1 Route A：继续做工程收口

当前更推荐按这个顺序推进：

1. `kb_service.import_files()` 继续拆职责；
2. `chat_targeted_fact.py` 继续拆 scoring / negative-contract / local-context expansion；
3. 前端入口进一步统一到 `/knowledge` 主路径；
4. root scratch backlog 已收口到 `managed_count = 0`，后续重点转为防回脏与定期巡检；
5. `.gitattributes` 补齐，继续减少 LF / CRLF review 噪音。

### 9.2 Route B：准备面试表达

如果当前目标是“先把这些整理完成，拿去讲”，建议固定按下面表达：

- **核心亮点**：多 KB 约束收口、scope isolation、evidence / preview、请求级 QueryRequest 真生效、前端 query/history 解耦、layered eval；
- **优化过程**：从单点功能可用，逐步补齐 contract、follow-up、negative contract、startup/docker/cleanup 治理；
- **诚实边界**：工程化收口仍在继续，但主能力闭环已经形成，不把系统讲成所有问题都清零。

---

## 10. 不建议再怎么讲

以下几种讲法建议避免：

1. 继续把 `20260821` 审计文档当第一入口；
2. 继续把 `ThinkRAG_面试全集_合并版.md` 当成长正文，而不是导航页；
3. 继续把 1~30 轮按流水账逐轮复述；
4. 继续把 `153` 条 layered eval、局部 `1.0` 或 Main `93 / 93` 讲成“系统已经没有问题”；
5. 继续混淆“主能力闭环”与“工程完成度彻底收尾”。

---

## 11. 最后一句收口

> 当前最稳的讲法不是“项目已经全做完了”，而是：**主能力闭环已经做实，最新真实问题正在按可验证的方式继续收口，工程完成度还在持续追上来。**
