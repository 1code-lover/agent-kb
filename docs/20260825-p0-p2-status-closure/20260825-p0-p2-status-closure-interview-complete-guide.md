# 20260825 P0/P2 Status Closure Interview Complete Guide

## 1. 文档定位

这份文档的目标只有一个：

> 把 **1~30 轮问题、12 项问题状态、当前主能力、真实验证证据、诚实边界表达** 收成一份可直接用于面试和汇报的完整讲稿底稿。

如果你不想在 `master-guide`、`interview-script`、`status-report`、`rounds-rollup`、`ThinkRAG_面试问答.md` 之间来回切，这一份就是最适合最后过一遍的版本。

推荐使用方式：

1. 先看本文件第 2~4 节，记住 30 秒 / 2 分钟 / 5 分钟骨架；
2. 再看第 5 节，把 12 项问题压成“我到底改了什么”；
3. 最后看第 6~8 节，准备应对“为什么很多指标是 1.0”“还有什么没做完”这类追问。

---

## 2. 一句话总判断

如果一定要把这 30 轮工作压成一句话，建议统一这样讲：

> 这 30 轮不是把一个 demo 从 0 做到 1，而是把一个已经有能力雏形的本地知识库助手，逐步收口成 **主能力闭环更完整、系统契约更一致、验证证据更扎实，但工程完成度仍在继续追赶能力完成度** 的系统。

这句话同时覆盖了两层意思：

- **能力完成度高**：多 KB、scope isolation、evidence / preview、layered eval 已经形成闭环；
- **工程完成度未满**：startup / Docker / 文档 / cleanup / 历史兼容层仍在继续收口。

---

## 3. 30 秒 / 2 分钟 / 5 分钟讲稿骨架

### 3.1 30 秒版本

我做的是一个本地优先的知识库助手项目，当前主线是 **FastAPI + React + Electron + LlamaIndex**。它不只是把模型接到文档上，而是把知识导入、单库作用域约束、答案证据、来源预览和分层评测做成了闭环。最近 30 轮优化，核心不是继续堆功能，而是把 scope、请求级参数、前端状态一致性、负向评测和工程治理逐步收口，让系统从“能跑”变成“更可控、可证、可维护”。

### 3.2 2 分钟版本

这个项目最初已经有本地知识库问答的能力雏形，但当我往工程角度审视时，发现问题不在“能不能答”，而在“答的边界是否受控、配置是否真的生效、用户体验是否一致、验证是否成体系”。

所以这 30 轮我主要做了四类事情：

1. **先修边界契约**：把 `basic` / `knowledge` 模式都显式绑定 active KB，让前端语义和后端 `single_kb` 约束一致；
2. **再修请求链路**：确保 QueryRequest 的 `top_k / response_mode / use_reranker / top_n / reranker_model` 这类参数不是表单摆设，而是真的能进入 runtime query engine；
3. **再修交互一致性**：query 成功不再被 history 的慢同步覆盖，用户不会看到“明明答出来了但 UI 像失败”的体验；
4. **最后补验证与治理**：把 layered eval、negative contract、startup contract、Docker smoke、repo hygiene、审计文档同步都做成可复跑规则。

所以现在更准确的项目状态不是“所有问题都没了”，而是：**主能力闭环已经比较完整，工程收口还在继续推进。**

### 3.3 5 分钟版本

我会把这个项目讲成一个“从能力雏形到工程收口”的优化过程。

第一层是**能力主线**。现在主线已经不是旧的 Streamlit demo，而是 **FastAPI + React + Electron + LlamaIndex**。系统支持多知识库管理、文档导入、基于单库作用域的问答，以及返回 evidence / preview 这类来源信息。也就是说，我不是只追求“给出一个答案”，而是希望答案能被追溯、被验证。

第二层是**边界与契约**。我优先处理的不是花哨功能，而是最容易把系统讲歪的地方。比如 `basic` 模式在产品语义上应该仍然受知识库范围约束，所以前端和后端都收口到 active KB / `single_kb`；又比如 QueryRequest 里的 runtime 参数，必须真正打进 query engine，否则调参就是假动作。

第三层是**用户体验一致性**。很多系统的问题不是接口报错，而是局部成功和全局状态被混在一起。这里我把 query 成功与 history 成功解耦，确保答案一旦生成成功，就不会被后续慢一步的历史同步错误覆盖，这样前端行为才和用户感知一致。

第四层是**验证体系**。我不想只靠“最近看起来还行”来证明系统稳定，所以做了 layered eval、contract test、chat 主链路回归、startup / Docker / requirements / cleanup / repo hygiene 这些工程门禁。现在 layered suite、主链路回归和文档同步链路都可以复跑，能比较稳定地解释“为什么我说它已经进入可讲解状态”。

第五层是**诚实边界**。我不会把若干 `1.0`、Main `93 / 93` 或 Hard `36 / 36` 讲成“现实世界所有问题都完美”。更准确的说法是：**我定义的主发布路径已经闭环，但工程完成度还在追赶能力完成度**。其中 Hard 这次之所以能到 `36 / 36`，关键不是把题放水，而是把 negative-contract modality marker 的 contract gate 真正补齐了；目前仍值得继续推进的，是 prompt / heuristic 复杂度、历史兼容层、Docker baseline 和根目录 scratch/temp 资产治理。

---

## 4. 把 1~30 轮问题压成 6 个主题

### 主题 A：把“能回答”升级成“受控边界内能回答”

对应问题：1、2、3

关键表达：

> 我优先处理的是系统边界而不是功能堆叠。现在前端模式语义、后端 `single_kb` 约束和主入口口径已经更一致，不再把旧路径和当前主路径混讲。

### 主题 B：把“参数存在”升级成“参数真的生效”

对应问题：4、7

关键表达：

> 我比较在意“配置是不是假动作”。这轮把 QueryRequest 参数真正打进主链路，也把 prompt / heuristic 的问题从“感觉不稳”推进到“可以被 contract 和回归定位”。

### 主题 C：把“接口成功”升级成“用户体验一致”

对应问题：5

关键表达：

> 我补的是状态一致性，不是提示文案。query 成功后 history 可以延迟同步，但不能再反过来把整次问答表现成失败。

### 主题 D：把“功能堆出来”升级成“能被验证”

对应问题：6、10、12

关键表达：

> layered eval、negative contract、审计文档同步和面试材料整理，本质上都是在做一件事：让系统可以被复跑、被复核、被解释，而不只是看起来像通过了。

### 主题 E：把“能开发”升级成“能长期维护”

对应问题：8、9、11

关键表达：

> startup contract、requirements profile、Docker smoke、cleanup、repo hygiene 这些工作短期不一定最显眼，但它们决定了系统能不能持续维护，而不是每次换环境都重新踩坑。

### 主题 F：把“做过很多修改”升级成“会讲清楚自己做了什么”

对应问题：12

关键表达：

> 我会主动区分能力完成度和工程完成度，这样既不会把项目讲成一个小 demo，也不会过度承诺成一个完全 finished 的产品。

---

## 5. 12 项问题在面试中的推荐讲法

| 编号 | 问题 | 当前建议口径 | 最关键证据入口 | 面试时一句话讲法 |
| --- | --- | --- | --- | --- |
| 1 | `basic` 模式和后端 `single_kb` 约束冲突 | **已收口** | `webapp/src/domain/agentExperience.js`、`api/services/query_scope.py`、`tests/api/test_chat_scope_contract.py` | `basic` 现在不是无范围聊天，而是受 active KB 约束，前后端口径一致。 |
| 2 | 启动链路 / 桌面链路存在硬编码 | **部分完成** | `start_dev.ps1`、`start_frontend.ps1`、`desktop/src/runtime-config.js`、`tests/scripts/test_dev_startup_contracts.py` | 启动和桌面链路已经有 contract，但默认端口、历史兼容别名和部分路径 fallback 仍在继续收口。 |
| 3 | 项目主入口不统一 | **大体收口** | `README.md`、`app.py`、`tests/test_legacy_streamlit_entry.py` | 当前主入口已经明确是 FastAPI + React + Electron，Streamlit 只保留为显式 opt-in 的 legacy shim。 |
| 4 | QueryRequest 参数疑似没有完整打进主链路 | **已收口** | `api/services/chat_query_flow.py`、`api/services/chat_service.py`、`tests/api/test_runtime_model_loading.py` | 请求级参数现在会真实影响 query engine，而不是只停留在请求层。 |
| 5 | 前端把 query 成功和 history 成功绑死 | **已收口** | `webapp/src/domain/chatWorkflow.js`、`webapp/src/domain/chatWorkflow.test.js` | query 成功优先，history 改成 best-effort，同步慢一拍不会再把刚生成的答案覆盖掉。 |
| 6 | refusal / negative contract 覆盖不足 | **大体收口** | `tests/test_rag_quality_fixtures.py`、`tests/api/test_chat_eval_contracts.py`、`tests/api/test_chat_eval_runner.py` | refusal 已经进入正式评测和报告闭环，而且 fixture 侧已补上按模态 marker guard：某个模态里只要已有该类 case，该模态下 required marker 就不能缺；但 semireal hard negatives 仍值得继续加深。 |
| 7 | Prompt 契约偏弱，后处理 heuristic 太重 | **部分完成** | `api/services/chat_*` 模块、`tests/api/test_chat_targeted_fact.py`、`tests/api/test_chat_answer_repair.py` | 已经开始把 heuristic 从大而全逻辑拆成可测模块，但复杂度还没有完全收干净。 |
| 8 | Docker / requirements / 端口 / 启动脚本配置漂移 | **部分完成** | `requirements-runtime.txt`、`scripts/docker_smoke.py`、`tests/test_requirements_profiles.py` | baseline 已经比以前稳定，但 Docker runtime baseline 和重依赖问题还没彻底收尾。 |
| 9 | 仓库根目录临时文件、日志、调试脚本较多 | **部分完成** | `scripts/cleanup_local_artifacts.py`、`tests/scripts/test_cleanup_local_artifacts.py` | 规则已经建立，但 inventory 减法还没做完，当前 scratch/temp 资产库存仍偏多。 |
| 10 | 文档闭环不够满 | **大体收口** | `scripts/build_audit_metrics_snapshot.py`、`tests/scripts/test_build_audit_metrics_snapshot.py` | 审计文档现在可以按测试快照同步，但历史材料代际依然较多。 |
| 11 | 日志与临时产物治理需要规范化 | **部分完成** | `scripts/cleanup_local_artifacts.py`、`tests/scripts/test_repo_hygiene_contracts.py` | 已经从“没人管”推进到“有脚本、有门禁”，但还没到“库存清空”。 |
| 12 | 面试表述需要区分能力完成度和工程完成度 | **已整理** | `20260825-p0-p2-status-closure-interview-script.md`、本文件 | 我会主动说明主能力闭环已完成得比较好，但工程收口还在继续。 |

---

## 6. 如果面试官追问“为什么很多指标是 1.0？”

推荐回答：

> 我不会把这些 1.0 解释成现实世界所有问题都完美，而是解释成“当前定义的 semireal layered suite 已全部通过”。它证明的是我定义的主发布路径已经闭环，比如 scope 没串、evidence 能回、preview 能落、cross-source fact 能组装出来。为了避免题太少也刷到 1.0，我还把 refusal / negative contract 以及 history-grounded answerable follow-up 都做成了数据集覆盖、单 case correctness 和最终报告可见性的闭环。真正还没做完的主要在工程层，比如 legacy 入口、Docker baseline、文档与 cleanup 收口等。

如果对方继续追问“那你怎么防止只看全局 marker、局部模态其实漏掉”，可以再补一句：现在 fixture 层已经新增 **per-modality marker gate**。它不是要求每个 category 在 markdown / pdf / image_ocr 都平均铺开，而是要求**某个模态里只要已经存在该类 refusal / negative-contract case，该模态下的 required marker 就不能缺**。这样既能防住局部漂移，又不会把数据集做成不真实的均匀分布。

你可以继续补一句：

- `1.0` 更像是**当前题集上的闭环证明**；
- 它不是“系统对所有真实世界问题都完美”的承诺。

---

## 7. 如果面试官追问“你到底是怎么把分数做上去的？”

建议按下面顺序回答：

1. **先修边界契约**：收口 `basic` / `knowledge` 与 active KB / `single_kb`；
2. **再修请求链路**：让 QueryRequest 参数真正进入 runtime query engine；
3. **再修体验一致性**：query 成功不再被 history 的慢同步拖垮；
4. **再修证据与答案一致性**：让 evidence / preview / excerpt 稳定返回；
5. **最后用 layered eval 和 contract 反推边界**：Smoke 守主入口，Main 守主能力与 answerable follow-up，Hard 查 refusal follow-up、scope trap、similar-document confusion、preview / OCR 等复杂边界。

这样回答的好处是：

- 不会把改进讲成“调了几条 prompt 就好了”；
- 能体现你是在从系统层逐步收口，而不是只在刷分。

---

## 8. 如果面试官问“现在还有什么没做完？”

建议固定落在这四条：

1. **prompt / heuristic 复杂度仍偏高**，长期维护成本还可以继续降；
2. **startup / Docker / requirements 仍有工程收口空间**，特别是 baseline 和重依赖问题；
3. **历史兼容层和文档代际仍较多**，容易干扰新同学理解当前主线；
4. **cleanup / inventory 减法还没做完**，根目录 scratch/temp 临时产物库存仍需治理。

最关键的一句是：

> 这个项目现在更准确的状态是：**能力完成度高于工程完成度。**

---

## 9. 最后给自己的提醒

面试时最怕两种讲法：

1. **讲太小**：把项目讲成“我做了一个本地问答 demo”；
2. **讲太满**：把项目讲成“所有问题都解决了、指标全是 1.0 所以已经完全 finished”。

更稳的讲法是：

- 我已经把主能力闭环、关键契约和主要验证路径做得比较扎实；
- 我也清楚哪些是工程收口、哪些是历史包袱、哪些是下一步最值得继续推进的 backlog。

只要你能稳定讲清楚这两层，整套材料就已经够面试使用了。
