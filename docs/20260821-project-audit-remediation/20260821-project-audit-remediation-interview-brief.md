# 20260821 Project Audit Remediation Interview Brief

> 角色定位：
> - 这是当前**面试 / 汇报口播主稿**，30 秒 / 2 分钟回答优先看本文；
> - 如果要专门讲“1~30 轮问题最后怎么收口”，补看 `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md`、`docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-pack.md` 与 `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-evidence-cheat-sheet.md`；
> - 需要展开问答细节时，再看 `docs/interview/ThinkRAG_面试问答.md`；
> - 需要核对证据和验证命令时，再看 `20260821-project-audit-remediation-status-matrix.md` 与 `20260821-project-audit-remediation-test-report.md`。

## 1. 一句话定位

这个项目不是简单的本地问答 demo，而是一个已经做出 **多知识库作用域隔离、证据链返回、preview 预览、分层评测体系** 的本地知识库助手；当前主链路是 **FastAPI + React + Electron**，而工程化收尾仍在继续。

## 2. 最新统一口径

当前建议以后统一这样讲：

- Layered suite：`153 / 153`
- Smoke：`24 / 24`
- Main：`90 / 90`
- Hard：`36 / 36`
- Chat 相关关键回归：`114 passed`
- Prompt / heuristic 模块化近期回归：`98 passed`、`49 passed`、`41 passed`
- 评测 harness 最近补强：`16 passed`、`12 passed`、`31 passed, 2 warnings`
- 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约：`83 passed`
- Docker smoke helper 契约：`20 passed`；startup / docker helper / repo hygiene bundle：`108 passed`
- 全量非慢测：`1299 passed, 4 deselected`
- 根目录治理：file-mode / directory-mode 均已回到 `managed_count = 0`；后续重点转为防回脏、定期巡检与受控 apply 预案固化
- Docker / requirements 当前真实进展：默认已经统一到 `INSTALL_PROFILE=runtime` + API 模式；runtime build 变慢的根因已定位为顶层 `llama_index` metapackage，最新 dry-run 已确认不再出现 `llama-parse / llama-cloud-services / llama-cloud / llama-index`；同时 `scripts/docker_smoke.py` 已切到 Docker 自分配 host port + `docker port` 反查映射，但完整 build/run smoke 仍待补齐
- 当前最真实的剩余问题：**能力完成度高于工程完成度**

## 3. 30 秒版本

我做的重点不是把一个模型简单接上文档，而是把**知识库边界、证据返回、回答质量评测**做成系统能力。现在主路径已经比较稳，当前 semireal layered suite 是 `150 / 150`，说明 scope、evidence、preview、cross-source fact 这些主能力已经闭环。同时，我也做了仓库治理：根目录文件级日志、临时探针和 OCR 草稿脚本已经完成多轮治理并清到 file-mode `0`。现在 cleanup 侧已经做到 file-mode / directory-mode 均已回到 `managed_count = 0`，后续重点转为防回脏、定期巡检与受控 apply 预案固化；legacy 入口、启动口径、文档统一、targeted-fact orchestration、hook builder 分散，以及 Docker runtime baseline 的完整 smoke 证据都还在继续收口。

## 4. 2 分钟版本

我主要做了三类事情：

1. **把核心能力做成闭环**
   - 多知识库单库作用域约束；
   - evidence / preview 返回链路；
   - layered eval，把 Smoke / Main / Hard 分开。
2. **把关键契约做对**
   - `basic` / `knowledge` 模式都显式绑定 active KB；
   - 请求级 QueryRequest 参数已经补成 route + runtime query engine effective config + semireal smoke + frontend API 闭环证据；
   - query 成功不会再因为 history 写回失败而被 UI 整体判成失败。
3. **用测试、评测和工程治理证明这些改动不是拍脑袋**
   - 当前 targeted fact / preview / metrics 相关回归 `114 passed`；
   - Prompt / heuristic 模块化回归 `98 passed`、`49 passed`、`41 passed`；
   - 评测 harness 最近补强 `16 passed`、`12 passed`、`31 passed, 2 warnings`；其中 `eval_v8_main` 当前 `history_grounded_case_count = 6`，markdown / pdf / image_ocr 各 `2` 条，semireal refusal follow-up 也已覆盖 Markdown / PDF / Image OCR 三模态；
   - 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约 `83 passed`；
   - layered suite 当前 `153 / 153`；
   - QueryRequest route / scope 回归 `19 passed, 2 warnings`，semireal smoke 非默认参数 `11 passed, 2 warnings`；
   - 全量非慢测回归 `1299 passed, 4 deselected`；
   - 根目录治理完成多轮 apply，累计归档 `100` 个对象，当前 file-mode dry-run 为 `0`，但 directory-mode 现已清零（`managed_count = 0`）；
   - Docker runtime baseline 已从顶层 `llama_index` metapackage 回退到 `llama-index-core` + 显式 integrations，最新 dry-run 已确认不再回流 `llama-parse` 链。

所以我会把这个项目定义成：

> **主能力闭环和评测闭环都已经成型，而且文件级仓库治理已经开始真正收口；但工程和维护体验还在继续完善。**

## 5. 如果面试官质疑“为什么现在很多指标是 1.0？”

推荐回答：

> 我不会把这个 1.0 讲成“系统对所有真实问题都完美”。它表示的是当前 semireal layered suite 全部通过，也就是我定义的主能力闭环已经打通：scope 没串、evidence 能回、preview 能落、cross-source 题能组装出来。为了避免“只有几道题也能刷出 1.0”，现在 schema 里还加了 `minimum_cases_per_judge_dimension` 这类门槛；最近还把 `eval_v7` smoke 层的 negative contract gate 补回来了，避免只有 main / hard 层才检查范围边界题。同时 refusal / negative contract 也已经形成三层闭环：数据集覆盖 gate、单 case correctness gate、最终报告里的 `refusal_summary` 可见层。更关键的是，单题 case 全过也不等于最终 `run_passed = true`；如果 required refusal marker 或 negative contract coverage 没满足，contract gate 会直接把最终 `run_passed` 拦成 `false`。所以我会主动补一句：工程完成度还没追平能力完成度，比如 legacy 入口虽已默认禁用并改成需 `KB_ALLOW_LEGACY_STREAMLIT=1` 显式 opt-in 的兼容入口、cleanup 侧已经做到 file-mode / directory-mode 均已回到 `managed_count = 0` 且重点转为后续重点转为防回脏、定期巡检与受控 apply 预案固化、Docker runtime baseline 虽然已经定位到顶层 `llama_index` metapackage 这个根因，但完整 build/run smoke 还要继续补；Prompt / heuristic 方向虽然已完成 source projection、answer repair、composite answers 三批模块化，但 targeted-fact orchestration 仍是下一步重点。

## 6. 如果面试官问“你具体怎么把分数做上去的？”

可以按下面这条线讲：

### 6.1 先修契约问题

- `basic` 不再伪装成全局检索，而是显式绑定 active KB；
- QueryRequest 的 `top_k / response_mode / use_reranker / top_n / reranker_model` 不再停留在 schema，而是已经形成 schema → route → query engine → semireal smoke → frontend API 的闭环证据；
- query/history 解耦，避免回答成功却被 UI 误判成失败。

### 6.2 再修答案与证据的一致性

- 让 source / evidence 返回更稳定；
- 对 scope、policy、cross-document 题做更精确的答案重组；
- 修 preview excerpt 污染和 forbidden-term 的误判问题。

### 6.3 再用 layered eval 驱动边界优化

- Smoke 守住环境与基础回归；
- Main 守住主发布路径；
- Hard 专门查 similar-document confusion、scope trap、chunk boundary、OCR 多源题。
- refusal / negative contract 现在不再只是“看总通过率”，而是会同时检查 schema 覆盖、case 级拒答正确性，以及最终报告里的 `Refusal 覆盖摘要`；单题全过但 contract gate 不过时，最终 `run_passed` 仍会失败。
- `eval_v7` smoke 层现在也已显式包含 `process_boundary / scope_contract` 两类 negative contract gate，避免边界约束只在更重的层里才被检查。

### 6.4 再补工程治理，避免“分数对了但工程口径还是乱的”

- 把根目录临时产物分类成日志、OCR 草稿脚本、temp probe；
- 先做 dry-run，再做分批 apply；
- 再把治理能力扩展到目录级，明确区分 file-mode `0` 和 directory-mode `0` 的现实差异；
- 把 Docker runtime baseline 的依赖根因从“minimal 语义含糊”进一步收口到“顶层 `llama_index` metapackage 会拉起云侧依赖链”，再通过 dry-run 验证修正结果。

## 7. 如果面试官追问“后处理是不是太重，你怎么收？”

推荐回答：

> 是，后处理仍然偏重，但现在已经不是所有规则都堆在一个巨石 service 里了。我先把 table / preview / boundary / scope-definition 下沉到 `chat_source_answers.py`，再把 brief-answer expansion / exact-term repair / answer-support segmentation 下沉到 `chat_answer_repair.py`，最近又把 multi-fact merge / summary bundle 下沉到 `chat_composite_answers.py`。`chat_service.py` 已经从 `1696` 行进一步压到 `1166` 行。下一步我不会再泛泛地说“继续优化 heuristic”，而是会直拆 targeted-fact orchestration，并整理 hook builder / dependency registry，同时把能稳定前移的能力继续前移到 prompt / response contract。

## 8. 四个常被问到的指标怎么解释

### 8.1 grounding

回答是不是落在命中的文档证据上，而不是模型自由发挥。

### 8.2 evidence

回答里的关键结论能不能在返回的 source / excerpt 中找到支撑。

### 8.3 preview

用户点击来源时，是否能在前端预览中落到正确片段、页码或 OCR 位置。

### 8.4 scope

请求声明的知识库范围与系统实际生效范围是否一致，有没有串库或越权。

## 9. 现在真正的瓶颈是什么

当前最真实的瓶颈已经不是“题做不过”，而是五类工程问题：

1. **启动链路、端口和历史命名口径还没有完全统一**；
2. **targeted-fact orchestration 仍在 `chat_service.py` 里偏重，长期维护成本高**；
3. **hook builder / dependency registry 开始分散，需要整理**；
4. **根目录 file-mode 已收敛，但 directory-mode 已清零（`managed_count = 0`）**；
5. **Docker runtime baseline 的 metapackage 根因已经定位并收口，smoke helper 端口竞争也已收口，但 `sentence-transformers / torch` 仍让默认 runtime 镜像偏重，完整 build/run smoke 还没补完**。

## 10. 能力完成度 vs 工程完成度怎么区分

### 10.1 能力完成度：可以比较放心讲

- 多知识库 scope contract
- evidence / preview 返回链路
- layered eval 分层评测
- targeted fact / refusal / cross-source 主路径
- 根目录文件级治理能力已经建立起来，并且完成了真实 apply + 复核

### 10.2 工程完成度：要诚实讲还在收口

现在更准确的说法是：**能力完成度高于工程完成度**。

- legacy 入口还在仓库中；
- 历史文档还有旧路径和旧叙事；
- prompt 与 heuristic 的职责边界还需继续优化；
- file-mode / directory-mode 均已回到 `managed_count = 0`，后续重点转为防回脏、定期巡检与受控 apply 预案固化；
- Docker runtime baseline 虽已移除顶层 `llama_index` metapackage，但完整 smoke 和默认依赖体重仍待继续做实。

## 11. 不建议的讲法

不要说：

- “所有东西都 1.0，所以系统已经没问题了。”
- “既然评测过了，工程问题就不重要。”
- “那些 legacy 文件反正不影响运行，可以不用管。”
- “现在 Docker 已经完全没问题了。”

更好的说法是：

- 当前 suite 全绿，说明主能力闭环已成型；
- file-mode / directory-mode 均已回到 `managed_count = 0`，后续重点转为防回脏、定期巡检与受控 apply 预案固化；
- runtime baseline 的依赖根因已经定位并修正，但完整 Docker smoke 证据还要继续补；
- heuristic 已从巨石 service 中拆出三批模块，但 targeted-fact orchestration 仍待继续下沉；
- 工程完成度仍低于能力完成度；
- 我能明确指出下一步该收哪些尾巴，而不是只会展示分数。

## 12. 最后一段收口话术

> 我会把这个项目定义成：一个已经把多知识库 scope、evidence / preview 和 layered eval 做成闭环的本地知识库助手。现在最值得继续投入的，不是追求表面上的‘更多 1.0’，而是把启动链路、legacy 入口、文档统一，以及 prompt/heuristic 的边界继续做实，并把 cleanup 侧已经做到 file-mode / directory-mode 均已回到 `managed_count = 0`、Docker runtime baseline 已收口但完整 Docker smoke 仍待补齐这两件事持续守住。这样讲既能体现我做出了东西，也能体现我对系统边界有真实判断。


