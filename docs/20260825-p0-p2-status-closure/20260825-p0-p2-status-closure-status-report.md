# 20260825 P0/P2 Status Closure Report

## 1. 目的

这份状态报告不是重新定义目标，而是把当前工作树里 **P0 / P1 / P2 的 12 个问题**按“已收口 / 大体收口 / 部分完成 / 待继续”重新归档，避免继续迭代时把“已经修过的点”和“还没做完的点”混在一起。

## 2. 本次核查使用的真实证据

### 2.1 本轮实际执行的命令
<!-- audit-sync:closure-status-command-lines -->
- `python -m pytest tests/scripts/test_dev_startup_contracts.py tests/scripts/test_docs_entry_contracts.py tests/test_legacy_streamlit_entry.py tests/scripts/test_build_audit_metrics_snapshot.py -q` → `75 passed`
- `python -m pytest tests/scripts/test_docker_smoke.py tests/test_requirements_profiles.py tests/scripts/test_dev_startup_contracts.py -q` → `49 passed`
- `python -m pytest tests/scripts/test_cleanup_local_artifacts.py tests/scripts/test_repo_hygiene_contracts.py -q` → `27 passed`
- `python -m pytest tests/api/test_runtime_model_loading.py -k "request or overrides_config_store_defaults" -q` → `2 passed, 32 deselected`
- `python -m pytest tests/api/test_chat_eval_runner.py tests/api/test_chat_eval_contracts.py tests/test_rag_quality_eval_dataset_v8.py -q` → `54 passed`
- `python -m pytest tests/api/test_chat_scope_contract.py tests/api/test_open_api_service.py tests/api/test_open_api_integration.py tests/api/test_chat_service.py tests/api/test_chat_routes.py -q` → `118 passed`
- `node --test webapp/src/domain/agentExperience.test.js webapp/src/domain/chatWorkflow.test.js` → `21 pass`

### 2.2 本轮新增脚本链路验证

- `python -m py_compile scripts/build_audit_metrics_snapshot.py tests/scripts/test_build_audit_metrics_snapshot.py` → `0 errors`
- `python -m pytest tests/scripts/test_build_audit_metrics_snapshot.py -q` → `26 passed`
- `python scripts/build_audit_metrics_snapshot.py --bundle chat_regression --bundle docs_contract --skip-node --skip-cleanup --print-json` → 成功输出 merge 后 snapshot，说明高频 bundle 已支持快速增量刷新
- `python scripts/build_audit_metrics_snapshot.py --bundle chat_regression --skip-node --skip-cleanup --sync-docs --output <missing-temp>.json` → 预期抛出 `ValueError`，不会在缺少完整基线时静默写坏文档
- `python scripts/build_audit_metrics_snapshot.py --bundle full_non_slow --sync-docs` → 已把 audit / interview / project 材料中的 full non-slow 口径刷新到当前快照
- `python -m pytest tests/scripts/test_docs_entry_contracts.py -q` → `27 passed`

### 2.3 2026-08-28 本轮整理补充

- `python -m pytest tests/test_rag_quality_fixtures.py tests/test_rag_quality_eval_dataset_v8.py tests/api/test_chat_eval_contracts.py -q` → `44 passed`
- `python -m pytest tests/api/test_chat_eval_runner.py -q` → `23 passed`
- `python -m pytest tests/scripts/test_docs_entry_contracts.py tests/test_rag_quality_fixtures.py tests/test_rag_quality_eval_dataset_v8.py tests/api/test_chat_eval_contracts.py tests/api/test_chat_eval_runner.py -q` → `94 passed`
- `python -m pytest tests/api/test_chat_service.py tests/api/test_chat_answer_repair.py tests/api/test_chat_source_selection.py tests/api/test_chat_source_reconciliation.py tests/api/test_chat_targeted_fact.py -q` → `121 passed`

这轮整理的重点不是再堆一层“说明文档”，而是把两个容易在面试和维护里说错的点正式收口：

1. **评测负向 gate 的语义更清楚了**：fixture 侧现在除了全局 marker 统计，还补上了 refusal / negative-contract 的 per-modality marker guard。它不是要求每个 category 在每个模态都出现，而是要求“某个模态里只要已经存在该类 case，该模态下 required marker 就不能缺”。
2. **文档口径漂移开始可增量修正**：`python scripts/build_audit_metrics_snapshot.py --bundle full_non_slow --sync-docs` 已把 audit / interview / project 里残留的 full non-slow 旧值同步到当前快照，减少后续逐篇手改的风险。

## 3. 12 个问题状态矩阵

| # | 问题 | 当前状态 | 当前证据 | 当前真实结论 |
| --- | --- | --- | --- | --- |
| 1 | basic 模式和后端 single_kb 约束冲突 | 已收口 | `webapp/src/domain/agentExperience.js` / `.test.js` 已要求 `basic` 与 `knowledge` 显式绑定 active KB；`api/services/query_scope.py` 明确把 chat 主链路收口到 `single_kb`；相关前后端测试通过（`21 pass` + `118 passed`） | 这一条当前不再是主阻塞，后续只需要防止新入口绕过 `kb_ids` 约束。 |
| 2 | 启动链路 / 桌面链路存在硬编码（旧绝对路径、固定端口假设、新旧前端入口并存） | 部分完成 | `scripts/dev-runtime-helpers.ps1` 现在继续吸收了 `Resolve-ExtraDevOrigins(...)` 与 `Resolve-FrontendUrl(...)`，`start_api.ps1` / `start_dev.ps1` / `start_frontend.ps1` / `scripts/dev-all.ps1` / `scripts/desktop-dev.ps1` 都开始复用共享 helper；其中 `scripts/desktop-dev.ps1` 已支持显式 `-ApiBaseUrl https://api.example.com:18443`，并补上 web / desktop 运行态环境的 `try/finally` 清理，随后重新跑过 `python -m pytest tests/scripts/test_dev_startup_contracts.py -q` | 旧绝对路径与本地端口假设又收紧了一步，启动链路里关于 API base、frontend url、dev origins、remote helper 的公共逻辑开始真正收口；同时 compatibility helper 的环境变量泄漏风险也被压低了一层，但 compatibility wrapper、历史文档和桌面链路仍保留兼容层，不能宣称彻底清零。 |
| 3 | 项目主入口不统一 | 大体收口 | README / `docs/project.md` / runbook / desktop contract 已由 `tests/scripts/test_docs_entry_contracts.py` 和 `tests/test_legacy_streamlit_entry.py` 兜底；本轮文档与 sync 脚本校验共 `75 passed` | 当前可以明确对外口径：主入口是 FastAPI + React(Vite) + Electron；Streamlit 仅是 opt-in legacy 兼容入口。 |
| 4 | 请求级 QueryRequest 参数疑似没有完整打进 chat 主链路 | 已收口 | `api/runtime.py` 的 `build_query_engine(...)` 已把请求级 `top_k / response_mode / use_reranker / top_n / reranker_model` 作为 override；`tests/api/test_runtime_model_loading.py -k "request or overrides_config_store_defaults"` 通过；`tests/api/test_chat_service.py` / `tests/api/test_chat_routes.py` 已覆盖透传 | 这条现在更像回归守护项，不是当前主风险。 |
| 5 | 前端把 query 成功和 history 成功绑死 | 已收口 | `webapp/src/domain/chatWorkflow.js` 已具备 `queryChatWithBestEffortHistory(...)`、`historyIncludesOptimisticResult(...)`、`resolveHistoryMessages(...)`；相关 node 测试 `30 pass` | 现在 query 成功后不会因为 history 慢一拍而静默覆盖结果，这条可以作为面试时的真实优化点。 |
| 6 | 评测 harness 对 refusal / negative contract 覆盖不足 | 部分完成 | `tests/api/test_chat_eval_runner.py`、`tests/api/test_chat_eval_contracts.py`、`tests/test_rag_quality_eval_dataset_v8.py` 当前 `54 passed`；说明 refusal / contract gate 已进入正式套件 | 负向覆盖已不是“没有”，但仍以 contract / fixture 驱动为主；后续更应该补 semireal hard negatives、真实追问型 refusal case。 |
| 7 | Prompt 契约偏弱，后处理 heuristic 太重 | 部分完成 | 代码已拆出 `api/services/chat_answer_repair.py`、`chat_composite_answers.py`、`chat_postprocessors.py`、`chat_targeted_fact.py`、`chat_source_selection.py`、`chat_query_flow.py` 等模块；其中 `chat_targeted_fact.py` 已完成评分层、targeted-fact orchestration，以及 `_build_targeted_question_signals(...)` / `_compute_targeted_structural_bonuses(...)` 的第三轮 helper 化减重，`chat_source_selection.py` 已把 `minimize_sources_for_answer(...)` 拆成 should-minimize / mentioned-source / support-map / greedy-cover 等 helper，`model_service.py` 已把 `attempt_model_fallback(...)` 下沉为 base-status / candidate-probe / success-finalize / failed-finalize helper；这轮又把 `chat_service.query(...)` 里的 fallback retry、history/evidence/model_health result assembly，以及 identifier-gap / refusal pruning / postprocessor 尾段分支继续下沉到 `chat_query_flow.py` 的 `execute_query_with_model_fallback(...)`、`build_query_result(...)`、`finalize_query_answer(...)` helper，并补了纯函数测试；相关回归已覆盖 `113 passed`（chat_query_flow/chat_service/model_service）和 `113 passed`（fallback 组合） | 当前是“评分层、orchestration、signals/structural bonus、source minimization、fallback orchestration，以及 query orchestration / answer-tail orchestration 都已明显减重，但 `chat_service.py` 尾段的 answer assembly 与 refusal / postprocessor overlap 仍未完全收干净”，这条不能报完成，下一步优先继续收口 `chat_service.py` 里的剩余 answer assembly 与 refusal / postprocessor 边界。 |
| 8 | Docker / requirements / 端口 / 启动脚本存在配置漂移 | 大体收口 | `tests/scripts/test_docker_smoke.py`、`tests/test_requirements_profiles.py`、`tests/scripts/test_dev_startup_contracts.py` 当前 `49 passed`；`scripts/docker_smoke.py` 已走 Docker host port 回查口径；requirements profile 已有契约测试 | 配置漂移已经有自动化 gate，不再完全靠人工记忆；但文档和历史脚本仍需继续统一，建议继续保守表述为“大体收口”。 |
| 9 | 仓库根目录临时文件、日志、调试脚本较多 | 部分完成 | 已存在 `scripts/cleanup_local_artifacts.py` 与 `tests/scripts/test_cleanup_local_artifacts.py` / `tests/scripts/test_repo_hygiene_contracts.py`，本轮 `27 passed` | 治理规则已经建立，但仓库的脚本/文档代际较多，仍需继续做 inventory 减法，不能算完全结束。 |
| 10 | 文档闭环不够满 | 部分完成 | `scripts/build_audit_metrics_snapshot.py` 已新增 `--bundle` / `--skip-node` / `--skip-cleanup`，支持 partial refresh + merge existing snapshot；随后用 `python scripts/build_audit_metrics_snapshot.py --bundle full_non_slow --sync-docs` 真实修正了 audit / interview / project 材料里的 full non-slow 漂移，并重新跑过 `python -m pytest tests/scripts/test_docs_entry_contracts.py tests/test_rag_quality_fixtures.py tests/test_rag_quality_eval_dataset_v8.py tests/api/test_chat_eval_contracts.py tests/api/test_chat_eval_runner.py -q` → `94 passed` | audit 文档链路已经从“只能整包重刷”推进到“可做快速增量刷新 + 定点回写”，而且本轮已经证明文档同步与评测说明补充可以一起过回归；但全仓历史文档仍多代并存，闭环程度依然是“改善中”而不是“完全完成”。 |
| 11 | 日志与临时产物治理需要规范化 | 部分完成 | 已有 cleanup 脚本、repo hygiene 契约和文档约束；`27 passed` 说明最基础的规则正在生效 | 规范化已经开始，但输出目录、临时产物命名和长期归档策略还可以继续统一。 |
| 12 | 面试表述需要主动区分“能力完成度”和“工程完成度” | 已整理 | 当前审计材料、`docs/project.md`、`interview-brief` / `report-script` 已能支撑这种区分；本报告补充了可直接复述的话术 | 面试时不要说“项目彻底完成”，要说“核心能力闭环已经完成，工程化收口仍在推进”。 |

## 4. 当前最准确的对外口径

### 4.1 能力完成度

可以比较稳地说已经完成的，是下面几条：

1. 单知识库主链路已经稳定收口，`basic` / `knowledge` 不再伪装成“全局检索”。
2. QueryRequest 的请求级 RAG 参数已经真正进入 chat 主链路，而不是停留在前端假透传。
3. query 成功和 history 成功已解耦，前端不会因为 history 慢一拍把刚返回的回答静默覆盖掉。
4. scope / evidence / preview / eval contract 这些主能力已经有比较系统的自动化回归。

### 4.2 工程完成度

也必须主动承认下面这些还在继续：

1. compatibility wrapper、legacy 文档、历史脚本和多代材料仍在逐步收口。
2. refusal / answerable 的多轮 follow-up 已经有 fixture gate，但 semireal answerable follow-up、hard negative 与更大规模真实失败样本仍可继续做深，不适合说“评测已经完全覆盖”。
3. heuristic 已经模块化，而且 targeted-fact 评分层已开始纯函数化，但它并没有消失；复杂度治理仍在继续。
4. 文档、日志、临时产物、根目录 hygiene 已建立规则，但距离彻底简化还没结束。

## 5. 面试 / 汇报推荐表述

### 5.1 一句话版本

> 这个项目的核心能力闭环已经完成，尤其是 single-kb scope、evidence/preview、请求级检索参数生效、前端 query/history 解耦和分层评测；但工程化收口我没有粉饰，像 legacy 入口、配置漂移、文档闭环、临时产物治理这些，我都在持续往自动化契约和明确边界上推进。

### 5.2 如果面试官追问“是不是都做完了”

推荐回答：

> 不是所有工程问题都已经清零，但我会区分“能力完成度”和“工程完成度”。能力层面，主链路已经闭环并有自动化回归；工程层面，我已经把最大风险收口成可测试、可回归、可解释的边界，剩余工作主要是继续减少兼容层、补更强负向评测、统一文档和产物治理，而不是重新推翻主架构。

## 6. 下一轮最值得继续做的三件事

1. **继续减少 prompt / heuristic 隐式复杂度**：`api/services/chat_targeted_fact.py` 的 orchestration、signals / structural bonus，`chat_source_selection.py` 的 source minimization，`model_service.py` 的 fallback orchestration，以及 `chat_service.query(...)` 的 query orchestration 已完成这一阶段减重；下一步优先继续收口 `api/services/chat_service.py` 内剩余的 answer assembly、refusal 分支与 postprocessor 串接复杂度。
2. **继续增强 answerable follow-up / semireal hard negative 覆盖**：fixture 层的 refusal / answerable follow-up gate 已补上，下一步让正向与负向多轮运行结果都更接近真实追问场景。
3. **继续把文档 / cleanup / audit 同步机制从“可用”升级到“更稳”**：partial refresh + merge baseline 这一层已经补上，但后续仍建议继续给 `sync-docs` 引入更稳定的 machine tag，并把高频 bundle 的刷新路径进一步固化到日常维护流程。
