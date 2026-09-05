# 20260821 Project Audit Remediation Report Script

## 1. 文档用途

这份材料是当前**长讲法 / 5 分钟汇报底稿**，用于把当前线程里 1~12 项核心问题和 30 轮审计结论整理成一份更适合口头表达的版本。它不替代 `issues-summary / status-matrix / test-report`，也不再重复维护“为什么很多指标是 1.0”这类追问答案的长正文：

- 如果只需要 30 秒 / 2 分钟口播，优先看 `20260821-project-audit-remediation-interview-brief.md`；
- 如果要核对总表和当前状态，不要反过来拿本文替代 `20260821-project-audit-remediation-issues-summary.md`；
- 如果要单独讲“1~30 轮问题最终怎么收口”，补看 `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md`；
- 如果要逐项查某条问题的关键文件和命令，补看 `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-evidence-cheat-sheet.md`；
- 如果汇报结束后进入追问，统一跳转 `docs/interview/ThinkRAG_面试问答.md`；
- 如果要逐项查证据，再看 `20260821-project-audit-remediation-status-matrix.md` 与 `20260821-project-audit-remediation-test-report.md`。

建议搭配阅读顺序：

1. `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-interview-brief.md`
2. `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-issues-summary.md`
3. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md`
4. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-evidence-cheat-sheet.md`
5. `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-test-report.md`
6. `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-status-matrix.md`

## 2. 当前统一结论

一句话版本：

> 这个项目现在**主能力闭环已经成立**：多知识库 scope isolation、evidence / preview 返回、layered eval 分层评测都能讲；当前 semireal layered suite 是 `153 / 153`，chat 关键回归是 `114 passed`，全量非慢测回归是 `1299 passed, 4 deselected`。但工程完成度还没有追平能力完成度：cleanup 侧已经做到 file-mode / directory-mode 均已回到 `managed_count = 0`，后续重点转为防回脏、定期巡检与受控 apply 预案固化；同时 legacy 入口、Docker runtime baseline、以及 chat_service 里剩余的 targeted-fact orchestration / hook builder 还要继续收口。

## 3. 5 分钟汇报讲稿

### 3.1 开场定位

这个项目不是一个简单的“把模型接到文档上”的 demo，而是一个本地知识库助手系统。我这轮工作的重点，不是单点改个 prompt，而是把下面几件事做成**系统能力**：

1. **多知识库作用域约束**：请求在哪个 KB 里问，就必须在那个 KB 范围内答；
2. **evidence / preview 链路**：回答不仅要对，还要能返回证据和前端可预览定位；
3. **分层评测体系**：把 Smoke / Main / Hard 分开，让环境回归、主发布 gate、边界 bug hunting 不是一锅粥；
4. **工程治理**：包括启动脚本、requirements profile、根目录临时产物治理和对外文档口径收敛。

### 3.2 我这轮实际解决了什么

这轮我主要把 12 个问题重新梳理成三类：

#### 第一类：已经修通、可以放心讲

1. **basic 模式和 single_kb 约束冲突**已经修掉了。现在 `basic` / `knowledge` 都要求显式 active KB，不再把 basic 伪装成全局检索。
2. **QueryRequest 请求级参数**已经真正打进 chat 主链路。`top_k / response_mode / use_reranker / top_n / reranker_model` 不再只是 schema 字段，而是已经形成 schema → route → runtime query engine effective config → semireal smoke → frontend API 的闭环证据。
3. **前端 query 成功和 history 成功绑死**也修掉了。现在 query 成功优先，history 失败只会给 notice，不会把整次问答判成失败。
4. **主评测路径已经闭环**。当前 layered suite 是 `153 / 153`，说明 scope、evidence、preview、cross-source fact 这些核心能力是闭合的。

#### 第二类：已经明显收敛，但还不能说完全结束

1. **启动链路 / 桌面链路硬编码**已经大幅收敛。主脚本不再依赖旧绝对路径，端口也支持覆盖，但历史文档和部分 artifact 仍然保留旧口径。
2. **项目主入口不统一**的问题，也从“主线混乱”收敛成“主线已统一、遗留入口还在”。README 和 runbook 主线已经统一到 `FastAPI + React + Electron`，但 `app.py` / `frontend/` / `.streamlit/` 还留在仓库中。
3. **Docker / requirements / 启动口径漂移**已经从“minimal 语义不诚实”进一步定位到了更具体的依赖根因：`requirements-runtime.txt` 曾引入顶层 `llama_index` metapackage，额外拉起 `llama-parse / llama-cloud-services / llama-cloud`。当前已改成 `llama-index-core==0.11.19` + 显式 integrations，并把 `langchain-core==0.3.63` / `langchain-text-splitters==0.3.8` 显式 pin 住；最新 dry-run 已确认不再出现那条云侧依赖链。与此同时，`scripts/docker_smoke.py` 默认也改成让 Docker 自分配 loopback host port，再通过 `docker port` 反查映射，避免 smoke helper 自身复现宿主机端口竞争。
4. **评测 harness 的 refusal / negative contract 覆盖**不再像之前那么弱了。现在 `eval_v7`、`eval_v8_main`、`eval_v8_hard` 已经有更明确的拒答/负向题分布，而且 fixture schema 里还加了 `minimum_cases_per_judge_dimension`，避免“指标是 1.0 但其实每个 judge 维度只测了很少题”。更关键的是，`chat_eval_runner` 已把 contract gate 直接联动到最终 `run_passed`：单题 case 即便都过，只要 required refusal marker 或 negative contract coverage 不满足，整次运行仍会被判失败。
5. **Prompt / heuristic 方向**也不再是“完全没动”。现在已经有三批真实模块化：
   - source projection → `chat_source_answers.py`
   - answer repair → `chat_answer_repair.py`
   - composite answers → `chat_composite_answers.py`
   `chat_service.py` 也已经从 `1696` 行进一步压到 `1166` 行。

#### 第三类：仍然是下一步重点

1. **targeted-fact orchestration 仍偏重**。这块还在 `chat_service.py` 里承担较多 scoring / source-selection 逻辑。
2. **hook builder / dependency registry 需要整理**。现在 builder 已经开始变多，不整理会从“巨石 service”变成“分散 builder”。
3. **legacy 入口和历史文档还没完全收口**。这不影响主路径运行，但会影响工程完成度和新同学理解成本。
4. **根目录治理已经从 file-mode 问题收敛成 directory-mode backlog 问题**。现在 file-mode 已清到 `0`，但 directory-mode 已清零（`managed_count = 0`）。
5. **Docker runtime baseline 的完整 smoke 仍要补**。helper、端口竞争和顶层 metapackage 根因已经收口，但正式 runtime / eval 口径仍偏重。

### 3.3 我怎么证明不是只会讲故事

我不是只给了一个“应该差不多可以”的印象，而是有几类真实证据：

1. **评测结果**
   - Layered suite：`153 / 153`
   - Smoke：`24 / 24`
   - Main：`90 / 90`
   - Hard：`36 / 36`
2. **主链路回归**
   - chat 关键回归：`114 passed`
   - QueryRequest route / scope：`19 passed, 2 warnings`
   - QueryRequest semireal smoke：`11 passed, 2 warnings`
   - OpenAPI answer / search 参数边界：`12 passed, 2 warnings`
3. **Prompt / heuristic 与 layered eval 增量回归**
   - `98 passed`
   - `49 passed`
   - `41 passed`
   - `chat_eval_runner` 现在会把 contract gate 直接纳入最终 `run_passed`，单题全过不再等于 suite 通过
4. **工程治理回归**
   - 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约：`83 passed`
   - Docker smoke helper 契约：`20 passed`
   - startup / docker helper / repo hygiene bundle：`108 passed`
   - 全量非慢测：`1299 passed, 4 deselected`
5. **仓库治理事实**
   - file-mode `managed_count = 0`
   - directory-mode `managed_count = 0`
6. **follow-up 覆盖摘要**
   - `history_grounded_case_count = 6`，且 `markdown / pdf / image_ocr` 各 `2` 条
   - `126 passed, 2 warnings` 的 semireal refusal follow-up 回归已覆盖 Markdown / PDF / Image OCR
   - 所以现在不是只有 refusal hard negative，而是 answerable follow-up + refusal follow-up 都有正式证据

### 3.4 收口话术
- `153 / 153` layered suite
- `114 passed` chat 相关关键回归
- `98 passed`、`49 passed`、`41 passed` Prompt / heuristic 模块化回归
- `83 passed` 启动 / 文档 / requirements / cleanup / repo hygiene 契约
- `1299 passed, 4 deselected` 全量非慢测
- `history_grounded_case_count = 6` + `126 passed, 2 warnings` semireal refusal follow-up
## 4. 12 个问题的 1 页压缩表

| # | 当前状态 | 最短解释 |
| --- | --- | --- |
| 1 | 已修 | `basic` / `knowledge` 都显式绑定 active KB，不再伪装成全局检索 |
| 2 | 基本收敛 | 启动主路径不再依赖旧绝对路径，剩余问题主要在历史文档与 artifact |
| 3 | 基本收敛 | README / runbook / 启动脚本主线已统一到 `FastAPI + React + Electron`，legacy 入口仍兼容保留 |
| 4 | 已修并补强到 semireal smoke | `top_k / response_mode / use_reranker / top_n / reranker_model` 现在不仅进入 query engine，而且已有 route + semireal smoke + frontend API 闭环断言 |
| 5 | 已修并持续拆分 | query 成功优先，history 写回失败只做 notice |
| 6 | 进一步收敛 | refusal 与 negative contract 已形成 smoke / main / hard 三层 gate，后续重点转为 OCR / preview hygiene / source_count 负向题继续补强 |
| 7 | 部分收敛 | source projection、answer repair、composite answers 已独立模块化；剩余重点是 targeted-fact orchestration |
| 8 | 持续收敛 | Docker 默认口径已回到 `runtime + api`，metapackage 根因与 smoke helper 端口竞争已收口，但完整 runtime / eval smoke 仍待补 |
| 9 | 部分收敛 | file-mode / directory-mode 均已清到 `0` |
| 10 | 部分收敛 | 审计目录材料已成型，但历史长文和旧 artifact 仍需继续收口 |
| 11 | 已收敛 | 临时产物治理能力已建立并被真实执行验证，当前 file-mode / directory-mode 均已回到 `managed_count = 0`，治理重点转为后续重点转为防回脏、定期巡检与受控 apply 预案固化 |
| 12 | 已整理 | 面试话术已经可讲，但要统一对外引用材料 |

## 5. 汇报后追问跳转卡

本文只保留**标准汇报稿**，不再重复维护 Q1 / Q2 / Q3 / Q4 的完整长答案。汇报结束后如果进入追问，统一跳转 `docs/interview/ThinkRAG_面试问答.md`：

- “为什么现在很多指标是 1.0？” → 看该文 **第五节：如果面试官质疑“为什么现在很多指标是 1.0？”**；
- “你具体是怎么把分数做上去的？” → 看该文 **第六节：如果继续追问“你是怎么把分数做上去的？”**；
- “既然都 1.0 了，为什么还说工程没完成？” → 看该文 **第九节：如果面试官问“项目现在是不是已经完全 finished？”**；
- “OCR 指标重要不重要？” → 看该文 **第十一节：如果被问到 OCR 指标重要不重要**；
- “grounding / evidence / preview / scope 是什么？” → 看该文 **第七节：grounding / evidence / preview / scope 四个指标怎么解释**。

标准使用方式建议固定成两段：
1. **先按本文第 3 节和第 6 节做 5 分钟汇报**；
2. **再按问答主稿处理追问，不要在本文继续维护成片问答正文**。

## 6. 汇报 PPT 建议结构

### 第 1 页：项目定位
- 本地知识库助手
- FastAPI + React + Electron
- 多 KB + evidence / preview + layered eval

### 第 2 页：这轮解决的核心问题
- basic / single_kb 契约统一
- QueryRequest 参数进入主链路，并已补到 semireal smoke
- query/history 解耦
- layered suite 达到 `153 / 153`

### 第 3 页：当前验证结果
- `153 / 153` layered suite
- `108 passed, 2 warnings` chat 相关关键回归
- `90 passed`、`49 passed`、`38 passed, 2 warnings` Prompt / heuristic 模块化回归
- `16 passed`、`12 passed`、`31 passed, 2 warnings` layered eval contract refresh（v7 smoke 已补齐 negative contract gate，且 `run_passed` 已显式纳入 contract gate）
- `72 passed` 启动 / 文档 / requirements / cleanup / repo hygiene 契约
- `1208 passed, 4 deselected, 2 warnings` 全量非慢测
- `history_grounded_case_count = 6`，三模态各 `2` 条
- `126 passed, 2 warnings` semireal refusal follow-up（Markdown / PDF / Image OCR）

### 第 4 页：工程治理结果
- 根目录三轮实际 apply
- 累计归档 `100` 个文件对象
- file-mode `managed_count = 0`
- directory-mode `managed_count = 0`
- runtime dry-run 已不再出现 `llama-parse / llama-cloud-services / llama-cloud / llama-index`
- `chat_service.py` 已从 `1696` 行进一步压到 `1166` 行

### 第 5 页：诚实边界
- legacy 兼容入口仍在（但已默认禁用，需 `KB_ALLOW_LEGACY_STREAMLIT=1` 显式 opt-in）
- 文档历史口径仍需继续收口
- targeted-fact orchestration 仍偏重
- hook builder / dependency registry 待整理
- runtime baseline 仍偏重，完整 Docker smoke 仍待补

### 第 6 页：下一步计划
- 继续拆 targeted-fact orchestration
- 整理 hook builder / dependency registry
- 补 Docker runtime / eval 的真实 build + run smoke
- 继续补 OCR / preview negative eval
- 继续清理 directory-mode backlog

## 7. 对外统一引用材料

以后如果只允许发 4 个路径，优先发固定四件套：

1. `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-interview-pack.md`
2. `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-issues-summary.md`
3. `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-test-report.md`
4. `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-status-matrix.md`

`interview-brief.md` 和本文保留为口播 / 长讲辅助材料，不再占用固定四件套名额。

## 8. 结论

这份材料整理完成后，后续对外表达可以统一成一句话：

> **项目已经把主能力闭环和评测闭环做出来了，当前更值得继续投入的不是“把数字讲得更花”，而是把工程完成度继续补上去。**


