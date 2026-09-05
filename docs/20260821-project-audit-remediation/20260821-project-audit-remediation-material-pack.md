# 20260821 Project Audit Remediation Material Pack

## 1. 这份材料是干什么的

如果你只想打开 **一份审计入口文件**，快速知道：

- 这个项目当前真实修到了什么程度；
- 1~12 项核心问题分别处于什么状态；
- 哪些内容可以放心讲，哪些必须诚实保留边界；
- 面试 / 汇报时 30 秒、2 分钟、5 分钟怎么说；
- 下一步继续整改应该先做什么；

那就先看这份 `material-pack`。

但要注意：
- 它更适合作为**审计 / 复盘 / 维护入口包**；
- 如果只需要一份更聚合的面试 / 汇报成稿，应优先看 `interview-pack`；
- 如果只需要 30 秒 / 2 分钟口播主稿，应优先看 `interview-brief`；
- 如果需要更长的追问展开，再看 `docs/interview/ThinkRAG_面试问答.md`。

它不替代 `issues-summary / status-matrix / test-report / interview-brief / report-script`，而是把这些材料压成一个**统一入口包**。

## 2. 一句话结论

> 这个项目已经把多知识库 scope isolation、evidence / preview 返回、layered eval 分层评测做成了主能力闭环；当前 semireal layered suite 是 `153 / 153`。但工程完成度仍低于能力完成度，当前剩余重点主要是 legacy 入口与历史文档收口、directory-mode backlog、Docker runtime / eval 完整 smoke，以及 `chat_service.py` 中剩余的 targeted-fact orchestration 与 hook builder 分散问题。

## 3. 这一轮整理完成后的固定交付包

如果你现在要把这批材料真正收口成一套可交付包，建议以后固定发这四份：

1. `20260821-project-audit-remediation-interview-pack.md`
   - 只看一份就能开口讲；
   - 适合面试前最后过一遍。
2. `20260821-project-audit-remediation-issues-summary.md`
   - 1~12 项问题总表；
   - 适合解释“哪些已修、哪些还在收口”。
3. `20260821-project-audit-remediation-test-report.md`
   - 统一验证口径；
   - 适合回答“这些结论凭什么成立”。
4. `20260821-project-audit-remediation-status-matrix.md`
   - 继续整改时代码侧的 source of truth；
   - 适合回答“下一步到底先改什么”。

也就是说，现在这批材料已经不是散文档，而是可以稳定复用的 **固定四件套**：

- `interview-pack` 负责说；
- `issues-summary` 负责总表；
- `test-report` 负责证据；
- `status-matrix` 负责继续做事。

## 4. 当前最可信的数字口径

统一优先讲下面这组：

- Layered suite：`153 / 153`
- Smoke：`24 / 24`
- Main：`90 / 90`
- Hard：`36 / 36`
- Chat 关键回归：`114 passed`
- 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约：`83 passed`
- Docker smoke helper 契约：`20 passed`；startup / docker helper / repo hygiene bundle：`108 passed`
- QueryRequest route / scope 闭环：`19 passed, 2 warnings`
- QueryRequest semireal smoke 非默认参数：`11 passed, 2 warnings`
- OpenAPI answer / search 参数边界回归：`12 passed, 2 warnings`
- 全量非慢测：`1299 passed, 4 deselected`
- Prompt / heuristic 近期模块化回归：
  - `python -m pytest tests/api/test_chat_composite_answers.py tests/api/test_chat_postprocessors.py tests/api/test_chat_service.py -q` → `98 passed`
  - `python -m pytest tests/api/test_chat_question_intents.py tests/api/test_chat_targeted_fact.py tests/api/test_chat_source_answers.py tests/api/test_chat_answer_repair.py -q` → `49 passed`
- 评测 harness 最近补强：
  - `python -m pytest tests/test_rag_quality_eval_dataset_v7.py tests/test_rag_quality_eval_builders.py tests/test_rag_quality_fixtures.py -q` → `16 passed`
  - `python -m pytest tests/test_rag_quality_eval_dataset_v8.py -q` → `12 passed`
  - `python -m pytest tests/api/test_chat_eval_runner.py tests/test_rag_quality_eval_dataset_v8.py -q` → `41 passed`
  - 说明：`chat_eval_runner` 现在已把 refusal / negative contract 的 contract gate 直接纳入最终 `run_passed`，且 `chat_eval_contracts.py` 已补独立纯函数单测，不再只是报告摘要展示
- 根目录治理：file-mode `managed_count = 0`；directory-mode `managed_count = 0`

### 4.1 本轮额外复核后，可以更稳地讲的三件事

1. **QueryRequest 参数已经不只是“接口能接住”**
   - `tests/api/test_runtime_model_loading.py` 里已经有两条关键证据：
     - `test_build_query_engine_loads_missing_index_and_forwards_settings`
     - `test_build_query_engine_request_params_override_saved_settings`
   - 它们证明 `RuntimeState.build_query_engine(...)` 会把默认配置和请求级覆盖后的 effective kwargs 真实传给 `create_query_engine(...)`。
2. **前端 query/history 解耦已经是稳定主契约**
   - `webapp/src/domain/chatWorkflow.js`、`webapp/src/pages/useAgentChatWorkspace.js` 与 `tests/scripts/test_webapp_contracts.py` 共同证明：query 成功优先、history 失败只降级成 notice、本地消息仍有兜底。
3. **当前最该继续拆的是复杂度热点，而不是重复补边界单测**
   - `api/services/chat_service.py`：`1166` 行；
   - `api/services/chat_targeted_fact.py`：`838` 行；
   - `api/services/kb_service.py`：`2954` 行；
   - `webapp/src/pages/AgentPage.jsx`：`792` 行；
   - `webapp/src/pages/useAgentChatWorkspace.js`：`251` 行；
   - `webapp/src/pages/agent-page/QaWorkbench.jsx`：`281` 行。

## 5. 12 项核心问题现在怎么讲

| # | 问题 | 当前状态 | 最短讲法 |
| --- | --- | --- | --- |
| 1 | basic 模式和 single_kb 约束冲突 | 已修 | `basic` / `knowledge` 都显式绑定 active KB，不再伪装成全局检索 |
| 2 | 启动链路 / 桌面链路存在硬编码 | 基本收敛 | 主路径已不依赖旧绝对路径，端口与 runtime root 可配置，剩余问题主要在历史文档与 artifact |
| 3 | 项目主入口不统一 | 基本收敛 | README / runbook / 脚本主线已统一到 `FastAPI + React + Electron`，legacy 入口已收口成默认禁用、需 `KB_ALLOW_LEGACY_STREAMLIT=1` 显式 opt-in 的兼容入口 |
| 4 | QueryRequest 参数未完整打入 chat 主链路 | 已修并补强 | 现在已有 schema → route → query engine → semireal smoke → frontend API 闭环证据；`tests/api/test_runtime_model_loading.py` 还额外证明了 default / request override 的 effective config 会真实传给 `create_query_engine(...)`；OpenAPI 也已明确为 `/search` 只支持 `top_k`、`/answer` 额外支持 `response_mode / use_reranker / top_n / reranker_model` |
| 5 | 前端把 query 成功和 history 成功绑死 | 已修 | query 成功优先，history 失败只作为 notice，不再整次判错；当前主链路已经形成 `chatWorkflow.js` → `useAgentChatWorkspace.js` → `QaWorkbench` 的稳定透传 |
| 6 | 评测 harness 对 refusal / negative contract 覆盖不足 | 进一步收敛 | `eval_v7` 现在也已显式补齐 negative contract gate，三层数据集都已覆盖 refusal + negative contract；`eval_v8_main` 当前 `history_grounded_case_count = 6`，markdown / pdf / image_ocr 各 `2` 条，semireal refusal follow-up 也已覆盖 Markdown / PDF / Image OCR 三模态；`chat_eval_runner` 也已把 contract gate 直接联动到最终 `run_passed`，但 OCR / preview / source_count 的负向题还可继续补 |
| 7 | Prompt 契约偏弱，后处理 heuristic 太重 | 部分收敛 | source projection、answer repair、composite answers 已独立模块化；剩余重点是 targeted-fact orchestration 与 hook builder 分散。当前更真实的风险已经从“全部堆在 chat_service”转成“chat_targeted_fact.py 也在长大” |
| 8 | Docker / requirements / 端口 / 启动脚本漂移 | 持续收敛 | runtime baseline 已从顶层 `llama_index` metapackage 回退，最新 dry-run 不再回流 `llama-parse / llama-cloud-services / llama-cloud / llama-index`，smoke helper 的 host-port 竞争也已收口，但 runtime / eval 的完整 Docker smoke 仍待补 |
| 9 | 仓库根目录临时文件、日志、调试脚本较多 | 部分收敛 | file-mode / directory-mode 均已归零 |
| 10 | 文档闭环不够满 | 部分收敛 | 20260821 审计目录已能统一引用，但历史长文、旧 artifact 和旧叙事还没完全收口 |
| 11 | 日志与临时产物治理需要规范化 | 已收敛 | 治理能力与单测已建立，当前 file-mode / directory-mode 均已回到 `managed_count = 0`，重点转为后续重点转为防回脏、定期巡检与受控 apply 预案固化 |
| 12 | 面试表述需要区分能力完成度和工程完成度 | 已整理 | 面试 brief / report script / issues summary 已可直接复用 |

## 6. 这份材料负责什么 / 不负责什么

### 6.1 它负责什么

- 给出当前统一的一句话结论；
- 汇总当前最可信的数字口径；
- 用一张表压住 1~12 项核心问题的当前状态；
- 告诉读者下一步还该优先做什么。

### 6.2 它不负责什么

- **聚合版面试 / 汇报成稿**：优先看 `20260821-project-audit-remediation-interview-pack.md`；
- **30 秒 / 2 分钟口播**：优先看 `20260821-project-audit-remediation-interview-brief.md`；
- **5 分钟长讲法**：优先看 `20260821-project-audit-remediation-report-script.md`；
- **逐项证据矩阵**：优先看 `20260821-project-audit-remediation-status-matrix.md`；
- **详细验证命令与测试记录**：优先看 `20260821-project-audit-remediation-test-report.md`。

也就是说，`material-pack` 现在只保留**入口包 / 阅读地图 / 当前快照**职责，不再重复维护长段口播正文。

## 7. 按场景怎么读

### 7.1 面试前 5~10 分钟

1. `20260821-project-audit-remediation-interview-pack.md`
2. `20260821-project-audit-remediation-interview-brief.md`
3. `docs/interview/ThinkRAG_面试问答.md`
4. `20260821-project-audit-remediation-test-report.md`

### 7.2 做项目汇报 / 周报

1. `20260821-project-audit-remediation-interview-pack.md`
2. `20260821-project-audit-remediation-report-script.md`
3. `20260821-project-audit-remediation-test-report.md`
4. `20260821-project-audit-remediation-status-matrix.md`

### 7.3 继续整改 / 接手维护

1. `20260821-project-audit-remediation-status-matrix.md`
2. `20260821-project-audit-remediation-issues-summary.md`
3. `20260821-project-audit-remediation-test-report.md`
4. `20260821-project-audit-remediation-plan.md`

## 8. 下一步继续整改优先级

### P0
1. 继续拆 `api/services/chat_targeted_fact.py` 的 orchestration / scoring / source-selection 邻近逻辑，并同步整理 hook builder / dependency registry；
2. 把目录治理从“清 backlog”切到“防回脏 + 定期巡检 + 受控 apply 预案”；当前 file-mode / directory-mode 均已回到 `managed_count = 0`；
3. 继续补 Docker runtime / eval 的真实 `docker build + docker run` smoke。

### P1
4. 开始拆 `api/services/kb_service.py`；
5. 前端继续收口时优先压 `AgentRuntimePanel` 或补 `QaWorkbench` 交互测试，而不是继续回头补 query/history 主契约；
6. 扩 refusal / weak-signal / preview hygiene 的 layered eval 样本分布；
7. 继续收口 `NorthAgent / ThinkRAG / Foxglove` 多套兼容命名；
8. 继续压缩 `docs/project.md` 与审计目录内部的平行叙事。

## 9. 结论

这份 `material-pack` 现在已经可以稳定承担**统一入口包**角色：

- **能导航**：知道先看哪份；
- **能定口径**：知道当前最可信数字和最短结论；
- **能分工**：知道 brief / report-script / status-matrix / test-report 分别负责什么；
- **能继续整改**：知道下一步该优先收哪里。

但它的定位仍然是**统一入口包**，不是口播主稿本身；详细口播优先看 `interview-brief` 与 `report-script`，长问答展开优先看 `docs/interview/ThinkRAG_面试问答.md`。也就是说，现在“把这些整理完成”的目标，在材料层已经形成了更稳定的 **固定四件套 + 一主多从** 结构，而不是继续让每份材料都重复维护同一套长正文。


