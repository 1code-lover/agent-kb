# 20260821 Project Audit Remediation Guide

## 1. 这份文档是干什么的

这份 guide 用来把 `docs/20260821-project-audit-remediation/` 目录里的材料做成一个**可交付、可导航、可直接使用**的索引，避免后续再出现：

- 不知道先看哪份；
- 面试时混用旧分数和旧口径；
- 汇报时把 `spec / test-report / interview-brief / issues-summary` 的边界讲乱；
- 代码已经继续整改了，但材料还停留在旧版本。

如果你当前更关心**“1~30 轮问题最后怎么收口、面试时该怎么讲”**，除了本目录，也要同步看：

- `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-status-report.md`
- `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md`
- `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-evidence-cheat-sheet.md`
- `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-pack.md`

它们不是替代本目录，而是基于当前工作树做的一轮**P0/P2 状态归档 + 最新面试收口材料**，适合在面试前快速统一“能力完成度高于工程完成度”的表达。

如果你只想记一句话，这个目录当前统一回答的是：

> **项目的主能力闭环已经完成，当前 semireal layered suite 是 `153 / 153`，chat 关键回归是 `114 passed`，全量非慢测回归是 `1299 passed, 4 deselected`；Prompt / heuristic 方向也已经完成 source projection、answer repair、composite answers 三批模块化，但工程尾巴还没收完，当前 cleanup 侧已经做到 file-mode / directory-mode 均已回到 `managed_count = 0`，后续重点转为防回脏、定期巡检与受控 apply 预案固化；同时 targeted-fact orchestration、hook builder 分散，以及 Docker runtime baseline 虽已移除顶层 `llama_index` metapackage 但完整 smoke 仍待补齐。**

## 2. 目录内每份文档怎么用

### 2.1 `20260821-project-audit-remediation-guide.md`

用途：
- 目录导航；
- 统一引用入口；
- 告诉别人“什么时候看哪份”。

### 2.2 `20260821-project-audit-remediation-material-pack.md`

用途：
- 审计 / 复盘 / 维护的单文件总入口；
- 把 12 个问题、最新指标、阅读路径和下一步动作压成一个包；
- 不再重复维护长口播正文，更适合先发给需要快速看全局状态的人。

### 2.3 `20260821-project-audit-remediation-issues-summary.md`

用途：
- 看 1~12 项核心问题和 30 轮审计结论的总表；
- 用一份文档快速掌握“哪些已修、哪些仍在收口”；
- 面试前 10 分钟做总复习；
- 不再继续堆叠长附录正文，附加证据统一跳转 audit-evidence。

### 2.4 `20260821-project-audit-remediation-status-matrix.md`

用途：
- 看 12 个问题当前分别是什么状态；
- 看每个问题的证据、真实结论和下一步；
- 继续按 P0 / P1 / P2 往下整改。

### 2.5 `20260821-project-audit-remediation-test-report.md`

用途：
- 看当前**最新、可信**的测试和评测结果；
- 对外证明“这不是口头说修好了”；
- 回答“现在到底跑了哪些验证”。

### 2.6 `20260821-project-audit-remediation-interview-brief.md`

用途：
- 当前**口播主稿**；
- 30 秒 / 2 分钟口头表达；
- 指标解释；
- “为什么都是 1.0” 和 “heuristic 为什么还重、已经拆到哪” 的回答模板。

### 2.7 `20260821-project-audit-remediation-interview-pack.md`

用途：
- 把 1~12 项核心问题、30 轮审计结论和面试/汇报主话术压成一份更聚合的成稿；
- 面试前如果只看一份文件，优先看它；
- 适合做 30 秒 / 2 分钟 / 5 分钟之间的桥接材料。

### 2.8 `20260821-project-audit-remediation-report-script.md`

用途：
- 5 分钟讲稿；
- 面试官高频追问模板；
- PPT 建议结构；
- 对外材料推荐顺序。

### 2.9 `20260821-project-audit-remediation-spec.md`

用途：
- 作为这轮审计的说明书；
- 统一“为什么这样判断”的背景；
- 给后续继续整改的人提供上下文。

### 2.10 `20260821-project-audit-remediation-audit-evidence.md`

用途：
- 审计证据附录 / 历史增量记录；
- refusal / Docker / startup alias / composite answers 等补充验证归档；
- Desktop build / package / release boundary 说明。

### 2.11 `20260821-project-audit-remediation-plan.md`

用途：
- 明确下一步继续整改的路线；
- 区分 P0 / P1 / P2；
- 防止“评测全绿后就停止推进”。

### 2.12 `../20260825-p0-p2-status-closure/`（目录外补充收口材料）

用途：
- 当你已经看完本目录，想把 **1~12 项问题 / 1~30 轮迭代**压成更适合面试表达的最新说法时，补看这一组；
- `status-report` 负责把当前工作树里的 P0 / P1 / P2 问题重新归到“已收口 / 大体收口 / 部分完成”；
- `interview-script` 负责给出 30 秒 / 2 分钟 / 5 分钟固定讲稿；
- `evidence-cheat-sheet` 负责给出 12 个问题的最短证据索引、关键文件和最值得记住的命令；
- `interview-pack` 负责把 1~30 轮问题压成 6 个主题，不再按轮次流水账复述。

## 3. 不同场景下，应该先看哪几份

### 3.1 面试前 10 分钟快速复习

按这个顺序：

1. `20260821-project-audit-remediation-interview-brief.md`
2. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md`
3. `docs/interview/ThinkRAG_面试问答.md`
4. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-evidence-cheat-sheet.md`
5. `20260821-project-audit-remediation-interview-pack.md`
6. `20260821-project-audit-remediation-test-report.md`

### 3.2 做技术汇报 / 周报

按这个顺序：

1. `20260821-project-audit-remediation-interview-brief.md`
2. `20260821-project-audit-remediation-report-script.md`
3. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-status-report.md`
4. `20260821-project-audit-remediation-issues-summary.md`
5. `20260821-project-audit-remediation-test-report.md`

### 3.3 继续按 P0 / P1 真正改代码

按这个顺序：

1. `20260821-project-audit-remediation-status-matrix.md`
2. `20260821-project-audit-remediation-plan.md`
3. `20260821-project-audit-remediation-spec.md`

### 3.4 需要对外证明“项目不是只会讲故事”

按这个顺序：

1. `20260821-project-audit-remediation-material-pack.md`
2. `20260821-project-audit-remediation-test-report.md`
3. `20260821-project-audit-remediation-status-matrix.md`
4. `20260821-project-audit-remediation-audit-evidence.md`
5. `temp/eval-layered-suite-20260821-targeted-fact-fix-r5/local_multi_kb_eval_v8_layered_suite-suite-report.json`
6. `temp/runtime-report-after-langchain-pin.json`

### 3.5 如果被要求单独讲“1~30 轮问题最后怎么收口”

按这个顺序：

1. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-status-report.md`
2. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md`
3. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-evidence-cheat-sheet.md`
4. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-pack.md`
5. `docs/interview/ThinkRAG_面试问答.md`

## 4. 现在统一应该怎么讲

### 4.1 一句话版

> 这是一个已经把多知识库 scope isolation、evidence / preview 返回和 layered eval 分层评测做成闭环的本地知识库助手；当前主能力已经稳定，但工程治理和长期维护体验还在继续收口。

### 4.2 最容易说错的地方

不要混用下面两种说法：

- “项目已经完全 finished”
- “项目还有很多问题所以不成熟”

更准确的说法应该是：

- **能力完成度已经比较高**；
- **工程完成度还没有追平**；
- **下一步重点是收工程尾巴，而不是重新证明系统能答对题。**

## 5. 当前最关键的数字口径

以后统一优先说下面这组：

- Layered suite：`153 / 153`
- Smoke：`24 / 24`
- Main：`90 / 90`
- Hard：`36 / 36`
- Chat 相关关键回归：`114 passed`
- Prompt / heuristic 模块化回归：`98 passed`、`49 passed`、`41 passed`
- Layered eval contract refresh：`16 passed`、`12 passed`、`31 passed, 2 warnings`（分别对应 v7 refresh / v8 / chat eval runner，且 v7 smoke 已补齐 negative contract gate，`run_passed` 也已显式纳入 contract gate）
- 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约：`83 passed`
- QueryRequest route / scope 闭环：`19 passed, 2 warnings`
- QueryRequest semireal smoke 非默认参数：`11 passed, 2 warnings`
- cleanup 单测：`13 passed`
- Desktop 关键单测：`19 passed`
- Web 关键单测：`16 passed`
- 全量非慢测：`1299 passed, 4 deselected`
- 根目录治理：file-mode `managed_count = 0`；directory-mode `managed_count = 0`
- Docker runtime baseline：默认已经统一到 `INSTALL_PROFILE=runtime` + API 模式；顶层 `llama_index` metapackage 已从 runtime baseline 中移除，最新 dry-run 不再出现 `llama-parse / llama-cloud-services / llama-cloud / llama-index`，但完整 build/run smoke 仍待补齐

## 6. 如果现在要把这批材料整理完成，固定发哪 4 个

推荐固定发这四份：

1. `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-interview-pack.md`
2. `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-issues-summary.md`
3. `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-test-report.md`
4. `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-status-matrix.md`

## 7. 这轮整理完成后，目录算什么状态

当前可以把这个目录理解成：

- **能导航**：知道先看哪份；
- **能证明**：有测试和评测结果；
- **能表达**：有短讲稿和长讲稿；
- **能继续做事**：有总表、状态矩阵和后续计划。

也就是说，这一轮‘把这些整理完成’的目标，在材料层已经基本闭环了；以后对外优先发第 6 节这套固定四件套，再按场景补 `interview-brief` 或 `report-script` 作为辅助口播材料。但对外口径必须同步保留 cleanup 侧已经做到 file-mode / directory-mode 均已回到 `managed_count = 0`、能力完成度高于工程完成度，以及 runtime baseline 已收口但完整 Docker smoke 仍待继续补齐这三个事实。

