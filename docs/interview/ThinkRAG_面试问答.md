# ThinkRAG 面试问答（当前口径）

> 更新时间：2026-08-27，已补齐 latest hard eval 收口口径。
>
> 本文角色：**扩展问答主稿**。
> - 需要先定当前主线与阅读顺序时，优先看 `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-master-guide.md`；
> - 需要先一次性过完整讲稿时，优先看 `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-complete-guide.md`；
> - 需要 30 秒 / 2 分钟口播时，当前优先看 `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md`；历史 audit 口播版见 `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-interview-brief.md`；
> - 需要标准 5 分钟固定汇报时，当前优先看 `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md`；历史 audit 固定稿见 `docs/20260821-project-audit-remediation/20260821-project-audit-remediation-report-script.md`；
> - 需要展开追问、解释指标、回答“为什么很多指标是 1.0”或把 1~30 轮问题压成追问提纲时，再看本文；
> - 需要核对 12 项问题状态时，看 `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-status-report.md`；
> - 需要追更深的历史审计证据时，再看 `docs/20260821-project-audit-remediation/` 下对应 audit / report / status-matrix。
>
> 本文更适合作为**追问稿 / 指标解释稿**，不是标准 5 分钟汇报底稿。
>
> 当前**统一引用顺序**：
> 1. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-master-guide.md`
> 2. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-complete-guide.md`
> 3. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md`
> 4. 本文
> 5. `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-status-report.md`
>
> 当前主线是 **FastAPI + React + Electron + LlamaIndex**。仓库里的 `ThinkRAG`、`app.py`、`frontend/`、Streamlit 相关内容更多属于历史兼容路径或旧阶段材料，不能再当作当前主入口来讲。

## 一、追问场景下的 1 分钟项目介绍

> 这一节保留给“请你先快速介绍一下项目”这类追问场景使用，不替代标准 5 分钟汇报底稿。

我做的是一个本地优先的知识库助手项目，当前主线是 **FastAPI + React + Electron + LlamaIndex**。它不只是把模型接到文档上，而是把知识接入、单库作用域约束、证据返回、来源预览和分层评测做成了闭环。现在用户可以在桌面端或 Web 端选择具体知识库，把 PDF、Markdown、图片 OCR、网页等资料导入后，再基于检索结果完成问答，而且回答会带 evidence / preview 元数据，方便验证结论是不是落在知识库内容上。

## 二、追问场景下的 3 分钟项目介绍

> 这一节适合在面试追问里做展开说明；如果是固定结构汇报，优先看 `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md`。

如果展开讲，我会把这个项目分成三层：

1. **产品与交互层**：当前用 React + Electron 承接 Knowledge Workspace 和 Agent Workspace；Web 调试走 Vite，桌面端通过 Electron 复用同一条前端链路。
2. **服务层**：FastAPI 提供知识库、预览、问答、健康检查等接口；`basic` / `knowledge` 模式都会要求显式知识库选择，避免隐式跨库。
3. **RAG 能力层**：LlamaIndex 负责文档摄取、索引和查询编排；系统同时覆盖文件导入、网页导入、OCR、证据元数据、preview 片段和多种问答后处理。

我重点做的不是单一算法调参，而是把几条关键契约做对：

- 前端 `basic` / `knowledge` 模式都显式绑定 active KB；
- query 成功不会再因为 history 写回失败被 UI 误判成整次问答失败；
- 回答里会尽量把 evidence、preview、scope 等信息稳定返回给前端；
- 用 layered eval 把 smoke / main / hard 分层，区分基础回归、主发布路径和难题边界。

所以我现在会把它定义成：**主能力闭环已经成型，但工程收尾仍在继续的本地知识库助手**。

## 三、这个项目解决什么问题

它解决的是“通用模型不了解企业或个人私有资料，回答缺少依据、容易串题”的问题。这个项目把本地文件、网页、扫描件等资料接入知识库后，在提问时先做受控检索，再基于证据生成回答，并把来源和预览一起返回，降低“答了但无法核对”的风险。

## 四、当前最值得讲的能力亮点

### 1. 作用域约束真正做进了产品
- 用户必须显式选择知识库；
- 后端按单库作用域执行，不默认跨库；
- 这类约束不仅是文档描述，也有前端与后端契约测试守住。

### 2. evidence / preview 不只是展示字段
- 回答会尽量返回来源片段、页码、excerpt 等元数据；
- preview 相关链路单独有回归测试；
- 面试里可以把它讲成“回答可核对，而不是只给一句结论”。

### 3. 分层评测让你能解释“为什么我说它稳”
当前审计口径里的 layered eval 更适合这样讲：
- 数据集总量：`153` 条（Smoke `24` + Main `93` + Hard `36`）
- Smoke：`24 / 24`
- Main：`93 / 93`
- Hard：最新可复核快照为 `36 / 36`，且 `run_passed = true`

这组结果不代表“现实世界所有问题都完美”；更准确地说，它代表 **Smoke / Main 主闭环已经打通，而 Hard 仍在持续暴露边界残差**。

另外我会主动补一句：**refusal / negative contract 现在也不是只看一个 pass_rate。** 当前已经做成三层闭环：

- 数据集覆盖层：schema 会约束 refusal category、modality 分布、judge dimension 最小样本量；
- 单 case 正确性层：缺 required marker、拒答时编造内容、命中 forbidden term，都会直接判失败；
- 报告可见层：最终 JSON / Markdown 会直接输出 `refusal_summary` 和 `Refusal 覆盖摘要`。

## 五、如果面试官质疑“为什么现在很多指标是 1.0？”

建议这样回答：

> 我不会把这些 1.0 解释成系统对所有真实问题都完美，而是解释成“当前 semireal layered suite 全部通过”。它证明的是我定义的主发布路径已经闭环，比如 scope 没串、evidence 能回、preview 能落、cross-source fact 能组装出来。为了避免“题太少也能刷到 1.0”，现在 refusal / negative contract 也不是只看一个通过率，而是同时看数据集覆盖、单 case correctness 和最终报告里的 `refusal_summary`。真正还没完全做完的，主要在工程层，比如 legacy 入口治理、文档统一、启动链路、Docker runtime baseline 的完整 smoke，以及 prompt / heuristic 的边界还在继续收口。

## 六、如果继续追问“你是怎么把分数做上去的？”

我会按下面这条线讲：

1. **先修契约**：让 `basic` / `knowledge` 都显式绑定 active KB，避免问答范围漂移。
2. **再修前后端链路**：query 成功后 history 同步失败时，不再把整次问答判成失败。
3. **再修答案与证据一致性**：把 evidence / preview / excerpt 这类信息稳定返回给前端。
4. **最后用 layered eval 反推边界**：Smoke 守基础，Main 守主路径，Hard 专门查 scope trap、similar-document confusion、preview 与 OCR 这类复杂边界。

## 七、grounding / evidence / preview / scope 四个指标怎么解释

- **grounding**：回答是不是落在检索到的知识片段上，而不是模型自由发挥。
- **evidence**：回答中的关键结论，能不能在返回的 source / excerpt 中找到依据。
- **preview**：用户点开来源时，前端能不能落到正确片段、页码或 OCR 位置。
- **scope**：请求声明的知识库范围和系统实际生效范围是否一致，有没有串库。

如果对方继续追问 refusal，我会补一句：**refusal 不是这四个主指标之一，但它现在有单独的三层闭环。** 也就是数据集覆盖要够、单 case 拒答文案要对、最终报告还要能看见 `Refusal 覆盖摘要`。

如果面试官继续追问“那你怎么防止只看全局 marker、局部模态其实漏掉了”，我会再补一句：现在 fixture 层已经新增 **per-modality marker gate**。它不是要求每个 category 在 markdown / pdf / image_ocr 三个模态都硬凑一遍，而是要求**某个模态只要已经存在该类 refusal / negative-contract case，该模态下的 required marker 就不能缺**。这样既能防住局部漂移，又不会把数据集设计硬改成不真实的均匀分布。

## 八、现在项目真正的瓶颈在哪里

当前更真实的瓶颈已经不是“题做不过”，而是四类工程问题：

1. **启动链路、端口契约和文档口径还需要继续统一**；
2. **`chat_service.py` 的规则后处理仍然偏重，长期维护成本高**；
3. **legacy 入口和历史材料仍在仓库里，需要持续收口，不然会干扰新同学或面试叙事**；
4. **Docker runtime baseline 的顶层 `llama_index` metapackage 根因虽然已经清掉，但完整 smoke 还没补完，`sentence-transformers / torch` 仍让默认 baseline 偏重**。

## 九、如果面试官问“项目现在是不是已经完全 finished？”

不建议直接说“做完了”。更准确的回答是：

> 这个项目现在是“能力完成度高于工程完成度”。主能力闭环和评测闭环已经成型，但工程治理和长期维护体验还在继续收尾。

## 十、目前有哪些真实验证可以拿出来讲

当前审计目录已经汇总了几组比较稳的验证：

- `python -m pytest tests/api/test_chat_qa_metrics.py tests/api/test_chat_service.py tests/api/test_chat_evidence_contract.py tests/api/test_kb_preview_route.py -q` → `114 passed`
- `python -m pytest tests/scripts/test_dev_startup_contracts.py tests/scripts/test_docs_entry_contracts.py tests/test_requirements_profiles.py tests/scripts/test_cleanup_local_artifacts.py tests/scripts/test_repo_hygiene_contracts.py -q` → `83 passed`
- `python -m pip install --dry-run --ignore-installed --report temp/runtime-report-after-langchain-pin.json -r requirements-runtime.txt` → 报告中不再出现 `llama-parse / llama-cloud-services / llama-cloud / llama-index`
- `node --test webapp/src/domain/agentExperience.test.js webapp/src/domain/chatWorkflow.test.js webapp/src/api/client.test.js` → `16 passed`

## 十一、如果被问到 OCR 指标重要不重要

我的建议是：不要把 OCR 讲成唯一核心，也不要直接说不重要。更准确的说法是：

- 对主问答体验来说，scope、grounding、evidence、preview 更核心；
- OCR 属于知识接入质量的一部分，尤其对扫描件、图片资料场景很关键；
- 所以它不是唯一 KPI，但也不能完全忽略。

## 十二、最后一段收口话术

> 我会把这个项目定义成：一个已经把多知识库 scope、evidence / preview 和 layered eval 做成闭环的本地知识库助手。现在最值得继续投入的，不是追求表面上的“更多 1.0”，而是把启动链路、legacy 入口、文档统一，以及 prompt / heuristic 的边界继续做实，并补齐 Docker runtime baseline 的完整 smoke。这样既能体现我做出了东西，也能体现我知道系统还差什么。

## 十三、如果要把 1~30 轮问题压缩成 6 个主题

如果面试官想听“你这一路到底修了什么”，我建议不要按时间线流水账讲，而是压成 6 个主题：

### 主题 A：主能力已经闭环，不再是“答不对题”阶段
- 当前 layered eval 数据集总量已经到 `153` 条，其中 Smoke `24 / 24`、Main `93 / 93`，Hard 最新可复核快照为 `36 / 36`，并且 hard contract gate 已闭环；
- 多 KB scope isolation、evidence / preview、targeted fact / refusal / cross-source 主路径已经有代码、测试、评测共同支撑；
- 所以现在项目已经不是“能不能做出一个 demo”，而是“如何把闭环做稳”。

### 主题 B：工程收口落后于能力收口
- 当前更真实的剩余问题已经不是题做不过，而是主入口统一、legacy 入口退场、Docker runtime smoke、文档口径和长期维护体验；
- 这也是为什么我会主动说“能力完成度高于工程完成度”。

### 主题 C：cleanup 已经从发现问题进入真实治理
- 根目录文件级日志、临时探针和 OCR 草稿脚本已经完成三轮实际 apply；
- 当前 file-mode `managed_count = 0`，但 directory-mode 已清零（`managed_count = 0`）；
- 这部分要讲成“治理能力和治理边界都是真的”。

### 主题 D：Docker / requirements 的问题已从语义漂移收口到构建确定性
- 当前默认已经统一到 `INSTALL_PROFILE=runtime` + API 模式；
- 顶层 `llama_index` metapackage 这个根因已经定位并移除，最新 dry-run 不再回流 `llama-parse / llama-cloud-services / llama-cloud / llama-index`；
- 但完整 build/run smoke 仍待补齐，所以我不会把它讲成“Docker 已经完全 finished”。

### 主题 E：大文件债务和命名债务是长期维护成本来源
- `chat_targeted_fact.py` 最新已经把 `score_targeted_answer_candidate(...)` 拆成纯函数，并把 `maybe_answer_targeted_fact_question_from_sources(...)`、`_build_targeted_question_signals(...)`、`_compute_targeted_structural_bonuses(...)` 继续压成 helper；`chat_source_selection.py` 的 `minimize_sources_for_answer(...)` 也已经拆成 helper + 独立契约测试；`model_service.py` 的 `attempt_model_fallback(...)` 已下沉成 base-status / candidate-probe / success-finalize / failed-finalize helper；这轮又把 `chat_service.query(...)` 中的 fallback retry、result assembly，以及 identifier-gap / refusal pruning / postprocessor 尾段分支继续下沉到 `chat_query_flow.py` helper，所以更真实的下一热点已经继续收缩到 `chat_service.py` 剩余的 answer assembly 与 targeted-fact / multi-fact overlap；
- `kb_service.py`、`chat_eval_runner.py`、`AgentPage.jsx` 等大文件也说明工程化收口还没结束；
- 面试里这能体现我不只是会堆功能，也知道长期维护成本在哪里。

### 主题 F：材料层已经基本闭环，但引用口径必须统一
- 当前对外优先引用顺序建议改成：`20260825-p0-p2-status-closure-master-guide.md` → `20260825-p0-p2-status-closure-interview-script.md` → 本文 → `20260825-p0-p2-status-closure-status-report.md`；
- `docs/project.md` 现在已经把当前可信快照和历史归档纪要分层；
- 我会避免现场临时从历史 ledger 里 grep 旧数字来回答问题。

## 十四、如果临场被要求把追问稿压成 5 分钟补充说法

先说明边界：**标准 5 分钟固定汇报优先看 `docs/20260825-p0-p2-status-closure/20260825-p0-p2-status-closure-interview-script.md`。**
下面这 5 步只适合在面试现场临时从追问稿里压缩表达，不替代汇报底稿。

建议按下面 5 步补充：

1. **先定项目定位**：这是本地知识库助手，不是简单接个模型的 demo。
2. **再讲主能力闭环**：多 KB scope、evidence / preview、layered eval 已经成型。
3. **再讲关键整改**：active KB 契约、QueryRequest 参数打通、query/history 解耦、prompt 模块化拆分。
4. **再讲怎么证明**：`153 / 153`、`114 passed`、`83 passed`、`1299 passed, 4 deselected`。
5. **最后主动讲边界和下一步**：工程完成度仍低于能力完成度，下一步重点是 `chat_service.py` 剩余的 answer assembly 与 targeted-fact / multi-fact overlap、Docker runtime smoke、legacy 入口和文档统一；其中 targeted-fact 评分层、model fallback orchestration，以及 query / refusal-tail orchestration 已经做过一轮 helper 化，但 chat 主链路还没完全拆完。

如果时间只够一句收口，我会直接说：**我已经把主能力闭环做出来了，现在最重要的是让工程完成度继续追上能力完成度。**

