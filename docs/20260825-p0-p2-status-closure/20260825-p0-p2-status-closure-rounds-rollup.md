# 20260825 P0/P2 Status Closure Rounds Rollup

## 1. 文档定位

这份文档的目标是把当前线程里的 **1~30 轮问题、12 项核心问题、最新审计结论和面试话术** 收口成一份单文件总览。

适用场景：

1. 面试前 10 分钟快速复习；
2. 汇报时需要一份“先讲结论、再讲证据、最后讲边界”的提纲；
3. 继续按 P0 / P1 / P2 改代码前，先确认哪些已经收口、哪些只是大体收口、哪些仍在继续。

配套材料建议阅读顺序：

1. `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260825-p0-p2-status-closure\20260825-p0-p2-status-closure-rounds-rollup.md`
2. `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260825-p0-p2-status-closure\20260825-p0-p2-status-closure-interview-script.md`
3. `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260825-p0-p2-status-closure\20260825-p0-p2-status-closure-status-report.md`
4. `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260825-p0-p2-status-closure\20260825-p0-p2-status-closure-evidence-cheat-sheet.md`
5. `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260821-project-audit-remediation\20260821-project-audit-remediation-issues-summary.md`

---

## 2. 一句话总判断

如果一定要把 1~30 轮问题压成一句话，当前最准确的讲法是：

> 这 30 轮的核心成果，不是把一个 demo 勉强跑通，而是把一个已经有能力雏形的本地知识库助手，逐步收口成 **主能力闭环更完整、系统契约更一致、验证证据更扎实，但工程完成度仍在继续追赶能力完成度** 的工程系统。

这句话同时兼顾三点：

1. **不讲小**：不是只做了几条小修小补；
2. **不讲满**：不是说所有工程问题都已经清零；
3. **可追问**：后面无论面试官追问能力、工程还是评测，都能顺着展开。

---

## 3. 当前最稳的项目定位

建议统一把项目定义成：

- **产品定位**：本地优先知识库助手；
- **主线架构**：FastAPI + React(Vite) + Electron + LlamaIndex；
- **核心能力**：single-kb scope、evidence / preview、请求级 QueryRequest 参数生效、前端 query/history 解耦、layered eval 与 contract test；
- **当前阶段**：主能力闭环已成型，工程收口仍在继续。

不建议再把项目讲成：

- “一个简单的 RAG demo”；
- “所有链路都已经完全 finished”；
- “只有 OCR / QA 指标好看”；
- “主要价值就是把分数刷到 1.0”。

---

## 4. 把 1~30 轮问题压成 6 个主题

### 主题 A：把“能回答”升级成“在受控边界内回答”

这一类问题的核心不是模型能不能答，而是系统是不是在 **明确的 active KB / scope 边界内** 回答。

典型问题：

- basic 模式和 single_kb 约束冲突；
- 项目主入口和真实产品口径不一致；
- 前端把局部模式讲成“全局检索”。

推荐讲法：

> 我不是只追求“能答出来”，而是先把“在什么边界里答”做对。现在 `basic` / `knowledge` 都显式绑定 active KB，后端也按 `single_kb` 约束执行，这样产品语义和系统约束是一致的。

### 主题 B：把“参数存在”升级成“参数真的生效”

这一类问题的重点是：很多系统表面上有配置项，但它未必真的进到主链路。

典型问题：

- QueryRequest 请求级参数疑似没有完整打进 chat 主链路；
- 一些 request-level 选项停留在前端透传；
- Prompt 契约偏弱，只能依赖后处理兜底。

推荐讲法：

> 我做的一件很实际的事，是把请求级参数从“前端表单字段”变成真正影响 runtime query engine 的输入，这样优化和调参才不是假动作。

### 主题 C：把“接口成功”升级成“用户感知的一致性”

这一类问题看上去不像算法问题，但决定用户会不会信系统。

典型问题：

- 前端把 query 成功和 history 成功绑死；
- 局部成功和全局失败状态混在一起；
- query 已成功但 UI 仍表现成失败。

推荐讲法：

> 我补的不是表面提示语，而是状态一致性。现在 query 成功优先，history 只负责后续同步，不再让慢一拍的回写把刚返回的答案覆盖掉。

### 主题 D：把“功能堆出来”升级成“能被验证和复跑”

这一类问题的核心是：能力是否有系统性证明，而不是靠口头说“最近效果不错”。

典型问题：

- refusal / negative contract 覆盖不足；
- 缺少对 scope / evidence / preview 的系统性证明；
- 结论只能靠口头描述，不能靠测试和评测坐实。

推荐讲法：

> 我比较强调 layered eval、contract test 和主链路回归，是因为我不想把系统稳定性建立在“感觉最近还行”上，而是建立在可复跑、可复核的证据上。

### 主题 E：把“能开发”升级成“能长期维护”

这一类问题重点在工程治理，而不是单条功能。

典型问题：

- 启动链路 / 桌面链路硬编码；
- Docker / requirements / 端口 / 启动脚本配置漂移；
- 仓库根目录临时文件、日志、调试脚本过多；
- 日志与临时产物治理不规范。

推荐讲法：

> 我不是只补功能，也在持续做工程收口，包括 startup contract、requirements profile、docker smoke、cleanup 和 repo hygiene。这些工作短期不一定最显眼，但决定系统能不能被后续稳定维护。

### 主题 F：把“做了很多事”升级成“会讲清楚自己做了什么”

这一类问题重点在表达和材料闭环。

典型问题：

- 文档闭环不够满；
- 面试表述混淆能力完成度和工程完成度；
- 1~30 轮问题如果按时间线讲，会非常散。

推荐讲法：

> 我现在会主动把项目讲成两层：第一层是主能力闭环已经完成到哪里，第二层是工程完成度还差在哪里。这样既不会过度包装，也不会把真实价值讲小。

---

## 5. 12 项核心问题当前状态总表

| 编号 | 问题 | 当前判断 | 面试时最适合怎么说 |
| --- | --- | --- | --- |
| 1 | basic 模式和后端 single_kb 约束冲突 | 已收口 | `basic / knowledge` 已与 active KB 和 `single_kb` 对齐，后续重点是防止新入口绕过约束。 |
| 2 | 启动链路 / 桌面链路存在硬编码 | 部分完成 | 旧绝对路径、固定端口、legacy 引导已大幅收口，但兼容层还没彻底退场。 |
| 3 | 项目主入口不统一 | 大体收口 | 当前可以统一讲成 FastAPI + React(Vite) + Electron，Streamlit 只是 opt-in legacy。 |
| 4 | 请求级 QueryRequest 参数疑似没有完整打进 chat 主链路 | 已收口 | 请求级 RAG 参数已经真正打进 route + runtime + chat 主链路，不再是假透传。 |
| 5 | 前端把 query 成功和 history 成功绑死 | 已收口 | query 成功和 history 写回已经解耦，UI 不会再因为 history 慢一拍覆盖成功结果。 |
| 6 | 评测 harness 对 refusal / negative contract 覆盖不足 | 大体收口 | hard 集 refusal follow-up 与 main 集 answerable follow-up 都已进入正式 gate，而且 fixture 侧已补上 per-modality marker 守卫；但 hard negatives、semireal refusal 与真实追问场景仍要继续补。 |
| 7 | Prompt 契约偏弱，后处理 heuristic 太重 | 部分完成 | 复杂度已模块化，最新不仅收紧了 `scope-definition` classifier 误判，还把 `chat_targeted_fact.py` 的评分逻辑拆成多层纯函数；但 orchestration 与 heuristic 仍偏重。 |
| 8 | Docker / requirements / 端口 / 启动脚本存在配置漂移 | 大体收口 | 已有自动化 gate 和 smoke，但历史脚本、文档、兼容路径还需继续统一。 |
| 9 | 仓库根目录临时文件、日志、调试脚本较多 | 部分完成 | cleanup / repo hygiene 规则已经建立，但 inventory 减法还没做完。 |
| 10 | 文档闭环不够满 | 部分完成 | audit / interview / status 材料已成链，但历史文档代际仍多，闭环程度是改善中。 |
| 11 | 日志与临时产物治理需要规范化 | 部分完成 | 规则和脚本已建立，但命名、目录和长期归档策略还值得继续统一。 |
| 12 | 面试表述需要主动区分“能力完成度”和“工程完成度” | 已整理 | 现在已经有固定口径：核心能力闭环已完成较多，工程治理仍在推进。 |

---

## 6. 面试最推荐的讲法骨架

### 6.1 30 秒版

> 我做的不是一个简单把模型接到文档上的 demo，而是一个本地优先的知识库助手。当前主线已经统一到 FastAPI + React(Vite) + Electron + LlamaIndex，核心闭环包括 single-kb scope、evidence / preview、请求级 QueryRequest 参数生效、前端 query/history 解耦和分层评测。更准确地说，现在是能力完成度高于工程完成度：主能力已经闭环，但 legacy 入口、配置收口、cleanup 和 hard negative 评测还在继续推进。

### 6.2 2 分钟版

建议按“三层闭环”讲：

1. **产品能力闭环**：active KB 边界、evidence / preview 返回、单库问答范围明确；
2. **系统契约闭环**：QueryRequest 参数生效、query/history 解耦、scope/product 语义对齐；
3. **验证闭环**：layered eval、route/runtime/test bundle、startup/docker/cleanup 契约都在持续回归。

最后主动补一句：

> 我不会把这个项目讲成“所有工程问题都清零”，而会讲成“核心能力闭环已经成型，工程完成度还在继续收口”。

### 6.3 5 分钟版

建议固定按下面顺序讲：

1. 项目定位：本地优先知识库助手，主线架构是 FastAPI + React(Vite) + Electron + LlamaIndex；
2. 能力边界：不是盲查全局资料，而是在 active KB / single-kb 约束下回答；
3. 主链路改动：QueryRequest 参数真的生效，query/history 已解耦；
4. 评测与契约：scope / evidence / preview / refusal / startup / cleanup 都有自动化验证；
5. 诚实边界：legacy 兼容层、hard negatives、heuristic 复杂度、文档代际和 root scratch backlog 还在继续治理。

---

## 7. 当前最有说服力的真实证据

### 7.1 已经沉淀到材料里的主证据

这些证据已经收口在现有 status / audit 材料中，可直接作为对外依据：

- Layered suite：`153` 条（Smoke `24 / 24`、Main `93 / 93`、Hard 最新可复核快照 `36 / 36`，且 `run_passed = true`）
- chat 关键回归：`101 passed, 2 warnings`
- 全量非慢测：`1140 passed, 4 deselected, 2 warnings`
- 启动 / 文档 / requirements / cleanup / repo hygiene：已有成组 smoke 与 contract test
- 前端 `agentExperience + chatWorkflow`：已有 Node 单测束

更详细的命令与上下文，统一看：

- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260825-p0-p2-status-closure\20260825-p0-p2-status-closure-status-report.md`
- `C:\Users\ethan1.zhao\Desktop\xiangmu\agent-kb\docs\20260821-project-audit-remediation\20260821-project-audit-remediation-issues-summary.md`

### 7.2 2026-08-26 的最新增量回归

这几轮又补了几类更细的证据：

1. **refusal / negative contract + answerable follow-up gate 收紧**
   - `python -m pytest tests/api/test_chat_eval_runner.py tests/api/test_chat_eval_contracts.py tests/test_rag_quality_eval_dataset_v8.py -q` → `45 passed, 2 warnings`
   - `python scripts/validate_rag_quality_fixtures.py --eval-cases tests/fixtures/rag_quality/eval_v8_main/cases.json --eval-schema tests/fixtures/rag_quality/eval_v8_main/schema.json --print-eval-summary` 已确认 `history_grounded_case_count = 6`，且 markdown / pdf / image_ocr 各 `2` 条
   - 这意味着现在不是只有 hard refusal follow-up：main 集的 answerable follow-up 也已经进入正式 gate
2. **scope-definition classifier 误判收紧**
   - `python -m pytest tests/api/test_chat_question_intents.py -q` → `10 passed`
   - `python -m pytest tests/api/test_chat_postprocessors.py -q` → `2 passed`
   - `python -m pytest tests/api/test_chat_service.py -q` → `79 passed`
   - `python -m pytest tests/api/test_chat_source_answers.py -q` → `6 passed`
3. **targeted-fact 评分链路减重**
   - `python -m pytest tests/api/test_chat_targeted_fact.py tests/api/test_chat_question_intents.py tests/api/test_chat_postprocessors.py -q` → `31 passed`
   - 函数级扫描显示 `score_targeted_answer_candidate(...)` 当前约 `71` 行，`maybe_answer_targeted_fact_question_from_sources(...)` 已压到约 `74` 行；并新增了 subquestion answer / negative-contract fallback / source regrouping helper
4. **source minimization 主链路减重**
   - `python -m pytest tests/api/test_chat_targeted_fact.py tests/api/test_chat_question_intents.py tests/api/test_chat_postprocessors.py tests/api/test_chat_source_selection.py -q` → `36 passed`
   - `python -m pytest tests/api/test_chat_source_selection.py tests/api/test_chat_postprocessors.py tests/api/test_chat_hook_builders.py tests/api/test_chat_service.py -q` → `91 passed`
   - 函数级扫描显示 `minimize_sources_for_answer(...)` 已压到约 `40` 行，并新增了 should-minimize / mentioned-source / support-map / greedy-cover helper 与独立 `test_chat_source_selection.py`
5. **targeted-fact signals / structural bonus 第三轮减重**
   - `python -m pytest tests/api/test_chat_targeted_fact.py tests/api/test_chat_question_intents.py tests/api/test_chat_postprocessors.py tests/api/test_chat_source_selection.py tests/api/test_chat_hook_builders.py tests/api/test_chat_service.py -q` → `120 passed`
   - 函数级扫描显示 `_build_targeted_question_signals(...)` 已压到约 `32` 行，`_compute_targeted_structural_bonuses(...)` 已压到约 `15` 行；并新增了 direct helper 测试，覆盖 role/scope/preview/negative signal 与 structural gating 语义
6. **model fallback orchestration 主链路减重**
   - `python -m pytest tests/api/test_model_service.py -q` → `22 passed`
   - `python -m pytest tests/api/test_model_service.py tests/api/test_chat_service.py tests/api/test_agent_tools.py tests/api/test_agent_runtime.py -q` → `113 passed`
   - 函数级扫描显示 `attempt_model_fallback(...)` 已压到约 `50` 行，并新增了 base-status / candidate-probe / success-finalize / failed-finalize helper；同时补了 direct helper 测试与 non-recoverable 不探测 candidate 的回归断言
7. **chat query orchestration 主链路减重**
   - `python -m pytest tests/api/test_chat_query_flow.py -q` → `11 passed`
   - `python -m pytest tests/api/test_chat_query_flow.py tests/api/test_chat_service.py tests/api/test_model_service.py -q` → `113 passed`
   - 这轮把 `chat_service.query(...)` 里的 fallback retry、history/evidence/model_health result assembly，以及 identifier-gap / refusal pruning / postprocessor 尾段分支继续下沉到 `chat_query_flow.py` 的 `execute_query_with_model_fallback(...)`、`build_query_result(...)`、`finalize_query_answer(...)` helper，并补了 fallback applied / fallback 未生效直抛 / result assembly / refusal-tail orchestration 的纯函数测试

这意味着：

- 第 6 条“refusal / negative contract 覆盖不足”虽然还不能报完成，但现在已经不是只有 refusal gate，而是 refusal + answerable follow-up 都有正式门槛；
- 第 7 条“Prompt 契约偏弱、后处理 heuristic 太重”虽然仍是部分完成，但已经开始从 classifier 误判、评分函数减重、orchestration 拆分、empty-source negative-contract 边界修复、source minimization helper 化、signals / structural bonus helper 化、fallback orchestration helper 化，以及 query orchestration helper 化八个层面做真实收口。

---

## 8. 被追问时最稳的回答模板

### 8.1 如果被问“为什么很多指标是 1.0？”

推荐回答：

> 我不会把 1.0 讲成系统对所有真实场景都完美，而是讲成当前 semireal / layered suite 下我定义的主能力闭环已经打通。为了避免刷题式 1.0，我不仅看 case pass rate，还持续补 refusal / negative contract gate、history-grounded answerable follow-up gate、startup / docker / cleanup 契约，以及更细的 postprocessor / classifier 回归。也就是说，这些 1.0 不是让我停止工作，而是让我更清楚下一步该去补哪类 hard negative 和工程边界。

如果对方追问“那为什么 refusal / negative-contract 还不是满分完成态”，可以补一句：现在我已经把 **全局 marker gate + per-modality marker gate + runner contract gate** 串起来了，所以当前缺口不再是‘有没有 gate’，而是‘真实 hard negative 和 semireal refusal 还可以继续扩厚’。

### 8.2 如果被问“现在是不是都做完了？”

推荐回答：

> 不是。我会主动区分能力完成度和工程完成度。能力层面，single-kb scope、evidence / preview、请求级参数、query/history 解耦和 layered eval 已经闭环；工程层面，legacy 兼容层、Docker / startup 统一、hard negative 覆盖、heuristic 降权、文档和产物治理还在继续推进。

### 8.3 如果被问“你下一步最想补什么？”

推荐回答：

> 我下一步最想继续补三件事：第一，继续增强 answerable follow-up / semireal hard negative 的真实多轮覆盖；第二，继续降低 prompt / heuristic 的隐式复杂度；第三，把 startup / docker / cleanup / docs 的同步机制从“可用”继续收口成“更稳”。

---

## 9. 当前最诚实的边界表达

建议固定主动讲下面三点，不要等面试官逼问：

1. **能力完成度高于工程完成度**：核心能力闭环已经站稳，但工程收口仍在继续；
2. **评测通过不等于所有真实场景都完美**：当前要继续补 hard negatives、answerable / refusal 的 semireal 多轮追问和更强 smoke；
3. **模块化不等于 heuristic 已经消失**：复杂度已经被拆开，但还没彻底变成“纯 prompt / 纯契约”的简单系统。

这三句话会显得你既有结果，也有边界意识。

---

## 10. 下一步最值得继续推进的三件事

1. **继续减少 heuristic overlap**：`model_service.py` 的 fallback orchestration，以及 `chat_service.query(...)` 的 query orchestration / refusal-tail orchestration 已各做一轮 helper 化，下一步优先继续收口 `chat_service.py` 里的剩余 answer assembly，以及 targeted-fact 与 multi_fact_merge 的重叠边界；
2. **继续增强 answerable follow-up / semireal hard negative**：让正向与负向多轮场景都不只是 contract pass，而是更接近真实追问；
3. **继续做工程收口**：统一 startup / docker / requirements / cleanup / docs 的最终口径。

---

## 11. 最后的一句话收口

> 如果把 1~30 轮问题压成一句最准确的话，那就是：我已经把这个项目从“能力雏形”推进到了“能力闭环 + 契约闭环 + 证据闭环”，而现在正在继续把工程完成度追上来。
