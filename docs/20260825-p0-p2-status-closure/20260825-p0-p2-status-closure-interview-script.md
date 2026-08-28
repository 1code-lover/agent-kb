# 20260825 P0/P2 Status Closure Interview Script

## 1. 这份文档的定位

这份 `interview-script` 是基于：

- `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-master-guide.md`
- `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-complete-guide.md`
- `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-status-report.md`
- `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-rounds-rollup.md`
- `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-evidence-cheat-sheet.md`
- `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-overlap-matrix.md`
- `docs/interview/ThinkRAG_面试问答.md`

并把 `docs/20260821-project-audit-remediation/` 保留为**深证据 / 历史审计归档**后，整理出的**当前更适合讲“1~30 轮问题最终收口状态”的固定话术**。

使用建议：

1. **先定当前总入口**：如果怕材料散，先看 `20260825-p0-p2-status-closure-master-guide.md`；
2. **先一次性过完整讲稿**：看 `20260825-p0-p2-status-closure-interview-complete-guide.md`；
3. **30 秒 / 2 分钟开场**：看本文第 2 节、第 3 节；
4. **5 分钟固定汇报**：看本文第 4 节；
5. **被点问单条问题 / 临时要查证据**：看 `20260825-p0-p2-status-closure-evidence-cheat-sheet.md`；
6. **被继续追问**：跳到本文第 5 节；
7. **要核对真实证据**：回看 `20260825-p0-p2-status-closure-status-report.md` 与 `20260825-p0-p2-status-closure-overlap-matrix.md`。

---

## 2. 30 秒版本

我做的不是一个简单把模型接到文档上的 demo，而是一个本地优先的知识库助手。当前主线已经统一到 **FastAPI + React(Vite) + Electron + LlamaIndex**，核心闭环包括：

- 单知识库 scope 约束；
- evidence / preview 返回；
- 请求级 QueryRequest 参数真正生效；
- 前端 query 成功与 history 写回解耦；
- 分层评测和契约测试持续回归。

如果要诚实一点说，**现在能力完成度高于工程完成度**：主能力已经闭环，但 legacy 兼容入口、文档统一、cleanup、负向评测和 heuristic 复杂度治理还在继续推进。

---

## 3. 2 分钟版本

我主要把这个项目做成了三层闭环。

### 3.1 第一层：产品能力闭环

现在用户不是对“全局资料”盲查，而是对**显式选中的 active KB**发起问答；回答会返回 evidence / preview 元数据，便于核对来源，而不是只给一句自然语言答案。

### 3.2 第二层：系统契约闭环

我重点修了几条容易在真实产品里出问题的契约：

1. `basic` / `knowledge` 模式都显式绑定 active KB，不再伪装成“全局检索”；
2. QueryRequest 里的 `top_k / response_mode / use_reranker / top_n / reranker_model` 已经真正打进 route + runtime query engine；
3. query 成功不会再因为 history 慢一拍就让前端把整次问答判成失败。

### 3.3 第三层：验证闭环

这些不是口头约定，我用测试和评测去证明：
<!-- audit-sync:closure-interview-validation-lines -->
- scope / open api / chat 主链路相关测试：`118 passed`
- QueryRequest 覆盖 runtime override：`2 passed, 32 deselected`
- refusal / eval contract / dataset v8：`54 passed`
- 启动 / 文档入口 / legacy / audit sync：`75 passed`
- Docker / requirements / startup contracts：`49 passed`
- cleanup / repo hygiene：`27 passed`
- 前端 `agentExperience + chatWorkflow`：`21 pass`
我不想把这些工作讲成“靠经验感觉变好了”，所以我比较强调验证证据。当前这轮核查里：
<!-- audit-sync:closure-report-validation-lines -->
- scope / open api / chat 主链路相关测试是 `118 passed`
- QueryRequest runtime override 是 `2 passed, 32 deselected`
- refusal / negative contract / dataset v8 是 `54 passed`
- 启动 / 文档 / legacy / audit sync 是 `75 passed`
- Docker / requirements / startup contracts 是 `49 passed`
- cleanup / repo hygiene 是 `27 passed`
- 前端状态与 experience 契约是 `21 pass`
我会落到四件具体事上：

1. 把 `basic` / `knowledge` 模式和单知识库 scope 统一，不再让前端语义和后端约束互相打架；
2. 把 QueryRequest 请求级参数真正打进 runtime query engine，而不是只停留在前端透传；
3. 把 query 成功和 history 成功解耦，避免 UI 因为 history 慢一拍把刚返回的结果覆盖掉。
4. 把 targeted-fact 的超长评分逻辑拆成可测试纯函数，并把 targeted-fact orchestration、signals、structural bonus 都继续收口到可回归 helper。
5. 把 source minimization 从大 if/while 逻辑拆成显式 helper + 独立契约测试，避免后处理阶段继续堆隐式 heuristic。
6. 把 model fallback orchestration 从大 for/if 探测逻辑拆成显式 helper，并补 non-recoverable / discovery-only 的回归保护。
7. 再把 `chat_service.query(...)` 中的 fallback retry、history/evidence/model_health result assembly，以及 identifier-gap / refusal pruning / postprocessor 尾段分支下沉到 `chat_query_flow.py` helper，并补 query_flow 纯函数回归。

这四件事都不是“调 prompt 试试看”，而是直接影响产品边界、系统稳定性和用户体验的主链路问题。

### 5.2 如果被问：“那现在是不是都做完了？”

推荐回答：

不是。我会主动区分能力完成度和工程完成度。能力层面，主链路已经闭环并且有自动化回归；工程层面，legacy 兼容层、cleanup、文档统一、负向评测和 heuristic 复杂度治理还在继续推进。我不会把这两者混成一句“都 finished 了”。

### 5.3 如果被问：“为什么很多指标是 1.0？”

推荐回答：

我不会把 1.0 讲成系统对所有真实场景都完美，它只说明我定义的 semireal / contract 能力闭环已经打通。为了避免刷题式 1.0，我会强调：

- 当前不仅看 pass rate，还看 refusal / negative contract，以及 history-grounded answerable follow-up gate；
- 当前不仅有 dataset，还有 route / runtime / UI / cleanup / startup 的工程契约测试；
- 我也明确承认 hard negative 和工程治理还在继续，不会把当前分数包装成“没有剩余问题”。

### 5.4 如果被问：“你下一步最想继续补什么？”

推荐回答：

优先是三件事：

1. answerable follow-up / semireal hard negative 的多轮回归继续补强；
2. prompt / heuristic 隐式复杂度继续下沉，`chat_targeted_fact.py`、`model_service.py` 与 `chat_service.query(...)` 已各做一轮 helper 化，下一步优先继续收口 `chat_service.py` 里剩余的 answer assembly 与 targeted-fact / multi-fact overlap；
3. 文档 / cleanup / audit 的同步机制从“可用”升级到“更稳”。

---

## 6. 讲项目时建议固定使用的结构

以后建议固定按下面顺序讲：

1. **先讲项目定位**：本地优先知识库助手，当前主线是 FastAPI + React(Vite) + Electron + LlamaIndex。
2. **再讲四个能力亮点**：single-kb scope、evidence / preview、请求级参数生效、query/history 解耦。
3. **再讲验证证据**：测试与评测数字。
4. **最后主动讲边界**：能力完成度高于工程完成度。

这样比“沿时间线流水账复盘 1~30 轮”更清晰，也更像一个知道自己在做什么的工程负责人。
