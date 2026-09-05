# 20260821 Project Audit Remediation Issues Summary

## 1. 文档目的

这份文档把当前线程里“1~12 项核心问题”和“30 轮项目审计结论”压成一份**单文件总表**，方便三种场景直接使用：

1. 面试前快速总复习；
2. 做项目汇报时快速判断哪些能讲、哪些要诚实保留边界；
3. 继续按 P0 / P1 / P2 真正改代码时，先看清楚当前状态。

如果只记一句话：

> 这个项目不是一个简单的本地问答 demo，而是把多知识库 scope isolation、evidence / preview 返回和 layered eval 分层评测做成了系统能力，当前主路径已经闭环到 `153 / 153`，chat 关键回归 `114 passed`，全量非慢测 `1299 passed, 4 deselected`。但我也不会把它包装成‘项目已经完全 finished’，因为当前重点已经转成工程收口：legacy 兼容入口虽然已经默认禁用，需要 `KB_ALLOW_LEGACY_STREAMLIT=1` 显式 opt-in；Docker runtime build 的真实 smoke 证据、`chat_service.py` 规则链，以及 file-mode / directory-mode 均已回到 `managed_count = 0`，后续重点转为防回脏、定期巡检与受控 apply 预案固化。

> 角色定位：
> - 本文是 **1~12 项问题总表 + 30 轮审计压缩索引**；
> - 如果只需要 30 秒 / 2 分钟口播，优先看 `20260821-project-audit-remediation-interview-brief.md`；
> - 如果需要 5 分钟长讲法，优先看 `20260821-project-audit-remediation-report-script.md`；
> - 如果要逐项核对证据矩阵，再看 `20260821-project-audit-remediation-status-matrix.md`。

## 2. 当前统一口径

### 2.1 最新可信验证结果

- Layered suite：`153 / 153`
  - Smoke：`24 / 24`
  - Main：`90 / 90`
  - Hard：`36 / 36`
- chat 关键回归：`114 passed`
- 启动 / 文档入口 / requirements / cleanup / repo hygiene 契约：`83 passed`
- 2026-08-22 `start_dev.ps1` 真实执行型 smoke：`python -m pytest tests/scripts/test_dev_startup_contracts.py tests/scripts/test_start_dev_smoke.py -q` → `11 passed`
- 2026-08-22 Docker smoke helper 契约：`python -m pytest tests/scripts/test_docker_smoke.py -q` → `20 passed`
- 2026-08-22 Desktop bridge contract 收口回归：`node --test desktop/src/desktop-bridge-contract.test.js desktop/src/runtime-config.test.js desktop/src/python-process.test.js desktop/src/renderer-entry.test.js` → `18 passed`
- 2026-08-24 Desktop 全量 Node 单测：`npm --prefix desktop test` → `136 passed`（已把 `desktop/package.json` 的 `test` 脚本收口为覆盖全部 `desktop/src/*.test.js` + `desktop/scripts/*.test.js`，不再只是旧的子集）
- 2026-08-22 startup + desktop 双 smoke：`python -m pytest tests/scripts/test_dev_startup_contracts.py tests/scripts/test_start_dev_smoke.py tests/scripts/test_dev_all_smoke.py -q` → `20 passed`
- 2026-08-22 startup / docker helper / repo hygiene bundle：`python -m pytest tests/scripts/test_docker_smoke.py tests/scripts/test_repo_hygiene_contracts.py tests/scripts/test_dev_startup_contracts.py tests/scripts/test_webapp_contracts.py tests/scripts/test_start_dev_smoke.py tests/scripts/test_dev_all_smoke.py tests/scripts/test_docs_entry_contracts.py tests/test_legacy_streamlit_entry.py tests/test_run_api.py tests/test_requirements_profiles.py -q` → `108 passed`
- cleanup 单测：`13 passed`
- Desktop 关键单测：`19 passed`
- Web 关键单测：`16 passed`
- 2026-08-22 Web AgentPage / bridge 增量回归：`node --test webapp/src/api/client.test.js webapp/src/domain/chatWorkflow.test.js webapp/src/domain/agentExperience.test.js webapp/src/domain/desktopBridge.test.js` → `19 passed`
- 2026-08-22 QueryRequest route / scope 闭环：`python -m pytest tests/api/test_chat_routes.py tests/api/test_chat_scope_contract.py -q` → `19 passed, 2 warnings`
- 2026-08-22 QueryRequest semireal smoke 非默认参数：`python -m pytest tests/api/test_chat_single_kb_qa_smoke.py -q` → `11 passed, 2 warnings`
- 2026-08-22 OpenAPI answer / search 参数边界回归：`python -m pytest tests/api/test_open_api.py tests/api/test_open_api_service.py tests/api/test_open_api_integration.py -q` → `12 passed, 2 warnings`
- 2026-08-22 Web 全量 Node 单测：`npm --prefix webapp test` → `139 passed`
- 2026-08-22 Web AgentPage 静态契约：`python -m pytest tests/scripts/test_webapp_contracts.py -q` → `4 passed`
- 2026-08-22 Web 生产构建：`npm --prefix webapp run build` → `built in 6.51s`
- 2026-08-22 启动链路增量回归：`python -m pytest tests/test_run_api.py tests/test_runtime_paths.py tests/scripts/test_dev_startup_contracts.py -q` → `17 passed`
- 2026-08-22 Desktop runtime / renderer alias 增量回归：`node --test desktop/src/runtime-config.test.js desktop/src/python-process.test.js desktop/src/renderer-entry.test.js` → `15 passed`
- 2026-08-22 Web bridge / API 增量回归：`node --test webapp/src/api/client.test.js webapp/src/domain/chatWorkflow.test.js webapp/src/domain/agentExperience.test.js webapp/src/domain/desktopBridge.test.js` → `19 passed`
- 2026-08-22 chat 主链路局部回归：`python -m pytest tests/api/test_chat_service.py tests/api/test_kb_preview_route.py tests/api/test_chat_scope_contract.py tests/api/test_chat_evidence_contract.py -q` → `100 passed, 2 warnings`
- 全量非慢测：`1299 passed, 4 deselected`

### 2.2 根目录治理统一口径

- file-mode：`python scripts/cleanup_local_artifacts.py --dry-run` → `managed_count = 0`
- directory-mode：`python scripts/cleanup_local_artifacts.py --dry-run --include-directories` → `managed_count = 0`
  - `scratch_eval_dir = 12`
  - `scratch_debug_dir = 2`

因此以后统一只能这样讲：

- **文件级治理已经收敛**；
- **目录级治理能力已补齐，但历史 backlog 还没清完**；
- **不能把 file-mode `0` 讲成“整个仓库临时产物已经全部归零”**。

补充一句本轮新口径：`start_dev.ps1` / `scripts/dev-all.ps1` 的 Windows smoke 假红，根因已经定位到测试端口选择策略，现已改成 backend `20000-29999`、frontend `30000-39999` 的稳定 loopback range 扫描；`scripts/docker_smoke.py` 默认也不再先抢宿主机临时端口，而是改为 Docker 自分配 loopback host port 后再反查映射。

## 3. 12 项核心问题总表

| # | 问题 | 当前状态 | 最短结论 | 继续怎么讲 / 怎么做 |
| --- | --- | --- | --- | --- |
| 1 | basic 模式和 single_kb 约束冲突 | 已修 | `basic` / `knowledge` 都要求 active KB，前端不再把 basic 伪装成全局检索 | 面试可讲“契约已统一”；工程上继续守单测 |
| 2 | 启动链路 / 桌面链路存在硬编码 | 持续收敛 | 主链路不再依赖旧绝对路径，端口与 API base 已可配置；`start_dev.ps1` 与 `scripts/dev-all.ps1` 都已补真实执行型 smoke；desktop preload/main 的 bridge key 与 pick-files IPC 已开始集中到共享 helper；desktop runtime root 也支持通过 `KB_RUNTIME_ROOT` 等 env 覆盖，不再只能写死到仓库根目录 | 对外可讲“startup/desktop smoke 已补、desktop runtime root 去硬编码了一层，下一步补 packaged desktop / Docker 联调” |
| 3 | 项目主入口不统一 | 基本收敛 | README / runbook / 启动脚本主线已统一到 `FastAPI + React + Electron`；legacy Streamlit 入口已收口成默认禁用、需 `KB_ALLOW_LEGACY_STREAMLIT=1` 显式 opt-in 的兼容入口 | 对外讲“主线已统一，legacy 仅兼容保留，未完全退场” |
| 4 | QueryRequest 参数未完整打入 chat 主链路 | 已修并补强到 semireal smoke | `top_k / response_mode / use_reranker / top_n / reranker_model` 现在不仅进入 query engine，而且已有 route + semireal smoke + frontend API 闭环断言；OpenAPI 也已明确成 `/search` 只承诺 `top_k`、`/answer` 额外承诺 `response_mode / use_reranker / top_n / reranker_model` | 可直接讲“请求级检索参数已生效”；对外协议则按 `/search` 与 `/answer` 分层承诺，不再保留“边界待定”口径 |
| 5 | 前端把 query 成功和 history 成功绑死 | 已修并持续拆分 | query 成功优先，history 写回失败只做 notice；`AgentPage.jsx` 已把 `chatNotice` 真正透传到 `QaWorkbench`，并进一步把问答 workflow 抽到 `useAgentChatWorkspace.js`；这轮又把 `QaWorkbench` 拆成 conversation / source list / kb selector 子组件，页面主体不再承载整块展示细节 | 这是典型“用户体验契约修复 + 结构收口”，后续前端优化更该压 `AgentRuntimePanel` 或补 UI 交互测试，而不是回头补救主契约 |
| 6 | harness 对 refusal / negative contract 覆盖不足 | 进一步收敛 | 现在不只是 refusal 有 gate，`eval_v7` smoke 层也已补齐 negative contract gate；`eval_v8_main` 当前有 23 条 refusal、19 条 negative contract，且 `history_grounded_case_count = 6`、markdown / pdf / image_ocr 各 2 条；另外 semireal 多轮 follow-up 也已补齐 Markdown / PDF / Image OCR 三模态的 refusal 对称性。`chat_eval_runner` 已把 contract gate 直接联动到最终 `run_passed`，但 OCR / preview hygiene / source_count 负向题仍值得继续补 | 后续扩题优先补更真实的范围约束 / preview / source_count 负向边界，而不是简单 fact lookup |
| 7 | Prompt 契约偏弱，后处理 heuristic 太重 | 部分收敛（source projection + answer repair + composite answers 已独立模块化） | `chat_service.py` 仍保留多段 `_maybe_*` 后处理链，但 table / preview / boundary / scope-definition 已下沉到 `api/services/chat_source_answers.py`，brief-answer expansion / exact-term repair / answer-support segmentation 已下沉到 `api/services/chat_answer_repair.py`，multi-fact merge / summary bundle 也已下沉到 `api/services/chat_composite_answers.py` 并补齐独立测试；`chat_service.py` 已进一步压到 `1166` 行 | 这是当前最核心的结构性技术债之一，但已经从“完全堆在巨石 service”进入“source-backed 纯函数块持续外移”的阶段，剩余重点主要是 targeted-fact orchestration |
| 8 | Docker / requirements / 端口 / 启动脚本存在漂移 | 持续收敛 | 已把 Docker 默认口径切回 `runtime + api`，并把误导性的 `minimal` Docker profile 退场；进一步确认 runtime build 变慢的根因是 `requirements-runtime.txt` 曾引入顶层 `llama_index` metapackage，额外拉起 OpenAI / LlamaCloud / LlamaParse 依赖链，当前已改成只保留 `llama-index-core` + 显式 integrations，并把 dry-run 选中的 `langchain-core==0.3.63` / `langchain-text-splitters==0.3.8` 显式 pin 住；最新 dry-run 报告已不再出现 `llama-parse / llama-cloud-services / llama-cloud / llama-index`；另外 `scripts/docker_smoke.py` 默认已改为 Docker 自分配 loopback host port + `docker port` 反查映射，避免 smoke helper 自身复现端口竞争 | 继续补完整 build/run smoke，并把新的依赖口径同步到长期文档 |
| 9 | 根目录临时文件、日志、调试脚本较多 | 部分收敛 | file-mode / directory-mode 均已清到 0 | 以后必须分开讲 file / directory 两个层面 |
| 10 | 文档闭环不够满 | 部分收敛 | 当前审计目录材料已成型，但 `docs/project.md` 仍很长，历史口径噪音高 | 适合继续拆“稳定总览”和“历史纪要” |
| 11 | 日志与临时产物治理需要规范化 | 已收敛 | 脚本能力、单测、manifest、directory-mode 治理能力都已建立 | 当前 file-mode / directory-mode 均已回到 `managed_count = 0`；下一步转为后续重点转为防回脏、定期巡检与受控 apply 预案固化 |
| 12 | 面试表述需要区分能力完成度和工程完成度 | 已整理 | 现在已经能稳定讲清“能力已闭环，工程还在收口” | 对外统一优先引用本目录材料 |

## 4. 30 轮审计压缩后的 6 个主题

### 4.1 主题 A：主能力已经闭环，不再是“答不对题”阶段

当前 layered suite 已是 `153 / 153`，说明下面几件事已经不是“概念上想做”，而是已经有代码、测试、评测共同支撑：

- 多 KB scope isolation；
- evidence / preview 返回链路；
- targeted fact / cross-source fact / refusal 主路径；
- layered eval 的 Smoke / Main / Hard 分层验证。

### 4.2 主题 B：工程收口落后于能力收口

当前最真实的剩余问题，已经从“能不能答对”转成：

- 主入口与 legacy 入口如何共存或退场；
- Docker build 是否稳定、默认 runtime 依赖是否只包含真正需要的 integrations；
- `chat_service.py` 规则链是否过重；
- 仓库治理能否长期守住；
- 新同学是否能快速理解并接手。

### 4.3 主题 C：cleanup 已经从“发现问题”进入“真执行治理”

这轮不只是写建议，而是已经完成三轮文件级实际 apply，累计归档 `100` 个对象；但目录级 backlog 还在。这意味着：

- 治理能力是真的；
- 治理成果也是真的；
- 但治理边界同样要诚实描述。

### 4.4 主题 D：Docker / requirements 的问题已从“默认语义跑偏”转成“构建确定性仍需加强”

当前并不是完全没做 profile：

- 已有 `runtime / full / dev / prod / eval` Docker profile；
- `requirements-minimal.txt` 已降级为本地兼容别名；
- 也有对应契约测试；

但真正的问题在于：

- Docker 默认已经切回 `INSTALL_PROFILE=runtime`；
- entrypoint 也改成默认 API 模式，`eval` / `prod` 需要显式声明；
- 误导性的 `minimal` Docker profile 已退场，不再把 runtime baseline 包装成轻量 smoke；
- 当前剩余问题已经从“为什么会慢”收敛到“如何用完整 build/run smoke 证明移除顶层 metapackage、并 pin 住 LangChain 热点依赖后，解析链和安装体验都更稳定”；
- 另外 Docker smoke helper 现在已经切到 Docker 自分配 host port + `docker port` 反查映射，说明这一块的残余风险更偏向依赖体重，而不是脚本自身的宿主机端口竞争。

### 4.5 主题 E：命名债务和大文件债务是长期维护成本的主要来源

当前最值得警惕的几个热点：

- `api/services/chat_service.py`：`1166` 行（目前已把 source projection 拆到 `api/services/chat_source_answers.py`，answer repair 拆到 `api/services/chat_answer_repair.py`，composite answers 拆到 `api/services/chat_composite_answers.py`）；
- `api/services/chat_targeted_fact.py`：`838` 行；
- `api/services/kb_service.py`：`2954` 行；
- `tests/api/chat_eval_runner.py`：`2742` 行；
- `webapp/src/pages/AgentPage.jsx`：`792` 行（已抽出 `webapp/src/pages/useAgentChatWorkspace.js` `251` 行，并把问答展示层继续拆到 `webapp/src/pages/agent-page/QaWorkbench.jsx` `281` 行与三个叶子组件）；
- `desktop/src/preload.js` / `desktop/src/renderer-entry.js` / `webapp/src/api/client.js` 同时兼容 `NorthAgent / ThinkRAG / Foxglove`。

### 4.6 主题 F：材料层已经基本闭环，但引用口径必须统一

当前 `docs/20260821-project-audit-remediation/` 已经具备：

- guide：导航；
- status matrix：问题状态；
- test report：验证结果；
- interview brief：短讲法；
- report script：长讲法；
- 本文：总表。

后续对外表达应优先引用这一套，而不是继续从 `docs/project.md` 中临时 grep 历史数字。

## 5. 面试 / 汇报讲法

### 5.1 30 秒版

> 这个项目不是一个简单的本地问答 demo，而是把多知识库 scope isolation、evidence / preview 返回和 layered eval 分层评测做成了系统能力，当前主路径已经闭环到 `153 / 153`，chat 关键回归 `114 passed`，全量非慢测 `1299 passed, 4 deselected`。但我也不会把它包装成‘项目已经完全 finished’，因为当前重点已经转成工程收口：legacy 兼容入口虽然已经默认禁用，需要 `KB_ALLOW_LEGACY_STREAMLIT=1` 显式 opt-in；Docker runtime build 的真实 smoke 证据、`chat_service.py` 规则链，以及 file-mode / directory-mode 均已回到 `managed_count = 0`，后续重点转为防回脏、定期巡检与受控 apply 预案固化。

### 5.2 2 分钟版

可按这条线讲：

1. 先讲能力闭环：多 KB、scope、evidence、preview、layered eval；
2. 再讲我修了哪些契约问题：basic/single_kb、QueryRequest 参数（现在已补到 semireal smoke，OpenAPI 也已明确 `/search` / `/answer` 分层边界）、query/history 解耦；
3. 再讲我怎么证明：`153 / 153`、`114 passed`、`83 passed`、`1299 passed, 4 deselected`；
4. 最后诚实补边界：heuristic 仍重、Docker runtime build 仍需更多真实 smoke；cleanup 侧已经做到 file-mode / directory-mode 均已回到 `managed_count = 0`，重点转为后续重点转为防回脏、定期巡检与受控 apply 预案固化。

### 5.3 如果被追问“为什么全是 1.0？”

标准回答建议：

> 我不会把这个 1.0 讲成系统对所有真实问题都完美，而是讲成当前 semireal layered suite 下我定义的主能力闭环已经打通。为了避免“只有几道题也能刷出 1.0”，现在 schema 里还加了 `minimum_cases_per_judge_dimension` 这类门槛；更关键的是，单题 case 全过也不再自动等于最终通过，因为 refusal / negative contract 的 contract gate 会直接阻断 `run_passed`。同时我也会主动补一句：工程完成度还没追平能力完成度，比如 Docker runtime build 虽然已经定位到顶层 metapackage 这个根因，但真实 smoke 证据还要继续补、legacy 入口虽已默认禁用并改成需 `KB_ALLOW_LEGACY_STREAMLIT=1` 显式 opt-in 的兼容入口、file-mode 已清到 0 但 directory-mode 现已清零（`managed_count = 0`）。这些都是我愿意主动讲出来的真实边界。

## 6. 继续整改的最短路线

### P0
1. 继续拆 `api/services/chat_service.py` 剩余的 targeted fact orchestration 后处理链，并开始整理 hook builder / dependency registry；
2. 把目录治理从“清 backlog”切到“防回脏 + 定期巡检 + 受控 apply 预案”；当前 file-mode / directory-mode 均已回到 `managed_count = 0`；
3. 补 Docker runtime / eval 的真实 `docker build + docker run` smoke，并验证移除顶层 `llama_index` metapackage 后的解析链。

### P1
4. 拆 `api/services/kb_service.py`；
5. 前端若继续收口，优先拆 `AgentRuntimePanel` 或补 `QaWorkbench` 交互层测试（`AgentPage.jsx` 已抽出 `useAgentChatWorkspace.js` 与 `QaWorkbench` 子组件层）；
6. 制定 `ThinkRAG / Foxglove` 兼容别名下线计划；
7. 继续给 packaged desktop / requirements 增加真实执行型 smoke；`start_dev.ps1` 与 `scripts/dev-all.ps1` 已经补上。

### P2
8. 拆分 `docs/project.md`，降低历史口径噪音；
9. 继续扩 refusal / OCR weak-signal / preview hygiene 负向题；
10. 把“能力完成度 vs 工程完成度”写成固定汇报模板。

## 7. 推荐阅读顺序

如果只给 10 分钟复习，按这个顺序看：

1. `20260821-project-audit-remediation-issues-summary.md`
2. `20260821-project-audit-remediation-interview-brief.md`
3. `20260821-project-audit-remediation-test-report.md`
4. `20260821-project-audit-remediation-status-matrix.md`

## 8. 最终结论

这 1~30 轮问题，现在已经可以被整理成一句统一表述：

> **项目的主能力和评测闭环已经站稳，当前最值钱的工作，不再是继续堆漂亮分数，而是把工程入口、配置语义、heuristic 负担和仓库 backlog 继续收干净。**

## 附录：补充更新与审计证据

> 详细增量证据、历史补充更新和 release/package 边界说明，统一收口到 `20260821-project-audit-remediation-audit-evidence.md`。
> 本文只保留总表 / 压缩索引 / 讲法入口，不再继续堆叠长附录正文。

如果你现在的目标是：

- 看 1~12 项问题的当前总判断；
- 面试前快速复习；
- 做 5 分钟汇报或 30 秒 / 2 分钟口播；

那么停在本文即可。

只有在需要下面这些内容时，再打开 `20260821-project-audit-remediation-audit-evidence.md`：

1. 每一轮补充更新的历史增量记录；
2. refusal / Docker / startup alias / composite answers 等专题的附加验证；
3. Desktop build / package / release 的四层边界说明。



